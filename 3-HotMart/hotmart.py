'''
New project # 2:

https://hotmart.com/es/marketplace/productos/seminariosonline/G7457141A

data to collect:
name: Mauricio Duque Zuluaga
course: 🔥 Seminarios.Online®
link: https://hotmart.com/es/marketplace/productos/seminariosonline/G7457141A
email: See Below

Then we need the email:
1) Add product to cart.
2) Under the buy button, there is a link:
"¿Tienes dudas sobre el producto? Ponte en contacto"
3) If you click the link, it shows the email address in an image format. The same email is available in the html, in a json object. No need to use OCR.

Getting product links:
The sitemap has the products. The customer states that there are 1,554,684 products. I am clarifying if they only want the spanish products (the 'en' in https://hotmart.com/es/marketplace/productos).
'''
import requests
from bs4 import BeautifulSoup
import json
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
import traceback
from alive_progress import alive_bar
import pandas as pd
import dataset
import time

proxy = {
    "http": "http://your-proxy-address:port",
    "https": "http://your-proxy-address:port",
}


def differentiate_urls(url):
    # Split the URL by '/'
    parts = url.split("/")

    # Find the index of 'categorias'
    try:
        index = parts.index("categorias")

        # Check the number of segments after 'categorias'
        if (
            len(parts) > index + 2 and parts[index + 2]
        ):  # Two segments after 'categorias'
            return True
        elif (
            len(parts) > index + 1 and parts[index + 1]
        ):  # One string after 'categorias'
            return False
        else:
            print(f"{url} -> Invalid format or not enough segments")
    except ValueError:
        print(f"'categorias' not found in {url}")


def retrive_page(url, index, bar):
    try:
        category_one = category_two = course = name = email = "Not Found"
        # url="https://hotmart.com/es/marketplace/productos/seminariosonline/G7457141A"
        product_id = url.split("/")[-1]
        # print(product_id)
        response = requests.get(url)
        if response.status_code == 200:
            soup = BeautifulSoup(response.content, "html.parser")
            # creater_div=soup.find("div",class_='creator_info')
            # name_div=creater_div.find("div",class_="_font-weight-bold")
            # name=name_div.text.strip()

            # Now Scrap Course Name

            h1=soup.find('h1',class_="redesigned-main-title")
            course=h1.text.strip()
            print(course)
            title_list = soup.find("title").text.split("-")
            lenght_title=len(title_list)
            # print(title_list)
            if len(title_list) == 1:
                 # course = title_list[0].split("|")[0].strip()
                 name = "Not Found"
            elif len(title_list)==2:
                # course = title_list[0]
                name = title_list[1].split("|")[0].strip()
            else:
                name=title_list[lenght_title-1].split("|")[0].strip()
            all_a = soup.find_all("a")
            for a in all_a:
                href = a.get("href")
                if href and "https://hotmart.com/es/marketplace/categorias" in href:
                    if differentiate_urls(href):
                        category_two = a.text
                    else:
                        category_one = a.text
                    # Do nothing for now

            # print(f"category_one: {category_one}")
            # print(f"category_two: {category_two}")
            # print(f"course:: {course}")
            # print(f"name:: {name}")
        else:
            print(
                f"Main Link Request has been failed with status code:{response.status_code}"
            )
            bar()
            return url
        response_email = requests.get(
            f"https://pay.hotmart.com/{product_id}?sck=HOTMART_PRODUCT_PAGE"
        )
        if response_email.status_code == 200:
            soup = BeautifulSoup(response_email.content, "html.parser")
            script = soup.find("script", type="application/json", id="__NUXT_DATA__")
            email_pattern = r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"

            # Search for email addresses in the text
            emails_match = re.search(email_pattern, script.text)

            if emails_match:
                email = emails_match.group(0)
            else:
                print("No email address found.")
                # bar()
                # return url
        else:
            print("Email Request Not Successfull")
            bar()
            return url

        obj = {
            "Url": url,
            "course": course,
            "name": name,
            "Email": email,
            "Main Category": category_one,
            "Sub Category": category_two,
        }
        print(f"Page Threading Reached at {index}")
        bar()
        return obj
    except Exception as e:
        print(url)
        traceback.print_exc()
        bar()
        return url


