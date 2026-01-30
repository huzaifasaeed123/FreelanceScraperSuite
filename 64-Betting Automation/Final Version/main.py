"""
Main Controller for Betting Odds Scraper
Manages all 8 scrapers, Google Sheets updates, Telegram notifications
"""

import json
import time
import hashlib
import re
from datetime import datetime
from pathlib import Path

# Google Sheets - using googleapiclient (quota safe)
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

# Telegram
import requests as http_requests

# Import scrapers
from scrapers import (
    scrape_netbet, scrape_genybet, scrape_olybet,
    scrape_betsson, scrape_psel, scrape_pmu,
    scrape_unibet, scrape_winamax
)

# Import browser manager for UC scrapers (betsson, winamax)
from scrapers.browser_manager import browser_manager


# -------------------------------------------------------------------------
# CONFIGURATION
# -------------------------------------------------------------------------
CONFIG_FILE = "config.json"
DATA_FILE = "betting_data.json"

# Map scraper names to functions
SCRAPER_MAP = {
    "netbet": scrape_netbet,
    "genybet": scrape_genybet,
    "olybet": scrape_olybet,
    "betsson": scrape_betsson,
    "psel": scrape_psel,
    "pmu": scrape_pmu,
    "unibet": scrape_unibet,
    "winamax": scrape_winamax
}


def load_config():
    """Load configuration from JSON file"""
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def load_previous_data():
    """Load previous scraping data from JSON file"""
    if Path(DATA_FILE).exists():
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_data(data):
    """Save scraping data to JSON file"""
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def generate_row_id(row):
    """Generate unique ID for a betting row"""
    unique_str = f"{row['Site']}|{row['Match']}|{row['Bet']}|{row['Cote']}"
    return hashlib.md5(unique_str.encode()).hexdigest()[:12]


# -------------------------------------------------------------------------
# DATA CLEANING FUNCTIONS
# -------------------------------------------------------------------------
def clean_match_value(text):
    """
    Clean match value by replacing 'v' or 'vs' with '-'

    Examples:
    - "Real Sociedad vs FC Barcelone" -> "Real Sociedad - FC Barcelone"
    - "Team A v Team B" -> "Team A - Team B"
    """
    if not text:
        return ""

    # Replace ' vs ' or ' v ' with ' - ' (case insensitive, with spaces)
    cleaned = re.sub(r'\s+vs\s+', ' - ', text, flags=re.IGNORECASE)
    cleaned = re.sub(r'\s+v\s+', ' - ', cleaned, flags=re.IGNORECASE)

    return cleaned.strip()


def clean_cote_value(cote):
    """
    Clean cote/odds value:
    - Ensure 2 decimal places
    - Use comma instead of period (e.g., 2,50 instead of 2.50)

    Examples:
    - "2.5" -> "2,50"
    - "2.50" -> "2,50"
    - "3,8" -> "3,80"
    - "2,50" -> "2,50" (unchanged)
    """
    if not cote:
        return "0,00"

    try:
        # Convert to string if not already
        cote_str = str(cote)

        # Replace comma with period for parsing
        cote_str = cote_str.replace(',', '.')

        # Convert to float and format to 2 decimal places
        cote_float = float(cote_str)

        # Format with 2 decimals and replace period with comma
        formatted = "{:.2f}".format(cote_float).replace('.', ',')

        return formatted
    except (ValueError, TypeError):
        # If conversion fails, return original with comma
        return str(cote).replace('.', ',')


