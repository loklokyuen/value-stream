import psycopg2
import os

def get_conn():
    database_url = os.getenv("DATABASE_URL")
    if database_url:
        return psycopg2.connect(database_url, sslmode="require")

    return psycopg2.connect(
        host=f"/cloudsql/{os.getenv('CLOUD_SQL_CONNECTION_NAME')}",
        database=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD")
    )

def save_bestsellers(products: list[dict]):
    conn = get_conn()
    cursor = conn.cursor()
    for p in products:
        cursor.execute("""
            INSERT INTO amazon_bestsellers (rank, asin, title, price, rating, url)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (
            int(p["rank"]),
            p["asin"],
            p["title"],
            p["price"],
            float(p["rating"]),
            p["url"]
        ))
    cursor.execute("""
        DELETE FROM amazon_bestsellers
        WHERE scraped_at < NOW() - INTERVAL '4 days'
    """)
    conn.commit()
    cursor.close()
    conn.close()
    print(f"Saved {len(products)} products")
