# Insurance Comparator - WebSite Application

A Flask-based insurance comparison platform that scrapes quotes from multiple Moroccan insurance providers and displays them in a unified interface.

## Features

- 🔐 **User Authentication**: Secure login system with admin and regular users
- 📊 **Insurance Comparison**: Compare quotes from AXA, Sanlam, MCMA, and RMA
- 📱 **Responsive Design**: Modern UI with Tailwind CSS
- 🔧 **Admin Panel**: Manage users, scrapers, and API keys
- 📄 **PDF Generation**: Export comparison results as PDF
- 📊 **Excel Export**: Download complete database as Excel file
- 🗄️ **MySQL Database**: Production-ready database with connection pooling
- 🚀 **Docker Ready**: Containerized for easy deployment

## Tech Stack

- **Backend**: Flask 3.0+, Python 3.11+
- **Database**: MySQL 8.0+ with connection pooling
- **Frontend**: HTML, Tailwind CSS, Vanilla JavaScript
- **Scraping**: Playwright, Camoufox, Requests
- **Deployment**: Docker, Gunicorn, Railway
- **File Generation**: ReportLab (PDF), OpenPyXL (Excel)

## Quick Start

### Local Development

1. **Clone the repository**
   ```bash
   cd WebSite
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   playwright install firefox
   ```

3. **Set up MySQL database**
   ```bash
   # Create database
   mysql -u root -p
   CREATE DATABASE insurance_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
   ```

4. **Configure environment**
   ```bash
   cp .env.example .env
   # Edit .env with your MySQL credentials
   ```

5. **Run the application**
   ```bash
   python app.py
   ```

6. **Access the application**
   - URL: http://localhost:5000
   - Default admin: Check .env file

### Docker Deployment

```bash
# Build image
docker build -t insurance-app .

# Run with MySQL
docker run -d \
  -p 8080:8080 \
  -e MYSQL_HOST=your-mysql-host \
  -e MYSQL_USER=your-mysql-user \
  -e MYSQL_PASSWORD=your-mysql-password \
  -e MYSQL_DATABASE=insurance_db \
  -e SECRET_KEY=your-secret-key \
  insurance-app
```

## Railway Deployment

For complete deployment instructions on Railway, see [RAILWAY_DEPLOYMENT.md](RAILWAY_DEPLOYMENT.md).

**Quick steps:**
1. Push code to GitHub
2. Create Railway project from GitHub repo
3. Add MySQL database plugin
4. Configure environment variables
5. Deploy automatically

## Environment Variables

Required variables (see `.env.example` for complete list):

```bash
# Flask
SECRET_KEY=your-secret-key
FLASK_ENV=production

# MySQL
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PASSWORD=your-password
MYSQL_DATABASE=insurance_db

# Or use Railway's MYSQL_URL
MYSQL_URL=mysql://user:pass@host:port/database

# Admin
ADMIN_EMAIL=admin@example.com
ADMIN_PASSWORD=SecurePassword123
ADMIN_NAME=Admin
```

## Project Structure

```
WebSite/
├── app.py                      # Main Flask application
├── requirements.txt            # Python dependencies
├── Dockerfile                  # Docker configuration
├── .env.example               # Environment variables template
├── RAILWAY_DEPLOYMENT.md      # Railway deployment guide
├── README.md                  # This file
│
├── database/
│   ├── __init__.py
│   └── models.py              # MySQL database models
│
├── scrapers/
│   ├── __init__.py
│   ├── axa_scraper.py         # AXA insurance scraper
│   ├── sanlam_scraper.py      # Sanlam scraper
│   ├── mcma_scraper.py        # MCMA scraper
│   ├── rma_scraper.py         # RMA scraper
│   ├── field_mapper.py        # Form field mapping
│   └── rma_browser_manager.py # Browser management
│
├── static/
│   ├── index.html             # Main form page
│   ├── login.html             # Login page
│   ├── admin.html             # Admin dashboard
│   ├── admin_scrapers.html    # Scraper management
│   ├── settings.html          # User settings
│   └── uploads/               # User uploaded files (logos)
│
├── auth.py                    # Authentication module
└── comparison_service.py      # Insurance comparison logic
```

## API Endpoints

