"""
Scraper for Betsson - Final Clean Version
- Removes Emojis at start
- Removes '!' and ' - Flash Boost' at end
- Removes (Max ...) limits
- Maps Sport IDs correctly
- Uses shared browser manager (no new Chrome instance per run)
"""

import time
from datetime import datetime, timedelta
import re
from bs4 import BeautifulSoup

# Import shared browser manager
from scrapers.browser_manager import browser_manager

URL = "https://betsson.fr/fr"

# Map ID from icon URL (e.g., "1.svg") to Sport Name
SPORT_ID_MAP = {
    "1": "Football",
    "2": "Basketball",
    "3": "Tennis",
    "4": "Rugby",
    "5": "Volleyball",
    "6": "Hockey sur glace",
    "7": "Handball",
    "8": "Basketball",
    "9": "Baseball",
    "12": "Rugby",
    "16": "Football Américain",
    "36": "Football Australien"
}

def parse_betsson_time(date_text, time_text):
    """Converts Betsson relative dates (Aujourd'hui, Demain) into DD/MM HH:MM"""
    try:
        now = datetime.now()
        date_str = ""
        text_lower = date_text.lower().strip()
        
        if "aujourd'hui" in text_lower:
            date_str = now.strftime("%d/%m")
        elif "demain" in text_lower:
            date_str = (now + timedelta(days=1)).strftime("%d/%m")
        else:
            date_str = date_text
            
        return f"{date_str} {time_text}"
    except Exception:
        return f"{date_text} {time_text}"

def clean_bet_text(text):
    """
    Cleans the bet description according to specific rules:
    1. Removes ' - Flash Boost'
    2. Removes ALL parentheses content throughout the text
    3. Removes leading emojis/symbols
    4. Removes trailing exclamation marks '!'

    Examples:
    - "⚡ Scott Mctominay Buteur! (Max 20€) - Flash Boost" -> "Scott Mctominay Buteur"
    - "Novak (Le Goat) gagne (Max 20€)" -> "Novak gagne"
    """
    if not text:
        return "Unknown"

    # 1. Remove " - Flash Boost" (case insensitive)
    text = re.sub(r'\s*-\s*Flash Boost', '', text, flags=re.IGNORECASE)

    # 2. Remove ALL parentheses content throughout the string
    text = re.sub(r'\s*\([^)]*\)', '', text)

    # 3. Remove leading non-alphanumeric chars (emojis, spaces)
    # Keeps letters, numbers, and quotes.
    text = re.sub(r'^[^\w"]+', '', text)

    # 4. Remove exclamation marks '!' specifically at the end (or everywhere if preferred)
    # Using replace to ensure all '!' are gone as they usually clutter the bet name
    text = text.replace('!', '')

    return text.strip()

def get_sport_from_card(card_soup):
    """Finds the sport icon inside the card and maps it to a sport name."""
    try:
        icon_tag = card_soup.find("i", class_="sportIcon")
        if icon_tag:
            img_tag = icon_tag.find("img")
            if img_tag and 'src' in img_tag.attrs:
                src = img_tag['src'] 
                # Regex to grab the number before .svg (e.g., /1.svg -> 1)
                match = re.search(r'/(\d+)\.svg', src)
                if match:
                    sport_id = match.group(1)
                    return SPORT_ID_MAP.get(sport_id, "Unknown")
    except Exception:
        pass
    return "Unknown"

def scrape_betsson():
    """Main scraper function for Betsson - Uses shared browser instance"""

    print(f"[BETSSON] Using shared browser instance...")

    # Use shared browser manager - opens in new tab, scrolls, then closes tab
    html = browser_manager.navigate_and_get_source(
        url=URL,
        wait_time=15,
        scroll_down=True,
        scroll_wait=5
    )

    if not html:
        print(f"[BETSSON] Failed to get page content")
        return []

    print("[BETSSON] HTML captured.")

    # Parse HTML
    soup = BeautifulSoup(html, "html.parser")
    
    # Target the boosted cards specifically
    cards = soup.find_all("div", class_="boostedOddsGameCard")
    print(f"[BETSSON] Found {len(cards)} potential betting cards.")

    all_data = []

    for card in cards:
        try:
            if not card.find("div", class_="betEventInfo"):
                continue

            # --- SPORT ---
            sport_val = get_sport_from_card(card)
            
            # --- MATCH ---
            home_team = card.find("div", class_="exhibitionHome")
            away_team = card.find("div", class_="exhibitionAway")
            
            if home_team and away_team:
                match_val = f"{home_team.get_text(strip=True)} - {away_team.get_text(strip=True)}"
            else:
                match_val = "Unknown"

            # --- TIME ---
            date_div = card.find("div", class_="exhibitionDate")
            time_div = card.find("div", class_="exhibitionTime")
            
            raw_date = date_div.get_text(strip=True) if date_div else ""
            raw_time = time_div.get_text(strip=True) if time_div else ""
            final_time = parse_betsson_time(raw_date, raw_time)

            # --- BET ---
            market_div = card.find("div", class_="liveMarketName")
            raw_bet = market_div.get_text(strip=True) if market_div else "Unknown"
            
            # CLEANING APPLIED HERE
            bet_val = clean_bet_text(raw_bet)

            # --- ODDS ---
            cote_val = "0,00"
            all_odd_containers = card.find_all("div", class_="betOddInfoContainer")
            
            for oc in all_odd_containers:
                is_boosted = "isBoosted" in oc.get("class", []) or oc.find_parent(class_="isBoosted")
                
                if is_boosted:
                    val_div = oc.find("div", class_="betOddValue")
                    if val_div:
                        raw_odd = val_div.get_text(strip=True)
                        try:
                            # 2 decimal places, comma separator
                            cote_val = "{:.2f}".format(float(raw_odd.replace(',', '.'))).replace('.', ',')
                        except:
                            cote_val = raw_odd
                    break

            all_data.append({
                "Time": final_time,
                "Site": "Betsson",
                "Sport": sport_val,
                "Match": match_val,
                "Bet": bet_val,
                "Cote": cote_val
            })

        except Exception as e:
            print(f"Error parsing card: {e}")
            continue

    print(f"[BETSSON] Scraped {len(all_data)} rows")
    return all_data

if __name__ == "__main__":
    data = scrape_betsson()
    print("-" * 50)
    for row in data:
        print(row)
    print("-" * 50)