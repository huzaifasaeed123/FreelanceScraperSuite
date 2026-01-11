# Betting Odds Scraper

A unified scraper for 8 French betting websites with Google Sheets integration and Telegram notifications.

## Supported Websites

1. **Netbet** - API scraper
2. **Genybet** - API scraper
3. **Olybet** - API scraper
4. **Betsson** - Selenium scraper
5. **ParionsSport** - API scraper
6. **PMU** - API scraper
7. **Unibet** - API scraper
8. **Winamax** - Selenium scraper

## Installation

```bash
# Install dependencies
pip install -r requirements.txt

# For Selenium-based scrapers (Betsson, Winamax), you also need Chrome installed
```

## Configuration

Edit `config.json` to customize:

```json
{
    "scrape_interval_minutes": 10,
    "telegram": {
        "bot_token": "YOUR_BOT_TOKEN",
        "channel_id": "YOUR_CHANNEL_ID"
    },
    "google_sheets": {
        "spreadsheet_name": "Betting_Odds_Data",
        "credentials": { ... }
    },
    "scrapers": {
        "netbet": {"enabled": true},
        "genybet": {"enabled": true},
        ...
    }
}
```

## Usage

### Run the main scraper (continuous)
```bash
python main.py
```

### Run individual scrapers (testing)
```bash
# Test single scraper
python -m scrapers.pmu
python -m scrapers.unibet
python -m scrapers.parionssport
python -m scrapers.netbet_genybet_olybet
```

## Output Format

All scrapers output data in a unified format:

| Field | Description |
|-------|-------------|
| Time | Match/event time (DD/MM HH:MM) |
| Site | Website name |
| Sport | Sport category |
| Match | Match/event name |
| Bet | Bet description |
| Cote | Odds value |

## Data Storage

- **betting_data.json** - Local JSON file with all scraped data
- **Google Sheets** - Cloud spreadsheet with all data + per-site tabs

## Notifications

Telegram notifications are sent when:
- New bets are detected
- First run (all bets are considered new)

## Project Structure

```
betting_scraper/
├── main.py                 # Main controller
├── config.json             # Configuration
├── requirements.txt        # Dependencies
├── betting_data.json       # Local data storage (created on first run)
└── scrapers/
    ├── __init__.py
    ├── netbet_genybet_olybet.py
    ├── betsson.py
    ├── parionssport.py
    ├── pmu.py
    ├── unibet.py
    └── winamax.py
```

## Troubleshooting

### Selenium scrapers not working
- Ensure Chrome/Chromium is installed
- Try running without headless mode for debugging

### API scrapers failing
- Check if the website structure has changed
- Verify headers and cookies are up to date

### Google Sheets errors
- Verify service account credentials
- Ensure spreadsheet permissions are correct