### Public Endpoints
- `GET /` - Main form (requires login)
- `GET /login` - Login page
- `POST /api/login` - User authentication
- `POST /api/logout` - User logout

### User Endpoints (Requires Login)
- `POST /api/compare` - Compare insurance quotes
- `POST /api/generate-comparison-pdf` - Generate PDF report
- `GET /api/settings` - Get user settings
- `POST /api/settings` - Update user settings
- `POST /api/upload-logo` - Upload company logo

### Admin Endpoints (Requires Admin)
- `GET /admin` - Admin dashboard
- `GET /api/admin/users` - List all users
- `POST /api/admin/create-user` - Create new user
- `DELETE /api/admin/delete-user/:id` - Delete user
- `GET /api/admin/scrapers` - List all scrapers
- `POST /api/admin/toggle-scraper` - Enable/disable scraper
- `GET /api/admin/api-keys` - List API keys
- `POST /api/admin/create-api-key` - Create API key
- `POST /api/admin/toggle-api-key` - Enable/disable API key
- `DELETE /api/admin/delete-api-key` - Delete API key
- `GET /api/admin/export-database` - Download database as Excel

### Public API
- `GET /api/health` - Health check
- `GET /api/providers` - List available providers

## Database Schema

### Main Tables
- **users** - User accounts
- **form_submissions** - Insurance quote requests
- **scraper_results** - Results from each scraper
- **user_settings** - User customization settings
- **scraper_settings** - Scraper enable/disable status
- **api_keys** - API keys for external access

### Legacy Tables (Backward Compatibility)
- **user_requests** - Old format requests
- **provider_responses** - Raw scraper responses
- **insurance_plans** - Individual insurance plans
- **plan_guarantees** - Coverage details
- **selectable_fields** - Dynamic form fields
- **selectable_options** - Field options
- **option_combinations** - Pricing combinations

## Key Features

### 1. Database Export
Admin users can download the complete database as an Excel file:
- Each table becomes a separate sheet
- Formatted headers with styling
- Auto-adjusted column widths
- Accessible from admin panel header

### 2. Scraper Management
- Enable/disable scrapers without code changes
- Real-time scraper status
- Error handling and logging

### 3. User Management
- Create multiple user accounts
- Admin privileges
- Activity tracking
- Password hashing with SHA-256

### 4. PDF Generation
- Custom company logo
- Personalized footer
- Professional formatting
- Vehicle and pricing details

### 5. API Key System
- Generate API keys for external access
- Enable/disable keys without deletion
- Usage tracking
- Secure authentication

## Development

### Running Tests
```bash
# Install test dependencies
pip install pytest pytest-cov

# Run tests
pytest

# With coverage
pytest --cov=. --cov-report=html
```

### Adding a New Scraper

1. Create scraper in `scrapers/new_scraper.py`
2. Implement required methods
3. Add to `scrapers/__init__.py`
4. Add to database scraper_settings
5. Test thoroughly

Example:
```python
def scrape_new_provider(form_data):
    """Scrape quotes from new provider"""
    try:
        # Scraping logic here
        return {
            "success": True,
            "plans": [...],
            "raw_data": {...}
        }
    except Exception as e:
        return {"success": False, "error": str(e)}
```

## Troubleshooting

### MySQL Connection Issues
- Verify MySQL is running: `mysql -u root -p`
- Check credentials in `.env`
- Ensure database exists: `SHOW DATABASES;`
- Check firewall rules for port 3306

### Scraper Failures
- Check if scraper is enabled in admin panel
- Verify network connectivity
- Check provider website status
- Review logs for specific errors

### Performance Issues
- Increase MySQL connection pool size
- Add database indexes
- Enable query caching
- Use Redis for session management (optional)

## Security Considerations

- ✅ All passwords are hashed (SHA-256)
- ✅ Session management with secure cookies
- ✅ SQL injection prevention (parameterized queries)
- ✅ CORS configured for specific origins
- ✅ Environment variables for sensitive data
- ✅ Input validation on all forms
- ✅ Admin-only endpoints protected

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## License

Proprietary - All rights reserved

## Support

For issues or questions:
- Check [RAILWAY_DEPLOYMENT.md](RAILWAY_DEPLOYMENT.md) for deployment help
- Review application logs
- Check Railway documentation for platform issues

---

**Built with ❤️ for efficient insurance comparison**
