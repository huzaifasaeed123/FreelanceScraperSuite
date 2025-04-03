#FileName="1.scrap_urls.py"
#The Following Code is used to scrap all Medicine Urls with some additonal Information
#To Get all Medicine links,we are iterating over all alphabets with upto Specific Page No 
import requests
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed
import traceback
from alive_progress import alive_bar
import pandas as pd
# Function that makes the request, parses with BeautifulSoup, and returns the result
proxy = "http://adf1f9b7b95b8a8e4bcc__cr.sg:eb36@gw.dataimpulse.com:823"

proxies = {
    "http": proxy,
    "https": proxy
}
def retrieve_page(url):
    try:
        # Make request
        response = requests.get(url)
        
        # Check if the request is successful
        if response.status_code == 200:
            # Parse with BeautifulSoup
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Example: Extract title (modify as needed)
            title = soup.title.string if soup.title else "No title found"
            
            # Return the parsed data (you can return any parsed object here)
            return {"url": url, "title": title}
        else:
            print(f"Failed to retrieve {url}. Status code: {response.status_code}")
            return None
    except Exception as e:
        # Handle exceptions and print traceback
        print(f"Exception occurred while processing {url}")
        traceback.print_exc()
        return None
def save_to_csv_and_excel(data, file_name):
    """
    Function to save a list of dictionaries to both CSV and Excel files.
    
    Parameters:
    - data: List of dictionaries
    - file_name: The base file name (without extension) for saving CSV and Excel files
    """
    try:
        # Convert the list of dictionaries to a DataFrame
        df = pd.DataFrame(data)
        
        # Save as CSV
        csv_file = f"{file_name}.csv"
        df.to_csv(csv_file, index=False)
        print(f"Data successfully saved to {csv_file}")
        
        # Save as Excel
        excel_file = f"{file_name}.xlsx"
        df.to_excel(excel_file, index=False)
        print(f"Data successfully saved to {excel_file}")
        
    except Exception as e:
        print(f"Error occurred: {e}")
# Function to manage threading using ThreadPoolExecutor
def Threading_Page_Urls():
    processes = []
    results = []
    Missing=[]
    base_url = "https://www.1mg.com/pharmacy_api_gateway/v4/drug_skus/by_prefix"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
    }
    
    results = []
    with alive_bar(1000000) as bar:
        # Use ThreadPoolExecutor for threading
        with ThreadPoolExecutor(max_workers=20) as executor:
            alphabet_counts = {
    "a": 1300,"b": 400, "c": 1200, "d": 750, "e": 600, "f": 500, "g": 500, 
    "h": 183, "i": 266, "j": 81, "k": 233, "l": 600, "m": 900, "n": 600, 
    "o": 550, "p": 800, "q": 57, "r": 800, "s": 750, "t": 800, "u": 137, 
    "v": 420, "w": 106, "x": 88, "y": 33, "z": 333
}

            for letter, count in alphabet_counts.items():
                print(f"Count that we found for alphabet {letter} is {count}")
                for page in range(1, count+2):
                    params = {"prefix_term": letter, "page": page, "per_page": 30}
                    processes.append(executor.submit(fetch_1mg_data,params))
            # for prefix in "abcdefghijklmnopqrstuvwxyz":
            #         params1 = {"prefix_term": prefix, "page": 1, "per_page": 30}
            #         response1 = requests.get(base_url, headers=headers, params=params1, proxies=proxies)
                    
            #         if response1.status_code == 200:
            #             count=response1.json()["meta"]["total_count"]
            #             count= int(int(count)/30)
            #             print(f"Count that we found for alphabets {prefix} is {count}")
            #             for page in range(1, count):
            #                 params = {"prefix_term": prefix, "page": page, "per_page": 30}
            #                 processes.append(executor.submit(fetch_1mg_data,params))
            for task in as_completed(processes):
                if isinstance(task.result(), list): 
                    # with lock:
                    #         Scrapedtable.update({'Url': result['Url'], 'Scraped': True}, ['Url'])
                    #         UpdatedTable.insert(result)
                    results.extend(task.result())
                else:
                    Missing.append(task.result())
                    # print(result)
                bar()
    # Set the progress bar to match the number of URLs
    # with alive_bar(len(PageUrlsData)) as bar:
    #     # Use ThreadPoolExecutor for threading
    #     with ThreadPoolExecutor(max_workers=50) as executor:
    #         # Submit all tasks
    #         for index, url in enumerate(PageUrlsData):
    #             # print(obj['id'])
    #             # if index>=0 and index<=40000:
    #                 processes.append(executor.submit(retrieve_page, url,index))
    #             # else:
    #             #     break
    #         # Process the completed tasks
    #         for task in as_completed(processes):
    #             if isinstance(task.result(), dict): 
    #                 # with lock:
    #                 #         Scrapedtable.update({'Url': result['Url'], 'Scraped': True}, ['Url'])
    #                 #         UpdatedTable.insert(result)
    #                 results.append(task.result())
    #             else:
    #                 Missing.append(task.result())
    #                 # print(result)
    #             bar()  # Update the progress bar after each task is completed
    
    return results


def fetch_1mg_data(params):
    base_url = "https://www.1mg.com/pharmacy_api_gateway/v4/drug_skus/by_prefix"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
    }
    
    results = []
    check=0
    while(check==0):
        try:
            response = requests.get(base_url, headers=headers, params=params, proxies=proxies)
            print(params)
            if response.status_code == 200:
                json_data=response.json()['data']["skus"]
                for data in json_data:
                    # time.sleep(0.1)
                    results.append( {
                        "Name": data["name"],
                        "Link": f"https://www.1mg.com{data['slug']}",
                        "ID": data["id"],
                        "Price": data["price"],
                        "Type": data["type"],
                        "Short_Composition": data["short_composition"],
                        "Manufacturer_Name": data["manufacturer_name"],
                        "Marketer_Name": data["marketer_name"],
                        "Quantitiy": data["quantity"]
                    })
                check=1
                return results
                    
            else:
                print(f"Failed to fetch data for prefix {params['prefix_term']}, page {params['page']} with status code {response.status_code}")
        except Exception as e:
            print(f"Exception has been Occur as {e}")           
                
    
    return results
# Example usage
if __name__ == "__main__":
    # scraped_data = scrape_1mg_data()
    # df=pd.DataFrame([scraped_data])
    # df.to_excel("test2.xlsx",index=False)
    # print(scraped_data)
    url_data=Threading_Page_Urls()
    print(len(url_data))
    df=pd.DataFrame(url_data)
    df.to_excel("index2.xlsx")
