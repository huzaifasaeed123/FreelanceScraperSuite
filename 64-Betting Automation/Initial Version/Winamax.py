import time
import undetected_chromedriver as uc
from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime, timedelta
import re

# -------------------------------------------------------------------------
# CONFIGURATION
# -------------------------------------------------------------------------
URL = "https://www.winamax.fr/paris-sportifs/sports/100000"
EXCEL_FILENAME = "Winamax_Result.xlsx"

# -------------------------------------------------------------------------
# TIME PARSING LOGIC
# -------------------------------------------------------------------------
def parse_winamax_time(time_text):
    """
    Parses Winamax time strings.
    Handles:
    1. "Demain 00:45" -> Tomorrow at 00:45
    2. "01:28" -> Countdown (Minutes:Seconds remaining) OR Time (Hour:Minute)
    3. "20:00" -> Today at 20:00
    """
    if not time_text:
        return "Unknown"

    now = datetime.now()
    clean_text = time_text.lower().strip()
    target_date = now

    try:
        # Check for "Demain" (Tomorrow)
        if "demain" in clean_text:
            target_date = now + timedelta(days=1)
        
        # Extract numbers (Hour:Minute OR Minute:Second)
        # Looks for patterns like "00:45", "31:28", "20h45"
        time_match = re.search(r'(\d{1,2})[:h](\d{2})', clean_text)
        
        if time_match:
            val1, val2 = map(int, time_match.groups())
            
            # LOGIC SPLIT:
            # If the first number is > 23, it implies it's a countdown in Minutes (e.g. 31:28)
            # because hours can only be 0-23.
            if val1 > 23:
                # Treat as Countdown: val1 = minutes, val2 = seconds
                target_date = now + timedelta(minutes=val1, seconds=val2)
            else:
                # It is a valid Hour (0-23). 
                # However, Winamax sometimes uses red text "01:28" for countdowns (1 min 28 sec)
                # and "01:28" for time (1 AM).
                # To be safe: we try to set the hour.
                try:
                    target_date = target_date.replace(hour=val1, minute=val2, second=0)
                    
                    # If the resulting time is in the past (e.g. it's 14:00 now and we parse 01:28),
                    # AND it wasn't marked "Demain", it's likely a countdown (1 min 28 sec left)
                    # BUT for betting sites, usually past times imply next day? 
                    # Let's stick to simple logic: if it parses as valid time, keep it.
                    # If it's in the past relative to execution, add 1 day? 
                    # For now, let's assume strict parsing.
                    if target_date < now and "demain" not in clean_text:
                         # Fallback: Treat as countdown if it looks like a past time but is live
                         # or simply accept it might be early morning next day not labeled 'demain'
                         pass 

                except ValueError:
                    # If replacing hour fails, calculate as timedelta
                    target_date = now + timedelta(minutes=val1, seconds=val2)

        return target_date.strftime("%d/%m %H:%M")

    except Exception as e:
        print(f"  [Warning] Could not parse date '{time_text}': {e}")
        return time_text

# -------------------------------------------------------------------------
# MAIN SCRAPER
# -------------------------------------------------------------------------
def main():
    # 1. SETUP SELENIUM
    options = uc.ChromeOptions()
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--start-maximized")

    driver = uc.Chrome(options=options)

    try:
        print(f"[INFO] Opening {URL}...")
        driver.get(URL)

        print("[INFO] Waiting 10 seconds for dynamic content...")
        time.sleep(10)

        html = driver.page_source
        print("[INFO] HTML captured. Closing browser.")

    finally:
        driver.quit()

    # 2. PARSE HTML
    soup = BeautifulSoup(html, "html.parser")
    
    # Class for the betting card container
    cards = soup.find_all("div", class_="sc-iPRpaO xNyLa")

    print(f"[INFO] Found {len(cards)} betting cards.")

    all_data = []

    for card in cards:
        try:
            # --- A. TIME EXTRACTION ---
            # Try specific class for countdowns (Live/Urgent)
            time_el = card.find("div", class_="sc-gsHvIN iuOOoY")
            
            # If not found, try class for Future/Demain times (Found in your HTML)
            if not time_el:
                time_el = card.find("div", class_="sc-eHayKN cyqWGm")
            
            # Fallback: Try generic class if both fail (the parent wrapper of time)
            if not time_el:
                time_el = card.find("div", attrs={"data-testid": "boosted-odds-countdown"})

            raw_time = time_el.get_text(strip=True) if time_el else ""
            final_time = parse_winamax_time(raw_time)

            # --- B. MATCH EXTRACTION ---
            match_el = card.find("div", class_="sc-fFdenn cCsdVR")
            match_val = match_el.get_text(strip=True) if match_el else "Unknown"

            # --- C. BET EXTRACTION ---
            bet_el = card.find("div", class_="sc-kMEpbU jAcTe")
            bet_val = bet_el.get_text(strip=True) if bet_el else "Unknown"

            # --- D. ODDS EXTRACTION ---
            # Look for the green/boosted odd class
            odd_el = card.find("span", class_="sc-jvicrE oAOiE")
            if odd_el:
                cote_val = odd_el.get_text(strip=True).replace(",", ".")
            else:
                cote_val = "0"

            # --- E. STATIC FIELDS ---
            site_val = "Winamax"
            sport_val = "Football" # Default, or you can extract specific sport if needed

            all_data.append({
                "Time": final_time,
                "Site": site_val,
                "Sport": sport_val,
                "Match": match_val,
                "Bet": bet_val,
                "Cote": cote_val
            })
            
            print(f"Parsed: {final_time} | {match_val} | {cote_val}")

        except Exception as e:
            print(f"Error parsing card: {e}")
            continue

    # 3. EXPORT
    if all_data:
        df = pd.DataFrame(all_data)
        df = df[["Time", "Site", "Sport", "Match", "Bet", "Cote"]]
        
        df.to_excel(EXCEL_FILENAME, index=False)
        print(f"\n[SUCCESS] Saved {len(all_data)} rows to {EXCEL_FILENAME}")
    else:
        print("\n[WARNING] No data found. Verify class names or site content.")

if __name__ == "__main__":
    main()