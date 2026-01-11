"""
Scraper for ParionsSport
Uses API with curl_cffi
"""

from curl_cffi import requests
from datetime import datetime


URL = "https://www.enligne.parionssport.fdj.fr/lvs-api/next/50/p59097045,p59097046,p59097047,p59097049,p59097050,p59097051,p59097052,p59097053,p59096999,p59097001,p59097003,p59096223,p59097009,p59097005,p59096959,p59096955,p59096957,p59096958,p59096929,p58482479,p58245556,p58429681,p58421879,p58422124,p58450232,p58557545,p58425119,p58422320,p58422324,p58406581,p58499583,p58470484,p58421212,p58559769,p58559623,p58429444,p58416562,p58474788,p58598438,p58712243?lineId=1&originId=3&breakdownEventsIntoDays=true&pageIndex=0&showPromotions=true"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9,fr;q=0.8",
    "Origin": "https://www.enligne.parionssport.fdj.fr",
    "Referer": "https://www.enligne.parionssport.fdj.fr/paris-sportifs/cotes-boostees",
    "X-Lvs-Hst": "RWFgXd8wY89JYZXjpX2EtIa-3aOZ2z5yOQAWJ_ppKagItJiANvqmWzodSylSO0e_Ps0UH530cphxp1l_PMkP4WcHLjIR4oBgG2UvENI4YhgbKlqCWw5KTk3tjuz6GBGVGkWNG4xphxgjTuy8cQkCTw=="
}


def parse_ps_date(date_str):
    """
    ParionsSport uses a format like '2601050100' (YYMMDDHHMM) in the 'start' field.
    """
    try:
        dt = datetime.strptime(date_str, "%y%m%d%H%M")
        return dt.strftime("%d/%m %H:%M")
    except Exception:
        return date_str


def scrape_parionssport():
    """Main scraper function for ParionsSport"""
    print("[PARIONSSPORT] Fetching data...")
    
    max_retries = 500
    for attempt in range(max_retries):
        try:
            response = requests.get(
                URL, 
                headers=HEADERS, 
                impersonate="chrome",
                timeout=30
            )
            
            if response.status_code == 401:
                print(f"[PARIONSSPORT] Auth failed (attempt {attempt+1}/{max_retries})")
                continue
            
            if response.status_code != 200:
                print(f"[PARIONSSPORT] Failed: Status {response.status_code}")
                continue

            data = response.json()
            items = data.get("items", {})
            
            # Organize items by type
            events = {}
            markets = {}
            outcomes = []

            for key, item in items.items():
                if key.startswith("e"):
                    events[key] = item
                elif key.startswith("m"):
                    markets[key] = item
                elif key.startswith("o"):
                    outcomes.append(item)

            rows = []

            # Link outcome -> market -> event
            for outcome in outcomes:
                try:
                    if outcome.get("desc") == "." or "hidden" in outcome.get("flags", []):
                        continue

                    market_id = outcome.get("parent")
                    market = markets.get(market_id)
                    if not market:
                        continue

                    event_id = market.get("parent")
                    event = events.get(event_id)
                    if not event:
                        continue

                    start_time = parse_ps_date(event.get("start", ""))
                    sport = event.get("path", {}).get("Sport", "Unknown")
                    match_name = event.get("desc", "-")
                    bet_name = market.get("desc", "")
                    cote_str = outcome.get("price", "0").replace(",", ".")
                    
                    rows.append({
                        "Time": start_time,
                        "Site": "ParionsSport",
                        "Sport": sport,
                        "Match": match_name,
                        "Bet": bet_name,
                        "Cote": cote_str
                    })

                except Exception as e:
                    continue
                    
            print(f"[PARIONSSPORT] Scraped {len(rows)} rows")
            return rows

        except Exception as e:
            print(f"[PARIONSSPORT] Error: {e}")
            continue
    
    return []


if __name__ == "__main__":
    data = scrape_parionssport()
    for row in data[:5]:
        print(row)
