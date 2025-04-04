import os
import dataset
import pandas as pd

def Final_updation_inDB(UpdatedTable, data_list):
    try:
        UpdatedTable.insert_many(data_list)
        print("Done Insertion of Updated Database")
    except Exception as e:
        print(f"Error during insertion: {e}")

# Directory where your databases are stored
database_dir = "G:/6-Python Scraping Code/Scraping_Class/Fiver Projects/LocalScraper/Databases"

# List of database files with .db extension
database_files = [
    "ScrapedData1.db", "ScrapedData2.db", "ScrapedData3.db", "ScrapedData4.db",
    "ScrapedData5.db", "ScrapedData6.db", "ScrapedData7.db", "ScrapedData8.db", "ScrapedData9.db",
    "ScrapedData10.db","ScrapedData11.db","ScrapedData12.db",
]

# Final combined database path
final_db_path = os.path.join(database_dir, "FinalDatabase.db")

# Create/connect to the final database using dataset
db = dataset.connect(f'sqlite:///{final_db_path}')
UpdatedTable = db['LocalFinalData']

# Combine data from each database and store it in a list
main_list = []

for db_file in database_files:
    db_path = os.path.join(database_dir, db_file)
    db = dataset.connect(f'sqlite:///{db_path}')
    table = db['LocalFinalData']
    print(db_file)
    # Fetch all records from the current table and drop 'id' field
    records = [dict(record) for record in table.all()]
    for record in records:
        record.pop('id', None)  # Remove the 'id' field
    main_list.extend(records)

# Insert the combined data into the final database table
Final_updation_inDB(UpdatedTable, main_list)

# Export the final database table to a CSV file
csv_path = os.path.join(database_dir, "FinalDatabase.csv")
df = pd.DataFrame(main_list)
df.to_csv(csv_path, index=False)

print(f"Databases combined and data exported to {csv_path}")
