"""
Main Controller for Betting Odds Scraper
Manages all 8 scrapers, Google Sheets updates, Telegram notifications
"""

import json
import time
import hashlib
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
    scrape_betsson, scrape_parionssport, scrape_pmu,
    scrape_unibet, scrape_winamax
)


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
    "parionssport": scrape_parionssport,
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
    """Format a NEW bet message with green icon"""
    return (
        # f"<b>NEW</b>\n"
        f"🟢 {bet['Site'].upper()}\n\n"
        f"{bet['Match']}\n\n"
        f"{bet['Bet']}\n\n"
        f"{bet['Cote']}"
    )


def format_updated_bet_message(bet, old_cote, new_cote):
    """Format an UPDATED bet message with orange icon showing old→new"""
    return (
        # f"<b>UPDATED</b>\n"
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
    
    for bet in new_bets:
        message = format_new_bet_message(bet)
        send_telegram_message(config, message)
        time.sleep(2)  # Small delay to avoid rate limit
    
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
        time.sleep(0.3)  # Small delay to avoid rate limit
    
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


def update_google_sheet(config, all_data):
    """
    Update Google Sheet with all betting data.
    Format: DATE | SITE | SPORT | MATCH | BET | COTE
    """
    try:
        service = get_sheets_service(config)
        if not service:
            return False
        
        spreadsheet_id = config["google_sheets"]["spreadsheet_id"]
        sheet_name = config["google_sheets"].get("worksheet_name", "BOT")
        
        # Clear existing data (keep header)
        clear_sheet_data(service, spreadsheet_id, sheet_name)
        
        # Prepare all rows
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
        
        # Append all rows at once
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
    new_data = run_all_scrapers(config)
    
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
    
    # Send Telegram notifications
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
    
    # First run
    is_first_run = True
    
    while True:
        try:
            run_scraping_cycle(config, is_first_run)
            is_first_run = False
            
            print(f"\n[INFO] Sleeping for {interval_minutes} minutes...")
            print(f"[INFO] Next run at: {datetime.now().strftime('%H:%M:%S')} + {interval_minutes} min")
            
            time.sleep(interval_minutes * 60)
            
        except KeyboardInterrupt:
            print("\n[INFO] Scraper stopped by user")
            break
        except Exception as e:
            print(f"\n[ERROR] Cycle failed: {e}")
            print(f"[INFO] Retrying in 1 minute...")
            time.sleep(60)


if __name__ == "__main__":
    main()