import os
import json
import re
import requests
import streamlit as st
from db import load_trending_products, sync_shopify_to_db
from dotenv import load_dotenv

load_dotenv()

SHOPIFY_STORE = "minimal-collection-3natuern.myshopify.com"
API_VERSION = "2024-07"

ACCESS_TOKEN = os.getenv("SHOPIFY_API_TOKEN")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")


DISCOUNT_RATE = 0.85

HEADERS = {
    "X-Shopify-Access-Token": ACCESS_TOKEN,
    "Content-Type": "application/json"
}


# DATA

def load_amazon_data(path="beauty_best_sellers.json"):
    with open(path, "r") as f:
        return json.load(f)


def get_shopify_products():
    url = f"https://{SHOPIFY_STORE}/admin/api/{API_VERSION}/products.json?limit=250"
    r = requests.get(url, headers=HEADERS)
    return r.json().get("products", [])



# SHOPIFY ACTIONS

def update_variant_price(variant_id, new_price, original_price):
    url = f"https://{SHOPIFY_STORE}/admin/api/{API_VERSION}/variants/{variant_id}.json"

    payload = {
        "variant": {
            "id": variant_id,
            "price": str(new_price),
            "compare_at_price": str(original_price)
        }
    }

    requests.put(url, json=payload, headers=HEADERS)


def update_tags(product_id, tags):
    url = f"https://{SHOPIFY_STORE}/admin/api/{API_VERSION}/products/{product_id}.json"

    payload = {
        "product": {
            "id": product_id,
            "tags": tags
        }
    }

    requests.put(url, json=payload, headers=HEADERS)


# RAG MATCHING

# Generic words that are too common to count as meaningful matches on their own.
# A match built entirely from these words is not a genuine product match.
GENERIC_WORDS = {
    "serum", "cream", "lotion", "gel", "oil", "spray", "mask", "cleanser",
    "moisturiser", "moisturizer", "toner", "balm", "mist", "treatment",
    "face", "skin", "body", "hair", "eye", "lip", "hand", "foot",
    "for", "with", "and", "the", "a", "an", "of", "in", "to",
    "ml", "g", "oz", "fl"
}


def normalize(text):
    return re.sub(r"[^a-z0-9 ]", "", text.lower())


def rag_similarity(title, trending_list):
    """
    Return (score, best_match) where score counts overlapping *meaningful* words.
    A word is meaningful if it is NOT in GENERIC_WORDS.
    This prevents e.g. 'Hyaluronic Acid Serum' matching 'Vitamin C Serum'
    purely on the word 'serum'.
    """
    title_words = set(normalize(title).split())
    meaningful_title_words = title_words - GENERIC_WORDS

    best_score = 0
    best_match = None

    for t in trending_list:
        t_words = set(normalize(t).split())
        meaningful_t_words = t_words - GENERIC_WORDS

        # Only count meaningful word overlaps
        score = len(meaningful_title_words & meaningful_t_words)

        if score > best_score:
            best_score = score
            best_match = t

    return best_score, best_match


# AI EXPLANATION
def explain(product, action, already_discounted=False):
    if not OPENROUTER_API_KEY:
        return "No AI key set"

    title = product["title"]
    price = product["variants"][0]["price"]
    tags = product.get("tags", "")

    # Build a tight, factual system prompt so the LLM doesn't go off-script
    system_prompt = (
        "You are a concise merchandising assistant. "
        "Your job is to write a single short sentence (max 20 words) explaining "
        "the merchandising action for a product. "
        "Do NOT give opinions, pros/cons, or recommendations. "
        "State only the factual business reason based on the action provided. "
        "Use the following rules:\n"
        "- RESTOCK: the product matches current market trends but stock is too low to meet demand.\n"
        "- DISCOUNT_SUGGESTED (no prior discount): the product is not trending and stock is above 150 units, making a discount appropriate.\n"
        "- DISCOUNT_SUGGESTED (already discounted): a discount was previously applied due to overstocking and lack of trend alignment.\n"
        "- SCALE_WINNER: the product is trending and well-stocked, making it a strong candidate to scale.\n"
        "- HOLD: the product aligns with current trends and stock levels are sufficient to meet demand.\n"
    )

    if already_discounted:
        user_prompt = (
            f"Product: {title}\n"
            f"Price: £{price}\n"
            f"Action: DISCOUNT_SUGGESTED (already discounted)\n"
            "Write one short sentence explaining this."
        )
    else:
        user_prompt = (
            f"Product: {title}\n"
            f"Price: £{price}\n"
            f"Action: {action}\n"
            "Write one short sentence explaining this."
        )

    try:
        r = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": "google/gemini-2.5-flash",
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                "temperature": 0.1
            },
            timeout=20
        )

        return r.json()["choices"][0]["message"]["content"]

    except Exception as e:
        return str(e)


def set_hero_banner(product_id):
    """Pin the product as the hero banner via a Shopify metafield."""
    url = f"https://{SHOPIFY_STORE}/admin/api/{API_VERSION}/products/{product_id}/metafields.json"
    payload = {
        "metafield": {
            "namespace": "merchandising",
            "key": "hero_banner",
            "value": "true",
            "type": "single_line_text_field"
        }
    }
    requests.post(url, json=payload, headers=HEADERS)


