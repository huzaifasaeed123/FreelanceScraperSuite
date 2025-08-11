# Swiss Business Data Scraper

A comprehensive Python scraper that extracts business information from Swiss business directories (Local.ch and MoneyHouse.ch) and formats the data into organized Excel spreadsheets.

## 🚀 Features

- **Local.ch Scraper**: Extracts business listings from Local.ch sitemaps
- **MoneyHouse.ch Scraper**: Gathers detailed company information including management data
- **Data Matching**: Intelligently matches businesses across both platforms
- **Excel Export**: Generates organized spreadsheets by industry (Branche)
- **Multi-threaded**: Fast concurrent processing with progress bars
- **SQLite Database**: Stores all data in a local database for easy access

## 📊 Data Collected

### Local.ch Data
- Business Name
- Address & Location
- Phone Numbers (Landline, Mobile)
- WhatsApp Numbers
- Email Address
- Website
- Business URL

### MoneyHouse.ch Data
- Company Legal Form (Rechtsform)
- Company Age
- Revenue (Umsatz)
- Number of Employees
- Management Information
- President/Board Members
- LinkedIn Profiles
- Industry Classification (Branche)
- Business Purpose (Firmenzweck)
- UID Number
- Canton Information

## 🛠️ Installation

### Prerequisites
- Python 3.7 or higher
- Internet connection
- At least 2GB free disk space

### Setup Instructions

1. **Clone the repository**
   ```bash
   git clone https://github.com/yourusername/swiss-business-scraper.git
   cd swiss-business-scraper
   ```

2. **Create virtual environment (recommended)**
   ```bash
   python -m venv scraper_env
   
   # Windows
   scraper_env\Scripts\activate
   
   # macOS/Linux
   source scraper_env/bin/activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

## 🚀 Usage

### Quick Start
Run the complete scraping process:
```bash
python index.py
```

### Individual Scrapers
You can also run scrapers individually:

```python
# Local.ch only
from LocalScraper import Local_Scraper
Local_Scraper()

# MoneyHouse.ch only
from MoneyHouse_Scraper import moneyhouse_main
moneyhouse_main()

# Format output only
from OutpuFormatting import OutPutFormatting
OutPutFormatting()
```

## 📁 Output Files

After successful execution, you'll find:

- **`Final_Combined.db`** - SQLite database with all scraped data
- **`combined_large.xlsx`** - Complete dataset with all columns
- **`combined_small.xlsx`** - Essential data only
- **`branche_spreadsheets_L/`** - Large format files organized by industry
- **`branche_spreadsheets_S/`** - Small format files organized by industry
- **`Missing.txt`** - URLs that couldn't be scraped (for retry)

## 📈 Performance

- **Local.ch**: Processes ~500,000+ business URLs
- **MoneyHouse.ch**: Handles ~300,000+ company records
- **Threading**: 30-50 concurrent requests for optimal speed
- **Runtime**: Complete process takes 4-8 hours depending on internet speed

## ⚙️ Configuration

### Thread Settings
Modify thread counts in the scraper files:
```python
# LocalScraper.py
with ThreadPoolExecutor(max_workers=30) as executor:

# MoneyHouse_Scraper.py
with ThreadPoolExecutor(max_workers=50) as executor:
```

### Database Configuration
The scrapers use SQLite by default. Database file: `Final_Combined.db`

## 🔧 Troubleshooting

### Common Issues

1. **SSL Certificate Errors**
   ```bash
   pip install --upgrade certifi
   ```

2. **Memory Issues**
   - Reduce thread count (`max_workers`)
   - Run scrapers individually
   - Ensure sufficient RAM (4GB+ recommended)

3. **Network Timeouts**
   - Check internet connection
   - Increase timeout values in request headers

4. **Database Locked**
   - Close any database browser tools
   - Restart the script

### Error Recovery
If scraping stops unexpectedly:
- The script will resume from where it left off
- Check `Missing.txt` for failed URLs
- Re-run individual scrapers if needed

## 📋 Requirements

```
requests>=2.28.0
beautifulsoup4>=4.11.0
pandas>=1.5.0
lxml>=4.9.0
dataset>=1.5.0
alive-progress>=3.0.0
openpyxl>=3.0.0
```

## 🏗️ Project Structure

```
swiss-business-scraper/
├── index.py                 # Main runner script
├── LocalScraper.py          # Local.ch scraper
├── MoneyHouse_Scraper.py    # MoneyHouse.ch scraper
├── OutpuFormatting.py       # Data formatting and export
├── requirements.txt         # Python dependencies
├── README.md               # This file
└── output/                 # Generated files (created during execution)
    ├── Final_Combined.db
    ├── combined_large.xlsx
    ├── combined_small.xlsx
    ├── branche_spreadsheets_L/
    └── branche_spreadsheets_S/
```

## 🔍 Data Schema

### MoneyHouse Table
- `Name` - Company name
- `Kanton` - Swiss canton
- `Rechtsform` - Legal form
- `Alter` - Company age
- `Umsatz` - Revenue
- `Mitarbeiter` - Employee count
- `Adresse` - Address
- `PLZ` - Postal code
- `ORT` - City
- `Telefonnummer` - Phone number
- `Webseite` - Website
- `Emailadresse` - Email
- `Branche` - Industry
- `Firmenzweck` - Business purpose

### Local Table
- `Name` - Business name
- `Address` - Full address
- `Email` - Email address
- `Website` - Website URL
- `Telefon 1/2` - Phone numbers
- `Mobiltelefon 1/2` - Mobile numbers
- `WhatsApp 1/2` - WhatsApp numbers

## ⚠️ Legal Notice

This scraper is for educational and research purposes. Please ensure you comply with:

- Website Terms of Service
- Local data protection laws (GDPR, Swiss DPA)
- Rate limiting and respectful scraping practices
- Commercial use restrictions

**Important**: Always respect robots.txt files and implement appropriate delays between requests.

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🆘 Support

If you encounter issues:

1. Check the [Troubleshooting](#-troubleshooting) section
2. Review error logs and console output
3. Open an issue on GitHub with:
   - Error message
   - Python version
   - Operating system
   - Steps to reproduce

## 📞 Contact

- **Author**: Huzaifa Saeed
- **Email**: saeedhuzaifa678@gmail.com
- **GitHub**: [@huzaifasaeed123](https://github.com/huzaifasaeed123)

## 🙏 Acknowledgments

- Local.ch for providing business directory data
- MoneyHouse.ch for Swiss company information
- Python community for excellent libraries

---

**⭐ If this project helped you, please give it a star on GitHub!**