import os
from lxml import etree
import dataset
# Directory containing XML files
def ParseXml():
    directory = 'G:/6-Python Scraping Code/Scraping_Class/Fiver Projects/LocalScraper/Files'

    # Prepare the list of file names in proper order
    files = [f"entries-business_de_{i}.xml" for i in range(14)]

    # List to hold all URLs
    all_urls = []

    # Namespace dictionary
    namespaces = {
        'sitemap': 'http://www.sitemaps.org/schemas/sitemap/0.9'
    }

    # Iterate through each file, parse, and extract URLs
    for file_name in files:
        file_path = os.path.join(directory, file_name)
        
        # Check if the file exists
        if not os.path.isfile(file_path):
            print(f"File {file_name} does not exist.")
            continue
        
        # Step 1: Read and parse the XML file
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                raw_content = file.read()
                print(f"Reading file: {file_name}")
                print("File content preview:", raw_content[:200])  # Print the first 200 characters of the file for debugging
            
            # Parse the XML content
            tree = etree.fromstring(raw_content.encode('utf-8'))
            root = tree
            print(f"Successfully parsed file: {file_name}")

            # Step 2: Extract all <loc> URLs using the correct namespace
            urls = root.xpath('//sitemap:loc', namespaces=namespaces)
            if not urls:
                print(f"No URLs found in file: {file_name}")
            for url in urls:
                all_urls.append(url.text)
                # print("Extracted URL:", url.text)

        except etree.XMLSyntaxError as e:
            print(f"XML Syntax Error in file {file_name}: {e}")
        except Exception as e:
            print(f"Error in file {file_name}: {e}")

    return all_urls

def converttoTxt(all_urls):
# Step 3: Print all extracted URLs
    if all_urls:
        print("jfgfdgkdfjkgjdf")
        # print("\nAll Extracted URLs:")
        # for url in all_urls:
        #     print(url)

        # Write the URLs to a text file
        output_file = 'extracted_urls.txt'
        with open(output_file, 'w', encoding='utf-8') as f:
            for url in all_urls:
                f.write(url + '\n')
        print(f"All URLs have been written to {output_file}")
    else:
        print("No URLs were extracted.")

def coonvert_to_db(all_urls):
    db = dataset.connect(f'sqlite:///ScrapedData.db')
    # Create or connect to the 'scraped_data' table
    table = db['LocalUrls']
    data_to_insert = [{"Url": url,"Scraped":False} for url in all_urls]
    try:
        # Insert the entire list at once using insert_many
        table.insert_many(data_to_insert)
    except Exception as e:
        print(f"Error during database insertion: {e}")
    finally:
        db.commit()  # Ensure data is committed to the database


def main():
    #Parse All XML Files placed in Local Directoy to get All url
    all_urls=ParseXml()
    #Create a txt files from Parsed URL
    # converttoTxt(all_urls)

    #Convert Url to DataBase

    coonvert_to_db(all_urls)

if __name__ == "__main__":
    main()


