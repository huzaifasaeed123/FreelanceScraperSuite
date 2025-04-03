from seleniumwire import webdriver  # Import from seleniumwire
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
import json
import gzip
import pandas as pd
import json
# Set up Chrome options
search1="asset"
search2=""
outputfile=f"{search1} {search2}.xlsx"
#initial_url = f"https://register.fca.org.uk/s/search?q={search1}%20{search2}&location=Exeter%2C%20UK&geocodes=ChIJp41J1MRSbEgRHq3fayXjdqk&type=Companies&sortby=status"  # Replace with the actual URL where the link is located
initial_url = f"https://register.fca.org.uk/s/search?q={search1}&location=Bristol%2C%20UK&geocodes=ChIJYdizgWaDcUgRH9eaSy6y5I4&type=Companies&sortby=status"  # Replace with the actual URL where the link is located

def targeted_ids(id,driver,data_list):
    url=f"https://register.fca.org.uk/s/firm?id={id}"
    driver.get(url)
    time.sleep(10)
    driver.implicitly_wait(30)
    for request in driver.requests:
        #print(f"RequestUrl {request.url}")
        if "https://register.fca.org.uk/s/sfsites/aura?r=" in request.url and "&other.ShPo_LEX_Reg_FirmDetail.initMethod" in request.url:
            if request.response:
                if request.response.body:
                    #print("Request has been arrived")
                    decompressed_data = gzip.decompress(request.response.body)
                    # Decode the JSON   
                    json_data = json.loads(decompressed_data.decode('utf-8'))
                    for acc_detail in json_data['actions']:
                        if acc_detail["state"]=="SUCCESS" and acc_detail["returnValue"]:
                            if not isinstance(acc_detail["returnValue"], list):
                                if "accnt" in acc_detail["returnValue"]:
                                    Additional_details={}
                                    FirstName=LastName=Company_Name="Not Available"
                                    #print(acc_detail["returnValue"]["accnt"]["Name"])
                                    Company_Name=acc_detail["returnValue"]["accnt"]["Name"]
                                    if "ComplaintContact" in acc_detail["returnValue"] and "FirstName" in acc_detail["returnValue"]["ComplaintContact"] and acc_detail["returnValue"]["ComplaintContact"]["FirstName"]:
                                        FirstName=acc_detail["returnValue"]["ComplaintContact"]["FirstName"]
                                    if "ComplaintContact" in acc_detail["returnValue"] and "LastName" in acc_detail["returnValue"]["ComplaintContact"] and acc_detail["returnValue"]["ComplaintContact"]["LastName"]:
                                        LastName=acc_detail["returnValue"]["ComplaintContact"]["LastName"]
                                    if "principalAddress" in acc_detail["returnValue"] and acc_detail["returnValue"]["principalAddress"]:
                                        Additional_details=acc_detail["returnValue"]["principalAddress"]
                                    Personal_data={
                                        #"Url": url,
                                        "Firm": Company_Name,
                                        "FirstName":FirstName, 
                                        "LastName": LastName,
                                        "Search Phares": f"{search1} {search2}"
                                    }
                                    #print(Personal_data) 
                                    Personal_data.update(Additional_details)
                                    data_list.append(Personal_data)



def Scrap_Pages(data_list,driver):
    index=0
    for request in driver.requests:
        if "https://register.fca.org.uk/s/sfsites/aura?r=" in request.url and "&other.ShPo_LEX_Reg_Search.getFirmDetails=1" in request.url:
            index+=1
            print(index),"HDsudsf"
            # if index>22:
            if request and request.response and request.response.body:
                decompressed_data = gzip.decompress(request.response.body)
                # Decode the JSON
                json_data = json.loads(decompressed_data.decode('utf-8'))
                
                for acc_detail in json_data['actions'][0]['returnValue']['accDetails']:
                    try:
                        index+=1
                        # if index >219:
                        if acc_detail["colour"]=="blue":
                            print(acc_detail["acc"]["Id"])
                            print(index)
                            id=acc_detail["acc"]["Id"]
                            targeted_ids(id,driver,data_list)
                    except Exception as e:
                        print("Exception has been Occur during page scraping APIs",e)

def makeExcel(data_list):
    df = pd.DataFrame(data_list)

    # Remove duplicate rows
    df.drop_duplicates(inplace=True)
    # Save the DataFrame to a CSV file
    df.to_excel(outputfile, index=False)

    print("CSV file created successfully.")
def main():
    data_list=[]
    # def initial_request():
    chrome_options = webdriver.ChromeOptions()
    # chrome_options.add_argument("--headless") 
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--ignore-certificate-errors")  # Add this option
    chrome_options.add_argument("--allow-running-insecure-content")
    # #chrome_options.add_argument("--headless")  
    seleniumwire_options = {
        'verify_ssl': False
    }
    # Set up the WebDriver
    driver = webdriver.Chrome(options=chrome_options)

    # Navigate to the initial page
    driver.get(initial_url)

    # Wait for the page to load
    driver.implicitly_wait(30)  # Wait up to 10 seconds for elements to be available
    Button = WebDriverWait(driver, 20).until(
                EC.element_to_be_clickable((By.XPATH, '//*[@id="modal-content-id-1"]/footer/div/button[3]'))
            )
    driver.implicitly_wait(30)
    time.sleep(5)
    Button.click()
    time.sleep(2)
    
    while True:
        try:
            link_element = WebDriverWait(driver, 20).until(
                EC.element_to_be_clickable((By.XPATH, '//*[@id="-pagination-next-btn"]'))
            )
            if link_element.get_attribute('disabled'):
                print("Button is disabled. Stopping the process.")
                break
            link_element.click()
            print("Button Got Clicked")
            time.sleep(5)
            # WebDriverWait(driver, 10).until(
            #         EC.presence_of_element_located((By.XPATH, '//*[@id="-pagination-next-btn"]'))
            #     )
        except Exception as e:
            print(f"An error occurred: {e}")
            break

    Scrap_Pages(data_list,driver)

    makeExcel(data_list)

    driver.implicitly_wait(10)

if __name__ == "__main__":
    main()