def Threading_Page_Urls(PageUrlsData):
    processes = []
    results = []
    Missing = []
    # Set the progress bar to match the number of URLs
    with alive_bar(len(PageUrlsData)) as bar:
        # Use ThreadPoolExecutor for threading
        with ThreadPoolExecutor(max_workers=8) as executor:
            # Submit all tasks
            for index, url in enumerate(PageUrlsData):
                # print(obj['id'])
                # if index>=115000:
                processes.append(executor.submit(retrive_page, url, index, bar))
            # else:
            #     break
            # Process the completed tasks
            for task in as_completed(processes):
                if isinstance(task.result(), dict):
                    # with lock:
                    #         Scrapedtable.update({'Url': result['Url'], 'Scraped': True}, ['Url'])
                    #         UpdatedTable.insert(result)
                    results.append(task.result())
                else:
                    Missing.append(task.result())
                    # print(result)
    return [results, Missing]


def download_and_parse_all_xml():
    url_list = []

    # Counter for URLs containing "es/marketplace/"
    es_marketplace_count = 0

    # Iterate over the range from 1 to 40
    for index in range(1, 41):
        # Construct the URL
        sitemap_url = f"https://hotmart.com/product-page/public/sitemap/ae6b0e92-a8c1-40d1-92ed-28d4bbc5b603/sitemap_page_{index}.xml"
        print(f"Processing Sitemap Xml File ::{sitemap_url}")
        # Fetch the content of the XML file
        response = requests.get(sitemap_url)
        xml_content = response.content

        # Parse the XML content using BeautifulSoup
        soup = BeautifulSoup(xml_content, "xml")

        # Find all <loc> tags and extract their text content (the URLs)
        for loc in soup.find_all("loc"):
            url = loc.text
            # Check if the URL contains "es/marketplace/"
            if "es/marketplace/" in url:
                es_marketplace_count += 1
                url_list.append(url)

    return url_list


def final_updation_inDB(UpdatedTable, list):
    UpdatedTable.insert_many(list)
    print("Done Insertionion of Updated Database")


def export_table_to_csv_and_excel(db_table, common_filename):
    """
    Function to export a database table to both CSV and Excel files.

    Parameters:
    - db_table: The dataset table object containing the data.
    - common_filename: The common name for the CSV and Excel files (without extension).
    """
    # Fetch all data from the database table
    data = list(db_table.all())

    # Convert the data into a Pandas DataFrame
    df = pd.DataFrame(data)

    # Export to CSV with UTF-8 encoding
    csv_filename = f"{common_filename}.csv"
    df.to_csv(csv_filename, index=False, encoding="utf-8")
    print(f"Data successfully exported to {csv_filename} (UTF-8)")

    # Export to Excel
    excel_filename = f"{common_filename}.xlsx"
    df.to_excel(excel_filename, index=False)
    print(f"Data successfully exported to {excel_filename}")


def create_Missing_txt(output_file, urls):
    with open(output_file, "w") as file:
        for url in urls:
            file.write(url + "\n")


def extract_urls_from_file(filename):
    urls = []
    try:
        # Open the file in read mode
        with open(filename, "r") as file:
            # Read each line in the file
            for line in file:
                # Strip any leading/trailing whitespace and add the line to the list if it's not empty
                url = line.strip()
                if url:
                    urls.append(url)
        return urls
    except FileNotFoundError:
        print(f"File {filename} not found.")
        return []
    except Exception as e:
        print(f"An error occurred: {e}")
        return []


def main():
    db = dataset.connect(f"sqlite:///HotMartMissing.db")
    updatedTable = db["FinalData"]
    time.sleep(5)
    # ScrapedData=read_db_to_dict_list(Scrapedtable)
    urls=download_and_parse_all_xml()
    # urls = extract_urls_from_file("MainMissing.txt")
    print(len(urls))
    combineList = Threading_Page_Urls(urls)
    time.sleep(30)
    final_updation_inDB(updatedTable, combineList[0])
    create_Missing_txt("Missing2.txt", combineList[1])
    finalDataName = "HotMartMissing"
    export_table_to_csv_and_excel(updatedTable, finalDataName)


main()
