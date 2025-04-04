import requests
import random
import datetime
from bs4 import BeautifulSoup
import os
import re
import concurrent.futures
import time
#Write date in following format YYYY-MM-DD ,Please Must Follow Date Sequence
#Start date must before the End_Date
Start_Date1='2024-06-20'  
End_Date1='2024-06-26'
#u have to adjust these two date according to your needs

def Complex_pdf_Download(initial_url,session,directory_name,file_name):
    time.sleep(2)
    base_url = "https://monitoruloficial.ro/"
    try:
        headers = {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
                                    "Accept-Encoding": "gzip, deflate, br, zstd",
                                    "Accept-Language": "en-US,en;q=0.9",
                                    "Cache-Control": "max-age=0",
                                    "Referer": f"https://monitoruloficial.ro/e-monitor/",
                                    "Sec-Ch-Ua": "\"Not/A)Brand\";v=\"8\", \"Chromium\";v=\"126\", \"Google Chrome\";v=\"126\"",
                                    "Sec-Ch-Ua-Mobile": "?0",
                                    "Sec-Ch-Ua-Platform": "\"Windows\"",
                                    "Sec-Fetch-Dest": "document",
                                    "Sec-Fetch-Mode": "navigate",
                                    "Sec-Fetch-Site": "same-origin",
                                    "Sec-Fetch-User": "?1",
                                    "Upgrade-Insecure-Requests": "1",
                                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
                                
        }
    
        response = session.get(initial_url, headers=headers)

        if response.status_code == 200:
            soup = BeautifulSoup(response.content, "html.parser")
            script_tag = soup.find("script", text=re.compile("var fid = '"))
            
            if script_tag:
                fid_match = re.search(r"var fid = '([^']+)'", script_tag.string)
                if fid_match:
                    fid = fid_match.group(1)

                    # Get Document Metadata
                    pdf_data_url = f"{base_url}ramo_customs/emonitor/gidf.php"
                    response = session.post(pdf_data_url, headers=headers,timeout=60, data={"fid": fid, "rand": "0.045363046087672165"})

                    if response.status_code == 200:
                        pdf_data = response.json()
                        doc_id = pdf_data.get('d')
                        folder_id = pdf_data.get('f')

                        if doc_id and folder_id:
                            # Construct Combined PDF URL
                            pdf_url = f"{base_url}ramo_customs/emonitor/showmo/services/view.php?doc={doc_id}&format=pdf&subfolder={folder_id}" 

                            # Download Combined PDF
                            pdf_response = session.get(pdf_url, headers=headers,stream=True,timeout=60)
                            # content_length = response.headers.get('Content-Length')
                            # print(response.headers)
                            # print(f"Content-Length: {content_length}")
                            # print("Request Successful")
                            # if int(content_length) > 5000000:
                            #     print("Skip that file due to its greatest size")
                            #     return
                            if pdf_response.status_code == 200:
                                if file_name.startswith('/'):
                                    file_name = file_name[1:]
                                #print(response.content)
                                if not os.path.exists(directory_name):
                                    os.makedirs(directory_name)
                                file_path = os.path.join(directory_name, file_name)
                                with open(f"{file_path}.pdf", "wb") as file:
                                    file.write(pdf_response.content)
                                print(f"PDF downloaded successfully! as name {file_path}")
                            else:
                                print(f"Failed to download combined PDF. Status code: {pdf_response.status_code}")
                        else:
                            print("Error: 'd' or 'f' values are missing in the response")
                    else:
                        print(f"Failed to get document metadata. Status code: {response.status_code}")        
                else:
                    print("Failed to extract fid value.")
            else:
                print("Failed to find the script tag containing the fid value.")
        else:
            print(f"Failed to fetch the initial page. Status code: {response.status_code}")
    except requests.exceptions.Timeout as e:
        print(f"Timeout occurred for: \n{e}")
    except requests.exceptions.RequestException as e:
        print(f"Failed to download the PDF due to a request exception.\n{e}")
    except Exception as e:
        print(f"Error has been occur: {e}")

