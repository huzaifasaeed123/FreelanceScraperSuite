"""
Scraper for Betsson
Uses Selenium for dynamic content
"""

import time
from datetime import datetime, timedelta
import re


import undetected_chromedriver as uc
from bs4 import BeautifulSoup




URL = "https://betsson.fr/fr"


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
            date_str = date_text
            
        return f"{date_str} {time_text}"
    except Exception:
        return f"{date_text} {time_text}"


def scrape_betsson():
    """Main scraper function for Betsson"""

    options = uc.ChromeOptions()
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--start-maximized")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")

    print(f"[BETSSON] Launching Chrome...")
    driver = None
    
    try:
        driver = uc.Chrome(options=options)
        print(f"[BETSSON] Opening {URL}...")
        driver.get(URL)

        print("[BETSSON] Waiting for content...")
        time.sleep(30) 
        
        driver.execute_script("window.scrollTo(0, 300);")
        time.sleep(10)

        html = driver.page_source
        print("[BETSSON] HTML captured.")

    except Exception as e:
        print(f"[BETSSON] Browser error: {e}")
        return []
    finally:
        if driver:
            driver.quit()

    # Parse HTML
    soup = BeautifulSoup(html, "html.parser")
    cards = soup.find_all("div", class_="boostedOddsGameCard")
    
    print(f"[BETSSON] Found {len(cards)} potential betting cards.")

    all_data = []

    for card in cards:
        try:
            if not card.find("div", class_="betEventInfo"):
                continue

            # Match extraction
            home_team = card.find("div", class_="exhibitionHome")
            away_team = card.find("div", class_="exhibitionAway")
            
            if home_team and away_team:
                match_val = f"{home_team.get_text(strip=True)} - {away_team.get_text(strip=True)}"
            else:
                match_val = "Unknown"

            # Time extraction
            date_div = card.find("div", class_="exhibitionDate")
            time_div = card.find("div", class_="exhibitionTime")
            
            raw_date = date_div.get_text(strip=True) if date_div else ""
            raw_time = time_div.get_text(strip=True) if time_div else ""
            final_time = parse_betsson_time(raw_date, raw_time)

            # Bet extraction
            market_div = card.find("div", class_="liveMarketName")
            bet_val = market_div.get_text(strip=True) if market_div else "Unknown"

            # Odds extraction
            cote_val = "0"
            all_odd_containers = card.find_all("div", class_="betOddInfoContainer")
            for oc in all_odd_containers:
                if "isBoosted" in oc.get("class", []) or oc.find_parent(class_="isBoosted"):
                    val_div = oc.find("div", class_="betOddValue")
                    if val_div:
                        cote_val = val_div.get_text(strip=True).replace(",", ".")
                    break

            # Sport extraction
            sport_el = card.find("span", class_="parentName")
            sport_val = sport_el.get_text(strip=True) if sport_el else "Football"

            all_data.append({
                "Time": final_time,
                "Site": "Betsson",
                "Sport": sport_val,
                "Match": match_val,
                "Bet": bet_val,
                "Cote": cote_val
            })

        except Exception as e:
            continue

    print(f"[BETSSON] Scraped {len(all_data)} rows")
    return all_data


if __name__ == "__main__":
    data = scrape_betsson()
    for row in data[:5]:
        print(row)
