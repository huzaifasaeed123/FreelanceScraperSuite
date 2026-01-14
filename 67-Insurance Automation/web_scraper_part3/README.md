# Insurance Comparator - Morocco

A comprehensive web application to compare auto insurance quotes from three major Moroccan insurers: **AXA**, **MAMDA-MCMA**, and **RMA Assurance**.

## Features

- **Real-time comparison** from 3 insurance providers
- **6-month and 12-month pricing** toggle
- **Complete guarantee details** for each plan
- **Selectable options** (e.g., Bris de glace coverage amounts for MCMA)
- **Best price highlighting** 
- **Database storage** of all requests and responses
- **Easy to extend** with new scrapers

## Project Structure

```
insurance_comparator/
├── app.py                      # Flask web server
├── comparison_service.py       # Aggregation service
├── requirements.txt            # Python dependencies
├── insurance_data.db           # SQLite database (auto-created)
├── database/
│   ├── __init__.py
│   └── models.py               # Database models and schema
├── scrapers/
│   ├── __init__.py             # Scraper registry
│   ├── base.py                 # Base classes (InsurancePlan, Guarantee, etc.)
│   ├── axa_scraper.py          # AXA Morocco scraper
│   ├── mcma_scraper.py         # MAMDA-MCMA scraper
│   └── rma_scraper.py          # RMA Assurance scraper
└── static/
    └── index.html              # Frontend (Tailwind CSS)
```

## Database Schema

### 4 SQL Tables:

1. **user_requests** - Stores user input parameters
   - id, valeur_neuf, valeur_venale, timestamp, ip_address, user_agent, status

2. **provider_responses** - Raw API responses from each provider
   - id, request_id, provider_name, provider_code, raw_response, fetch_time, status

3. **insurance_plans** - Individual plan details
   - id, response_id, provider_name, plan_name, annual/semi-annual pricing, fees, etc.

4. **plan_guarantees** - Guarantees/coverages for each plan
   - id, plan_id, guarantee_name, capital, franchise, options, etc.

## Installation & Running

```bash
cd insurance_comparator
pip install -r requirements.txt
python app.py
```

Open http://localhost:5000

## API Endpoints

### POST `/api/compare`
```json
{
    "valeur_neuf": 250000,
    "valeur_venale": 180000
}
```

### GET `/api/health`
Health check with available providers.

### GET `/api/history`
Recent request history from database.

## Adding New Scrapers

1. Create `scrapers/new_provider_scraper.py`:

```python
from .base import BaseScraper, InsurancePlan, Guarantee

class NewProviderScraper(BaseScraper):
    PROVIDER_NAME = "New Provider"
    PROVIDER_CODE = "newprov"
    PROVIDER_COLOR = "#FF0000"
    
    def fetch_quotes(self, params):
        # Your API logic here
        pass
    
    def _parse_response(self, data):
        # Parse response into InsurancePlan objects
        pass
```

2. Register in `scrapers/__init__.py`:
```python
from .new_provider_scraper import NewProviderScraper

SCRAPER_REGISTRY = {
    'axa': AXAScraper,
    'mcma': MCMAScraper,
    'rma': RMAScraper,
    'newprov': NewProviderScraper,  # Add here
}
```

That's it! The new scraper will automatically be included.

## Data Structures

### InsurancePlan
- Provider info (name, code)
- Annual pricing (prime_net, taxes, prime_total, cnpac, accessoires)
- Semi-annual pricing
- Guarantees list
- Selectable fields (for options like coverage amounts)
- Display properties (color, is_promoted, is_eligible)

### Guarantee
- name, code, description
- capital, franchise, prime_annual
- is_included, is_obligatory, is_optional
- options (for selectable guarantees)

## Notes

- Scrapers use hardcoded values for driver info, dates, etc.
- Only `valeur_neuf` and `valeur_venale` are dynamic
- API calls run in parallel for faster results
- Individual provider failures don't break the comparison