def is_already_discounted(variant):
    """Check if a discount has already been applied by looking at compare_at_price."""
    compare_at = variant.get("compare_at_price")
    price = variant.get("price")
    if compare_at and price:
        try:
            return float(compare_at) > float(price)
        except (ValueError, TypeError):
            return False
    return False


# STREAMLIT UI

st.set_page_config(layout="wide")
st.title("🛍️ AI Merchandising Dashboard")


# LOAD DATA
with st.spinner("Running AI merchandising engine..."):
    trending = load_trending_products()
    trending_titles = [row["title"].lower() for row in trending]
    shopify_products = get_shopify_products()
    sync_shopify_to_db(shopify_products)

    processed = []
    matched_trending_titles = set()  # Track which trending items matched a Shopify product

    for product in shopify_products:

        variant = product["variants"][0]

        price = float(variant["price"])
        stock = variant.get("inventory_quantity", 0)

        product_id = product["id"]
        variant_id = variant["id"]

        title = product["title"]

        # RAG MATCH (stricter: only meaningful word overlaps count)
        score, match = rag_similarity(title, trending_titles)
        is_trending = score >= 2

        if is_trending and match:
            matched_trending_titles.add(match)

        # INVENTORY LOGIC
        if stock > 150:
            inventory_status = "OVERSTOCKED"
        elif stock < 15:
            inventory_status = "LOW_STOCK"
        else:
            inventory_status = "NORMAL"

        # BUSINESS DECISION ENGINE
        if is_trending and stock < 15:
            action = "RESTOCK"
        elif not is_trending and stock > 150:
            action = "DISCOUNT_SUGGESTED"
        elif is_trending and stock > 150:
            action = "SCALE_WINNER"
        else:
            action = "HOLD"

        already_discounted = is_already_discounted(variant)
        explanation = explain(product, action, already_discounted=already_discounted)

        processed.append({
            "product": product,
            "price": price,
            "stock": stock,
            "action": action,
            "match": match,
            "score": score,
            "explanation": explanation,
            "already_discounted": already_discounted
        })


# METRICS
st.subheader("📊 Overview")

col1, col2, col3, col4 = st.columns(4)

col1.metric("Total", len(processed))
col2.metric("Trending", sum(p["action"] == "RESTOCK" for p in processed))
col3.metric("Discount Suggested", sum(p["action"] == "DISCOUNT_SUGGESTED" for p in processed))
col4.metric("Scale Winners", sum(p["action"] == "SCALE_WINNER" for p in processed))


st.markdown("---")

# PRODUCT VIEW
for item in processed:

    p = item["product"]
    variant = p["variants"][0]

    title = p["title"]
    price = item["price"]
    stock = item["stock"]

    product_id = p["id"]
    variant_id = variant["id"]

    action = item["action"]
    already_discounted = item["already_discounted"]

    # BADGES
    if action == "RESTOCK":
        badge = "🟢 RESTOCK"
    elif action == "DISCOUNT_SUGGESTED":
        badge = "🔴 DISCOUNT SUGGESTED"
    elif action == "SCALE_WINNER":
        badge = "🚀 SCALE WINNER"
    else:
        badge = "🟡 HOLD"

    cols = st.columns([1.2, 2])

    # IMAGE
    with cols[0]:
        if p.get("image"):
            st.image(p["image"]["src"], width=200)
        else:
            st.markdown("📦 No Image")

    # DETAILS
    with cols[1]:

        st.markdown(f"### {title}")
        st.markdown(f"💰 £{price} | 📦 Stock: {stock}")
        st.markdown(f"**{badge}**")

        # RAG INFO
        if item["match"]:
            st.success(f"Matches trend: {item['match']} (score {item['score']})")

        st.info(item["explanation"])

        # MANUAL ACTION BUTTONS
        if action == "DISCOUNT_SUGGESTED":
            if already_discounted:
                st.warning("✅ Discount already applied.")
            else:
                if st.button("💸 Apply Discount", key=f"disc_{variant_id}"):
                    new_price = round(price * DISCOUNT_RATE, 2)
                    update_variant_price(variant_id, new_price, price)
                    update_tags(product_id, "Sale")
                    st.success("Discount applied!")
                    st.rerun()

        if action == "SCALE_WINNER":
            if st.button("🏆 Set as Hero Banner", key=f"hero_{product_id}"):
                update_tags(product_id, "Hero, Trending, Featured")
                set_hero_banner(product_id)
                st.success("Set as hero banner!")
                st.rerun()

        if action == "RESTOCK":
            if st.button("📦 Mark for Restock", key=f"restock_{variant_id}"):
                update_tags(product_id, "Restock, Trending")
                st.success("Marked for restock")
                st.rerun()

    st.markdown("---")


# TREND SECTION — only show trending items we have NO matching product for
missed_trends = [
    item for item in trending
    if item["title"].lower() not in matched_trending_titles
]

st.subheader("🔥 Trending Market Items (Gaps in Your Catalogue)")

if missed_trends:
    for item in missed_trends[:15]:
        st.write("•", item["title"])
else:
    st.write("You have matching products for all current trending items.")