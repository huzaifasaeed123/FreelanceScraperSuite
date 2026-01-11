from curl_cffi import requests
import json
import pandas as pd
from datetime import datetime

# -------------------------------------------------------------------------
# CONFIGURATION
# -------------------------------------------------------------------------
URL = "https://www.enligne.parionssport.fdj.fr/lvs-api/next/50/p59097045,p59097046,p59097047,p59097049,p59097050,p59097051,p59097052,p59097053,p59096999,p59097001,p59097003,p59096223,p59097009,p59097005,p59096959,p59096955,p59096957,p59096958,p59096929,p58482479,p58245556,p58429681,p58421879,p58422124,p58450232,p58557545,p58425119,p58422320,p58422324,p58406581,p58499583,p58470484,p58421212,p58559769,p58559623,p58429444,p58416562,p58474788,p58598438,p58712243?lineId=1&originId=3&breakdownEventsIntoDays=true&pageIndex=0&showPromotions=true"

# PASTE YOUR HEADERS HERE (Cookies, Tokens, etc.)
# I have added standard ones, but you should update 'Cookie' or 'X-Lvs-Hst' if needed.
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9,fr;q=0.8",
    "Origin": "https://www.enligne.parionssport.fdj.fr",
    "Referer": "https://www.enligne.parionssport.fdj.fr/paris-sportifs/cotes-boostees",
    # "Cookie": "TCPID=125120205147786327629; pa_privacy=%22optin%22; CAID=202512071651565404692152; TC_PRIVACY_PSEL=0%40016%7C46%7C1881%408%2C9%2C10%40%401765128791599%2C1765128791599%2C1780680791599%40; TC_PRIVACY_PSEL_CENTER=8%2C9%2C10; _pcid=%7B%22browserId%22%3A%22mivwhhrl65xtd9x9%22%2C%22_t%22%3A%22mykf1dmy%7Cmiw03way%22%7D; pa_vid=%22mivwhhrl65xtd9x9%22; kameleoonVisitorCode=a9cmpr031hlkhce1; ry_ry-p4r1p53l_realytics=eyJpZCI6InJ5XzA1RUI1MTcwLUYzMzUtNDcxMC05QkMzLTI1MUYxQTJGN0RGMyIsImNpZCI6bnVsbCwiZXhwIjoxNzk2NjY0NzkzMDEwLCJjcyI6MX0%3D; _gcl_au=1.1.1889872320.1765128794; _fbp=fb.1.1765128794945.322372678991306001; _pctx=%7Bu%7DN4IgrgzgpgThIC4B2YA2qA05owMoBcBDfSREQpAeyRCwgEt8oBJAE0RXSwH18yBbAJ74ALADYAjGEIAffgCsRABwAcAa3qEQAXyA; _cs_c=0; _clck=1ghf5fk%5E2%5Eg1u%5E1%5E2167; loop_num=a3d661a1-0f90-4cb2-8a5d-c14a5f400527%3ALxEvZ%7CDR%7C%2Fcotes-boostees; _sp_srt_id.6807=2d0b7cc4-f921-45be-a896-a8985f6fa9f0.1765128795.6.1765741462.1765727224.7cd5b0ba-8d7d-46ba-9732-56a86fe28480.d82e0cc5-a845-4ca5-8232-83314441374b...0; _MFB_=eyIzMjQzMSI6MTc2NTEyODgyNH18eyIzNDkyMiI6MTc2NTEyODgyNH18MTJ8fHxbXXx8fDk0LjUxODM4NzYwNDc0NTR8; _cs_id=2430a5c7-42fe-ae26-d697-bf34a2dc8450.1765654732.2.1765741463.1765740426.1.1799818732651.0.x; datadome=VHj_62xTvS83t0p~Y0VjW~ABqOySV7X0wYwuFYGWSjOy5S3xwr14o7Zl8~88Ve8hFDPXdn8pQTbJg6O10VV1YsHrHW5hJakPMXEQo6nZt0hkX4zvIqJwyd7gX7iie7el; _uetvid=cf3e3360d39211f0bcd719d10804dac2|nc0161|1765741872290|6|1|bat.bing.com/p/insights/c/n; abp-pselw=1149829898.41733.0000",     # <--- Uncomment and add if required
    "X-Lvs-Hst": "RWFgXd8wY89JYZXjpX2EtIa-3aOZ2z5yOQAWJ_ppKagItJiANvqmWzodSylSO0e_Ps0UH530cphxp1l_PMkP4WcHLjIR4oBgG2UvENI4YhgbKlqCWw5KTk3tjuz6GBGVGkWNG4xphxgjTuy8cQkCTw=="     # <--- Uncomment and add if required
}

