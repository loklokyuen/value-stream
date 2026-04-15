import requests
import os
import json
from dotenv import load_dotenv
load_dotenv(override=True)

SHOPIFY_API_TOKEN = os.getenv("SHOPIFY_API_TOKEN")
SHOP = 'minimal-collection-3natuern.myshopify.com'
API = f'https://{SHOP}/admin/api/2025-01'

headers = {
    'X-Shopify-Access-Token': SHOPIFY_API_TOKEN,
    'Content-Type': 'application/json'
}

def get_all_products():
    products = []
    url = f'{API}/products.json?limit=250'

    while url:
        res = requests.get(url, headers=headers)
        if not res.ok:
            print(f"Error {res.status_code}: {res.text}")
            break
        products.extend(res.json().get('products', []))

        link_header = res.headers.get('Link', '')
        if 'rel="next"' in link_header:
            url = [l.split(';')[0].strip('<>') for l in link_header.split(',') if 'rel="next"' in l][0]
        else:
            url = None

    return products

products = get_all_products()
with open('products.json', 'w') as f:
    json.dump(products, f, indent=2)

print(f"Saved {len(products)} products to products.json")