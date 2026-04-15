from scraper import scrape_best_sellers
from db import save_bestsellers

BS_URL = (
    "https://www.amazon.co.uk/Best-Sellers-Beauty/zgbs/beauty"
    "/ref=zg_bs_pg_1_beauty?_encoding=UTF8&pg=1"
)

if __name__ == "__main__":
    print("Scraping Amazon bestsellers...")
    products = scrape_best_sellers(BS_URL)

    if products:
        save_bestsellers(products)
    else:
        print("No products scraped — skipping DB write")