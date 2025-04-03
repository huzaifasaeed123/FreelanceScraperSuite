import pandas as pd
from email_validator import validate_email, EmailNotValidError
from concurrent.futures import ThreadPoolExecutor, as_completed

# Function to validate email using email-validator library
def is_valid_email(email):
    try:
        # Validate the email and return True if it's valid
        validate_email(email)
        return 'Valid'
    except EmailNotValidError:
        return 'Not Valid'

# Function to validate emails concurrently using threading
def validate_emails_concurrently(emails):
    # Create a ThreadPoolExecutor for threading
    with ThreadPoolExecutor(max_workers=50) as executor:
        # Submit tasks for email validation
        futures = {executor.submit(is_valid_email, email): email for email in emails}
        
        # Collect the results as they are completed
        results = []
        for future in as_completed(futures):
            email = futures[future]
            try:
                results.append(future.result())
            except Exception as exc:
                print(f"Email validation generated an exception: {exc}")
                results.append('Not Valid')  # Mark as 'Not Valid' in case of any exception
        return results

# Function to process the CSV
def process_csv(file_path):
    # Load Excel file
    df = pd.read_excel(file_path)

    # Display columns and their indices for the user to select the email column
    print("Columns in the CSV file:")
    for index, column in enumerate(df.columns):
        print(f"{index}: {column}")

    # Get the user's choice of the email column index
    email_column_index = int(input("Enter the index of the column containing emails: "))
    email_column_name = df.columns[email_column_index]

    # Extract the email column as a list
    emails = df[email_column_name].tolist()

    # Validate emails concurrently and get validation results
    validation_results = validate_emails_concurrently(emails)

    # Add a new column to the dataframe with the validation results
    df['Validation_Status'] = validation_results

    # Save the updated dataframe to a new Excel file
    output_file = "Physcotherapist(Updated).xlsx"
    df.to_excel(output_file, index=False)
    print(f"Validation complete. Updated Excel saved as {output_file}")

# Example usage:
file_path = "Physcotherapist.xlsx"  # Replace with your actual Excel file path
process_csv(file_path)
