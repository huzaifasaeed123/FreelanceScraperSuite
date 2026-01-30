"""
Scraper for Winamax - Final Excel Ready Version
- Aligns with Excel format (DATE, SITE, SPORT, MATCH, BET, COTE)
- Forces 2 decimal places with comma for odds
- Replaces 'vs' with '-'
- Captures only the final (best) odd
"""
import undetected_chromedriver as uc
import time
from datetime import datetime, timedelta
import re
import os
from bs4 import BeautifulSoup

# Map specific element classes to sport names
SPORT_CLASS_MAP = {
    "jBEKhk": "Football", "dkHLgg": "Tennis", "hseKCd": "AutoMobile", "gLfCBJ": "Basketball",
    "IykmB": "Badminton", "jYItmE": "BaseBall", "eiNeLb": "Biathlon",
    "fZlkIQ": "Boxe", "LVgKa": "Combiné Nordique", "iPFkIL": "Curling",
    "jBXQGj": "Cyclisme", "jBQquK": "Football américain", "kHOGoy": "Football australien",
    "cXCHye": "Formule 1", "eePDFL": "Futsal", "eggrth": "Golf",
    "bSTPIj": "Handball", "fPXfKq": "Hockey sur glace", "edwWlp": "JO Milano Cortina 2026",
    "hUaBXW": "MMA", "bPZTXN": "Moto", "bIWJLP": "Rugby à XV",
    "cJUbgF": "Rugby à XIII", "eLpoQn": "Ski de fond", "gCqCtm": "Snooker",
    "brAQKf": "Volley-ball", "btfeGD": "Water-polo"
}

def clean_text(text):
    """Removes newlines and replaces multiple spaces with a single space."""
    if not text:
        return ""
    text = text.replace('\n', ' ').replace('\t', ' ')
    text = re.sub(r'\s+', ' ', text)
    return text.strip()

def format_final_odd(odds_list):
    """
    Takes a list of odds (e.g. ['2.08', '2.30']), finds the max/final one,
    formats to 2 decimals, and replaces dot with comma.
    """
    if not odds_list:
        return "0,00"
    
    try:
        # Convert strings to floats to find the best odd (max)
        float_odds = [float(o.replace(',', '.')) for o in odds_list]
        best_odd = max(float_odds)
        
        # Format: 2 decimal places, then replace dot with comma
        # e.g. 2.5 -> "2.50" -> "2,50"
        return "{:.2f}".format(best_odd).replace('.', ',')
    except Exception:
        return "0,00"

def clean_match_name(match_text):
    """Replaces 'v', 'vs', 'vs.' with '-' """
    if not match_text:
        return "Unknown"
    # Regex to find vs surrounded by spaces, case insensitive
    return re.sub(r'\s+(?:vs?\.?|v)\s+', ' - ', match_text, flags=re.IGNORECASE)

def parse_winamax_time(time_text):
    """Parses relative time strings into date format"""
    if not time_text:
        return "Unknown"

    now = datetime.now()
    clean_val = clean_text(time_text.lower())
    target_date = now

    try:
        if "demain" in clean_val:
            target_date = now + timedelta(days=1)
        
        time_match = re.search(r'(\d{1,2})[:h](\d{2})', clean_val)
        
        if time_match:
            val1, val2 = map(int, time_match.groups())
            if val1 > 23: # Countdown
                target_date = now + timedelta(minutes=val1, seconds=val2)
            else: # Standard Time
                try:
                    target_date = target_date.replace(hour=val1, minute=val2, second=0)
                except ValueError:
                    target_date = now + timedelta(minutes=val1, seconds=val2)

        return target_date.strftime("%d/%m %H:%M")
    except Exception:
        return clean_val

def get_sport_from_card(card_soup):
    """Scans all elements to find a class matching our Sport Map"""
    all_tags = card_soup.find_all(True)
    for tag in all_tags:
        classes = tag.get("class", [])
        for cls in classes:
            if cls in SPORT_CLASS_MAP:
                return SPORT_CLASS_MAP[cls]
    return "Unknown"

