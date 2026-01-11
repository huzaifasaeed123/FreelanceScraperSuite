from curl_cffi import requests
import json


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


def display_outright(outright, site_name):
    """Display outright data in formatted way"""
    if not outright:
        print(f"  No outright data found")
        return
    
    print(f"  Title: {outright.get('title')}")
    print(f"  Icon: {outright.get('icon')}")
    print(f"  Events: {len(outright.get('events', []))}")
    
    for event in outright.get("events", []):
        print(f"\n  Event: {event.get('label')}")
        print(f"  Start: {event.get('start')}")
        print(f"  Sport: {event.get('sport', {}).get('label')}")
        
        for market in event.get("markets", []):
            for bet in market.get("bets", []):
                print(f"\n  Bet: {bet.get('label')}")
                for sel in bet.get("selections", []):
                    odds = sel.get('odds', 0)
                    odds_display = sel.get('odds_display', '-')
                    print(f"    {sel.get('label')}: {odds_display} (odds: {odds})")


def fetch_outright(site_name):
    """Fetch outright data from a specific site"""
    config = APIS.get(site_name)
    if not config:
        print(f"Unknown site: {site_name}")
        return None
    
    headers = get_headers(config["origin"], config["referer"])
    payload = {
        "context": {
            "url_key": "/super-cotes",
            "clientIp": "",
            "version": "1.0.1",
            "device": "web_vuejs_desktop",
            "lang": "fr",
            "timezone": "Asia/Karachi",
            "url_params": {}
        }
    }
    
    try:
        response = requests.post(
            config["url"], 
            headers=headers, 
            json=payload,
            impersonate="chrome"
        )
        
        print(f"  Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            
            # Save full response
            with open(f"{site_name}_response.json", "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            outright = extract_outright(data)
            
            if outright:
                # Save outright data
                with open(f"{site_name}_outright.json", "w", encoding="utf-8") as f:
                    json.dump(outright, f, indent=2, ensure_ascii=False)
                
                display_outright(outright, site_name)
            else:
                print("  No outright data found in response")
            
            return outright
        else:
            print(f"  Failed: {response.text[:300]}")
            return None
            
    except Exception as e:
        print(f"  Error: {e}")
        return None


def fetch_all():
    """Fetch outright data from all configured sites"""
    results = {}
    
    for site_name in APIS.keys():
        print(f"\n{'='*60}")
        print(f"Fetching from {site_name.upper()}")
        print('='*60)
        outright = fetch_outright(site_name)
        results[site_name] = outright
    
    return results


def compare_odds(results):
    """Compare odds across all sites"""
    print(f"\n{'='*60}")
    print("ODDS COMPARISON")
    print('='*60)
    
    all_selections = {}
    
    for site_name, outright in results.items():
        if not outright:
            continue
        
        for event in outright.get("events", []):
            event_label = event.get("label", "Unknown")
            
            for market in event.get("markets", []):
                for bet in market.get("bets", []):
                    for sel in bet.get("selections", []):
                        sel_label = sel.get("label")
                        odds = sel.get("odds", 0)
                        
                        key = f"{event_label}|{sel_label}"
                        if key not in all_selections:
                            all_selections[key] = {}
                        all_selections[key][site_name] = odds
    
    # Display comparison
    for key, sites in all_selections.items():
        event_label, sel_label = key.split("|", 1)
        print(f"\n{event_label[:50]}...")
        print(f"  Selection: {sel_label}")
        
        best_site = max(sites.keys(), key=lambda x: sites[x]) if sites else None
        
        for site, odds in sites.items():
            marker = " ⭐ BEST" if site == best_site and odds > 1 else ""
            print(f"    {site}: {odds}{marker}")


def main():
    print("Super Cotes Fetcher - Netbet / Genybet / Olybet")
    print("================================================")
    
    # Fetch from all sites
    results = fetch_all()
    
    # Compare odds
    compare_odds(results)
    
    # Summary
    print(f"\n{'='*60}")
    print("FILES SAVED")
    print('='*60)
    for site_name in APIS.keys():
        print(f"  {site_name}_response.json - Full API response")
        print(f"  {site_name}_outright.json - Outright data only")


if __name__ == "__main__":
    main()