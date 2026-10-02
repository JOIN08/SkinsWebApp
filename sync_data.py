import os
import requests
import psycopg2
from psycopg2.extras import execute_batch
from dotenv import load_dotenv

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")

def fetch_collection_map():
    print("1. Fetching base skin collection mapping from grouped skins API...")
    url = "https://raw.githubusercontent.com/ByMykel/CSGO-API/main/public/api/en/skins.json"
    col_map = {}
    try:
        res = requests.get(url, timeout=15)
        res.raise_for_status()
        data = res.json()
        for item in data:
            pattern_id = item.get("id")
            cols = item.get("collections", [])
            crates = item.get("crates", [])
            
            col_name = None
            if cols and isinstance(cols, list) and len(cols) > 0:
                col_name = cols[0].get("name") if isinstance(cols[0], dict) else cols[0]
            elif crates and isinstance(crates, list) and len(crates) > 0:
                col_name = crates[0].get("name") if isinstance(crates[0], dict) else crates[0]
                
            if pattern_id and col_name:
                col_map[pattern_id] = col_name
        print(f"   Indexed collection mappings for {len(col_map):,} skins.")
        return col_map
    except Exception as e:
        print(f"   [ERROR] Failed to fetch collection map: {e}")
        return {}

def fetch_game_metadata(col_map):
    print("2. Fetching detailed CS2 item metadata...")
    url = "https://raw.githubusercontent.com/ByMykel/CSGO-API/main/public/api/en/skins_not_grouped.json"
    try:
        res = requests.get(url, timeout=15)
        res.raise_for_status()
        data = res.json()
        print(f"   Fetched {len(data):,} items from game metadata API.")
        return data
    except Exception as e:
        print(f"   [ERROR] Failed to fetch game metadata: {e}")
        return []

def fetch_skinport_prices():
    print("3. Fetching live market prices from Skinport API...")
    url = "https://api.skinport.com/v1/items"
    params = {"app_id": 730, "currency": "USD", "tradable": 0}
    headers = {"Accept-Encoding": "br"}
    try:
        res = requests.get(url, params=params, headers=headers, timeout=15)
        res.raise_for_status()
        data = res.json()
        print(f"   Fetched {len(data):,} live price records from Skinport.")
        return {item["market_hash_name"]: item for item in data if "market_hash_name" in item}
    except Exception as e:
        print(f"   [ERROR] Failed to fetch Skinport prices: {e}")
        return {}

def sync_to_supabase():
    col_map = fetch_collection_map()
    metadata = fetch_game_metadata(col_map)
    skinport_prices = fetch_skinport_prices()

    if not metadata or not skinport_prices:
        print("[ERROR] Missing data. Aborting sync.")
        return

    print("4. Syncing catalog & collections directly to Supabase...")
    
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()

    skins_batch = []
    prices_batch = []

    for item in metadata:
        market_name = item.get("name")
        if not market_name:
            continue

        weapon = item.get("weapon", {}).get("name") if isinstance(item.get("weapon"), dict) else None
        skin_name = item.get("pattern", {}).get("name") if isinstance(item.get("pattern"), dict) else None
        wear = item.get("wear", {}).get("name") if isinstance(item.get("wear"), dict) else None
        min_float = item.get("min_float")
        max_float = item.get("max_float")
        rarity = item.get("rarity", {}).get("name") if isinstance(item.get("rarity"), dict) else None
        image_url = item.get("image")
        
        # Match collection using skin_id reference
        skin_id = item.get("skin_id")
        collection_name = col_map.get(skin_id)

        skins_batch.append((
            market_name, weapon, skin_name, wear, min_float, max_float, rarity, image_url, collection_name
        ))

        sp_item = skinport_prices.get(market_name)
        if sp_item:
            sp_price = sp_item.get("min_price")
            sp_qty = sp_item.get("quantity", 0)
            prices_batch.append((market_name, sp_price, sp_qty))

    skins_query = """
        INSERT INTO skins (market_hash_name, weapon, skin_name, wear, min_float, max_float, rarity, image_url, collection)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (market_hash_name) 
        DO UPDATE SET 
            min_float = EXCLUDED.min_float,
            max_float = EXCLUDED.max_float,
            image_url = EXCLUDED.image_url,
            collection = EXCLUDED.collection,
            updated_at = NOW();
    """
    
    prices_query = """
        INSERT INTO market_prices (market_hash_name, skinport_price, skinport_quantity, last_updated)
        VALUES (%s, %s, %s, NOW())
        ON CONFLICT (market_hash_name)
        DO UPDATE SET
            skinport_price = EXCLUDED.skinport_price,
            skinport_quantity = EXCLUDED.skinport_quantity,
            last_updated = NOW();
    """

    try:
        print(f"   Writing {len(skins_batch):,} skins to database...")
        execute_batch(cursor, skins_query, skins_batch, page_size=1000)
        
        print(f"   Writing {len(prices_batch):,} price records to database...")
        execute_batch(cursor, prices_query, prices_batch, page_size=1000)

        conn.commit()
        print("\n [SUCCESS] Complete sync with mapped collections finished!")

    except Exception as e:
        conn.rollback()
        print(f" [ERROR] Sync failed: {e}")
    finally:
        cursor.close()
        conn.close()

if __name__ == "__main__":
    sync_to_supabase()