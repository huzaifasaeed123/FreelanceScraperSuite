from curl_cffi import requests
import json
import pandas as pd
from datetime import datetime

# -------------------------------------------------------------------------
# CONFIGURATION
# -------------------------------------------------------------------------
URL = "https://www.unibet.fr/zones/v1/offer/scbs.json"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Referer": "https://www.unibet.fr/sport/super-cotes-boostees",
    "Origin": "https://www.unibet.fr"
}

# -------------------------------------------------------------------------
# HELPER FUNCTIONS
# -------------------------------------------------------------------------

def format_timestamp(timestamp_ms):
    try:
        if not timestamp_ms: return ""
        dt = datetime.fromtimestamp(timestamp_ms / 1000)
        return dt.strftime("%d/%m %H:%M")
    except Exception:
        return ""

def calculate_decimal_odd(up, down):
    """
    Standard conversion from Fractional to Decimal:
    (Numerator / Denominator) + 1
    """
    try:
        up = int(up)
        down = int(down)
        
        if down == 0: return 0
        
        decimal_odd = (up / down) + 1
        return round(decimal_odd, 2)
    except (ValueError, TypeError, ZeroDivisionError):
        return 0

def fetch_unibet_data():
    print(f"[INFO] Fetching Unibet Super Cotes...")
    
    try:
        response = requests.get(URL, headers=HEADERS, impersonate="chrome")
        
        if response.status_code != 200:
            print(f"[ERROR] Failed to fetch data. Status: {response.status_code}")
            return []

        data = response.json()
        all_bets = []

        markets_by_type = data.get("marketsByType", [])
        
        for market_type in markets_by_type:
            # We specifically look for "Super Cote Boostée" sections
            days = market_type.get("days", [])
            
            for day in days:
                events = day.get("events", [])
                
                for event in events:
                    match_name = event.get("eventName", "Unknown")
                    sport_name = event.get("cmsSportName", "Sport")
                    start_ms = event.get("eventStartDate", 0)
                    time_str = format_timestamp(start_ms)

                    # Iterate through markets inside the event
                    markets = event.get("markets", [])
                    for market in markets:
                        selections = market.get("selections", [])
                        
                        for selection in selections:
                            bet_name = selection.get("name", "")
                            
                            # PRICE LOGIC
                            price_up = selection.get("currentPriceUp")
                            price_down = selection.get("currentPriceDown")
                            
                            # If for some reason price is missing, fallback to 'originalOdd' (though that is non-boosted)
                            if price_up and price_down:
                                decimal_val = calculate_decimal_odd(price_up, price_down)
                            else:
                                decimal_val = selection.get("originalOdd", 0)

                            # Format with comma for Excel
                            cote_str = str(decimal_val).replace(".", ",")

                            all_bets.append({
                                "Time": time_str,
                                "Site": "Unibet",
                                "Sport": sport_name,
                                "Match": match_name,
                                "Bet": bet_name,
                                "Cote": cote_str
                            })

        return all_bets

    except Exception as e:
        print(f"[ERROR] Exception occurred: {e}")
        return []

# -------------------------------------------------------------------------
# MAIN
# -------------------------------------------------------------------------
def main():
    rows = fetch_unibet_data()

    print(f"\n{'Time':<15} | {'Site':<10} | {'Match':<30} | {'Bet':<40} | {'Cote'}")
    print("-" * 110)
    
    for row in rows:
        m = (row['Match'][:27] + '..') if len(row['Match']) > 27 else row['Match']
        b = (row['Bet'][:37] + '..') if len(row['Bet']) > 37 else row['Bet']
        print(f"{row['Time']:<15} | {row['Site']:<10} | {m:<30} | {b:<40} | {row['Cote']}")

    if rows:
        df = pd.DataFrame(rows)
        # Enforce column order
        df = df[["Time", "Site", "Sport", "Match", "Bet", "Cote"]]
        df.to_excel("Unibet_Result.xlsx", index=False)
        print(f"\n[SUCCESS] Saved {len(rows)} rows to Unibet_Result.xlsx")
    else:
        print("\n[INFO] No data found.")

if __name__ == "__main__":
    main()