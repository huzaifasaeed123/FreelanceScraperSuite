
import requests

# Specify the path to your CSV file
file_path = 'ScrapedData.csv'

# Use file.io API to upload the file
url = 'https://file.io'

# Open the file in binary mode
with open(file_path, 'rb') as file:
    response = requests.post(url, files={'file': file})

# Check if the request was successful
if response.status_code == 200:
    # Extract the link from the response
    download_link = response.json()['link']
    print(f'File uploaded successfully: {download_link}')
else:
    print(f'Failed to upload file. Status code: {response.status_code}')
