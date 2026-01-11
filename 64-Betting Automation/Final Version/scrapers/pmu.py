"""
Scraper for PMU
Uses API with curl_cffi
"""

from curl_cffi import requests
from datetime import datetime


URL = "https://sports.pmu.fr/sportsbook/rest/v2/matches/?marketGroup=boost&featureType=boost&sportId=1&sportId=2&sportId=3&sportId=12&sportId=29&sportId=7&sportId=55&sportId=24&sportId=16&sportId=8&sportId=25&sportId=10&sportId=56&sportId=26&sportId=5&sportId=52&sportId=27&sportId=18&sportId=14&ln=fr"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Referer": "https://paris-sportifs.pmu.fr/",
    "Origin": "https://paris-sportifs.pmu.fr"
}


def format_pmu_date(date_str):
    """
    Converts PMU ISO date '2026-01-06T20:00:00.000+0000' to '06/01 20:00'
    """
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%dT%H:%M:%S.%f%z")
        return dt.strftime("%d/%m %H:%M")
    except Exception:
        return date_str


def clean_bet_name(text):
    """
    Only removes tabs and newlines, keeps rest intact.
    """
    if not text:
        return ""
    cleaned = text.replace("\t", " ").replace("\n", " ")
    cleaned = " ".join(cleaned.split())
    return cleaned


def scrape_pmu():
    """Main scraper function for PMU"""
    print("[PMU] Fetching data...")
    
    try:
        response = requests.get(
            URL, 
            headers=HEADERS, 
            impersonate="chrome",
            timeout=30
        )
        
        if response.status_code != 200:
            print(f"[PMU] Failed: Status {response.status_code}")
            return []

        data = response.json()
        all_bets = []

        for match in data:
            try:
                match_name = match.get("name", "Unknown")
                sport_name = match.get("sportName", "Unknown")
                start_date_raw = match.get("startDate", "")
                time_str = format_pmu_date(start_date_raw)

                odds_groups = match.get("odds", [])
                
                for group in odds_groups:
                    outcomes = group.get("outcomes", [])
                    
                    for outcome in outcomes:
                        raw_bet_name = outcome.get("outcome", "")
                        bet_name = clean_bet_name(raw_bet_name)
                        decimal_odd = outcome.get("oddValue", 0)
                        cote_str = str(decimal_odd).replace(".", ",")

                        all_bets.append({
                            "Time": time_str,
                            "Site": "PMU",
                            "Sport": sport_name,
                            "Match": match_name,
                            "Bet": bet_name,
                            "Cote": cote_str
                        })
            except Exception as e:
                continue

        print(f"[PMU] Scraped {len(all_bets)} rows")
        return all_bets

    except Exception as e:
        print(f"[PMU] Error: {e}")
        return []


if __name__ == "__main__":
    data = scrape_pmu()
    for row in data[:5]:
        print(row)
