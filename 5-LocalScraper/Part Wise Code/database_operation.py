# import dataset

# # Source databases
# db1 = dataset.connect('sqlite:///Final_MoneyHouse.db')
# db2 = dataset.connect('sqlite:///Final_LocalCh.db')

# # New combined database
# db_combined = dataset.connect('sqlite:///Final_Combined.db')

# # Mapping: source_db -> table_name -> new_table_name in combined DB
# tables_to_copy = [
#     (db1, 'FinalData', 'Money_house'),   # from DatabaseA.db
#     (db2, 'LocalFinalData', 'Local_ch')    # from DatabaseB.db
# ]

# for source_db, source_table, target_table in tables_to_copy:
#     src_table = source_db[source_table]
#     rows = list(src_table.all())

#     if rows:
#         # Insert into new database under new table name
#         dest_table = db_combined[target_table]
#         dest_table.insert_many(rows)
#         print(f"✅ Copied {len(rows)} rows from {source_table} → {target_table}")

# print("🎯 Final combined database created successfully: FinalCombined.db")


# import sqlite3

# # Connect to database
# conn = sqlite3.connect("Final_Combined.db")
# cursor = conn.cursor()

# # Create matched table if not exists
# cursor.execute("""
# CREATE TABLE IF NOT EXISTS matched (
#     id INTEGER PRIMARY KEY AUTOINCREMENT,
#     local_id INTEGER,
#     money_id INTEGER
# )
# """)
# conn.commit()

# # Fetch data
# cursor.execute("SELECT id, Name FROM Money_house")
# money_data = cursor.fetchall()

# cursor.execute("SELECT id, Name FROM Local_ch")
# local_data = cursor.fetchall()

# # Create a dictionary for fast lookup (lowercase names → id)
# money_dict = {}
# for mid, mname in money_data:
#     if mname:
#         money_dict[mname.strip().lower()] = mid

# matches = []

# # Compare Local_ch names against dictionary
# for lid, lname in local_data:
#     if lname:
#         mid = money_dict.get(lname.strip().lower())
#         if mid:
#             matches.append((lid, mid))

# # Insert matched records in batch
# cursor.executemany("INSERT INTO matched (local_id, money_id) VALUES (?,?)", matches)
# conn.commit()
# conn.close()

# print(f"Inserted {len(matches)} matches into 'matched' table.")

# import sqlite3

# conn = sqlite3.connect("Final_Combined.db")
# cursor = conn.cursor()

# # Rename tables
# cursor.execute("ALTER TABLE Local_ch RENAME TO Local")
# cursor.execute("ALTER TABLE Money_house RENAME TO MoneyHouse")

# conn.commit()
# conn.close()

# print("Tables renamed successfully!")
#Coulmn Splitting appraoch
import dataset

# Connect to your database
# Example for SQLite: db = dataset.connect('sqlite:///mydatabase.db')
# Replace with your actual DB connection string
db = dataset.connect('sqlite:///Final_Combined.db')

table = db['MoneyHouse']

# Step 1: Add columns if they don't exist
# dataset doesn't have direct "ALTER TABLE" but we can do raw SQL
db.query('ALTER TABLE MoneyHouse ADD COLUMN "Präsident" TEXT')
db.query('ALTER TABLE MoneyHouse ADD COLUMN "Leiter der Zweigniederlassungen" TEXT')

# Step 2: Iterate and update rows
for row in table.all():
    rechtsform = row.get('Rechtsform 2(Extra For Testing)')
    president_value = row.get('President/Leader')

    update_data = {}
    if rechtsform == 3:
        update_data['Präsident'] = president_value
    elif rechtsform == 9:
        update_data['Leiter der Zweigniederlassungen'] = president_value

    if update_data:
        table.update(
            dict(id=row['id'], **update_data),  # Assuming your table has primary key 'id'
            ['id']
        )

print("Table 'MoneyHouse' updated successfully!")


#Updated Matching Appraoch


# import sqlite3
# import re

# # Regex to extract postal code from Local_ch URL
# def extract_postal_code(url):
#     match = re.search(r"/(\d{4})/", url)
#     return match.group(1) if match else None

# # Connect to database
# conn = sqlite3.connect("Final_Combined.db")
# cursor = conn.cursor()

# # Create matched table if not exists
# cursor.execute("""
# CREATE TABLE IF NOT EXISTS matched (
#     id INTEGER PRIMARY KEY AUTOINCREMENT,
#     local_id INTEGER,
#     money_id INTEGER
# )
# """)
# conn.commit()

# # Fetch Money_house data (id, name, PLZ)
# cursor.execute("SELECT id, Name, PLZ FROM MoneyHouse")
# money_data = cursor.fetchall()

# # Build dictionary: name -> list of (money_id, plz)
# money_dict = {}
# for mid, mname, plz in money_data:
#     if mname and plz:
#         key = mname.strip().lower()
#         money_dict.setdefault(key, []).append((mid, str(plz)))

# # Fetch Local_ch data (id, name, url)
# cursor.execute("SELECT id, Name, Url FROM Local")
# local_data = cursor.fetchall()

# matches = []
# seen_pairs = set()  # To track already matched (money_id, postal_code)

# # Compare Local_ch with Money_house
# for lid, lname, url in local_data:
#     if not (lname and url):
#         continue

#     key = lname.strip().lower()
#     local_plz = extract_postal_code(url)

#     if key in money_dict:
#         for mid, money_plz in money_dict[key]:
#             # Check postal code match
#             if local_plz and local_plz == money_plz:
#                 pair = (mid, local_plz)  # Unique combination
#                 if pair not in seen_pairs:
#                     matches.append((lid, mid))
#                     seen_pairs.add(pair)  # Mark as already matched
#                 break  # ✅ Stop after first valid Local_ch match for this money_id
# # Insert matched records in batch
# if matches:
#     cursor.executemany("INSERT INTO matched (local_id, money_id) VALUES (?,?)", matches)
#     conn.commit()

# conn.close()
# print(f"Inserted {len(matches)} matches into 'matched' table.")





