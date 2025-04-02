import pandas as pd

# Define the file paths
input_file = "IndianProjectSample1.csv"
output_file = "updatedIndianProjectSample11.csv"

# Specify the columns to update
columns_to_update = ['Indian Employees','Total Employees']

# Process the file in chunks
chunk_size = 100000  # Adjust this to balance speed and memory usage

def process_chunk(chunk):
    # Replace NaN with an empty string
    chunk.fillna('', inplace=True)
    
    # Add single quotes around the values of the specified columns
    for column in columns_to_update:
        if column in chunk.columns:
            chunk[column] = "'" + chunk[column].astype(str) + "'"
    return chunk

# Initialize the writing process
with pd.read_csv(input_file, chunksize=chunk_size) as reader:
    for i, chunk in enumerate(reader):
        processed_chunk = process_chunk(chunk)
        
        # Write to output file (append mode after first chunk)
        if i == 0:
            processed_chunk.to_csv(output_file, index=False, mode='w')
        else:
            processed_chunk.to_csv(output_file, index=False, mode='a', header=False)

print("CSV processing complete!")