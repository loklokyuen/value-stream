import os
import json
import re
import requests
import streamlit as st
from db import load_trending_products, sync_shopify_to_db
from dotenv import load_dotenv
from datetime import datetime
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

    # Build a tight, factual system prompt so the LLM doesn't go off-script
    system_prompt = (
        "You are a factual merchandising analyst. "
        "Your job is to write a clear, detailed explanation (3-5 sentences) justifying the recommended merchandising action for a product. "
        "Focus strictly on the business reasoning: stock levels, trend alignment, and what action is required and why. "
        "Do NOT offer opinions, subjective assessments, or speculate about why a product might be trending or popular. "
        "Do NOT say things like 'this is a great product' or 'customers love this'. "
        "Only state facts about the stock situation, trend data, and the operational consequences of the action. "
        "Use the following definitions to guide your explanation:\n\n"
        "- RESTOCK: This product has been matched to current market trends but stock has fallen below 15 units. "
        "Explain that demand cannot be met at current stock levels, that the trend match makes this a priority restock, "
        "and what the risk is of not restocking promptly.\n\n"
        "- DISCOUNT_SUGGESTED (no prior discount): This product does not match any current market trends and stock exceeds 150 units. "
        "Explain the overstock situation, the lack of trend alignment, and why a price reduction is the appropriate lever to move inventory.\n\n"
        "- DISCOUNT_SUGGESTED (already discounted): A discount was previously applied to this product for the same reasons. "
        "Explain that it was already identified as overstocked and non-trending, that a discount has been applied, and that the situation should continue to be monitored.\n\n"
        "- SCALE_WINNER: This product matches current market trends and stock exceeds 150 units. "
        "Explain that it is well-positioned to be pushed harder, that stock levels can support increased demand, "
        "and what promoting it as a hero product could achieve operationally.\n\n"
        "- HOLD: This product does not match the tracked trending items list but stock levels are within a normal range (15-150 units). "
        "Explain that while it is not appearing in external trend data, it is moving steadily through stock at its current rate, "
        "that no urgent action is needed, and that it should be monitored for changes in either stock velocity or trend alignment.\n"
    )

    if already_discounted:
        user_prompt = (
            f"Product: {title}\n"
            f"Price: £{price}\n"
            f"Action: DISCOUNT_SUGGESTED (already discounted)\n"
            "Write a 3-5 sentence factual explanation for this action."
        )
    else:
        user_prompt = (
            f"Product: {title}\n"
            f"Price: £{price}\n"
            f"Action: {action}\n"
            "Write a 3-5 sentence factual explanation for this action."
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


FEATURED_COLLECTION_ID = os.getenv("SHOPIFY_FEATURED_COLLECTION_ID")
def promote_scale_winner(product_id):
    """
    Push a Scale Winner product via three reliable Shopify levers:
    1. Tags it as 'Hero, Trending, Featured, Bestseller' so theme sections
       that filter by tag (e.g. 'Featured') will surface it automatically.
    2. Adds it to your Featured collection (if SHOPIFY_FEATURED_COLLECTION_ID
       is set in .env) — most reliable way to control homepage/collection-page
       placement without touching theme code.
    3. Sets a 'merchandising/promoted' metafield as a supplementary signal
       for any theme sections that read metafields.
    """
    # 1. Tags
    update_tags(product_id, "Hero, Trending, Featured, Bestseller")

    # 2. Add to Featured collection (most reliable homepage lever)
    if FEATURED_COLLECTION_ID:
        url = f"https://{SHOPIFY_STORE}/admin/api/{API_VERSION}/collects.json"
        payload = {
            "collect": {
                "product_id": product_id,
                "collection_id": int(FEATURED_COLLECTION_ID)
            }
        }
        requests.post(url, json=payload, headers=HEADERS)

    # 3. Metafield as supplementary signal
    url = f"https://{SHOPIFY_STORE}/admin/api/{API_VERSION}/products/{product_id}/metafields.json"
    payload = {
        "metafield": {
            "namespace": "merchandising",
            "key": "promoted",
            "value": "true",
            "type": "single_line_text_field"
        }
    }
    requests.post(url, json=payload, headers=HEADERS)


def is_already_promoted(product):
    """Check if a Scale Winner has already been promoted by inspecting its tags."""
    tags = [t.strip().lower() for t in product.get("tags", "").split(",")]
    return "featured" in tags


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
    # sync_shopify_to_db(shopify_products)

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
        already_promoted = is_already_promoted(product)
        explanation = explain(product, action, already_discounted=already_discounted)

        processed.append({
            "product": product,
            "price": price,
            "stock": stock,
            "action": action,
            "match": match,
            "score": score,
            "explanation": explanation,
            "already_discounted": already_discounted,
            "already_promoted": already_promoted
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
            if item["already_promoted"]:
                st.warning("✅ Already promoted (tagged Featured, added to Featured collection).")
            else:
                if st.button("🚀 Promote Product", key=f"promote_{product_id}"):
                    promote_scale_winner(product_id)
                    st.success("Promoted! Tagged as Featured/Trending/Bestseller and added to Featured collection.")
                    st.rerun()

        if action == "RESTOCK":
            if st.button("📦 Mark for Restock", key=f"restock_{variant_id}"):
                update_tags(product_id, "Restock, Trending")
                st.success("Marked for restock")
                st.rerun()

    st.markdown("---")



missed_trends = [
    item for item in trending
    if item["title"].lower() not in matched_trending_titles
]
st.session_state["missed_trends"] = missed_trends

with st.sidebar:
    st.header("Data Controls")
    if st.button("🔄 Sync Shopify → DB"):
        with st.spinner("Syncing..."):
            sync_shopify_to_db(shopify_products)
        st.session_state["last_synced"] = datetime.now()
        st.success("Done!")
    if "last_synced" in st.session_state:
        st.caption(f"Last synced: {st.session_state['last_synced'].strftime('%H:%M:%S')}")
    else:
        st.caption("Not synced this session")