def scrape_winamax():
    URL = "https://www.winamax.fr/paris-sportifs/sports/100000"

    options = uc.ChromeOptions()
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--start-maximized")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")

    print("[WINAMAX] Launching Chrome...")
    driver = None

    try:
        driver = uc.Chrome(options=options)
        print(f"[WINAMAX] Opening {URL}...")
        driver.get(URL)

        print("[WINAMAX] Waiting for content...")
        time.sleep(10) # Wait for load

        html = driver.page_source
        print("[WINAMAX] HTML captured.")

    except Exception as e:
        print(f"[WINAMAX] Browser error: {e}")
        return []
    finally:
        if driver:
            driver.quit()

    soup = BeautifulSoup(html, "html.parser")
    
    main_div = soup.find("div", class_="ReactVirtualized__Grid__innerScrollContainer")
    if not main_div:
        print("[ERROR] Main grid container not found.")
        return []

    cards = main_div.find_all("div", recursive=False)
    print(f"[WINAMAX] Found {len(cards)} betting cards.")

    all_data = []

    for card in cards:
        try:
            # 1. Get Clean Text Lines
            raw_lines = list(card.stripped_strings)
            text_lines = [clean_text(line) for line in raw_lines if clean_text(line)]
            
            if not text_lines:
                continue

            # 2. Identify Indices for TIME and ODDS
            time_val = "Unknown"
            time_index = -1
            time_pattern = re.compile(r'(\d{2}[:h]\d{2})|demain|aujourd|live', re.IGNORECASE)

            # Find Time
            for i, line in enumerate(text_lines):
                if time_pattern.search(line):
                    time_val = parse_winamax_time(line)
                    time_index = i
                    break
            
            # Find Odds (Collect all numbers that look like odds)
            odds_values = []
            odds_indices = []
            odd_pattern = re.compile(r'^\d+[,.]\d{2}$') 

            for i, line in enumerate(text_lines):
                if odd_pattern.match(line):
                    odds_values.append(line)
                    odds_indices.append(i)

            # 3. Extract MATCH and BET
            match_val = ""
            bet_val = ""

            # Determine content area (Text between Time and Odds)
            start_idx = time_index + 1 if time_index != -1 else 0
            end_idx = odds_indices[0] if odds_indices else len(text_lines)
            
            content_lines = text_lines[start_idx:end_idx]

            if content_lines:
                # Logic: The first line is usually the Match Name. 
                # Everything after is the Bet Description.
                
                # 1. Match Name
                raw_match_name = content_lines[0]
                match_val = clean_match_name(raw_match_name)

                # 2. Bet Description
                if len(content_lines) > 1:
                    bet_val = " ".join(content_lines[1:])
                else:
                    # If only one line exists, sometimes the match IS the bet (e.g. Winner)
                    # But usually formatting implies Line 1 is Match.
                    bet_val = match_val 

            # 4. Format Odds (Get max value, comma separated, 2 decimals)
            cote_val = format_final_odd(odds_values)
            
            # 5. Get Sport
            sport_val = get_sport_from_card(card)

            # 6. Build Dict matching Excel Header
            # Excel Headers: DATE | SITE | SPORT | MATCH | BET | COTE
            card_data = {
                "Time": time_val,       # Maps to DATE
                "Site": "Winamax",      # Maps to SITE
                "Sport": sport_val,     # Maps to SPORT
                "Match": match_val,     # Maps to MATCH
                "Bet": bet_val,         # Maps to BET
                "Cote": cote_val        # Maps to COTE
            }
            all_data.append(card_data)

        except Exception as e:
            print(f"[ERROR] Error parsing card: {e}")
            continue

    print(f"[WINAMAX] Scraped {len(all_data)} rows")
    return all_data

if __name__ == "__main__":
    data = scrape_winamax()
    print("-" * 50)
    for row in data:
        print(row)
    print("-" * 50)