import dataset

# Connect to the source database
source_db = dataset.connect('sqlite:///bc_products.db')  # Replace with your actual source DB URI

# Connect to the target database
target_db = dataset.connect('sqlite:///target_db.db')  # Replace with your actual target DB URI

# Fetch all rows from the source where 'scraped' is None
products = source_db['products'].find(scraped=None)

# Insert the fetched rows into the target database
for product in products:
    # Assuming the same table structure in target_db
    target_db['products'].insert(dict(product))

print("Data transferred successfully!")
