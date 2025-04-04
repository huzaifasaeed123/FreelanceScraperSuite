# Hotel B2B Lead Scraper

This project scrapes detailed information from 750+ hotels, including their names, locations, addresses, and much more. Additionally, it scrapes leadership details for each hotel. The data is then stored in two separate tables in an SQLite database and combined using a SQL query to generate a unified CSV file.

## Features
- Scrapes hotel details such as name, location, address, etc.
- Scrapes leadership details for each hotel.
- Saves scraped data into SQLite database tables.
- Joins the data from both tables to create a comprehensive CSV file.

## Prerequisites
- Python 3.x
- Required Python packages: `requests`, `beautifulsoup4`, `json`, `dataset`, `pandas`

## Installation
1. Clone the repository:
    ```bash
    git clone https://github.com/yourusername/HotelB2BLeadScraper.git
    cd HotelB2BLeadScraper
    ```


## Usage
1. Before running the script, manually update the cookies in the `headers` dictionary in `index1.py`. You need to copy the cookies from your browser's request headers when accessing the target website.

2. Run the script:
    ```bash
    python index3.py
    ```

3. The script will:
    - Scrape hotel details and leadership profiles.
    - Save the data to an SQLite database.
    - Join the tables and export the data to `joined_data.csv`.

## Code Flow And Understanding
1. **Initialize Headers and Session**: Define headers and create a session object to handle requests.
2. **Scrape Hotel List**: Iterate over multiple pages to scrape hotel details like name, address, and phone number.
3. **Scrape Leadership Profiles**: For each hotel, scrape leadership details such as name, title, and contact information.
4. **Save to Database**: Store the scraped hotel and leadership details in separate tables in an SQLite database.
5. **Join Tables and Export**: Use a SQL query to join the hotel and leadership tables and export the combined data to a CSV file.

## Notes
- **Manual Cookie Update**: Each time you run the script, you must manually update the cookies in the `headers` dictionary. This is necessary to make successful requests to the target website.
- **Error Handling**: The script includes basic error handling for failed requests and data extraction issues.

## Contributing
Pull requests are welcome. For major changes, please open an issue first to discuss what you would like to change.

