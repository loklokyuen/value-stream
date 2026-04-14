import os, json, re, time, random
from bs4 import BeautifulSoup
import requests
from urllib.parse import quote_plus
from dotenv import load_dotenv
load_dotenv()
SCRAPER_API_KEY = os.getenv("SCRAPER_API_KEY")

def scraperapi_url(target_url: str, render_js: bool = False):
    base = (
        f"http://api.scraperapi.com"
        f"?api_key={SCRAPER_API_KEY}"
        f"&url={quote_plus(target_url)}"
        f"&country_code=gb"         
    )
    if render_js:
        base += "&render=true"
    return base


def extract_price(item):
    offscreen = item.select_one(".a-price .a-offscreen")
    if offscreen:
        return offscreen.get_text(strip=True)
    whole = item.select_one(".a-price-whole")
    frac  = item.select_one(".a-price-fraction")
    if whole:
        return f"£{whole.get_text(strip=True).rstrip('.')}.{frac.get_text(strip=True) if frac else '00'}"
    m = re.search(r"£\s*(\d[\d,]*\.?\d{0,2})", item.get_text())
    return m.group(0).replace(" ", "") if m else "N/A"


def extract_title(item):
    for sel in ["h2 a span", "h2 span", ".a-size-base-plus", ".a-size-medium"]:
        el = item.select_one(sel)
        if el:
            t = el.get_text(strip=True)
            if len(t) > 5:
                return t
    return "N/A"


def extract_rating(item):
    for sel in ["i[class*='a-star'] span.a-icon-alt", ".a-icon-alt"]:
        el = item.select_one(sel)
        if el:
            m = re.search(r"(\d[\d.]+)\s*out of", el.get_text())
            if m:
                return m.group(1)
    return "N/A"


def extract_url(item):                                         
    link = item.select_one("h2 a[href]")                       # only match if href exists
    if not link:
        link = item.select_one("a[href*='/dp/']")              # fallback: any product link
    if not link:
        return "N/A"
    href = link.get("href", "")
    href = href.split("?")[0]                                  # strip tracking params
    return href if href.startswith("http") else "https://www.amazon.co.uk" + href


def extract_stock(item):
    # Amazon hides out-of-stock items from search results in most cases,
    # so appearing here = In Stock. We just check for the rare exceptions.
    text = item.get_text().lower()
    if "temporarily out of stock" in text:
        return "Temporarily Out of Stock"
    if "currently unavailable" in text:
        return "Unavailable"
    return "In Stock"


def search_amazon(query: str, pages: int = 2,
                  render_js: bool = False) -> list[dict]:
    """
    render_js=False  → 1 credit per page  (use for most searches)
    render_js=True   → 5 credits per page  (use if you get empty results)
    """
    results = []

    for page in range(1, pages + 1):
        target = (
            f"https://www.amazon.co.uk/s"
            f"?k={quote_plus(query)}&s=review-rank&page={page}"
        )
        url = scraperapi_url(target, render_js=render_js)
        print(f"[page {page}] fetching... (render_js={render_js})")

        try:
            resp = requests.get(url, timeout=60)
        except requests.RequestException as e:
            print(f"  Request failed: {e}")
            break

        if resp.status_code != 200:
            print(f"  HTTP {resp.status_code}")
            break

        soup = BeautifulSoup(resp.text, "lxml")

        if soup.select_one("form[action*='validateCaptcha']"):
            print("  CAPTCHA — try render_js=True")
            break

        items = soup.select('[data-component-type="s-search-result"][data-asin]')
        items = [i for i in items if len(i.get("data-asin", "")) > 3]

        if not items:
            print("  No cards found — try render_js=True")
            break

        print(f"  {len(items)} products found")

        for item in items:
            title  = extract_title(item)
            price  = extract_price(item)
            rating = extract_rating(item)
            asin   = item.get("data-asin", "N/A")
            url_p  = extract_url(item)                         # FIXED
            stock  = extract_stock(item)                       # NEW

            if title != "N/A":
                results.append({
                    "asin":   asin,
                    "title":  title,
                    "price":  price,
                    "rating": rating,
                    "stock":  stock,                           # NEW
                    "url":    url_p,
                })

        if page < pages:
            time.sleep(random.uniform(1, 2))   

    return results


if __name__ == "__main__":
    query = input("Product name: ").strip()

    data = search_amazon(query, pages=2, render_js=False)

    if not data:
        print("\nNo results without JS rendering. Retrying with render_js=True...")
        data = search_amazon(query, pages=2, render_js=True)

    print(f"\nFound {len(data)} products:\n")
    for i, p in enumerate(data, 1):
        print(f"{i:>3}. {p['title'][:65]}")
        print(f"     ASIN: {p['asin']}  |  Price: {p['price']}  |  Rating: {p['rating']}  |  Stock: {p['stock']}")

    product_name = query.replace(" ", "_").lower()
    with open(f"{product_name}_results.json", "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print("\nSaved to json")