def simple_download_pdf(url, session, directory_name, file_name):
    headers = {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
        "Accept-Encoding": "gzip, deflate, br, zstd",
        "Accept-Language": "en-US,en;q=0.9",
        "Cache-Control": "max-age=0",
        "Cookie": "_ga=GA1.1.1286714755.1719947054; sbjs_migrations=1418474375998%3D1; sbjs_current_add=fd%3D2024-07-02%2019%3A05%3A07%7C%7C%7Cep%3Dhttps%3A%2F%2Fmonitoruloficial.ro%2Fe-monitor%2F%7C%7C%7Crf%3Dhttps%3A%2F%2Fmonitoruloficial.ro%2F; sbjs_first_add=fd%3D2024-07-02%2019%3A05%3A07%7C%7C%7Cep%3Dhttps%3A%2F%2Fmonitoruloficial.ro%2Fe-monitor%2F%7C%7C%7Crf%3Dhttps%3A%2F%2Fmonitoruloficial.ro%2F; sbjs_current=typ%3Dtypein%7C%7C%7Csrc%3D%28direct%29%7C%7C%7Cmdm%3D%28none%29%7C%7C%7Ccmp%3D%28none%29%7C%7C%7Ccnt%3D%28none%29%7C%7C%7Ctrm%3D%28none%29%7C%7C%7Cid%3D%28none%29%7C%7C%7Cplt%3D%28none%29%7C%7C%7Cfmt%3D%28none%29%7C%7C%7Ctct%3D%28none%29; PHPSESSID=iv2a77a0lg369ntni1qoju46b9; sbjs_udata=vst%3D2%7C%7C%7Cuip%3D%28none%29%7C%7C%7Cuag%3DMozilla%2F5.0%20%28Windows%20NT%2010.0%3B%20Win64%3B%20x64%29%20AppleWebKit%2F537.36%20%28KHTML%2C%20like%20Gecko%29%20Chrome%2F126.0.0.0%20Safari%2F537.36; sbjs_session=pgs%3D5%7C%7C%7Ccpg%3Dhttps%3A%2F%2Fmonitoruloficial.ro%2Fcategorie-produse%2Feditura-monitorul-oficial%2Fcolectii-de-arta%2F; _ga_GH5JF2LV9N=GS1.1.1719949439.2.1.1719951477.59.0.0",
        "Priority": "u=0, i",
        "Referer": "https://monitoruloficial.ro/e-monitor/",
        "Sec-Ch-Ua": "\"Not/A)Brand\";v=\"8\", \"Chromium\";v=\"126\", \"Google Chrome\";v=\"126\"",
        "Sec-Ch-Ua-Mobile": "?0",
        "Sec-Ch-Ua-Platform": "\"Windows\"",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "same-origin",
        "Sec-Fetch-User": "?1",
        "Upgrade-Insecure-Requests": "1",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    }

    try:
        #print("Request going to be sent")
        response = session.get(url, headers=headers, stream=True, timeout=60)
        content_length = response.headers.get('Content-Length')
        print(f"Content-Length: {content_length}")
        #print("Request Successful")
        if int(content_length) > 5000000:
            #print("Skip that file due to its greatest size")
            return
        if response.status_code == 200:
            if file_name.startswith('/'):
                file_name = file_name[1:]

            if not os.path.exists(directory_name):
                os.makedirs(directory_name)

            file_path = os.path.join(directory_name, file_name)

            # Save the response content to a file
            with open(f"{file_path}.pdf", "wb") as file:
                file.write(response.content)
            print(f"PDF downloaded successfully as {file_path}.pdf")
        else:
            print("Failed to download the PDF.")
            print(response.status_code)
            print(response.content)

    except requests.exceptions.Timeout as e:
        print(f"Timeout occurred for: {url}\n{e}")
    except requests.exceptions.RequestException as e:
        print(f"Failed to download the PDF due to a request exception.\n{e}")
    except Exception as e:
        print(f"An unexpected error occurred.\n{e}")

def iterate_dates(start_date: str, end_date: str):
    """
    This function takes two dates in the format 'YYYY-MM-DD' and iterates over each date between them.

    :param start_date: The start date in 'YYYY-MM-DD' format.
    :param end_date: The end date in 'YYYY-MM-DD' format.
    :return: A generator that yields each date between start_date and end_date inclusive.
    """
    # Convert the string dates to datetime.date objects
    start_date_obj = datetime.datetime.strptime(start_date, '%Y-%m-%d').date()
    end_date_obj = datetime.datetime.strptime(end_date, '%Y-%m-%d').date()
    #print(start_date_obj)
    # Initialize the current date to the start date
    current_date = start_date_obj

    # Iterate until the current date is greater than the end date
    while current_date <= end_date_obj:
        yield current_date
        # Move to the next day
        current_date += datetime.timedelta(days=1)
        #print(current_date)

# Example usage
def scrape_html(html_content):
    """
    if u dont understand the flow then please see the docs attached with Project
    This function scrapes the given HTML content and extracts all href links below the 'ol' element within 'card-body' divs.
    Based on the number of 'card-body' divs, it performs specific actions.

    :param html_content: The HTML content to be scraped.
    :return: A list of extracted href links.
    """
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # Find all div elements with the class 'card-body'
    card_bodies = soup.find_all('div', class_='card-body')
    simple_pdf_link = []
    complex_pdf_link = []

    # Iterate through each 'card-body' div
    index=1
    for card_body in card_bodies:
        ol = card_body.find('ol', class_='breadcrumb')
        li_tag = ol.find('li', class_='breadcrumb-item active')
        a_tag_text = li_tag.find('a').get_text(strip=True)
        contains_part = 'Partea I' in a_tag_text or 'Partea a II-a' in a_tag_text
        if ol:
            ol.extract()
    # Ignore the 'ol' list
        if contains_part:
            # Extract all href links below the 'ol' list
            for a_tag in card_body.find_all('a', href=True):
                simple_pdf_link.append(a_tag['href'])
        else:
            for a_tag in card_body.find_all('a', href=True):
                complex_pdf_link.append(a_tag['href'])
        index+=1
   
    return [simple_pdf_link,complex_pdf_link]

