import os
import json
import re
import requests
import streamlit as st
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
def normalize(text):
    return re.sub(r"[^a-z0-9 ]", "", text.lower())


def rag_similarity(title, trending_list):
    title_words = set(normalize(title).split())

    best_score = 0
    best_match = None

    for t in trending_list:
        t_words = set(normalize(t).split())
        score = len(title_words & t_words)

        if score > best_score:
            best_score = score
            best_match = t

    return best_score, best_match


# AI EXPLANATION
def explain(product, status):
    if not OPENROUTER_API_KEY:
        return "No AI key set"

    prompt = f"""
Explain briefly why this product is {status}.

Product: {product['title']}
Price: {product['variants'][0]['price']}
"""

    try:
        r = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": "google/gemini-2.5-flash",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.3
            },
            timeout=20
        )

        return r.json()["choices"][0]["message"]["content"]

    except Exception as e:
        return str(e)



# STREAMLIT UI

st.set_page_config(layout="wide")
st.title("🛍️ AI Merchandising Dashboard")


# LOAD DATA
with st.spinner("Running AI merchandising engine..."):

    amazon = load_amazon_data()
    shopify = get_shopify_products()

    trending = [x["title"].lower() for x in amazon]

    processed = []

    for product in shopify:

        variant = product["variants"][0]

        price = float(variant["price"])
        stock = variant.get("inventory_quantity", 0)

        product_id = product["id"]
        variant_id = variant["id"]

        title = product["title"]

        # RAG MATCH
        score, match = rag_similarity(title, trending)
        is_trending = score >= 2

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

        explanation = explain(product, action)

        processed.append({
            "product": product,
            "price": price,
            "stock": stock,
            "action": action,
            "match": match,
            "score": score,
            "explanation": explanation
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

    # IMAGE FIX
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

            if st.button("💸 Apply Discount", key=f"disc_{variant_id}"):

                new_price = round(price * DISCOUNT_RATE, 2)

                update_variant_price(variant_id, new_price, price)
                update_tags(product_id, "Sale, AI-Discounted")

                st.success("Discount applied!")
                st.rerun()

        if action == "RESTOCK":

            if st.button("📦 Mark for Restock", key=f"restock_{variant_id}"):

                update_tags(product_id, "Restock, Trending")

                st.success("Marked for restock")
                st.rerun()

    st.markdown("---")


# TREND SECTION
st.subheader("🔥 Trending Market Items")

for item in amazon[:15]:
    st.write("•", item["title"])