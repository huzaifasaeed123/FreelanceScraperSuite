import pandas as pd

def compare_csv_and_save_result(file1, file2, output_file, encoding='utf-8'):
    """
    Compare the first column of two CSV files, and save rows from the first file 
    that do not exist in the second file to a new CSV file.

    Parameters:
    file1 (str): The path to the first CSV file.
    file2 (str): The path to the second CSV file.
    output_file (str): The path to the output CSV file where the result will be saved.
    encoding (str): The encoding to use for reading the CSV files.

    Returns:
    None
    """
    # Load the CSV files into DataFrames
    df1 = pd.read_csv(file1, encoding=encoding)
    df2 = pd.read_csv(file2, encoding=encoding)
    
    # Ensure both DataFrames have the first column named the same for comparison
    col1 = df1.columns[0]
    col2 = df2.columns[0]
    
    # Find rows in df1 where the first column value does not exist in df2's first column
    result_df = df1[~df1[col1].isin(df2[col2])]
    
    # Save the result to a new CSV file
    result_df.to_csv(output_file, index=False)

# Example usage
file1 = 'OveralIds.csv'
file2 = 'main1.csv'
output_file = 'result.csv'

compare_csv_and_save_result(file1, file2, output_file, encoding='latin1')
