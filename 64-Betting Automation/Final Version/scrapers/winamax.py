"""
Scraper for Winamax
Uses Selenium for dynamic content
"""

import time
from datetime import datetime, timedelta
import re


import undetected_chromedriver as uc
from bs4 import BeautifulSoup




URL = "https://www.winamax.fr/paris-sportifs/sports/100000"


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
        time_match = re.search(r'(\d{1,2})[:h](\d{2})', clean_text)
        
        if time_match:
            val1, val2 = map(int, time_match.groups())
            
            if val1 > 23:
                # Treat as Countdown
                target_date = now + timedelta(minutes=val1, seconds=val2)
            else:
                try:
                    target_date = target_date.replace(hour=val1, minute=val2, second=0)
                except ValueError:
                    target_date = now + timedelta(minutes=val1, seconds=val2)

        return target_date.strftime("%d/%m %H:%M")

    except Exception as e:
        return time_text


def scrape_winamax():
    """Main scraper function for Winamax"""

    options = uc.ChromeOptions()
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--start-maximized")
    # options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")

    print("[WINAMAX] Launching Chrome...")
    driver = None

    try:
        driver = uc.Chrome(options=options)
        print(f"[WINAMAX] Opening {URL}...")
        driver.get(URL)

        print("[WINAMAX] Waiting for content...")
        time.sleep(10)

        html = driver.page_source
        print("[WINAMAX] HTML captured.")

    except Exception as e:
        print(f"[WINAMAX] Browser error: {e}")
        return []
    finally:
        if driver:
            driver.quit()

    # Parse HTML
    soup = BeautifulSoup(html, "html.parser")
    cards = soup.find_all("div", class_="sc-iPRpaO xNyLa")

    print(f"[WINAMAX] Found {len(cards)} betting cards.")

    all_data = []

    for card in cards:
        try:
            # Time extraction
            time_el = card.find("div", class_="sc-gsHvIN iuOOoY")
            if not time_el:
                time_el = card.find("div", class_="sc-eHayKN cyqWGm")
            if not time_el:
                time_el = card.find("div", attrs={"data-testid": "boosted-odds-countdown"})

            raw_time = time_el.get_text(strip=True) if time_el else ""
            final_time = parse_winamax_time(raw_time)

            # Match extraction
            match_el = card.find("div", class_="sc-fFdenn cCsdVR")
            match_val = match_el.get_text(strip=True) if match_el else "Unknown"

            # Bet extraction
            bet_el = card.find("div", class_="sc-kMEpbU jAcTe")
            bet_val = bet_el.get_text(strip=True) if bet_el else "Unknown"

            # Odds extraction
            odd_el = card.find("span", class_="sc-jvicrE oAOiE")
            if odd_el:
                cote_val = odd_el.get_text(strip=True).replace(",", ".")
            else:
                cote_val = "0"

            all_data.append({
                "Time": final_time,
                "Site": "Winamax",
                "Sport": "Football",
                "Match": match_val,
                "Bet": bet_val,
                "Cote": cote_val
            })

        except Exception as e:
            continue

    print(f"[WINAMAX] Scraped {len(all_data)} rows")
    return all_data


if __name__ == "__main__":
    data = scrape_winamax()
    for row in data[:5]:
        print(row)
