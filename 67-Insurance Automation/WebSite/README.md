# 🚗 Morocco Car Insurance Comparison Platform

**Live Website:** [https://freelancescrapersuite-production.up.railway.app/](https://freelancescrapersuite-production.up.railway.app/)

---

## 📋 Table of Contents

1. [For Insurance Brokers & Clients](#-for-insurance-brokers--clients)
2. [For Technical Users & Developers](#-for-technical-users--developers)

---

# 👥 For Insurance Brokers & Clients

## What is this platform?

This is a **Car Insurance Comparison Platform** designed specifically for the Moroccan insurance market. Think of it as a one-stop solution where you can get insurance quotes from **multiple Moroccan insurance companies** in just a few minutes, all in one place.

Instead of visiting 4-5 different insurance company websites, filling out the same information over and over, and waiting for responses, our platform does all of this automatically for you.

## 🎯 Why use this platform?

### Save Time
- **Before:** 30-45 minutes to get quotes from multiple insurers
- **With our platform:** 2-3 minutes to get all quotes simultaneously

### Compare Easily
- See all insurance offers side-by-side
- Compare prices, coverage, and guarantees in one place
- Identify the best deal instantly

### Professional Reports
- Generate professional PDF comparison reports
- Add your company logo and branding
- Share reports directly with clients

### For Brokers
- Manage multiple client requests efficiently
- Track all quotations in one dashboard
- Export client data to Excel
- Provide faster, more comprehensive service to clients

## 🏢 Supported Insurance Companies

Our platform currently compares quotes from these major Moroccan insurance providers:

1. **AXA Assurance** - Full coverage plans with customizable options
2. **RMA Watanya** - Comprehensive vehicle insurance solutions
3. **MCMA** - Competitive pricing with flexible coverage
4. **Saham Assurance (Sanlam)** - Trusted insurance provider

---

## 📸 Platform Screenshots

### Main Insurance Comparison Form
<!-- Add screenshot of the main form here -->
![Main Form](docs/screenshots/main-form.png)

*Simple form where you enter vehicle and driver details*

---

### Comparison Results Dashboard
<!-- Add screenshot of results page here -->
![Results Dashboard](docs/screenshots/results-page.png)

*All insurance quotes displayed side-by-side for easy comparison*

---

### Professional PDF Reports
<!-- Add screenshot of PDF report here -->
![PDF Report](docs/screenshots/pdf-report.png)

*Generate branded PDF reports for your clients*

---

### Admin Dashboard
<!-- Add screenshot of admin panel here -->
![Admin Panel](docs/screenshots/admin-panel.png)

*Manage users, track submissions, and export data*

---

## 🎬 How It Works (Simple 3-Step Process)

### Step 1: Enter Vehicle Information
Fill out a simple form with:
- Vehicle brand and model (e.g., Renault Clio)
- Year of first registration
- License plate number
- Vehicle value (new and current)
- Number of seats and engine power

### Step 2: Enter Driver Information
Provide basic details:
- Full name
- Date of birth
- Phone number and email
- City
- Driver's license date
- Current insurance provider (optional)

### Step 3: Get Your Quotes
- Click "Compare" button
- Wait 30-60 seconds while we fetch quotes
- View all offers in a clean comparison table
- See prices for both annual and semi-annual payment options
- Generate PDF report with one click

## 💰 What You'll See in Results

For each insurance company, you'll get:

### Basic Information
- Insurance company name and logo
- Package/coverage type (Basic, Optimal, Premium, etc.)
- Response time

### Pricing Details
- **Annual Payment:** Total price for 12-month coverage
- **Semi-Annual Payment:** Total price for 6-month coverage
- Net premium (before taxes)
- Tax amount (16.5%)
- Total amount to pay

### Coverage Details
- Liability coverage (Responsabilité Civile)
- Fire and theft protection
- Glass breakage coverage
- Collision damage options
- All-risk coverage options
- Additional guarantees and protections

### Customization Options
For some insurers (like AXA and MCMA), you can:
- Select different coverage levels
- Adjust deductible amounts
- Add or remove optional protections
- See updated prices in real-time

## 🔐 User Roles & Access

### Regular Users (Brokers)
- Submit insurance comparison requests
- View comparison results
- Generate PDF reports
- Customize company logo and branding
- Access personal dashboard

### Admin Users
- All regular user features, plus:
- Create and manage user accounts
- Enable/disable insurance providers
- View all submissions across all users
- Export complete database to Excel
- Generate API keys for integrations

## 📊 Benefits for Your Business

### For Insurance Brokers
1. **Faster Service:** Respond to client requests in minutes instead of hours
2. **More Quotes:** Present clients with 4+ options instead of 1-2
3. **Professional Image:** Deliver branded, professional comparison reports
4. **Better Commissions:** Help clients find the best deal, increasing satisfaction and referrals
5. **Track Everything:** All client requests saved in one place

### For Insurance Agencies
1. **Centralized Platform:** All agents use the same system
2. **Data Management:** Export all submissions for analysis
3. **Quality Control:** Monitor what quotes agents are providing
4. **Reporting:** Track which insurance companies are most competitive

### For Direct Clients
1. **Save Money:** See all options and choose the cheapest
2. **Transparency:** Compare coverage details side-by-side
3. **Convenience:** Get all quotes in one place, one time
4. **Fast:** Get quotes in minutes, not days

## 📞 Getting Started

### Access the Platform
Visit: [https://freelancescrapersuite-production.up.railway.app/](https://freelancescrapersuite-production.up.railway.app/)

### Login Credentials
Contact your administrator to get:
- Your username (email address)
- Your password
- Access level (user or admin)

### First Time Setup
1. Log in with your credentials
2. Go to Settings page
3. Upload your company logo (optional)
4. Add your company name and footer text
5. Start comparing insurance quotes!

## ❓ Common Questions

**Q: How accurate are the quotes?**
A: The quotes are fetched directly from insurance company APIs and websites in real-time. They are as accurate as what you would get from the insurance company directly.

**Q: How long does it take to get quotes?**
A: Typically 30-60 seconds. Some insurance companies may take longer depending on their server response times.

**Q: Can I use this for any vehicle?**
A: Yes, the platform supports all vehicle types registered in Morocco with standard license plates.

**Q: What if one insurance company doesn't respond?**
A: The platform will show quotes from available providers. If one fails, you'll still get quotes from the others.

**Q: Can I save quotes for later?**
A: Yes, all your submissions are automatically saved in your dashboard. You can access them anytime.

**Q: Is my client data secure?**
A: Yes, all data is encrypted and stored securely. Only you and administrators can access your submissions.

---

---

# 🛠️ For Technical Users & Developers

## Architecture Overview

This is a **Flask-based web application** with a **MySQL database backend**, designed for production deployment on Railway. The application uses a modern **microservices architecture** with separate scraper modules for each insurance provider.

### Technology Stack

#### Backend
- **Framework:** Flask 3.0+
- **Language:** Python 3.11+
- **Database:** MySQL 8.0+ with connection pooling
- **ORM:** Raw SQL with mysql-connector-python
- **Web Server:** Gunicorn (production)
- **Session Management:** Flask sessions with secure cookies

#### Frontend
- **HTML5** with semantic markup
- **CSS:** Tailwind CSS 3.x
- **JavaScript:** Vanilla JS (ES6+)
- **AJAX:** Fetch API for asynchronous requests

#### Scraping & Automation
- **HTTP Requests:** Python requests library
- **Browser Automation:** Playwright + Camoufox
- **Anti-Detection:** Camoufox with GeoIP spoofing
- **Async Processing:** Python asyncio

#### File Generation
- **PDF:** ReportLab
- **Excel:** OpenPyXL

#### Deployment
- **Container:** Docker
- **Platform:** Railway
- **CI/CD:** Automatic deployment from GitHub

## System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                         Frontend                            │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  │
│  │  Login   │  │  Form    │  │  Results │  │  Admin   │  │
│  │  Page    │  │  Page    │  │  Page    │  │  Panel   │  │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘  │
└─────────────────────────────────────────────────────────────┘
                           ↓ HTTPS
┌─────────────────────────────────────────────────────────────┐
│                    Flask Application                        │
│  ┌──────────────────────────────────────────────────────┐  │
│  │              Authentication Layer                    │  │
│  │  • Session Management  • Password Hashing           │  │
│  │  • Role-Based Access   • API Key Authentication     │  │
│  └──────────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────────┐  │
│  │              API Endpoints                           │  │
│  │  /api/compare  /api/login  /api/admin/*             │  │
│  └──────────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────────┐  │
│  │           Comparison Service                         │  │
│  │  • Request Routing  • Result Aggregation            │  │
│  │  • Error Handling   • Response Formatting           │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│                    Scraper Layer                            │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐      │
│  │   AXA   │  │   RMA   │  │  MCMA   │  │ Sanlam  │      │
│  │ Scraper │  │ Scraper │  │ Scraper │  │ Scraper │      │
│  └─────────┘  └─────────┘  └─────────┘  └─────────┘      │
│       ↓            ↓            ↓            ↓             │
│   API Calls   Playwright   API Calls    API Calls         │
└─────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│                    MySQL Database                           │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  • users              • form_submissions             │  │
│  │  • scraper_results    • user_settings                │  │
│  │  • api_keys           • scraper_settings             │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

## Authentication & Authorization

### Authentication System

#### Session-Based Authentication
- Uses Flask sessions with secure cookies
- Session timeout: 24 hours
- CSRF protection enabled
- Secure flag set in production

#### Password Security
- SHA-256 hashing with salt
- Passwords never stored in plain text
- Password complexity requirements enforced

#### API Key Authentication
- Alternative authentication method for API access
- Keys are randomly generated (32 characters)
- Can be enabled/disabled without deletion
- Usage tracking per key

### Authorization Levels

#### Public Routes
- `/login` - Login page
- `/api/login` - Authentication endpoint
- `/api/health` - Health check

#### Authenticated Routes (Requires Login)
- `/` - Main comparison form
- `/settings` - User settings
- `/api/compare` - Submit comparison request
- `/api/generate-comparison-pdf` - Generate PDF
- `/api/settings` - Manage user settings
- `/api/upload-logo` - Upload company logo

#### Admin Routes (Requires Admin Role)
- `/admin` - Admin dashboard
- `/admin/scrapers` - Scraper management
- `/api/admin/users` - User management
- `/api/admin/create-user` - Create new users
- `/api/admin/delete-user/:id` - Delete users
- `/api/admin/scrapers` - Manage scrapers
- `/api/admin/toggle-scraper` - Enable/disable scrapers
- `/api/admin/api-keys` - API key management
- `/api/admin/export-database` - Export database to Excel

### Role-Based Access Control (RBAC)

```python
# Decorator Examples
@login_required              # Any authenticated user
@admin_required              # Admin users only
@api_key_or_login_required   # API key OR session auth
```

## Admin Panel Features

### User Management
- **Create Users:** Add new broker accounts with email and password
- **Delete Users:** Remove user accounts (except admin)
- **View Users:** List all users with creation dates
- **Role Assignment:** Set users as admin or regular user

### Scraper Management
- **Enable/Disable Scrapers:** Turn providers on/off without code changes
- **View Status:** See which scrapers are active
- **Real-time Control:** Changes take effect immediately

### API Key Management
- **Generate Keys:** Create API keys for external integrations
- **Enable/Disable:** Control key access without deletion
- **View Usage:** Track last used timestamp
- **Description:** Add notes for each key

### Database Export
- **Excel Export:** Download complete database
- **All Tables:** Each table as separate sheet
- **Formatted:** Professional styling with headers
- **Comprehensive:** Includes all submissions and results

### Dashboard Statistics
- Total users count
- Total submissions count
- Active scrapers count
- System health status

## Database Schema

### Core Tables

#### users
Stores user accounts and credentials
```sql
CREATE TABLE users (
    id INT PRIMARY KEY AUTO_INCREMENT,
    name VARCHAR(255) NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    is_admin BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_email (email)
) ENGINE=InnoDB;
```

#### form_submissions
Stores insurance comparison requests
```sql
CREATE TABLE form_submissions (
    id INT PRIMARY KEY AUTO_INCREMENT,
    user_id INT,
    form_data JSON NOT NULL,
    ip_address VARCHAR(45),
    user_agent TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    user_name VARCHAR(255),
    user_email VARCHAR(255),
    FOREIGN KEY (user_id) REFERENCES users(id),
    INDEX idx_user_id (user_id),
    INDEX idx_created_at (created_at)
) ENGINE=InnoDB;
```

#### scraper_results
Stores results from each scraper
```sql
CREATE TABLE scraper_results (
    id INT PRIMARY KEY AUTO_INCREMENT,
    form_submission_id INT,
    scraper_name VARCHAR(50) NOT NULL,
    success BOOLEAN DEFAULT FALSE,
    result_data JSON,
    error_message TEXT,
    execution_time_ms INT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (form_submission_id) REFERENCES form_submissions(id),
    INDEX idx_submission_id (form_submission_id),
    INDEX idx_scraper_name (scraper_name)
) ENGINE=InnoDB;
```

#### user_settings
Stores user customization preferences
```sql
CREATE TABLE user_settings (
    id INT PRIMARY KEY AUTO_INCREMENT,
    user_id INT UNIQUE,
    company_name VARCHAR(255),
    logo_filename VARCHAR(255),
    footer_text TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    INDEX idx_user_id (user_id)
) ENGINE=InnoDB;
```

#### api_keys
Stores API keys for external access
```sql
CREATE TABLE api_keys (
    id INT PRIMARY KEY AUTO_INCREMENT,
    api_key VARCHAR(255) UNIQUE NOT NULL,
    description TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    created_by INT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_used_at TIMESTAMP NULL,
    FOREIGN KEY (created_by) REFERENCES users(id),
    INDEX idx_api_key (api_key),
    INDEX idx_is_active (is_active)
) ENGINE=InnoDB;
```

#### scraper_settings
Stores scraper enable/disable status
```sql
CREATE TABLE scraper_settings (
    id INT PRIMARY KEY AUTO_INCREMENT,
    scraper_code VARCHAR(50) UNIQUE NOT NULL,
    scraper_name VARCHAR(100) NOT NULL,
    is_enabled BOOLEAN DEFAULT TRUE,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_scraper_code (scraper_code)
) ENGINE=InnoDB;
```

### Connection Pooling

The application uses MySQL connection pooling for optimal performance:

```python
connection_pool = pooling.MySQLConnectionPool(
    pool_name='insurance_pool',
    pool_size=5,
    pool_reset_session=True,
    autocommit=False,
    host='localhost',
    port=3306,
    user='root',
    password='password',
    database='insurance_db'
)
```

**Benefits:**
- Reduced connection overhead
- Better performance under load
- Automatic connection management
- Connection reuse

## Scraper Architecture

### Scraper Types

#### 1. API-Based Scrapers (AXA, MCMA, Sanlam)
- Make direct HTTP requests to provider APIs
- Fast response times (1-3 seconds)
- JSON request/response format
- Timezone-aware date handling
- Error handling and retries

**Example: AXA Scraper**
```python
def scrape_axa(form_data):
    # Map form data to AXA format
    payload = FieldMapper.map_to_axa(form_data)

    # Get Morocco timezone date
    morocco_tz = ZoneInfo('Africa/Casablanca')
    today = datetime.now(morocco_tz).strftime("%d-%m-%Y")

    # Make API request
    response = requests.post(
        "https://axa.ma/bff/website/v1/quotation",
        json=payload,
        headers=get_axa_headers()
    )

    # Parse and return results
    return parse_axa_response(response.json())
```

#### 2. Browser-Based Scrapers (RMA)
- Uses Playwright + Camoufox for JavaScript-heavy sites
- Handles complex interactions (dropdowns, checkboxes)
- Screenshot capture on errors
- Browser instance pooling
- Queue-based request management

**Example: RMA Scraper**
```python
async def scrape_rma(form_data):
    # Get browser from pool
    browser = await browser_manager.get_browser()

    # Navigate and fill form
    page = await browser.new_page()
    await page.goto("https://rma.ma/quotation")
    await page.fill("#lastName", form_data['nom'])
    # ... more form filling

    # Submit and wait for results
    await page.click("#submit")
    results = await page.wait_for_selector(".quotation-results")

    # Extract and return data
    return parse_rma_results(results)
```

### Field Mapping System

The `field_mapper.py` module handles conversion between different data formats:

- **Input:** Standardized form data
- **Output:** Provider-specific payload format

**Key Features:**
- Brand code mapping (different codes per provider)
- Fuel type conversion
- Date format transformation (DD-MM-YYYY vs YYYY-MM-DD)
- Dummy data generation (for testing)
- Timezone-aware date calculation

### Error Handling

Each scraper implements comprehensive error handling:

1. **Network Errors:** Timeout, connection refused
2. **API Errors:** 4xx, 5xx responses with detailed messages
3. **Validation Errors:** Invalid data from provider
4. **Parsing Errors:** Unexpected response format
5. **Browser Errors:** Page load failures, element not found

All errors are:
- Logged with full details
- Stored in database
- Returned to user with friendly message
- Not blocking other scrapers

## API Documentation

### Authentication

#### Session Authentication
```http
POST /api/login
Content-Type: application/json

{
  "email": "user@example.com",
  "password": "password123"
}

Response:
{
  "success": true,
  "message": "Connexion réussie",
  "is_admin": false,
  "name": "John Doe"
}
```

#### API Key Authentication
```http
POST /api/compare
Authorization: Bearer your-api-key-here
Content-Type: application/json

{...}
```

### Main Endpoints

#### Compare Insurance
```http
POST /api/compare
Content-Type: application/json

{
  "marque": "Renault",
  "modele": "Clio",
  "carburant": "diesel",
  "nombre_places": 5,
  "puissance_fiscale": 6,
  "date_mec": "2020-05-15",
  "type_plaque": "standard",
  "immatriculation": "WW378497",
  "valeur_neuf": 200000,
  "valeur_actuelle": 150000,
  "nom": "Alami",
  "prenom": "Ahmed",
  "telephone": "0661652022",
  "email": "ahmed@email.com",
  "date_naissance": "1990-01-15",
  "date_permis": "2010-03-20",
  "ville": "Casablanca",
  "assureur_actuel": "AXA",
  "consent": true,
  "selected_scrapers": ["axa", "rma"]  // Optional
}

Response:
{
  "success": true,
  "results": {
    "axa": {
      "success": true,
      "plans": [...],
      "execution_time_ms": 2341
    },
    "rma": {
      "success": true,
      "plans": [...],
      "execution_time_ms": 15234
    }
  },
  "form_submission_id": 123
}
```

#### Generate PDF
```http
POST /api/generate-comparison-pdf
Content-Type: application/json

{
  "plans": [...],
  "duration": "annual",
  "vehicle_info": {...}
}

Response:
Binary PDF file download
```

#### Admin - Create User
```http
POST /api/admin/create-user
Content-Type: application/json

{
  "name": "New Broker",
  "email": "broker@example.com",
  "password": "SecurePass123"
}

Response:
{
  "success": true,
  "message": "Utilisateur créé avec succès",
  "user_id": 5
}
```

#### Admin - Export Database
```http
GET /api/admin/export-database

Response:
Binary Excel file download (insurance_database_20260129_235959.xlsx)
```

## Environment Configuration

### Required Variables

```bash
# Flask Configuration
SECRET_KEY=your-secret-key-change-in-production
FLASK_ENV=production
PORT=8080

# MySQL Database (Option 1: Individual parameters)
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PASSWORD=your-secure-password
MYSQL_DATABASE=insurance_db

# MySQL Database (Option 2: Connection URL - Railway format)
MYSQL_URL=mysql://user:password@host:port/database

# Admin User (Created on first run)
ADMIN_EMAIL=admin@insurance.com
ADMIN_PASSWORD=ChangeThisPassword123!
ADMIN_NAME=Administrator
```

### Optional Variables

```bash
# Session Configuration
SESSION_COOKIE_SECURE=True
SESSION_COOKIE_HTTPONLY=True
SESSION_COOKIE_SAMESITE=Lax

# Database Pool Configuration
MYSQL_POOL_SIZE=5
MYSQL_POOL_NAME=insurance_pool

# Logging
LOG_LEVEL=INFO
```

## Deployment

### Docker Deployment

#### Build Image
```bash
docker build -t insurance-comparator .
```

#### Run Container
```bash
docker run -d \
  --name insurance-app \
  -p 8080:8080 \
  -e MYSQL_URL=mysql://user:pass@host:3306/dbname \
  -e SECRET_KEY=your-secret-key \
  -e FLASK_ENV=production \
  insurance-comparator
```

### Railway Deployment

1. **Connect Repository**
   - Create Railway account
   - Connect GitHub repository
   - Select branch to deploy

2. **Add MySQL Database**
   - Click "New" → "Database" → "MySQL"
   - Railway automatically sets MYSQL_URL

3. **Configure Environment**
   ```bash
   SECRET_KEY=generate-strong-random-key
   FLASK_ENV=production
   ADMIN_EMAIL=admin@yourdomain.com
   ADMIN_PASSWORD=StrongPassword123!
   ```

4. **Deploy**
   - Push to GitHub
   - Railway automatically builds and deploys
   - Access via provided URL

### Production Considerations

#### Security
- Use strong SECRET_KEY (32+ random characters)
- Enable HTTPS (Railway provides automatically)
- Use strong admin password
- Regularly rotate API keys
- Keep dependencies updated

#### Performance
- Increase MySQL connection pool size for high traffic
- Enable MySQL query caching
- Add database indexes for frequently queried fields
- Use Redis for session storage (optional)

#### Monitoring
- Enable Railway logging
- Monitor scraper success rates
- Track response times
- Set up uptime monitoring

#### Backup
- Regular MySQL database backups
- Export database weekly via admin panel
- Store backups in secure location
- Test restore procedures

## Development Setup

### Local Development

1. **Clone Repository**
   ```bash
   git clone <repository-url>
   cd WebSite
   ```

2. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   playwright install firefox
   ```

3. **Setup MySQL**
   ```bash
   mysql -u root -p
   CREATE DATABASE insurance_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
   ```

4. **Configure Environment**
   ```bash
   cp .env.example .env
   # Edit .env with your local MySQL credentials
   ```

5. **Run Application**
   ```bash
   python app.py
   ```

6. **Access Application**
   - URL: http://localhost:5000
   - Login with credentials from .env

### Adding New Insurance Provider

1. **Create Scraper File**
   ```bash
   touch scrapers/newprovider_scraper.py
   ```

2. **Implement Scraper**
   ```python
   def scrape_newprovider(form_data):
       """Scrape quotes from New Provider"""
       try:
           # Map form data
           payload = FieldMapper.map_to_newprovider(form_data)

           # Make request
           response = requests.post(url, json=payload)

           # Parse results
           return {
               "success": True,
               "plans": parse_results(response.json())
           }
       except Exception as e:
           return {"success": False, "error": str(e)}
   ```

3. **Register Scraper**
   ```python
   # scrapers/__init__.py
   from .newprovider_scraper import scrape_newprovider

   SCRAPER_FUNCTIONS = {
       "newprovider": scrape_newprovider,
       # ... other scrapers
   }
   ```

4. **Add to Database**
   ```sql
   INSERT INTO scraper_settings (scraper_code, scraper_name, is_enabled)
   VALUES ('newprovider', 'New Provider', TRUE);
   ```

5. **Test**
   ```bash
   python -c "from scrapers import scrape_newprovider; print(scrape_newprovider({...}))"
   ```

### Testing

```bash
# Unit tests
pytest tests/

# Integration tests
pytest tests/integration/

# Scraper tests
pytest tests/scrapers/

# With coverage
pytest --cov=. --cov-report=html
```

## Troubleshooting

### Common Issues

#### MySQL Connection Failed
```
Error: 2003 (HY000): Can't connect to MySQL server
```
**Solutions:**
- Verify MySQL is running: `mysql -u root -p`
- Check credentials in .env file
- Ensure database exists: `SHOW DATABASES;`
- Check firewall allows port 3306

#### Scraper Timeout
```
Error: Scraper timeout after 30 seconds
```
**Solutions:**
- Check internet connection
- Verify provider website is accessible
- Increase timeout in scraper code
- Check if provider is blocking your IP

#### AXA Date Validation Error
```
Error: La date d'effet ne doit pas être inférieure à la date système
```
**Solutions:**
- Already fixed in code (uses Morocco timezone)
- Verify server timezone is correct
- Check `field_mapper.py` line 250-253

#### PDF Generation Failed
```
Error: Failed to generate PDF
```
**Solutions:**
- Ensure reportlab is installed: `pip install reportlab`
- Check logo file exists and is valid image format
- Verify temp directory is writable
- Check for special characters in vehicle data

#### Excel Export Failed
```
Error: Failed to export database
```
**Solutions:**
- Ensure openpyxl is installed: `pip install openpyxl`
- Verify database connection is active
- Check temp directory permissions
- Ensure sufficient disk space

### Logs

#### View Application Logs (Railway)
```bash
railway logs
```

#### View MySQL Query Logs
```sql
SET GLOBAL general_log = 'ON';
SHOW VARIABLES LIKE 'general_log%';
```

#### Enable Debug Mode
```bash
# .env
FLASK_ENV=development
```

Then check terminal output for detailed logs.

## Project Structure

```
WebSite/
├── app.py                          # Main Flask application
├── auth.py                         # Authentication & authorization
├── comparison_service.py           # Insurance comparison logic
├── requirements.txt                # Python dependencies
├── Dockerfile                      # Docker configuration
├── .env                           # Environment variables (local)
├── .env.example                   # Environment template
├── README.md                      # This file
├── RAILWAY_DEPLOYMENT.md          # Railway deployment guide
│
├── database/
│   ├── __init__.py               # Database package init
│   └── models.py                 # MySQL models & queries
│
├── scrapers/
│   ├── __init__.py               # Scraper registration
│   ├── field_mapper.py           # Form data transformation
│   ├── axa_scraper.py            # AXA insurance scraper
│   ├── sanlam_scraper.py         # Sanlam (Saham) scraper
│   ├── mcma_scraper.py           # MCMA scraper
│   ├── rma_scraper.py            # RMA Watanya scraper
│   └── rma_browser_manager.py    # Playwright browser manager
│
└── static/
    ├── index.html                # Main comparison form
    ├── login.html                # Login page
    ├── admin.html                # Admin dashboard
    ├── admin_scrapers.html       # Scraper management
    ├── settings.html             # User settings
    └── uploads/                  # User uploaded files (logos)
```

## Security Best Practices

### Implemented Security Measures

✅ **Password Security**
- SHA-256 hashing with salt
- Never stored in plain text
- Minimum length enforcement

✅ **Session Security**
- Secure cookie flags in production
- HttpOnly flag prevents XSS
- SameSite policy prevents CSRF
- 24-hour session timeout

✅ **SQL Injection Prevention**
- Parameterized queries only
- No string concatenation in SQL
- Input validation on all endpoints

✅ **XSS Prevention**
- HTML escaping in templates
- Content-Security-Policy headers
- Input sanitization

✅ **CORS Configuration**
- Specific origin allowlist
- Credentials support enabled
- Method restrictions

✅ **API Security**
- Rate limiting (optional, can be added)
- API key authentication
- Request validation

✅ **File Upload Security**
- File type validation
- Size limits
- Secure filename generation
- Stored outside web root

### Recommended Additional Measures

📋 **To Implement:**
- Enable 2FA for admin accounts
- Add rate limiting with Flask-Limiter
- Implement request logging
- Add CAPTCHA on login form
- Set up intrusion detection
- Regular security audits
- Automated dependency scanning

## Performance Optimization

### Database Optimization
- Connection pooling (already implemented)
- Indexed columns on frequently queried fields
- Query result caching
- Batch inserts for multiple records

### Application Optimization
- Async scraper execution (can be improved)
- Response compression (gzip)
- Static file caching
- Database query optimization

### Frontend Optimization
- Minified CSS/JS
- Image optimization
- Lazy loading
- CDN for static assets (optional)

## Contributing

### Code Style
- Follow PEP 8 for Python code
- Use meaningful variable names
- Add docstrings to functions
- Comment complex logic

### Git Workflow
1. Create feature branch from main
2. Make changes with clear commit messages
3. Test thoroughly
4. Submit pull request
5. Wait for code review

### Testing Requirements
- Write tests for new features
- Ensure existing tests pass
- Maintain >80% code coverage

## Support & Contact

For technical issues:
- Check logs first (Railway or local)
- Review this documentation
- Check RAILWAY_DEPLOYMENT.md for deployment issues
- Open GitHub issue with detailed description

For business inquiries:
- Contact system administrator
- Request access credentials
- Training and onboarding support available

---

## License

**Proprietary Software** - All rights reserved

This software is proprietary and confidential. Unauthorized copying, distribution, or use of this software is strictly prohibited.

---

**Built with ❤️ for the Moroccan insurance market**

*Last Updated: January 2026*
