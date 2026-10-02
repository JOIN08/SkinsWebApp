import requests
import sys

def fetch_skinport_prices():
    url = "https://api.skinport.com/v1/items"
    params = {"app_id": 730, "currency": "USD", "tradable": 0}
    headers = {"Accept-Encoding": "br"}

    print("1. Downloading 20,000+ items from Skinport (Bulk Endpoint)...")
    try:
        # 5 second timeout so it never hangs
        response = requests.get(url, params=params, headers=headers, timeout=5)
        response.raise_for_status()
        items = response.json()
        print(f"   [SUCCESS] Loaded {len(items):,} items from Skinport!\n")
        return {item["market_hash_name"]: item for item in items if "market_hash_name" in item}
    except Exception as e:
        print(f"   [ERROR] Skinport failed: {e}")
        return {}

def main():
    catalog = fetch_skinport_prices()
    if not catalog:
        print("No items fetched. Exiting.")
        return

    # Filter cheap skins under $3.00
    cheap_skins = [
        item for item in catalog.values()
        if item.get("min_price") is not None and item["min_price"] <= 3.00
    ]
    cheap_skins.sort(key=lambda x: x["min_price"])

    print("--- CHEAP TRADE-UP INPUT CANDIDATES (SKINPORT) ---")
    for idx, item in enumerate(cheap_skins[:10], start=1):
        name = item.get("market_hash_name")
        price = item.get("min_price")
        qty = item.get("quantity")
        img = item.get("item_page")

        print(f"{idx}. {name}")
        print(f"   ├─ Lowest Listing: ${price:.2f} USD")
        print(f"   ├─ Stock Available: {qty}")
        print(f"   └─ Valve CDN / Page: {img}")
        print("-" * 55)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nProcess manually cancelled by user.")
        sys.exit(0)