def download_with_timeout(futures, timeout_duration):
    end_time = time.time() + timeout_duration  # Calculate end time for the timeout period
    for future in futures:
        remaining_time = max(0, end_time - time.time())  # Calculate time remaining
        try:
            future.result(timeout=remaining_time)  # Wait with adjusted timeout
        except concurrent.futures.TimeoutError:
            print(f"Timeout occurred for {future.link}. Skipping to next download.")

def main(start_date,endDate):
    max_workers = 5
    session=requests.Session()
    for date in iterate_dates(start_date,endDate):
        print(date)

        # URL for the POST request
        url = "https://monitoruloficial.ro/ramo_customs/emonitor/get_mo.php"

        # Generate a random float for the rand parameter
        rand_value = random.random()

        # Define the payload with the required parameters
        payload = {
            "today": date,  # Use the current date or the date required by your application
            #"rand": 0.35411579494818035
        }
        headers = {
            "Accept": "*/*",
            "Accept-Encoding": "gzip, deflate, br, zstd",
            "Accept-Language": "en-US,en;q=0.9",
            "Content-Length": "40",
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "Cookie": "_ga=GA1.1.1286714755.1719947054; sbjs_migrations=1418474375998%3D1; sbjs_current_add=fd%3D2024-07-02%2019%3A05%3A07%7C%7C%7Cep%3Dhttps%3A%2F%2Fmonitoruloficial.ro%2Fe-monitor%2F%7C%7C%7Crf%3Dhttps%3A%2F%2Fmonitoruloficial.ro%2F; sbjs_first_add=fd%3D2024-07-02%2019%3A05%3A07%7C%7C%7Cep%3Dhttps%3A%2F%2Fmonitoruloficial.ro%2Fe-monitor%2F%7C%7C%7Crf%3Dhttps%3A%2F%2Fmonitoruloficial.ro%2F; sbjs_current=typ%3Dtypein%7C%7C%7Csrc%3D%28direct%29%7C%7C%7Cmdm%3D%28none%29%7C%7C%7Ccmp%3D%28none%29%7C%7C%7Ccnt%3D%28none%29%7C%7C%7Ctrm%3D%28none%29%7C%7C%7Cid%3D%28none%29%7C%7C%7Cplt%3D%28none%29%7C%7C%7Cfmt%3D%28none%29%7C%7C%7Ctct%3D%28none%29; sbjs_first=typ%3Dtypein%7C%7C%7Csrc%3D%28direct%29%7C%7C%7Cmdm%3D%28none%29%7C%7C%7Ccmp%3D%28none%29%7C%7C%7Ccnt%3D%28none%29%7C%7C%7Ctrm%3D%28none%29%7C%7C%7Cid%3D%28none%29%7C%7C%7Cplt%3D%28none%29%7C%7C%7Cfmt%3D%28none%29%7C%7C%7Ctct%3D%28none%29; sbjs_udata=vst%3D1%7C%7C%7Cuip%3D%28none%29%7C%7C%7Cuag%3DMozilla%2F5.0%20%28Windows%20NT%2010.0%3B%20Win64%3B%20x64%29%20AppleWebKit%2F537.36%20%28KHTML%2C%20like%20Gecko%29%20Chrome%2F126.0.0.0%20Safari%2F537.36; sbjs_session=pgs%3D1%7C%7C%7Ccpg%3Dhttps%3A%2F%2Fmonitoruloficial.ro%2Fe-monitor%2F; PHPSESSID=iv2a77a0lg369ntni1qoju46b9; _ga_GH5JF2LV9N=GS1.1.1719947054.1.1.1719947190.60.0.0",
            "Origin": "https://monitoruloficial.ro",
            "Priority": "u=1, i",
            "Referer": "https://monitoruloficial.ro/e-monitor/",
            "Sec-Ch-Ua": '"Not/A)Brand";v="8", "Chromium";v="126", "Google Chrome";v="126"',
            "Sec-Ch-Ua-Mobile": "?0",
            "Sec-Ch-Ua-Platform": '"Windows"',
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-origin",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
            "X-Requested-With": "XMLHttpRequest"
        }
        # Make the POST request
        response = session.post(url,headers=headers, data=payload)

        list=scrape_html(response.content)
        base_url=f"https://monitoruloficial.ro"
        
        for simple_link in list[0]:
            url=f"{base_url}{simple_link}"
            #print("fdfd")
            simple_download_pdf(url,session,date.strftime('%Y-%m-%d'),simple_link)
        #print("Complex PDF Downloading Start")
        
        for complex_link in list[1]:
            url=f"{base_url}{complex_link}"
            #print(url)
            Complex_pdf_Download(url,session,date.strftime('%Y-%m-%d'),complex_link)
        
        #break #use to limit for testing and check for only one day
if __name__ == "__main__":
    main(Start_Date1, End_Date1)
    