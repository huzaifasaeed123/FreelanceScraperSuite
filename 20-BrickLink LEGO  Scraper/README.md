# BrickLink LEGO Catalog Web Scraper

A comprehensive web scraping solution for extracting and organizing LEGO catalog data from BrickLink.com into a normalized relational database structure.

## 🎯 Overview

This project implements a four-stage pipeline to scrape the entire BrickLink catalog, including:
- **Sets**: 409 catalog pages
- **Minifigures**: 352 catalog pages  
- **Parts**: 1,757 catalog pages

The system processes over 50,000 items, downloads product images, and creates complex relationship mappings between different LEGO components.

## ✨ Features

- **Complete Catalog Extraction**: Scrapes all sets, minifigures, and parts from BrickLink
- **Image Downloading**: Automatically downloads and stores product images
- **Relationship Mapping**: Creates normalized connections between items
- **Price Data Collection**: Extracts historical and current pricing information
- **Excel Export**: Generates spreadsheets for data analysis
- **Concurrent Processing**: Utilizes multi-threading and multiprocessing for efficiency
- **Error Handling**: Implements retry mechanisms and comprehensive logging
- **Database Normalization**: Transforms data into 3rd Normal Form (3NF)

## 📁 Project Structure

```
bricklink-scraper/
├── index.py             # Main orchestrator
├── item_scraper.py      # Item number discovery
├── data_scraper.py      # HTML and image collection
├── parser.py            # Data extraction and parsing
├── db_connection.py     # Relationship normalization
├── Images/              # Downloaded product images
├── output/              # Excel export files
└── logs/                # Application logs
```

## 📋 File Descriptions

- **index.py**: Orchestrates the entire scraping workflow by sequentially executing item discovery, data collection, parsing, and relationship normalization stages
- **item_scraper.py**: Extracts item numbers from BrickLink catalog listing pages using concurrent requests across all categories (sets, minifigures, parts)
- **data_scraper.py**: Downloads main product pages, price tables, inventory pages, and product images for each item, storing raw HTML in database
- **parser.py**: Transforms raw HTML into structured data by extracting item details, pricing information, and relationship data using BeautifulSoup and regex
- **db_connection.py**: Creates and populates a normalized connection table by converting comma-separated relationships into individual many-to-many database records

## 🚀 Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/bricklink-scraper.git
cd bricklink-scraper
```

2. Install required dependencies:
```bash
pip install -r requirements.txt
```

3. Create necessary directories:
```bash
mkdir Images output logs
```

## 📖 Usage

Run the main orchestrator to start the complete scraping process:

```bash
python index.py
```

The process will:
1. Discover all item numbers across categories
2. Download HTML content and images
3. Parse data into structured format
4. Create relationship mappings
5. Export results to Excel files

## 💾 Database Schema

### Raw Data Storage (`bricklink_data_raw.db`)
```
├── sets           # Raw HTML for sets
├── minifigures    # Raw HTML for minifigures
└── parts          # Raw HTML for parts
```

### Parsed Data Storage (`bricklink_parse.db`)
```
├── set_parse          # Parsed set data
├── minifigures_parse  # Parsed minifigure data
├── part_parse         # Parsed part data
└── connection_table   # Normalized relationships
```

## 🔄 Data Flow

1. **Item Discovery**: Scrapes catalog pages to collect item numbers
2. **Data Collection**: Downloads HTML content and product images
3. **Data Extraction**: Parses HTML to extract structured information
4. **Relationship Normalization**: Converts comma-separated relations into normalized database records

## 🔗 Relationship Management

The system manages three types of relationships:

1. **Set-to-Part**: Links sets with their component parts
2. **Set-to-Minifigure**: Links sets with included minifigures
3. **Minifigure-to-Part**: Links minifigures with their component parts

Example transformation:
```
Input:  "parts_relation": "3023, 3024, 3069b"
Output: Three separate connection records
```

## 🛠️ Technical Details

- **Concurrency**: ThreadPoolExecutor with 20 workers for HTTP requests
- **Multiprocessing**: CPU count - 1 cores for parsing operations
- **Batch Processing**: 1,000 records per database transaction
- **Retry Mechanism**: 5 attempts for failed requests
- **Progress Tracking**: Real-time progress indicators using alive_progress

## 📊 Output Files

- **SQLite Databases**: Complete structured data with relationships
- **Excel Files**: Parsed data exports for each category
- **Product Images**: Downloaded to `Images/` directory
- **Logs**: Detailed execution logs in `logs/` directory

## 📄 Requirements

```
requests
beautifulsoup4
dataset
pandas
alive-progress
demjson3
openpyxl
```

## ⚖️ License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🤝 Contributing

1. Fork the project
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## 📧 Contact

Your Name - Huzaifa Saeed

Project Link: [https://github.com/huzaifasaeed123/bricklink-scraper](https://github.com/huzaifasaeed123/bricklink-scraper)

## 🙏 Acknowledgments

- BrickLink.com for providing the data source
- All contributors who help improve this project

---

**Note**: This scraper is for educational purposes. Please respect BrickLink's terms of service and implement appropriate rate limiting.