def clean_bet_description(text, site_name=""):
    """
    Clean bet description by removing unnecessary details:
    - For PSEL and Betsson ONLY: Removes ALL parentheses content throughout the text
    - For Winamax and Unibet: NO filtering (returns text as-is)
    - For other sites: NO parentheses filtering
    - Removes extra whitespace for all sites

    Examples for PSEL/Betsson:
    - "CB - Text (info1) more (info2) end (info3)" -> "CB - Text more end"
    - "Buteur(s) en 1ere (remboursé) (Max 25€)" -> "Buteur en 1ere"

    Examples for Winamax/Unibet:
    - "Any text (with info)" -> "Any text (with info)" (unchanged)
    """
    if not text:
        return ""

    cleaned = text

    # Apply parentheses removal ONLY for PSEL and Betsson (ALL occurrences)
    if site_name.lower() in ["psel", "betsson"]:
        # Remove ALL parentheses content throughout the string
        cleaned = re.sub(r'\s*\([^)]*\)', '', cleaned)

    # Remove any double spaces that might result from removal
    cleaned = re.sub(r'\s+', ' ', cleaned)

    # Strip leading/trailing whitespace
    cleaned = cleaned.strip()

    # Remove trailing " -" or "- " that might be left after removing parentheses (PSEL/Betsson only)
    if site_name.lower() in ["psel", "betsson"]:
        cleaned = re.sub(r'\s*-\s*$', '', cleaned)
        cleaned = re.sub(r'^\s*-\s*', '', cleaned)

    return cleaned


def clean_data(data):
    """
    Main cleaning function that processes all scraped data for all sites.
    Applies the following transformations:

    1. Match: Replace 'v' or 'vs' with '-'
    2. Cote: Format to 2 decimal places with comma (e.g., 2,50)
    3. Bet: Site-specific filtering
       - PSEL/Betsson: Remove parentheses at the end only
       - Winamax/Unibet: NO filtering (keep entire bet text)
       - Others: NO parentheses filtering

    Args:
        data: Dictionary with site names as keys and list of bet dicts as values

    Returns:
        Dictionary with all cleaned data
    """
    cleaned_data = {}

    for site_name, bets in data.items():
        cleaned_bets = []

        for bet in bets:
            cleaned_bet = bet.copy()

            # Clean Match value: replace 'v' or 'vs' with '-'
            if 'Match' in cleaned_bet:
                cleaned_bet['Match'] = clean_match_value(cleaned_bet['Match'])

            # Clean Cote value: 2 decimals with comma
            if 'Cote' in cleaned_bet:
                cleaned_bet['Cote'] = clean_cote_value(cleaned_bet['Cote'])

            # Clean Bet description: site-specific filtering
            if 'Bet' in cleaned_bet:
                cleaned_bet['Bet'] = clean_bet_description(cleaned_bet['Bet'], site_name)

            cleaned_bets.append(cleaned_bet)

        cleaned_data[site_name] = cleaned_bets

    return cleaned_data


def process_bet_data(bet, site_name=""):
    """
    Process a single bet dictionary and clean its description.
    Returns a new dictionary with cleaned 'Bet' field.
    (Legacy function - kept for backward compatibility)
    """
    processed = bet.copy()
    if 'Bet' in processed:
        processed['Bet'] = clean_bet_description(processed['Bet'], site_name)
    return processed


def process_all_bets(data):
    """
    Process all bets from all sites and clean their descriptions.
    Returns a new dictionary with all cleaned data.
    (Legacy function - now calls clean_data for full cleaning)
    """
    return clean_data(data)


# -------------------------------------------------------------------------
# TELEGRAM FUNCTIONS
# -------------------------------------------------------------------------
def send_telegram_message(config, message):
    """Send message to Telegram channel"""
    try:
        bot_token = config["telegram"]["bot_token"]
        channel_id = config["telegram"]["channel_id"]
        
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        payload = {
            "chat_id": channel_id,
            "text": message,
            "parse_mode": "HTML"
        }
        
        response = http_requests.post(url, json=payload, timeout=10)
        if response.status_code == 200:
            return True
        else:
            print(f"[TELEGRAM] Failed: {response.text}")
            return False
    except Exception as e:
        print(f"[TELEGRAM] Error: {e}")
        return False


def format_new_bet_message(bet):
    """Format a NEW bet message with green icon - ONE MESSAGE PER BET"""
    return (
        f"🟢 {bet['Site'].upper()}\n\n"
        f"{bet['Match']}\n\n"
        f"{bet['Bet']}\n\n"
        f"{bet['Cote']}"
    )


