"""
Scraper for Netbet, Genybet, and Olybet
These 3 sites share the same API structure
"""

from curl_cffi import requests
from datetime import datetime
import json


def parse_iso_time(time_str):
    """
    Convert ISO time format to readable DD/MM HH:MM
    Input: '2026-01-07T20:00:00.000+01:00'
    Output: '07/01 20:00'
    """
    if not time_str:
        return ""
    try:
        # Handle various ISO formats
        # Remove milliseconds and timezone for simpler parsing
        clean_str = time_str.split('.')[0]  # Remove .000+01:00
        dt = datetime.strptime(clean_str, "%Y-%m-%dT%H:%M:%S")
        return dt.strftime("%d/%m %H:%M")
    except Exception:
        try:
            # Try with timezone
            dt = datetime.fromisoformat(time_str.replace('Z', '+00:00'))
            return dt.strftime("%d/%m %H:%M")
        except Exception:
            return time_str


APIS = {
    "netbet": {
        "url": "https://ws.netbet.fr/component/datatree",
        "origin": "https://www.netbet.fr",
        "referer": "https://www.netbet.fr/"
    },
    "genybet": {
        "url": "https://ws.genybet.fr/component/datatree",
        "origin": "https://sport.genybet.fr",
        "referer": "https://sport.genybet.fr/"
    },
    "olybet": {
        "url": "https://ws.olybet.fr/component/datatree",
        "origin": "https://www.olybet.fr",
        "referer": "https://www.olybet.fr/"
    }
}


def get_headers(origin, referer):
    return {
        "Sec-Ch-Ua-Platform": '"Windows"',
        "Accept-Language": "en-US,en;q=0.9",
        "Sec-Ch-Ua": '"Chromium";v="143", "Not A(Brand";v="24"',
        "Content-Type": "application/json",
        "Sec-Ch-Ua-Mobile": "?0",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36",
        "Accept": "*/*",
        "Origin": origin,
        "Sec-Fetch-Site": "same-site",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Dest": "empty",
        "Referer": referer,
        "Accept-Encoding": "gzip, deflate, br",
        "Priority": "u=1, i"
    }


def find_component(components, tree_compo_key):
    """Recursively find a component by its tree_compo_key"""
    if not components:
        return None
    for component in components:
        if component.get("tree_compo_key") == tree_compo_key:
            return component
        nested = component.get("components", [])
        if nested:
            result = find_component(nested, tree_compo_key)
            if result:
                return result
    return None


def extract_outright(response_json):
    """Extract outright data from the response"""
    try:
        components = response_json.get("tree", {}).get("components", [])
        featured = find_component(components, "sport_page_featured")
        if featured:
            return featured.get("data", {}).get("outright")
        return None
    except Exception as e:
        print(f"Error extracting outright: {e}")
        return None


def parse_outright_to_rows(outright, site_name):
    """Convert outright data to standard row format"""
    rows = []
    if not outright:
        return rows
    
    for event in outright.get("events", []):
        event_label = event.get("label", "Unknown")
        start_time_raw = event.get("start", "")
        start_time = parse_iso_time(start_time_raw)  # Convert to readable format
        sport = event.get("sport", {}).get("label", "Unknown")
        
        for market in event.get("markets", []):
            for bet in market.get("bets", []):
                bet_label = bet.get("label", "")
                for sel in bet.get("selections", []):
                    odds = sel.get('odds', 0)
                    odds_display = sel.get('odds_display', str(odds))
                    
                    rows.append({
                        "Time": start_time,
                        "Site": site_name.capitalize(),
                        "Sport": sport,
                        "Match": event_label,
                        "Bet": f"{bet_label} - {sel.get('label', '')}",
                        "Cote": odds_display
                    })
    
    return rows


def fetch_site_data(site_name):
    """Fetch data from a specific site"""
    config = APIS.get(site_name)
    if not config:
        print(f"Unknown site: {site_name}")
        return []
    
    headers = get_headers(config["origin"], config["referer"])
    payload = {
        "context": {
            "url_key": "/super-cotes",
            "clientIp": "",
            "version": "1.0.1",
            "device": "web_vuejs_desktop",
            "lang": "fr",
            "timezone": "Europe/Paris",
            "url_params": {}
        }
    }
    
    try:
        response = requests.post(
            config["url"], 
            headers=headers, 
            json=payload,
            impersonate="chrome",
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            outright = extract_outright(data)
            rows = parse_outright_to_rows(outright, site_name)
            print(f"[{site_name.upper()}] Fetched {len(rows)} rows")
            return rows
        else:
            print(f"[{site_name.upper()}] Failed: Status {response.status_code}")
            return []
            
    except Exception as e:
        print(f"[{site_name.upper()}] Error: {e}")
        return []


def scrape_netbet():
    """Scrape Netbet"""
    return fetch_site_data("netbet")


def scrape_genybet():
    """Scrape Genybet"""
    return fetch_site_data("genybet")


def scrape_olybet():
    """Scrape Olybet"""
    return fetch_site_data("olybet")


if __name__ == "__main__":
    # Test
    print("Testing Netbet...")
    data = scrape_netbet()
    for row in data[:3]:
        print(row)