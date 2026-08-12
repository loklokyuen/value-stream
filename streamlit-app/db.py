"""
db.py — Cloud SQL connection and all database operations.

Required environment variables:
    CLOUD_SQL_CONNECTION_NAME  "project:region:instance"
    DB_NAME
    DB_USER
    DB_PASSWORD

Cloud Run:  connects via Unix socket (detected automatically via K_SERVICE).
Local dev:  connects via the public IP in DB_HOST.
"""

import os
import psycopg2
import streamlit as st
import sqlalchemy
from dotenv import load_dotenv
load_dotenv(override=True)

DB_NAME = os.getenv("DB_NAME", "")
DB_USER = os.getenv("DB_USER", "")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
DB_HOST = os.getenv("DB_HOST", "")

def get_conn():
    database_url = os.getenv("DATABASE_URL")
    if database_url:
        return psycopg2.connect(database_url, sslmode="require")

    if os.getenv("K_SERVICE"):  # running in Cloud Run
        return psycopg2.connect(
            host=f"/cloudsql/{os.getenv('CLOUD_SQL_CONNECTION_NAME')}",
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD,
        )
    else:  # local dev
        return psycopg2.connect(
            host=DB_HOST,
            port=5432,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD,
        )


@st.cache_resource
def get_engine():
    """SQLAlchemy engine using psycopg2. Cached for the Streamlit session."""
    return sqlalchemy.create_engine(
        "postgresql+psycopg2://",
        creator=get_conn,
        pool_pre_ping=True,
    )

@st.cache_data(ttl=300)
def load_trending_products():
    """
    Return the latest bestseller rankings from the v_product_trend_analysis view.

    View columns used: asin, title, current_rank, daily_change
    """
    with get_engine().connect() as conn:
        rows = conn.execute(sqlalchemy.text("""
            SELECT asin, title, current_rank, daily_change, rank_yesterday, rank_2_days_ago, rank_3_days_ago, scraped_at
            FROM   v_product_trend_analysis
            WHERE  scraped_at >= NOW() - INTERVAL '2 days'
            ORDER  BY current_rank
        """))
        return [dict(row._mapping) for row in rows]



def sync_shopify_to_db(products: list[dict]):
    """
    Upsert active Shopify products into the Cloud SQL `products` table.
    Draft and archived products are skipped.

    Table schema:
        id                 BIGINT        PRIMARY KEY
        title              TEXT
        body_html          TEXT
        vendor             TEXT
        product_type       TEXT
        tags               TEXT
        status             TEXT
        price              NUMERIC(10,2)
        compare_at_price   NUMERIC(10,2)
        inventory_quantity INT
        variant_id         BIGINT
        image_src          TEXT
        updated_at         TIMESTAMP
    """
    rows = [
        {
            "id":                  p["id"],
            "title":               p["title"],
            "body_html":           p.get("body_html", ""),
            "vendor":              p.get("vendor", ""),
            "product_type":        p.get("product_type", ""),
            "tags":                p.get("tags", ""),
            "status":              p.get("status", "active"),
            "price":               float(p["variants"][0]["price"]),
            "compare_at_price":    float(p["variants"][0]["compare_at_price"])
                                   if p["variants"][0].get("compare_at_price")
                                   else None,
            "inventory_quantity":  p["variants"][0].get("inventory_quantity", 0),
            "variant_id":          p["variants"][0]["id"],
            "image_src":           p["image"]["src"] if p.get("image") else None,
        }
        for p in products
        if p.get("status") == "active"  # skip drafts and archived products
    ]

    if not rows:
        return

    with get_engine().begin() as conn:
        conn.execute(sqlalchemy.text("""
            INSERT INTO products
                (id, title, body_html, vendor, product_type, tags, status,
                 price, compare_at_price, inventory_quantity,
                 variant_id, image_src, updated_at)
            VALUES
                (:id, :title, :body_html, :vendor, :product_type, :tags, :status,
                 :price, :compare_at_price, :inventory_quantity,
                 :variant_id, :image_src, NOW())
            ON CONFLICT (id) DO UPDATE SET
                title              = EXCLUDED.title,
                body_html          = EXCLUDED.body_html,
                vendor             = EXCLUDED.vendor,
                product_type       = EXCLUDED.product_type,
                tags               = EXCLUDED.tags,
                status             = EXCLUDED.status,
                price              = EXCLUDED.price,
                compare_at_price   = EXCLUDED.compare_at_price,
                inventory_quantity = EXCLUDED.inventory_quantity,
                variant_id         = EXCLUDED.variant_id,
                image_src          = EXCLUDED.image_src,
                updated_at         = NOW()
            WHERE (
                products.title              IS DISTINCT FROM EXCLUDED.title              OR
                products.price              IS DISTINCT FROM EXCLUDED.price              OR
                products.compare_at_price   IS DISTINCT FROM EXCLUDED.compare_at_price  OR
                products.inventory_quantity IS DISTINCT FROM EXCLUDED.inventory_quantity OR
                products.image_src          IS DISTINCT FROM EXCLUDED.image_src          OR
                products.tags               IS DISTINCT FROM EXCLUDED.tags
            )
        """), rows)
