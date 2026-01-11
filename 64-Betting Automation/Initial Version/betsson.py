import time
import undetected_chromedriver as uc
from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime, timedelta
import re

# -------------------------------------------------------------------------
# CONFIGURATION
# -------------------------------------------------------------------------
URL = "https://betsson.fr/fr"
EXCEL_FILENAME = "Betsson_Result.xlsx"

# -------------------------------------------------------------------------
# HELPER FUNCTIONS
# -------------------------------------------------------------------------

def parse_betsson_time(date_text, time_text):
    """
    Converts Betsson relative dates (Aujourd'hui, Demain) into DD/MM HH:MM
    """
    try:
        now = datetime.now()
        date_str = ""
        
        text_lower = date_text.lower().strip()
        
        if "aujourd'hui" in text_lower:
            date_str = now.strftime("%d/%m")
        elif "demain" in text_lower:
            date_str = (now + timedelta(days=1)).strftime("%d/%m")
        else:
            # Try to parse if it's a specific date (e.g. 12/01)
            # Usually Betsson format is specific, but fallback to raw if unknown
            date_str = date_text
            
        return f"{date_str} {time_text}"
    except Exception:
        return f"{date_text} {time_text}"

def clean_bet_name(text):
    """
    Cleans bet title. 
    Input: "⚡ Scott Mctominay Buteur! (Max 20€) - Flash Boost"
    Output: "Scott Mctominay Buteur!"
    """
    if not text: return "Unknown"
    
    # Remove Emojis like ⚡ or ⚽
    text = re.sub(r'[^\w\s\(\)\-!,\.]', '', text)
    
    # Remove (Max 20€) or similar text
    text = re.sub(r'\s*\(Max \d+€\)', '', text, flags=re.IGNORECASE)
    
    # Remove "- Flash Boost" suffix
    text = text.replace("- Flash Boost", "").strip()
    
    # Remove leading special chars if left
    return text.strip()

# -------------------------------------------------------------------------
# MAIN SCRAPER
# -------------------------------------------------------------------------
def main():
    # 1. SETUP HEADLESS BROWSER
    options = uc.ChromeOptions()
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--start-maximized")
    # options.add_argument("--headless")  # Headless mode as requested

    print(f"[INFO] Launching Headless Chrome...")
    driver = uc.Chrome(options=options)

    try:
        print(f"[INFO] Opening {URL}...")
        driver.get(URL)

        # 2. WAIT & SCROLL
        # Betsson uses a slider (Swiper). We wait for it to load.
        print("[INFO] Waiting for content...")
        time.sleep(8) 
        
        # Optional: Small scroll to trigger lazy loading if needed
        driver.execute_script("window.scrollTo(0, 300);")
        time.sleep(2)

        # 3. GET HTML
        html = driver.page_source
        print("[INFO] HTML captured.")

    finally:
        driver.quit()

    # 4. PARSE HTML
    soup = BeautifulSoup(html, "html.parser")
    
    # Find all boosted cards based on your HTML snippet
    cards = soup.find_all("div", class_="boostedOddsGameCard")
    
    print(f"[INFO] Found {len(cards)} potential betting cards.")

    all_data = []

    for card in cards:
        try:
            # Only process cards that actually contain match info (ignore wrapper divs)
            if not card.find("div", class_="betEventInfo"):
                continue

            # A. MATCH extraction
            home_team = card.find("div", class_="exhibitionHome")
            away_team = card.find("div", class_="exhibitionAway")
            
            if home_team and away_team:
                match_val = f"{home_team.get_text(strip=True)} - {away_team.get_text(strip=True)}"
            else:
                match_val = "Unknown"

            # B. TIME extraction
            date_div = card.find("div", class_="exhibitionDate")
            time_div = card.find("div", class_="exhibitionTime")
            
            raw_date = date_div.get_text(strip=True) if date_div else ""
            raw_time = time_div.get_text(strip=True) if time_div else ""
            final_time = parse_betsson_time(raw_date, raw_time)

            # C. BET extraction
            # Found in class "liveMarketName" -> "label"
            market_div = card.find("div", class_="liveMarketName")
            raw_bet = market_div.get_text(strip=True) if market_div else "Unknown"
            bet_val = raw_bet #clean_bet_name(raw_bet) no need for cleaning

            # D. ODDS extraction
            # We look for the container with "isBoosted" to get the boosted price
            # Your HTML: <div class="betOddInfoContainer ... isBoosted"> ... <div class="betOddValue"><span>3.30</span>
            boosted_container = card.find("div", class_=["betOddInfoContainer", "isBoosted"])
            
            # Note: Sometimes find returns the first match which might be the crossed out one.
            # We specifically want the one inside the div that HAS the class 'isBoosted'
            
            # Robust Search for Boosted Odd:
            cote_val = "0"
            all_odd_containers = card.find_all("div", class_="betOddInfoContainer")
            for oc in all_odd_containers:
                # Check if this specific container has 'isBoosted' class or is inside a parent with 'isBoosted'
                if "isBoosted" in oc.get("class", []) or oc.find_parent(class_="isBoosted"):
                    val_div = oc.find("div", class_="betOddValue")
                    if val_div:
                        cote_val = val_div.get_text(strip=True).replace(",", ".")
                    break

            # E. SPORT & SITE
            # Sport is in <span class="parentName">
            sport_el = card.find("span", class_="parentName")
            raw_sport = sport_el.get_text(strip=True) if sport_el else "Football"
            # Cleanup sport name (e.g. "Serie A - Italie" -> "Football" or keep as is)
            sport_val = raw_sport 
            
            site_val = "Betsson"

            # Add to list
            all_data.append({
                "Time": final_time,
                "Site": site_val,
                "Sport": sport_val,
                "Match": match_val,
                "Bet": bet_val,
                "Cote": cote_val
            })
            
            print(f"Parsed: {match_val} | {cote_val}")

        except Exception as e:
            # print(f"Error parsing card: {e}") # Uncomment to debug
            continue

    # 5. EXPORT TO EXCEL
    if all_data:
        df = pd.DataFrame(all_data)
        df = df[["Time", "Site", "Sport", "Match", "Bet", "Cote"]]
        
        df.to_excel(EXCEL_FILENAME, index=False)
        print(f"\n[SUCCESS] Saved {len(all_data)} rows to {EXCEL_FILENAME}")
    else:
        print("\n[WARNING] No data found. The website structure might have changed or content is hidden.")

if __name__ == "__main__":
    main()