# -------------------------------------------------------------------------
# PARSING FUNCTIONS
# -------------------------------------------------------------------------

def parse_ps_date(date_str):
    """
    ParionsSport uses a format like '2601050100' (YYMMDDHHMM) in the 'start' field.
    """
    try:
        # Format: Year(2) Month(2) Day(2) Hour(2) Minute(2)
        # 2601050100 -> 2026-01-05 01:00
        dt = datetime.strptime(date_str, "%y%m%d%H%M")
        return dt.strftime("%d/%m %H:%M")
    except Exception:
        return date_str

def clean_bet_name(text):
    """
    Cleans the bet text.
    Example Input: "CB - D.Medvedev gagne... (2,2 -> 2,5 / Mise max 25€)"
    Example Output: "D.Medvedev gagne..."
    """
    # Remove prefix "CB - " (Cote Boostée)
    if text.startswith("CB - "):
        text = text[5:]
    
    # Remove parenthesis with price info if present (e.g. "(2,2 -> 2,5...)")
    if "(" in text and "->" in text:
        text = text.split("(")[0].strip()
        
    return text

def fetch_parionssport_data():
    print(f"Fetching ParionsSport...")
    while True:
        try:
            response = requests.get(
                URL, 
                headers=HEADERS, 
                impersonate="chrome"
            )
            
            if response.status_code == 401:
                print(f"Failed to fetch data. Status Code: {response.status_code}")
                print("Response:", response.text[:200])
                continue
            # elif res

            data = response.json()
            items = data.get("items", {})
            
            # 1. ORGANIZE ITEMS BY TYPE
            events = {}
            markets = {}
            outcomes = []

            for key, item in items.items():
                if key.startswith("e"): # Event
                    events[key] = item
                elif key.startswith("m"): # Market
                    markets[key] = item
                elif key.startswith("o"): # Outcome (Odds)
                    outcomes.append(item)

            rows = []

            # 2. LINK OUTCOME -> MARKET -> EVENT
            for outcome in outcomes:
                try:
                    # We usually only want the 'Oui' selection or the active boost
                    # Filter out hidden or tiny odds if necessary
                    if outcome.get("desc") == "." or "hidden" in outcome.get("flags", []):
                        continue

                    market_id = outcome.get("parent")
                    market = markets.get(market_id)
                    if not market: continue

                    event_id = market.get("parent")
                    event = events.get(event_id)
                    if not event: continue

                    # EXTRACT DATA
                    start_time = parse_ps_date(event.get("start", ""))
                    site_name = "ParionsSport"
                    sport = event.get("path", {}).get("Sport", "Unknown")
                    match_name = event.get("desc", "-")
                    
                    # Get Bet Name (Market description) and clean it
                    raw_bet_name = market.get("desc", "")
                    bet_name = raw_bet_name #clean_bet_name(raw_bet_name)

                    # Get Odds
                    # ParionsSport sends odds as a string with comma "2,50". Convert to float/standard.
                    cote_str = outcome.get("price", "0").replace(",", ".")
                    
                    rows.append({
                        "Time": start_time,
                        "Site": site_name,
                        "Sport": sport,
                        "Match": match_name,
                        "Bet": bet_name,
                        "Cote": cote_str
                    })

                except Exception as e:
                    print(f"Error parsing item: {e}")
                    continue
                    
            return rows

        except Exception as e:
            print(f"Connection Error: {e}")
            return []

# -------------------------------------------------------------------------
# MAIN
# -------------------------------------------------------------------------

def main():
    # 1. Fetch Data
    all_rows = fetch_parionssport_data()

    # 2. Display in Console
    print(f"\n{'Time':<15} | {'Site':<15} | {'Sport':<12} | {'Match':<25} | {'Bet':<40} | {'Cote'}")
    print("-" * 120)
    
    for row in all_rows:
        match_disp = (row['Match'][:22] + '..') if len(row['Match']) > 22 else row['Match']
        bet_disp = (row['Bet'][:37] + '..') if len(row['Bet']) > 37 else row['Bet']
        print(f"{row['Time']:<15} | {row['Site']:<15} | {row['Sport']:<12} | {match_disp:<25} | {bet_disp:<40} | {row['Cote']}")

    # 3. Save to Excel
    if all_rows:
        df = pd.DataFrame(all_rows)
        df.to_excel("ParionsSport_Result1.xlsx", index=False)
        print("\n[SUCCESS] Saved to ParionsSport_Result.xlsx")
    else:
        print("\n[INFO] No data found.")

if __name__ == "__main__":
    main()
