import dataset

# Connect to your SQLite database
db = dataset.connect('sqlite:///final_database.db')

# List all tables in the database
tables = db.tables
print("Tables:", tables)

# Loop through each table and print its columns
for table_name in tables:
    table = db[table_name]
    print(f"\nTable: {table_name}")
    print("Columns:", table.columns)
