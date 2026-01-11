# Insurance Comparator - Morocco

A web application to compare auto insurance quotes from three major Moroccan insurers: **AXA**, **MAMDA-MCMA**, and **RMA Assurance**.

## 🏗️ Project Structure

```
insurance_comparator/
├── app.py                    # Flask web server
├── comparison_service.py     # Aggregation service for all scrapers
├── requirements.txt          # Python dependencies
├── README.md
├── scrapers/
│   ├── __init__.py          # Package exports
│   ├── base.py              # Base scraper class & InsurancePlan dataclass
│   ├── axa_scraper.py       # AXA Morocco API scraper
│   ├── mcma_scraper.py      # MAMDA-MCMA API scraper
│   └── rma_scraper.py       # RMA Assurance API scraper
└── static/
    └── index.html           # Frontend with Tailwind CSS
```

## 🚀 Installation & Running

### 1. Install Dependencies

```bash
cd insurance_comparator
pip install -r requirements.txt
```

### 2. Run the Server

```bash
python app.py
```

The server will start at `http://localhost:5000`

### 3. Open the Application

Open your browser and navigate to `http://localhost:5000`

## 📝 API Endpoints

### POST `/api/compare`

Compare insurance quotes from all providers.

**Request Body:**
```json
{
    "valeur_neuf": 250000,
    "valeur_venale": 180000
}
```

**Response:**
```json
{
    "success": true,
    "params": {
        "valeur_neuf": 250000,
        "valeur_venale": 180000
    },
    "providers": [
        {
            "name": "AXA Assurance",
            "color": "#00008F",
            "logo": "...",
            "plans": [...],
            "plan_count": 4,
            "fetch_time": 1.23
        },
        ...
    ],
    "summary": {
        "total_plans": 10,
        "total_providers": 3,
        "total_fetch_time": 2.5,
        "cheapest_plan": {...},
        "price_range": {
            "min": 3044.42,
            "max": 6963.20
        }
    }
}
```

### GET `/api/health`

Health check endpoint.

## 🔧 Architecture

### Scrapers

Each scraper inherits from `BaseScraper` and implements:
- `fetch_quotes(params)`: Fetches quotes from the provider API
- `_parse_response(data)`: Parses API response into `InsurancePlan` objects

### InsurancePlan Dataclass

Standardized representation of an insurance plan:
- `provider`: Provider name
- `plan_name`: Name of the plan
- `annual_premium`: Net annual premium (HT)
- `taxes`: Total taxes
- `total_price`: Total annual cost (TTC)
- `guarantees`: List of included guarantees
- `color`: Display color
- `is_promoted`: Whether the plan is promoted/recommended
- `extra_info`: Additional provider-specific data

### Comparison Service

The `ComparisonService` class:
1. Runs all scrapers in parallel using ThreadPoolExecutor
2. Aggregates results from all providers
3. Calculates summary statistics (cheapest, most expensive, etc.)

## 🎨 Frontend Features

- **Modern Design**: Built with Tailwind CSS
- **Responsive**: Works on mobile, tablet, and desktop
- **Real-time Loading**: Skeleton loaders during API calls
- **Quick Presets**: Pre-filled values for common vehicle types
- **Visual Comparison**: Color-coded cards for each provider
- **Best Price Highlight**: Automatic highlighting of the cheapest plan

## 📌 Notes

- The scrapers use hardcoded values for most fields (driver info, dates, etc.)
- Only `valeur_neuf` and `valeur_venale` are passed as dynamic parameters
- API responses are fetched in parallel for faster results
- Error handling is implemented for individual provider failures
