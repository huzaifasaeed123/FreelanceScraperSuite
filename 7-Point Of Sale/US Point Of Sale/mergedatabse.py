import dataset

# Connect to both SQLite databases
db1 = dataset.connect('sqlite:///webpages2.db')
db2 = dataset.connect('sqlite:///webpages3.db')

# Create or connect to the final database where merged data will be stored
final_db = dataset.connect('sqlite:///final_database.db')

# Access the tables from the first and second databases
table1 = db1['review']   # First database table
table2 = db2['pages']   # Second database table

# Create a new table in the final database to store the merged data
final_table = final_db['merged_listings']

# Merge the tables on the 'url' column
for row1 in table1:
    # Find matching row in the second table based on 'url'
    row2 = table2.find_one(url=row1['url'])
    
    if row2:  # If there's a match
        # Combine both rows into one dictionary
        merged_row = {**row1, **row2}
        
        # Insert the merged row into the final table
        final_table.insert(merged_row)

print("Merged rows have been inserted into the 'merged_listings' table in the final database.")
