import pandas as pd
import dataset
import requests
from urllib.parse import urlparse
import time
import random
import os
import csv
import socket

proxy = "Write Your PRoxy Here"
proxies = {
    "http": f"http://{proxy}",
    "https": f"http://{proxy}"
}

def is_valid_domain(domain):
    
    try:
        socket.gethostbyname(domain)
    except socket.error:
        return False
    
    # Check HTTP response
    try:
        response = requests.get(f"http://{domain}", timeout=5)
        if response.status_code == 200:
            return True
    except requests.RequestException:
        return False

    return False

def fetch_archive_data(domain):
    url = f"http://web.archive.org/cdx/search/cdx?url={domain}/&matchType=host"
    response = requests.get(url)
    if response.status_code == 200:
        print(f"Initial Data has been saved by URL :{url}")
        return response.text.splitlines()
    return []

def scrape_data(lines, domain):
    index = 0
    data = []
    domain_folder = domain.replace('.', '_')
    
    if not os.path.exists(domain_folder):
        os.makedirs(domain_folder)
    
    for line in lines:
        try:
            parts = line.split()
            timestamp, url, mimetype, statuscode = parts[1], parts[2], parts[3], parts[4]
            if mimetype == 'text/html' and statuscode == '200':
                index += 1
                updatedurl = f"http://web.archive.org/web/{timestamp}/{url}"
                page_source = requests.get(updatedurl,proxies=proxies).text
                
                # Save the HTML content to a file
                file_name = f"{domain_folder}/{timestamp}_{index}.html"
                with open(file_name, 'w', encoding='utf-8') as file:
                    file.write(page_source)
                
                # Append the file path instead of the HTML content
                data.append({
                    'timestamp': timestamp,
                    'domain': domain,
                    'url': url,
                    'file_path': file_name
                })
                print(f"{index}-Data has been get and saved by URL:: {updatedurl}")
                # if index >= 10:
                #     break
                    # delay = random.uniform(1, 5)
                    # print(f"Waiting for {delay:.2f} seconds before next request")
                    # time.sleep(delay)
        except Exception as e:
            print(e)
    return data

def save_to_database(data, db_url):
    db = dataset.connect(db_url)
    table = db['web_archive']
    table.insert_many(data)

def load_from_database(db_url):
    db = dataset.connect(db_url)
    table = db['web_archive']
    return pd.DataFrame(table.all())

def main():
    try:
        domain = input("Enter a domain name:Just Write domian name without http like (saeedmdcat.com): ")
        if not is_valid_domain(domain):
            print("Invalid domain name. Please try again.")
            return
        domain_folder = domain.replace('.', '_')
        lines = fetch_archive_data(domain)
        if not lines:
            print("No data found for the domain.")
            return

        data = scrape_data(lines, domain)
        if not data:
            print("No valid HTML data found.")
            return

        save_to_database(data,f"sqlite:///{domain_folder}.db")
        df = load_from_database(f"sqlite:///{domain_folder}.db")
        
        # Save to CSV with file paths
        final_csv = f'{domain_folder}.csv'
        df.to_csv(final_csv, index=False, quoting=csv.QUOTE_ALL)

        print(f"Data has been saved to {domain_folder}.csv")
    except Exception as e:
        print(e)

if __name__ == "__main__":
    main()
