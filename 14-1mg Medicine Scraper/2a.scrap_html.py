#File Name=2a.scrap_html.py
#The Following Code used the Medicine links and related Information that we scraped previously  from scrap_urls.py file
#Then this code hit on each medicine links and store the html content in Database
#The Following Code used the Multi-Threading Approach and Proxies
import pandas as pd
import requests
import dataset
import requests
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed
import traceback
from alive_progress import alive_bar
import pandas as pd
import threading
lock = threading.Lock()

proxy= "http://791149d37c1c6ba881cb__cr.ca,in,cl,au:8e900@gw.dataimpulse.com:823"

proxies = {
    "http": proxy,
    "https": proxy
}
# Database setup
db = dataset.connect("sqlite:///MedicineMain2.db")  # Change this for other DBs
table = db["Scraped"]

def read_excel_to_dict(file_name):
    """Reads the Excel file and converts it to a list of dictionaries."""
    df = pd.read_excel(file_name)
    return df.to_dict(orient="records")




def process_single_entry(entry):
    """Processes a single entry: fetch HTML and store in DB."""
    link = entry.get("Link")
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
    }
    check=0
    while(check==0):
        try:
            response = requests.get(link,headers=headers, proxies=proxies) 
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, "html.parser")
                soup=soup.find(id="container")
                entry["Html_Content"]=str(soup)
                check=1
                return  entry # Return the HTML content
            else:
                print(f"Request Faied with status code:{response.status_code}")
        except Exception as e:
            print(f"Failed to fetch {link}: {e}")


# Function to manage threading using ThreadPoolExecutor
def Threading_Page_Urls(PageUrlsData):
    processes = []
    results = []
    Missing=[]
    # Set the progress bar to match the number of URLs
    with alive_bar(3000) as bar:
        # Use ThreadPoolExecutor for threading
        with ThreadPoolExecutor(max_workers=20) as executor:
            # Submit all tasks
            for entry in PageUrlsData:
                # print(obj['id'])
                index=entry["index"]
                if index>=127500 and index<130000:
                    processes.append(executor.submit(process_single_entry, entry))
                # else:
                #     break
            # Process the completed tasks
            for task in as_completed(processes):
                if isinstance(task.result(), dict): 
                    data=task.result()
                    with lock:
                            # table.update({'Url': result['Url'], 'Scraped': True}, ['Url'])
                            table.insert(data)
                            print(f'Index Reached At successfully :{data["index"]}')
                    # results.append(task.result())
                # else:
                #     Missing.append(task.result())
                    # print(result)
                bar()  # Update the progress bar after each task is completed
    
   

# Main execution
file_name = "index2.xlsx"
data_dict = read_excel_to_dict(file_name)
Threading_Page_Urls(data_dict)
#127538