def format_updated_bet_message(bet, old_cote, new_cote):
    """Format an UPDATED bet message with orange icon showing old→new - ONE MESSAGE PER BET"""
    return (
        f"🟠 {bet['Site'].upper()}\n\n"
        f"{bet['Match']}\n\n"
        f"{bet['Bet']}\n\n"
        f"{old_cote} → {new_cote}"
    )


def send_new_bet_notifications(config, new_bets):
    """Send one Telegram message per NEW bet (green icon)"""
    if not new_bets:
        return
    
    print(f"[TELEGRAM] Sending {len(new_bets)} NEW bet notifications...")
    
    for i, bet in enumerate(new_bets, start=1):
        message = format_new_bet_message(bet)
        send_telegram_message(config, message)


        # Dynamic delay
        if i % 15 == 0:
            time.sleep(10)
        else:
            time.sleep(2)  # remaining messages # Small delay to avoid rate limit
    
    print(f"[TELEGRAM] Sent {len(new_bets)} new bet messages")


def send_updated_bet_notifications(config, updated_bets):
    """Send one Telegram message per UPDATED bet (orange icon with old→new)"""
    if not updated_bets:
        return
    
    print(f"[TELEGRAM] Sending {len(updated_bets)} UPDATED bet notifications...")
    
    for item in updated_bets:
        bet = item["bet"]
        old_cote = item["old_cote"]
        new_cote = item["new_cote"]
        message = format_updated_bet_message(bet, old_cote, new_cote)
        send_telegram_message(config, message)
        time.sleep(1)  # Small delay to avoid rate limit
    
    print(f"[TELEGRAM] Sent {len(updated_bets)} updated bet messages")


# -------------------------------------------------------------------------
# GOOGLE SHEETS FUNCTIONS
# -------------------------------------------------------------------------
def get_sheets_service(config):
    """Create Google Sheets service using googleapiclient"""
    try:
        creds_dict = config["google_sheets"]["credentials"]
        scopes = ["https://www.googleapis.com/auth/spreadsheets"]
        
        credentials = Credentials.from_service_account_info(creds_dict, scopes=scopes)
        service = build("sheets", "v4", credentials=credentials)
        
        return service
    except Exception as e:
        print(f"[GSHEETS] Auth error: {e}")
        return None


def clear_sheet_data(service, spreadsheet_id, sheet_name):
    """Clear all data from sheet except header row"""
    try:
        # Clear from row 2 onwards (keep header)
        range_to_clear = f"{sheet_name}!A2:F1000"
        service.spreadsheets().values().clear(
            spreadsheetId=spreadsheet_id,
            range=range_to_clear
        ).execute()
        print(f"[GSHEETS] Cleared data from {sheet_name}")
        return True
    except Exception as e:
        print(f"[GSHEETS] Clear error: {e}")
        return False


def append_to_sheet(service, spreadsheet_id, sheet_name, rows):
    """Append rows to Google Sheet using append method (quota safe)"""
    try:
        if not rows:
            return True
        
        body = {"values": rows}
        
        service.spreadsheets().values().append(
            spreadsheetId=spreadsheet_id,
            range=f"{sheet_name}!A1",
            valueInputOption="RAW",
            insertDataOption="INSERT_ROWS",
            body=body
        ).execute()
        
        print(f"[GSHEETS] Appended {len(rows)} rows to {sheet_name}")
        return True
    except Exception as e:
        print(f"[GSHEETS] Append error: {e}")
        return False

