import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")

def test_query():
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()

    # Query cheapest Mil-Spec inputs available on Skinport
    query = """
        SELECT 
            s.market_hash_name, 
            s.rarity, 
            s.min_float, 
            s.max_float, 
            p.skinport_price, 
            p.skinport_quantity,
            s.image_url
        FROM skins s
        JOIN market_prices p ON s.market_hash_name = p.market_hash_name
        WHERE s.rarity LIKE '%Mil-Spec%' 
          AND p.skinport_price IS NOT NULL 
          AND p.skinport_price > 0
        ORDER BY p.skinport_price ASC
        LIMIT 10;
    """

    cursor.execute(query)
    rows = cursor.fetchall()

    print("--- TOP 10 CHEAPEST MIL-SPEC TRADE-UP INPUTS (FROM SUPABASE) ---")
    for idx, row in enumerate(rows, start=1):
        name, rarity, min_f, max_f, price, qty, img = row
        print(f"{idx}. {name}")
        print(f"   Price: ${price:.2f} USD | Quantity: {qty}")
        print(f"   Float Range: {min_f} -> {max_f}")
        print(f"   CDN URL: {img}")
        print("-" * 55)

    cursor.close()
    conn.close()

if __name__ == "__main__":
    test_query()