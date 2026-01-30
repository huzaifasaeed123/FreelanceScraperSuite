from curl_cffi import requests
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

URL = "https://www.unibet.fr/zones/v1/offer/scbs.json"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Referer": "https://www.unibet.fr/sport/super-cotes-boostees",
    "Origin": "https://www.unibet.fr"
}


def format_timestamp(timestamp_ms):
    """Convert millisecond UTC timestamp to France local time DD/MM HH:MM"""
    try:
        if not timestamp_ms:
            return ""

        # Create UTC datetime from milliseconds
        dt_utc = datetime.fromtimestamp(timestamp_ms / 1000, tz=timezone.utc)

        # Convert to France time
        france_dt = dt_utc.astimezone(ZoneInfo("Europe/Paris"))

        return france_dt.strftime("%d/%m %H:%M")
    except Exception:
        return ""

def calculate_decimal_odd(up, down):
    """
    Convert fractional odds to decimal: (Numerator / Denominator) + 1
    """
    try:
        up = int(up)
        down = int(down)
        if down == 0:
            return 0
        decimal_odd = (up / down) + 1
        return round(decimal_odd, 2)
    except (ValueError, TypeError, ZeroDivisionError):
        return 0


def scrape_unibet():
    """Main scraper function for Unibet"""
    print("[UNIBET] Fetching data...")
    
    try:
        response = requests.get(
            URL, 
            headers=HEADERS, 
            impersonate="chrome",
            timeout=30
        )
        
        if response.status_code != 200:
            print(f"[UNIBET] Failed: Status {response.status_code}")
            return []

        data = response.json()
        all_bets = []

        markets_by_type = data.get("marketsByType", [])
        # with open("unibet_debug.json", "w", encoding="utf-8") as f:
        #     import json
        #     json.dump(data, f, ensure_ascii=False, indent=4)
        for market_type in markets_by_type:
            days = market_type.get("days", [])
            
            for day in days:
                events = day.get("events", [])
                
                for event in events:
                    match_name = event.get("eventName", "Unknown")
                    sport_name = event.get("cmsSportName", "Sport")
                    start_ms = event.get("eventStartDate", 0)
                    time_str = format_timestamp(start_ms)

                    markets = event.get("markets", [])
                    for market in markets:
                        selections = market.get("selections", [])
                        
                        for selection in selections:
                            bet_name = selection.get("name", "")
                            
                            price_up = selection.get("currentPriceUp")
                            price_down = selection.get("currentPriceDown")
                            
                            if price_up and price_down:
                                decimal_val = calculate_decimal_odd(price_up, price_down)
                            else:
                                decimal_val = selection.get("originalOdd", 0)

                            cote_str = str(decimal_val).replace(".", ",")

                            all_bets.append({
                                "Time": time_str,
                                "Site": "Unibet",
                                "Sport": sport_name,
                                "Match": match_name,
                                "Bet": bet_name,
                                "Cote": cote_str
                            })

        print(f"[UNIBET] Scraped {len(all_bets)} rows")
        return all_bets

    except Exception as e:
        print(f"[UNIBET] Error: {e}")
        return []


if __name__ == "__main__":
    data = scrape_unibet()
    for row in data[:5]:
        print(row)