def update_google_sheet(config, all_data, changes):
    """
    Update Google Sheet with all betting data ONLY if there are changes.
    Format: DATE (with refresh timestamp) | SITE | SPORT | MATCH | BET | COTE
    """
    try:
        # Only update sheet if there are any changes
        if not changes["new"] and not changes["updated"] and not changes["deleted"]:
            print("[GSHEETS] No changes detected. Sheet not updated.")
            return False

        service = get_sheets_service(config)
        if not service:
            return False

        spreadsheet_id = config["google_sheets"]["spreadsheet_id"]
        sheet_name = config["google_sheets"].get("worksheet_name", "BOT")

        # 1️⃣ Clear entire sheet
        service.spreadsheets().values().clear(
            spreadsheetId=spreadsheet_id,
            range=f"{sheet_name}!A1:Z10000"
        ).execute()
        print(f"[GSHEETS] Sheet fully cleared")

        # 2️⃣ Insert headers with refresh timestamp
        refresh_time = datetime.now().strftime("%d/%m %H:%M:%S")
        headers = [[f"DATE({refresh_time})", "SITE", "SPORT", "MATCH", "BET", "COTE"]]

        service.spreadsheets().values().update(
            spreadsheetId=spreadsheet_id,
            range=f"{sheet_name}!A1",
            valueInputOption="RAW",
            body={"values": headers}
        ).execute()
        print(f"[GSHEETS] Headers inserted with refresh timestamp: {refresh_time}")

        # 3️⃣ Prepare all rows
        rows = []
        for site_name, bets in all_data.items():
            for bet in bets:
                row = [
                    bet.get("Time", ""),      # DATE
                    bet.get("Site", ""),      # SITE
                    bet.get("Sport", ""),     # SPORT
                    bet.get("Match", ""),     # MATCH
                    bet.get("Bet", ""),       # BET
                    bet.get("Cote", "")       # COTE
                ]
                rows.append(row)

        # 4️⃣ Append rows under headers
        if rows:
            append_to_sheet(service, spreadsheet_id, sheet_name, rows)
            print(f"[GSHEETS] Total {len(rows)} rows updated")

        return True

    except Exception as e:
        print(f"[GSHEETS] Error: {e}")
        return False


# -------------------------------------------------------------------------
# DATA COMPARISON
# -------------------------------------------------------------------------
def compare_data(old_data, new_data):
    """
    Compare old and new data to find:
    - New bets (added)
    - Updated bets (odds changed)
    - Deleted bets (removed)
    """
    changes = {
        "new": [],
        "updated": [],
        "deleted": []
    }
    
    for site_name, new_bets in new_data.items():
        old_bets = old_data.get(site_name, [])
        
        # Create lookup dictionaries
        old_lookup = {}
        for bet in old_bets:
            key = f"{bet['Match']}|{bet['Bet']}"
            old_lookup[key] = bet
        
        new_lookup = {}
        for bet in new_bets:
            key = f"{bet['Match']}|{bet['Bet']}"
            new_lookup[key] = bet
        
        # Find new and updated
        for key, bet in new_lookup.items():
            if key not in old_lookup:
                changes["new"].append(bet)
            elif bet.get("Cote") != old_lookup[key].get("Cote"):
                changes["updated"].append({
                    "bet": bet,
                    "old_cote": old_lookup[key].get("Cote"),
                    "new_cote": bet.get("Cote")
                })
        
        # Find deleted
        for key, bet in old_lookup.items():
            if key not in new_lookup:
                changes["deleted"].append(bet)
    
    return changes


# -------------------------------------------------------------------------
# MAIN SCRAPING LOGIC
# -------------------------------------------------------------------------
def run_all_scrapers(config):
    """Run all enabled scrapers and return combined data"""
    all_data = {}
    
    for scraper_name, scraper_func in SCRAPER_MAP.items():
        scraper_config = config["scrapers"].get(scraper_name, {})
        
        if not scraper_config.get("enabled", True):
            print(f"[{scraper_name.upper()}] Disabled, skipping...")
            continue
        
        try:
            print(f"\n{'='*50}")
            print(f"Running {scraper_name.upper()} scraper...")
            print('='*50)
            
            data = scraper_func()
            all_data[scraper_name] = data
            
            print(f"[{scraper_name.upper()}] Got {len(data)} bets")
            
        except Exception as e:
            print(f"[{scraper_name.upper()}] Error: {e}")
            all_data[scraper_name] = []
    
    return all_data


