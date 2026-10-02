import os
import psycopg2
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

def setup_database():
    if not DATABASE_URL or "YOUR_ACTUAL_PASSWORD_HERE" in DATABASE_URL:
        print("[ERROR] Please update your .env file with your real Supabase password!")
        return

    print("Connecting to Supabase PostgreSQL database...")
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()

        # 1. Create 'skins' table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS skins (
                id SERIAL PRIMARY KEY,
                market_hash_name VARCHAR(255) UNIQUE NOT NULL,
                weapon VARCHAR(100),
                skin_name VARCHAR(100),
                wear VARCHAR(50),
                min_float FLOAT,
                max_float FLOAT,
                rarity VARCHAR(50),
                image_url TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # 2. Create 'market_prices' table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS market_prices (
                id SERIAL PRIMARY KEY,
                market_hash_name VARCHAR(255) REFERENCES skins(market_hash_name) ON DELETE CASCADE,
                skinport_price NUMERIC(10, 2),
                skinport_quantity INT DEFAULT 0,
                csfloat_price NUMERIC(10, 2),
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        conn.commit()
        cursor.close()
        conn.close()
        
        print(" [SUCCESS] Database tables ('skins', 'market_prices') successfully created in Supabase!")

    except Exception as e:
        print(f" [ERROR] Failed to connect or setup database: {e}")

if __name__ == "__main__":
    setup_database()