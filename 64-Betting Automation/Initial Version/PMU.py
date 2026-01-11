from curl_cffi import requests
import json
import pandas as pd
from datetime import datetime

# -------------------------------------------------------------------------
# CONFIGURATION
# -------------------------------------------------------------------------
# The specific PMU API URL for Boosts
URL = "https://sports.pmu.fr/sportsbook/rest/v2/matches/?marketGroup=boost&featureType=boost&sportId=1&sportId=2&sportId=3&sportId=12&sportId=29&sportId=7&sportId=55&sportId=24&sportId=16&sportId=8&sportId=25&sportId=10&sportId=56&sportId=26&sportId=5&sportId=52&sportId=27&sportId=18&sportId=14&ln=fr"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Referer": "https://paris-sportifs.pmu.fr/",
    "Origin": "https://paris-sportifs.pmu.fr"
}

# -------------------------------------------------------------------------
# HELPER FUNCTIONS
# -------------------------------------------------------------------------

def format_pmu_date(date_str):
    """
    Converts PMU ISO date '2026-01-06T20:00:00.000+0000' to '06/01 20:00'
    """
    try:
        # Parse ISO format with timezone
        dt = datetime.strptime(date_str, "%Y-%m-%dT%H:%M:%S.%f%z")
        return dt.strftime("%d/%m %H:%M")
    except Exception as e:
        return date_str

def clean_bet_name(text):
    """
    Only removes tabs (\t), newlines (\n) and extra outer spaces.
    Keeps text like '(15€ max)'.
    """
    if not text: return ""
    
    # Replace tabs and newlines with a single space
    cleaned = text.replace("\t", " ").replace("\n", " ")
    
    # Remove multiple spaces and strip start/end
    cleaned = " ".join(cleaned.split())
    
    return cleaned

def fetch_pmu_data():
    print(f"[INFO] Fetching PMU Super Cotes...")
    
    try:
        # Use curl_cffi to avoid bot detection
        response = requests.get(URL, headers=HEADERS, impersonate="chrome")
        
        if response.status_code != 200:
            print(f"[ERROR] Failed to fetch data. Status: {response.status_code}")
            return []

        data = response.json()
        all_bets = []

        # PMU JSON is a list of Matches
        for match in data:
            try:
                # 1. MATCH INFO
                match_name = match.get("name", "Unknown")
                sport_name = match.get("sportName", "Unknown")
                
                # 2. TIME
                start_date_raw = match.get("startDate", "")
                time_str = format_pmu_date(start_date_raw)

                # 3. ODDS ITERATION
                # The 'odds' list contains the boost markets
                odds_groups = match.get("odds", [])
                
                for group in odds_groups:
                    # We iterate outcomes inside the group
                    outcomes = group.get("outcomes", [])
                    
                    for outcome in outcomes:
                        # 4. BET DESCRIPTION (Cleaned lightly)
                        raw_bet_name = outcome.get("outcome", "")
                        bet_name = clean_bet_name(raw_bet_name)
                        
                        # 5. COTE
                        decimal_odd = outcome.get("oddValue", 0)
                        cote_str = str(decimal_odd).replace(".", ",")

                        # Add to list
                        all_bets.append({
                            "Time": time_str,
                            "Site": "PMU",
                            "Sport": sport_name,
                            "Match": match_name,
                            "Bet": bet_name,
                            "Cote": cote_str
                        })
            except Exception as inner_e:
                print(f"Error parsing match ID {match.get('id')}: {inner_e}")
                continue

        return all_bets

    except Exception as e:
        print(f"[ERROR] Exception occurred: {e}")
        return []

# -------------------------------------------------------------------------
# MAIN
# -------------------------------------------------------------------------
def main():
    rows = fetch_pmu_data()

    # Console Display
    print(f"\n{'Time':<15} | {'Site':<10} | {'Match':<30} | {'Bet':<40} | {'Cote'}")
    print("-" * 110)
    
    for row in rows:
        m = (row['Match'][:27] + '..') if len(row['Match']) > 27 else row['Match']
        b = (row['Bet'][:37] + '..') if len(row['Bet']) > 37 else row['Bet']
        print(f"{row['Time']:<15} | {row['Site']:<10} | {m:<30} | {b:<40} | {row['Cote']}")

    # Excel Export
    if rows:
        df = pd.DataFrame(rows)
        # Ensure column order
        df = df[["Time", "Site", "Sport", "Match", "Bet", "Cote"]]
        
        filename = "PMU_Result.xlsx"
        df.to_excel(filename, index=False)
        print(f"\n[SUCCESS] Saved {len(rows)} rows to {filename}")
    else:
        print("\n[INFO] No data found.")

if __name__ == "__main__":
    main()