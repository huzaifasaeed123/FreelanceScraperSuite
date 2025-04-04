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
database_dir = "G:/6-Python Scraping Code/Scraping_Class/Fiver Projects/MoneyHouseScraper/Databases"

# List of database files with .db extension
database_files = [
    "FinalData1.db", "FinalData2.db", "FinalData3.db", "FinalData4.db",
    "FinalData5.db", "FinalData6.db", "FinalData7.db", "FinalData8.db", "FinalData9.db",
    "FinalData10.db","FinalData11.db","FinalData12.db","FinalData13.db","FinalData14.db","FinalData15.db","FinalData16.db"
]

# Final combined database path
final_db_path = os.path.join(database_dir, "FinalDatabase2.db")

# Check if the directory and files exist
if not os.path.exists(database_dir):
    raise Exception(f"Directory does not exist: {database_dir}")

for db_file in database_files:
    db_path = os.path.join(database_dir, db_file)
    if not os.path.exists(db_path):
        raise Exception(f"Database file does not exist: {db_path}")

# Create/connect to the final database using dataset
db = dataset.connect(f'sqlite:///{final_db_path}')
UpdatedTable = db['MoneyFinalData']

# Combine data from each database and store it in a list
main_list = []
count=0
for db_file in database_files:
    db_path = os.path.join(database_dir, db_file)
    print(f"Processing {db_file}...")
    db = dataset.connect(f'sqlite:///{db_path}')
    table = db['FinalData']
    print(table.count())
    count=count+table.count()
    # Fetch all records from the current table and drop 'id' field
    records = [dict(record) for record in table.all()]
    for record in records:
        record.pop('id', None)  # Remove the 'id' field
    main_list.extend(records)
print(f"Total Count:{count}")
# Insert the combined data into the final database table
Final_updation_inDB(UpdatedTable, main_list)

# Export the final database table to a CSV file
csv_path = os.path.join(database_dir, "FinalDatabase2.csv")
df = pd.DataFrame(main_list)
df.to_csv(csv_path, index=False)

print(f"Databases combined and data exported to {csv_path}")
