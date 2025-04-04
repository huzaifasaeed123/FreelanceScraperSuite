import pandas as pd
import os

# Define the folder containing the Excel files (use an absolute path)
folder_path = 'First Round/'

# Verify that the folder exists
if not os.path.exists(folder_path):
    raise FileNotFoundError(f"The folder at {folder_path} does not exist.")

# Get a list of all Excel files in the folder
files = [f for f in os.listdir(folder_path) if f.endswith('.csv')]

# List to hold the dataframes
dataframes = []

# Loop through each file, read it into a dataframe, and append it to the list
for file in files:
    print(file)
    if file=="QouteData(550k-750k)k.csv":
        # file_path = os.path.join(folder_path, file)
        # df = pd.read_csv(file_path,encoding="utf-8")
        # dataframes.append(df)
        continue
    else:
        file_path = os.path.join(folder_path, file)
        df = pd.read_csv(file_path)
        dataframes.append(df)

# Concatenate all dataframes into a single dataframe
combined_df = pd.concat(dataframes, ignore_index=True)

# Save the combined dataframe to a CSV file
combined_df.to_csv('Newcombined_data.csv', index=False)
