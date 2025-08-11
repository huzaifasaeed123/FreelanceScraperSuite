import requests
import pandas as pd
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock
import dataset
import time
import os
import traceback
import re
from bs4 import BeautifulSoup
import json
import threading

lock = threading.Lock()

def get_management_info(record,headers):
    linkedin_link = ""
    president_name = ""
    branch_leader=""
    try:
        # Extract URL path from the full URL
        base_url = "https://www.moneyhouse.ch/de/company/"
        url_path = record['Url']
        
        management_url = f"{base_url}{url_path}/management"
        # Headers (to mimic a real browser)
        # Send GET request
        response = requests.get(management_url, headers=headers)

        # Check if the request was successful
        if response.status_code == 200:
            soup = BeautifulSoup(response.content, "html.parser")
            key_classes = soup.find_all("td", class_="entity-name")

            rechtsform_id = int(record.get('Rechtsform', 0))
            
            for key in key_classes:
                president_span = key.find("span", class_="role bean bean-col-mandate")
                if president_span:
                    if rechtsform_id == 3:
                        if "Verwaltungsrat-Präsident" in president_span.text:
                            president_name_a = key.find("a", class_="name-link l-mobile-one-whole")
                            if president_name_a:
                                president_name = president_name_a.text.strip()

                            entity_follow = key.find_next_sibling("td", class_="entity-follow")
                            if entity_follow:
                                a = entity_follow.find("a", class_="icon-linkedIn linkedin-link")
                                if a:
                                    linkedin_link = a.get("href", "")
                            break
                            
                    elif rechtsform_id == 9:
                        if "Leiter der Zweigniederlassung" in president_span.text:
                            president_name_a = key.find("a", class_="name-link l-mobile-one-whole")
                            if president_name_a:
                                branch_leader = president_name_a.text.strip()

                            entity_follow = key.find_next_sibling("td", class_="entity-follow")
                            if entity_follow:
                                a = entity_follow.find("a", class_="icon-linkedIn linkedin-link")
                                if a:
                                    linkedin_link = a.get("href", "")
                            break

            print(f"Management info scraped for record ID: {record.get('Url', 'Unknown')}")
            
            return {
                "Präsident": president_name,
                "Leiter der Zweigniederlassungen": branch_leader,
                "LinkedIn Link": linkedin_link,
            }
        else:
            print(f"Failed to retrieve management page. Status code: {response.status_code} for record ID: {record.get('Url', 'Unknown')}")
            return{
                "Präsident": president_name,
                "Leiter der Zweigniederlassungen": branch_leader,
                "LinkedIn Link": linkedin_link,
            }
    except Exception as e:
        print(f"Exception occurred for record ID {record.get('Url', 'Unknown')}: {e}")
        traceback.print_exc()
        return{
                "Präsident": president_name,
                "Leiter der Zweigniederlassungen": branch_leader,
                "LinkedIn Link": linkedin_link,
            }

def get_records_needing_management_info(database_name, table_name):
    """Get records where Rechtsform 2(Extra For Testing) is 3 or 9"""
    db = dataset.connect(f'sqlite:///{database_name}')
    table = db[table_name]
    
    # Get records where Rechtsform 2(Extra For Testing) is 3 or 9
    records = []
    for row in table.all():
        rechtsform_value = row.get('Rechtsform 2(Extra For Testing)')
        if rechtsform_value in [3, 9, '3', '9']:
            records.append(dict(row))
    
    print(f"Found {len(records)} records that need management info scraping")
    return records

def update_database_with_management_info(database_name, table_name, management_data):
    """Update the database with the new management information"""
    db = dataset.connect(f'sqlite:///{database_name}')
    table = db[table_name]
    
    with lock:
        for data in management_data:
            try:
                # Update the record with the new columns
                table.update({
                    'id': data['id'],
                    'President/Leader': data['President/Leader'],
                    'LinkedIn Link': data['LinkedIn Link']
                }, ['id'])
                print(f"Updated record ID: {data['id']}")
            except Exception as e:
                print(f"Error updating record ID {data['id']}: {e}")

def threading_management_scraper(database_name='Final_Combined.db', table_name='FinalData'):
    """Main function to scrape management info with threading"""
    
    # Check if database exists
    if not os.path.exists(database_name):
        print(f"Database {database_name} not found!")
        return
    
    # Get records that need management info
    records_to_scrape = get_records_needing_management_info(database_name, table_name)
    
    if not records_to_scrape:
        print("No records found that need management info scraping")
        return
    
    # List to store results
    management_results = []
    
    # Use threading to scrape management info
    
    with ThreadPoolExecutor(max_workers=20) as executor:  # Reduced workers to be respectful
        futures = []
        
        for record in records_to_scrape:
            futures.append(executor.submit(get_management_info, record))
        
        # Collect results
        for future in as_completed(futures):
            try:
                result = future.result()
                if result:
                    with lock:
                        management_results.append(result)
            except Exception as e:
                print(f"Error in thread: {e}")
    
    # Update database with the new information
    if management_results:
        update_database_with_management_info(database_name, table_name, management_results)
        print(f"Successfully updated {len(management_results)} records with management information")
        
        # Export updated data to CSV
        export_updated_data_to_csv(database_name, table_name)
    else:
        print("No management information was successfully scraped")

def export_updated_data_to_csv(database_name, table_name, csv_filename='UpdatedFinalData.csv'):
    """Export the updated database to CSV"""
    db = dataset.connect(f'sqlite:///{database_name}')
    table = db[table_name]
    
    # Get all records
    rows = list(table.all())
    
    # Convert to DataFrame and save
    df = pd.DataFrame(rows)
    df.to_csv(csv_filename, index=False)
    print(f"Updated data exported to {csv_filename}")

# Main execution
if __name__ == "__main__":
    print("Starting management info scraping...")
    threading_management_scraper()
    print("Management info scraping completed!")