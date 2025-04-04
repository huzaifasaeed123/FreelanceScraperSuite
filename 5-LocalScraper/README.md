
# Local.Ch Scraper

## Overview

This project is designed for efficiently scraping data from multiple web pages using Python. The script processes URLs concurrently using threading, retrieves relevant information from the pages, and stores the results in a SQLite database. Finally, the data is exported to a CSV file for further use.

## Table of Contents

- [Project Structure](#project-structure)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Usage](#usage)
- [Approaches](#approaches)
  - [Old Approach](#old-approach)
  - [New Approach](#new-approach)
- [Performance Comparison](#performance-comparison)
- [Contributing](#contributing)
- [License](#license)

## Project Structure

```
.
├── extracted_urls.txt          # Input file containing the list of URLs to be scraped
├── FinalData.csv               # Output file containing the scraped data in CSV format
├── Missing.txt                 # Output file containing URLs that failed to be scraped
├── ScrapedData.db              # SQLite database file storing scraped data
├── script_name.py              # Main Python script (replace with actual name)
└── README.md                   # This README file
```

## Prerequisites

Before you begin, ensure you have the following installed on your system:

- Python 3.8+
- `pip` (Python package installer)

### Required Python Packages

Install the required packages by running:

```bash
pip install requests beautifulsoup4 pandas dataset alive-progress
```

## Installation

1. **Clone the repository:**

    ```bash
    git clone https://github.com/your-username/repository-name.git
    cd repository-name
    ```

2. **Install dependencies:**

    ```bash
    pip install -r requirements.txt
    ```

3. **Prepare the input file:**

    Place your URLs in a file named `extracted_urls.txt`, with each URL on a new line.

## Usage

To run the script, execute the following command in your terminal:

```bash
python script_name.py
```

This will:

1. Read the list of URLs from `extracted_urls.txt`.
2. Scrape each URL concurrently.
3. Store the successfully scraped data in a SQLite database.
4. Export the final data to `FinalData.csv`.
5. Save any URLs that could not be scraped in `Missing.txt`.

## Approaches

### Old Approach

- **Frequent Database Updates:** The script updates the database after each URL is processed, which leads to a high number of database transactions.
- **Drawbacks:** This method is inefficient for large datasets due to the high overhead of database operations, resulting in slower performance.

### New Approach

- **Deferred Database Updates:** The script accumulates all scraped data in memory and performs a single bulk insertion into the database at the end.
- **Advantages:** This method is significantly faster, as it reduces the number of database transactions and minimizes thread contention. Failed URLs are stored separately in `Missing.txt`.

## Performance Comparison

The new approach is optimized for large-scale data scraping. By deferring database operations and handling failed URLs more efficiently, it offers a considerable speed improvement over the old approach.

- **Old Approach:** Over 600,000+ database updates, leading to high execution time.
- **New Approach:** Single bulk database insertion, reducing execution time significantly.

## Contributing

Contributions are welcome! Please follow these steps:

1. Fork the repository.
2. Create a new branch (`git checkout -b feature-branch`).
3. Make your changes.
4. Commit your changes (`git commit -m 'Add some feature'`).
5. Push to the branch (`git push origin feature-branch`).
6. Open a pull request.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
