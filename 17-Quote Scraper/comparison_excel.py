import pandas as pd

# Load the CSV files into pandas DataFrames
file1 = 'QouteThreadingDied.csv'
file2 = 'QouteAllData.csv'

# Try reading the files with different encodings
encodings = ['utf-8', 'latin1', 'ISO-8859-1', 'cp1252']

# Load the data with 'latin1' encoding
df1 = pd.read_csv(file1, encoding="latin1")
df2 = pd.read_csv(file2, encoding="latin1")

# Ensure the columns used for comparison are unique by appending suffixes
df1.columns = [f"{col}_file1" for col in df1.columns]
df2.columns = [f"{col}_file2" for col in df2.columns]

# Extract the key columns without suffixes for easy access
key_column_df1 = df1.columns[7]
key_column_df2 = df2.columns[12]

# Create a hash map for the second DataFrame based on the key column
df2_dict = df2.set_index(key_column_df2).T.to_dict('list')

# Initialize lists for matches and non-matches
match_rows = []
unmatch_rows = []

# Iterate over each row in the first DataFrame
for index, row in df1.iterrows():
    # Get the value of the key column
    key = row[key_column_df1]
    
    # Check if the key exists in the hash map of the second DataFrame
    if key in df2_dict:
        # Combine the rows if a match is found
        matching_row = pd.Series(df2_dict[key], index=df2.columns)
        combined_row = pd.concat([row, matching_row])
        match_rows.append(combined_row)
    else:
        # Append the row to the unmatch list if no match is found
        unmatch_rows.append(row)

# Convert lists to DataFrames
match_df = pd.DataFrame(match_rows)
unmatch_df = pd.DataFrame(unmatch_rows)

# Save the matches and non-matches to new CSV files
match_df.to_csv('match.csv', index=False)
unmatch_df.to_csv('unmatch.csv', index=False)

print('Comparison completed. Results saved to match.csv and unmatch.csv.')
