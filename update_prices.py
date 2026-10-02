import os
import sys
import time
import requests
import psycopg2
from psycopg2.extras import execute_batch
from dotenv import load_dotenv

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")

def fetch_skinport_prices():
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Fetching live prices from Skinport...")
    url = "https://api.skinport.com/v1/items"
    params = {"app_id": 730, "currency": "USD", "tradable": 0}
    headers = {"Accept-Encoding": "br", "User-Agent": "CS2-TradeUp-Engine/1.0"}
    
    try:
        res = requests.get(url, params=params, headers=headers, timeout=15)
        res.raise_for_status()
        data = res.json()
        print(f" ► Received {len(data):,} market items from Skinport.")
        return [(item["market_hash_name"], item.get("min_price"), item.get("quantity", 0)) 
                for item in data if "market_hash_name" in item]
    except Exception as e:
        print(f" [ERROR] Failed to fetch Skinport prices: {e}")
        return []

def update_database(prices_batch):
    if not prices_batch:
        print(" [WARNING] No prices to update.")
        return

    print(" Updating Supabase market_prices table...")
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()

    # Filters out any new market_hash_name that doesn't exist in 'skins' table yet
    prices_query = """
        INSERT INTO market_prices (market_hash_name, skinport_price, skinport_quantity, last_updated)
        SELECT %s, %s, %s, NOW()
        WHERE EXISTS (
            SELECT 1 FROM skins WHERE market_hash_name = %s
        )
        ON CONFLICT (market_hash_name)
        DO UPDATE SET
            skinport_price = EXCLUDED.skinport_price,
            skinport_quantity = EXCLUDED.skinport_quantity,
            last_updated = NOW();
    """

    # Format batch to pass market_hash_name twice (once for insert, once for EXISTS check)
    formatted_batch = [(name, price, qty, name) for name, price, qty in prices_batch]

    try:
        execute_batch(cursor, prices_query, formatted_batch, page_size=2000)
        conn.commit()
        print(f" [{time.strftime('%Y-%m-%d %H:%M:%S')}] SUCCESS: Updated prices in Supabase!")
    except Exception as e:
        conn.rollback()
        print(f" [ERROR] Database update failed: {e}")
    finally:
        cursor.close()
        conn.close()

if __name__ == "__main__":
    prices = fetch_skinport_prices()
    update_database(prices)