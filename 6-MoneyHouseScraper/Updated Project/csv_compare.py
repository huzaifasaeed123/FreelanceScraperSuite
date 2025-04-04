import pandas as pd

def compare_csvs(file1, file2):
    # Step 1: Read CSV files into DataFrames
    df1 = pd.read_csv(file1)
    df2 = pd.read_csv(file2)

    # Step 2: Convert df2 into a dictionary for fast lookup, handling duplicates
    df2_dict = {}
    for _, row in df2.iterrows():
        url = row["Url"]  # Replace "URL" with your actual column name
        url1=f"https://www.moneyhouse.ch/de/company/{url}"
        df2_dict[url1] = row.to_dict()  # Overwrite if duplicates exist

    matched = []
    unmatched = []

    # Step 3: Iterate through df1 and compare
    for _, row in df1.iterrows():
        url = row["Url"]  # Replace "URL" with your actual column name
        row_dict = row.to_dict()
        if url in df2_dict:
            # Combine rows from both DataFrames
            combined_row = {**row_dict, **df2_dict[url]}
            matched.append(combined_row)
        else:
            unmatched.append(row_dict)

    return matched, unmatched

# Example Usage
file1 = "FinalIndividualPages1.csv"
file2 = "ScrapedData.csv"

matched, unmatched = compare_csvs(file1, file2)

# Save matched and unmatched results to CSV files
pd.DataFrame(matched).to_csv("matched.csv", index=False)
pd.DataFrame(unmatched).to_csv("unmatched.csv", index=False)

print(f"Matched rows: {len(matched)}, Unmatched rows: {len(unmatched)}")
