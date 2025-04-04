# import dataset

# # File paths for the existing databases
# db1_path = "FinalDataBaseLocal.db"
# db2_path = "FinalDatabase2.db"

# # New database file path
# new_db_path = "Combine.db"

# # Connect to the first database and read its table
# db1 = dataset.connect(f'sqlite:///{db1_path}')
# table1_data = list(db1['FinalData'].all())  # Replace 'FinalTable1' with the actual table name
# print(len(table1_data))
# # Connect to the second database and read its table
# db2 = dataset.connect(f'sqlite:///{db2_path}')
# table2_data = list(db2['FinalData'].all())  # Replace 'FinalTable2' with the actual table name
# print(len(table2_data))
# print("Above and now updated below")
# # Connect to the new database
# new_db = dataset.connect(f'sqlite:///{new_db_path}')

# # Insert data from the first database into the new table in the new database
# new_table1 = new_db['Local']  # Table for data from FinalDataBase1.db
# new_table1.insert_many(table1_data)
# print(new_table1.count())
# # Insert data from the second database into another table in the new database
# new_table2 = new_db['MoneyHouse']  # Table for data from FinalDataBase2.db
# new_table2.insert_many(table2_data)
# print(new_table2.count())
# print(f"Data from {db1_path} and {db2_path} has been combined into {new_db_path}.")
import dataset

# File paths for the existing databases
db1_path = "FinalDataBaseLocal.db"
db2_path = "FinalDatabase2.db"

# New database file path
new_db_path = "Combine.db"

# Connect to the first database and read its table
db1 = dataset.connect(f'sqlite:///{db1_path}')
table1_data = list(db1['FinalData'].all())  # 'FinalData' exists
print(f"Rows in FinalData (FinalDataBaseLocal): {len(table1_data)}")

# Connect to the second database and read its table 'MoneyFinalData'
db2 = dataset.connect(f'sqlite:///{db2_path}')
if 'MoneyFinalData' in db2.tables:
    table2_data = list(db2['MoneyFinalData'].all())  # 'MoneyFinalData' exists
    print(f"Rows in MoneyFinalData (FinalDatabase2): {len(table2_data)}")
else:
    print("Table 'MoneyFinalData' does not exist in FinalDatabase2.db")

# Connect to the new database to combine the data
new_db = dataset.connect(f'sqlite:///Combine.db')

# Insert data from the first database into the new table in the new database
new_table1 = new_db['Local']  # Table for data from FinalDataBaseLocal.db
new_table1.insert_many(table1_data)
print(f"Rows in Local table (new database): {new_table1.count()}")

# Insert data from the second database into another table in the new database
new_table2 = new_db['MoneyHouse']  # Table for data from FinalDatabase2.db
new_table2.insert_many(table2_data)
print(f"Rows in MoneyHouse table (new database): {new_table2.count()}")

print(f"Data from {db1_path} and {db2_path} has been combined into {new_db_path}.")
