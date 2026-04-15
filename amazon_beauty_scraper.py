import os, json, re
from bs4 import BeautifulSoup
import requests
from urllib.parse import quote_plus
from dotenv import load_dotenv
load_dotenv()
SCRAPER_API_KEY = os.getenv("SCRAPER_API_KEY")

def scraperapi_url(target_url: str):
    return (
        f"http://api.scraperapi.com"
        f"?api_key={SCRAPER_API_KEY}"
        f"&url={quote_plus(target_url)}"
        f"&country_code=gb"
    )

def extract_title(item):
    for sel in ["span[class*='p13n-sc-truncate']", ".p13n-sc-truncate-desktop-type2",
                ".p13n-sc-truncate", "a.a-link-normal span"]:
        el = item.select_one(sel)
        if el:
            t = el.get_text(strip=True)
            if len(t) > 5:
                return t
    return "N/A"

def extract_price(item):
    for sel in ["span.p13n-sc-price", ".p13n-sc-price", ".a-price .a-offscreen"]:
        el = item.select_one(sel)
        if el:
            return el.get_text(strip=True)
    m = re.search(r"£\s*(\d[\d,]*\.?\d{0,2})", item.get_text())
    return m.group(0).replace(" ", "") if m else "N/A"

def extract_rating(item):
    for sel in ["i[class*='a-star'] span.a-icon-alt", ".a-icon-alt"]:
        el = item.select_one(sel)
        if el:
            m = re.search(r"(\d[\d.]+)\s*out of", el.get_text())
            if m:
                return m.group(1)
    return "N/A"

def scrape_best_sellers(url: str) -> list[dict]:
    print(f"Fetching {url} …")
    try:
        resp = requests.get(scraperapi_url(url), timeout=60)
    except requests.RequestException as e:
        print(f"Request failed: {e}")
        return []

    if resp.status_code != 200:
        print(f"HTTP {resp.status_code}")
        return []

    soup = BeautifulSoup(resp.text, "lxml")

    if soup.select_one("form[action*='validateCaptcha']"):
        print("CAPTCHA detected")
        return []

    results = []
    for card in soup.select("div[data-asin]"):
        asin = card.get("data-asin", "")
        if len(asin) < 4:
            continue

        rank_el = card.select_one(".zg-bdg-text, .zg-badge-text")
        rank    = rank_el.get_text(strip=True).lstrip("#") if rank_el else "N/A"

        results.append({
            "rank":   rank,
            "asin":   asin,
            "title":  extract_title(card),
            "price":  extract_price(card),
            "rating": extract_rating(card),
            "url":    f"https://www.amazon.co.uk/dp/{asin}",
        })

    print(f"Found {len(results)} products")
    return results


if __name__ == "__main__":
    BS_URL = (
        "https://www.amazon.co.uk/Best-Sellers-Beauty/zgbs/beauty"
        "/ref=zg_bs_pg_1_beauty?_encoding=UTF8&pg=1"
    )

    data = scrape_best_sellers(BS_URL)

    for p in data:
        print(f"#{p['rank']:>2}  {p['title'][:60]}")
        print(f"      ASIN: {p['asin']}  |  Price: {p['price']}  |  Rating: {p['rating']}")

    with open("beauty_best_sellers.json", "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print("\nSaved to beauty_best_sellers.json")