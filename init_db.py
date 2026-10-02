# Save this as update_schema.py and run it
import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()
conn = psycopg2.connect(os.getenv("DATABASE_URL"))
cursor = conn.cursor()

cursor.execute("ALTER TABLE skins ADD COLUMN IF NOT EXISTS collection VARCHAR(150);")
conn.commit()
cursor.close()
conn.close()

print("[SUCCESS] Added 'collection' column to skins table!")