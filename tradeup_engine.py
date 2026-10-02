import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")

RARITY_ORDER = {
    "Consumer Grade": "Industrial Grade",
    "Industrial Grade": "Mil-Spec Grade",
    "Mil-Spec Grade": "Restricted",
    "Restricted": "Classified",
    "Classified": "Covert"
}

def get_wear_name(float_val):
    if float_val < 0.07:
        return "Factory New"
    elif float_val < 0.15:
        return "Minimal Wear"
    elif float_val < 0.38:
        return "Field-Tested"
    elif float_val < 0.45:
        return "Well-Worn"
    else:
        return "Battle-Scarred"

def evaluate_tradeup(input_names):
    if len(input_names) != 10:
        print("[ERROR] Trade-up requires exactly 10 inputs.")
        return

    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()

    # Get unique names to fetch from DB
    unique_names = list(set(input_names))
    format_strings = ','.join(['%s'] * len(unique_names))
    
    query = f"""
        SELECT s.market_hash_name, s.collection, s.rarity, s.min_float, s.max_float, p.skinport_price
        FROM skins s
        LEFT JOIN market_prices p ON s.market_hash_name = p.market_hash_name
        WHERE s.market_hash_name IN ({format_strings});
    """
    cursor.execute(query, tuple(unique_names))
    fetched_rows = cursor.fetchall()
    db_map = {row[0]: row for row in fetched_rows}

    total_cost = 0.0
    float_sum = 0.0
    collections = []
    input_rarity = None

    print("\n=================== CONTRACT INPUTS ===================")
    for idx, item_name in enumerate(input_names, start=1):
        item = db_map.get(item_name)
        if not item:
            print(f" {idx:2d}. {item_name} [NOT FOUND IN DB]")
            continue

        name, col, rarity, min_f, max_f, price = item
        price = float(price) if price else 0.0
        
        # Default float mid-point fallback if bounds missing
        min_f = min_f if min_f is not None else 0.00
        max_f = max_f if max_f is not None else 1.00
        est_float = (min_f + max_f) / 2.0
        
        total_cost += price
        float_sum += est_float
        if col:
            collections.append(col)

        if not input_rarity and rarity:
            for r in RARITY_ORDER.keys():
                if r in rarity:
                    input_rarity = r
                    break

        print(f" {idx:2d}. {name}")
        print(f"     ├─ Price: ${price:.2f} | Est Float: {est_float:.4f}")
        print(f"     └─ Collection: {col}")

    avg_input_float = float_sum / 10.0
    target_rarity = RARITY_ORDER.get(input_rarity)

    print("\n================== CONTRACT SUMMARY ==================")
    print(f" Total Input Cost:    ${total_cost:.2f} USD")
    print(f" Avg Input Float:     {avg_input_float:.6f}")
    print(f" Input Rarity:        {input_rarity}")
    print(f" Target Rarity:       {target_rarity}")

    if not target_rarity:
        print("[ERROR] Could not determine target rarity.")
        cursor.close()
        conn.close()
        return

    # Fallback if collection was None on input items: query collection directly by weapon/skin pattern
    if not collections:
        cursor.execute("SELECT DISTINCT collection FROM skins WHERE collection IS NOT NULL AND collection != '';")
        all_cols = [c[0] for c in cursor.fetchall()]
        print(f"\n [INFO] Querying outcome skins for target rarity '{target_rarity}'...")
        outcome_query = """
            SELECT s.market_hash_name, s.weapon, s.skin_name, s.min_float, s.max_float, s.collection
            FROM skins s
            WHERE s.rarity LIKE %s AND s.weapon IS NOT NULL AND s.skin_name IS NOT NULL
            LIMIT 10;
        """
        cursor.execute(outcome_query, (f"%{target_rarity}%",))
    else:
        col_format = ','.join(['%s'] * len(collections))
        outcome_query = f"""
            SELECT s.market_hash_name, s.weapon, s.skin_name, s.min_float, s.max_float, s.collection
            FROM skins s
            WHERE s.collection IN ({col_format})
              AND s.rarity LIKE %s;
        """
        params = list(collections) + [f"%{target_rarity}%"]
        cursor.execute(outcome_query, tuple(params))

    possible_outcomes = cursor.fetchall()

    if not possible_outcomes:
        print(f"\n [NOTICE] No outcomes found in database for rarity '{target_rarity}'.")
        cursor.close()
        conn.close()
        return

    # Filter distinct weapon/skin patterns for outcomes
    distinct_outcomes = {}
    for item in possible_outcomes:
        m_name, weapon, skin_name, min_f, max_f, col = item
        key = f"{weapon} | {skin_name}"
        if key not in distinct_outcomes:
            distinct_outcomes[key] = (min_f, max_f)

    print("\n================ DYNAMIC OUTCOME POOL ================")
    probability = 1.0 / len(distinct_outcomes)
    total_expected_return = 0.0

    for item_key, bounds in distinct_outcomes.items():
        min_f, max_f = bounds
        min_f = min_f if min_f is not None else 0.00
        max_f = max_f if max_f is not None else 1.00

        # Valve Float Transformation
        outcome_float = avg_input_float * (max_f - min_f) + min_f
        wear_condition = get_wear_name(outcome_float)

        target_market_name = f"{item_key} ({wear_condition})"

        cursor.execute("SELECT skinport_price FROM market_prices WHERE market_hash_name = %s;", (target_market_name,))
        price_row = cursor.fetchone()
        outcome_price = float(price_row[0]) if (price_row and price_row[0]) else 0.0

        total_expected_return += outcome_price * probability

        print(f" ► {item_key}")
        print(f"   ├─ Outcome Float: {outcome_float:.6f} ({wear_condition})")
        print(f"   ├─ Odds:          {probability * 100:.2f}%")
        print(f"   └─ Est Price:     ${outcome_price:.2f} USD")

    net_profit = total_expected_return - total_cost
    ev_percent = (total_expected_return / total_cost * 100) if total_cost > 0 else 0.0

    print("\n================ REAL METRICS & EV ================")
    print(f" Expected Return:     ${total_expected_return:.2f} USD")
    print(f" Net Profit/Loss:     ${net_profit:+.2f} USD")
    print(f" Contract EV:         {ev_percent:.2f}%")
    
    if ev_percent > 100:
        print(" 🔥 [PROFITABLE CONTRACT] EV is above 100%!")
    else:
        print(" ⚠️  [UNPROFITABLE CONTRACT] EV is below 100%.")

    cursor.close()
    conn.close()

if __name__ == "__main__":
    # Test with 10 real skins from database
    test_inputs = [
        "MAC-10 | Whitefish (Field-Tested)",
        "MAC-10 | Whitefish (Field-Tested)",
        "MAC-10 | Whitefish (Field-Tested)",
        "MAC-10 | Whitefish (Field-Tested)",
        "MAC-10 | Whitefish (Field-Tested)",
        "MAC-10 | Whitefish (Field-Tested)",
        "MAC-10 | Whitefish (Field-Tested)",
        "MAC-10 | Whitefish (Field-Tested)",
        "MAC-10 | Whitefish (Field-Tested)",
        "MAC-10 | Whitefish (Field-Tested)"
    ]
    evaluate_tradeup(test_inputs)