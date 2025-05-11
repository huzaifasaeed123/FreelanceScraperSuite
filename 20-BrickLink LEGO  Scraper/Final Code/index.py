# index.py
import os
import logging
import time
import dataset
from datetime import datetime
from item_scraper import get_all_items
from data_scraper import process_items, fetch_html, download_image, process_item
from parser import parse_all_data
from db_connection import create_connection_table, populate_connection_table_batch, verify_statistics, fix_wal_issue

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bricklink_scraping.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Configuration
CONFIG = {
    'sets': {
        'pages': 409,
        'cat_type': 'S',
        'table_name': 'sets',
        'parse_table': 'set_parse',
        'excel_output': 'parsed_sets_data.xlsx'
    },
    'minifigures': {
        'pages': 352,
        'cat_type': 'M',
        'table_name': 'minifigures',
        'parse_table': 'minifigures_parse',
        'excel_output': 'parsed_minifigures_data.xlsx'
    },
    'parts': {
        'pages': 1757,
        'cat_type': 'P',
        'table_name': 'parts',
        'parse_table': 'part_parse',
        'excel_output': 'parsed_parts_data.xlsx'
    }
}

# Database paths
RAW_DB_PATH = "sqlite:///bricklink_data_raw.db"
PARSED_DB_PATH = "sqlite:///bricklink_parse.db"  # Contains both parsed data and connection table

def main():
    """Main orchestrator function"""
    start_time = time.time()
    logger.info("Starting BrickLink scraping process...")
    
    try:
        # Create output directory for Excel files
        os.makedirs('output', exist_ok=True)
        
        # Step 1: Get all item numbers
        logger.info("Step 1: Scraping item numbers...")
        all_items = {}
        
        for category, config in CONFIG.items():
            logger.info(f"Getting {category} items...")
            items = get_all_items(config['pages'], config['cat_type'])
            all_items[category] = items
            logger.info(f"Found {len(items)} {category} items")
        
        # Step 2: Scrape and store HTML data
        logger.info("Step 2: Scraping HTML data...")
        raw_db = dataset.connect(RAW_DB_PATH)
        
        for category, config in CONFIG.items():
            logger.info(f"Processing {category}...")
            table = raw_db[config['table_name']]
            
            # Process items with appropriate consist_of_url based on type
            process_items(
                item_nos=all_items[category],
                cat_type=config['cat_type'],
                table=table,
                is_parts=(config['cat_type'] == 'P')
            )
        
        # Step 3: Parse stored HTML data
        logger.info("Step 3: Parsing HTML data...")
        parsed_db = dataset.connect(PARSED_DB_PATH)
        
        for category, config in CONFIG.items():
            logger.info(f"Parsing {category} data...")
            raw_table = raw_db[config['table_name']]
            parsed_table = parsed_db[config['parse_table']]
            
            # Parse data with appropriate settings
            parsed_data = parse_all_data(
                raw_table=raw_table,
                parsed_table=parsed_table,
                is_parts=(config['cat_type'] == 'P'),
                batch_size=1000,
                output_excel=f"output/{config['excel_output']}"
            )
            
            logger.info(f"Parsed {len(parsed_data)} {category} items")
        
        # Step 4: Create connection table (in the same database)
        logger.info("Step 4: Creating connection table...")
        
        # Fix any existing WAL issues (using the parsed database path)
        fix_wal_issue('bricklink_parse.db')
        
        # Create connection table structure (in the same database as parsed data)
        create_connection_table('bricklink_parse.db')
        
        # Populate connections
        populate_connection_table_batch('bricklink_parse.db', batch_size=1000)
        
        # Verify statistics
        verify_statistics('bricklink_parse.db')
        
        end_time = time.time()
        elapsed_time = end_time - start_time
        logger.info(f"✅ BrickLink scraping completed successfully in {elapsed_time:.2f} seconds")
        
    except Exception as e:
        logger.error(f"❌ Error in main process: {e}")
        raise

if __name__ == "__main__":
    main()