def run_scraping_cycle(config, is_first_run=False):
    """Run one complete scraping cycle"""
    print(f"\n{'#'*60}")
    print(f"# SCRAPING CYCLE - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print('#'*60)
    
    # Load previous data
    old_data = load_previous_data()
    
    # Run all scrapers
    raw_data = run_all_scrapers(config)
    
    # Clean bet descriptions using the centralized function
    new_data = process_all_bets(raw_data)
    print(f"\n[INFO] Cleaned bet descriptions for all scraped data")
    
    # Compare data
    if is_first_run or not old_data:
        # First run - all data is "new"
        all_new_bets = []
        for site_name, bets in new_data.items():
            all_new_bets.extend(bets)
        
        changes = {"new": all_new_bets, "updated": [], "deleted": []}
        print(f"\n[INFO] First run - {len(all_new_bets)} total bets collected")
    else:
        changes = compare_data(old_data, new_data)
        print(f"\n[INFO] Changes detected:")
        print(f"  - New: {len(changes['new'])}")
        print(f"  - Updated: {len(changes['updated'])}")
        print(f"  - Deleted: {len(changes['deleted'])}")
    
    # Save new data to JSON
    save_data(new_data)
    print(f"[INFO] Data saved to {DATA_FILE}")
    
    # Update Google Sheet
    print("\n[INFO] Updating Google Sheets...")
    update_google_sheet(config, new_data)
    
    # Send Telegram notifications (ONE MESSAGE PER BET)
    # New bets - green icon
    if changes["new"]:
        print(f"\n[INFO] Sending Telegram notifications for {len(changes['new'])} NEW bets...")
        send_new_bet_notifications(config, changes["new"])
    
    # Updated bets - orange icon with old→new
    if changes["updated"]:
        print(f"\n[INFO] Sending Telegram notifications for {len(changes['updated'])} UPDATED bets...")
        send_updated_bet_notifications(config, changes["updated"])
    
    # Summary
    total_bets = sum(len(bets) for bets in new_data.values())
    print(f"\n[SUMMARY] Total bets across all sites: {total_bets}")
    
    return new_data


def main():
    """Main entry point"""
    print("="*60)
    print("BETTING ODDS SCRAPER - Starting...")
    print("="*60)

    # Load config
    config = load_config()
    interval_minutes = config.get("scrape_interval_minutes", 10)

    print(f"[CONFIG] Scrape interval: {interval_minutes} minutes")
    print(f"[CONFIG] Enabled scrapers: {[k for k, v in config['scrapers'].items() if v.get('enabled', True)]}")

    # Check if UC scrapers (betsson, winamax) are enabled
    uc_scrapers_enabled = (
        config["scrapers"].get("betsson", {}).get("enabled", True) or
        config["scrapers"].get("winamax", {}).get("enabled", True)
    )

    # Initialize shared browser if UC scrapers are enabled
    if uc_scrapers_enabled:
        print("\n[BROWSER] Initializing shared Chrome instance for UC scrapers...")
        print("[BROWSER] This browser will stay open and be reused across all scraping cycles")
        driver = browser_manager.get_driver()
        if driver:
            print("[BROWSER] Chrome ready - will use tabs for betsson/winamax scrapers")
        else:
            print("[BROWSER] Warning: Failed to initialize Chrome, UC scrapers may fail")

    # First run
    is_first_run = True

    try:
        while True:
            try:
                run_scraping_cycle(config, is_first_run)
                is_first_run = False

                print(f"\n[INFO] Sleeping for {interval_minutes} minutes...")
                print(f"[INFO] Next run at: {datetime.now().strftime('%H:%M:%S')} + {interval_minutes} min")

                time.sleep(interval_minutes * 60)

            except KeyboardInterrupt:
                raise  # Re-raise to be caught by outer try
            except Exception as e:
                print(f"\n[ERROR] Cycle failed: {e}")
                print(f"[INFO] Retrying in 1 minute...")
                time.sleep(60)

    except KeyboardInterrupt:
        print("\n[INFO] Scraper stopped by user")

    finally:
        # Cleanup: Close browser on exit (optional - comment out if you want browser to stay open)
        # browser_manager.shutdown()
        print("[INFO] Exiting... (Browser stays open for next run)")


if __name__ == "__main__":
    main()