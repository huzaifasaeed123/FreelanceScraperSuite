import pandas as pd

def remove_quotes_from_column_excel(file_path, column_name='Mitarbeiter'):
    # Read the Excel file into a DataFrame
    print("zzzzzzzzzzzzzzzzzzzzzr")
    df = pd.read_excel(file_path)
    print("zzzzzzzzzzzzzzzzzzzzzr")
    # Convert DataFrame to a list of dictionaries (each row as a dictionary)
    rows = df.to_dict(orient='records')
    print(len(rows))
    print(len(rows)[0])
    # Iterate over the list and update the column Mitarbeiter
    for row in rows:
        if column_name in row and isinstance(row[column_name], str):
            row[column_name] = row[column_name].replace("'", "")  # Remove single quotes

    # Convert list back to DataFrame
    updated_df = pd.DataFrame(rows)

    # Optionally, write the updated DataFrame back to a new Excel file
    updated_df.to_csv('updated_' + file_path, index=False)

# Example usage
remove_quotes_from_column_excel('FinalData1.xlsx')
