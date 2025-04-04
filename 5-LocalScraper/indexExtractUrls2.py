import requests
import gzip
from lxml import etree  # lxml for better XPath and namespace handling
from io import BytesIO

def download_and_parse_all_xml():
    # Namespace for the XML files
    namespaces = {'sitemap': 'http://www.sitemaps.org/schemas/sitemap/0.9'}
    
    # List to store all the URLs across files
    all_urls = []
    
    # Iterate through integers 0 to 13 for the different .gz files
    for i in range(14):
        # Step 1: Download the .gz file from the URL
        url = f"https://www.local.ch/sitemaps/entries-business_de_{i}.xml.gz"
        response = requests.get(url)
        
        if response.status_code == 200:
            try:
                # Step 2: Extract the XML content from the .gz file
                with gzip.GzipFile(fileobj=BytesIO(response.content)) as gz_file:
                    xml_content = gz_file.read()

                # Step 3: Parse the XML content
                root = etree.fromstring(xml_content)
                print(f"Successfully parsed XML from integer {i}")

                # Step 4: Extract all <loc> URLs using the correct namespace
                urls = root.xpath('//sitemap:loc', namespaces=namespaces)
                
                # Append extracted URLs to the final list
                if urls:
                    all_urls.extend([url.text for url in urls])
                    print(len(all_urls))
                else:
                    print(f"No URLs found in XML from integer {i}")
            
            except etree.XMLSyntaxError as e:
                print(f"XML Syntax Error for integer {i}: {e}")
            except Exception as e:
                print(f"Error processing XML for integer {i}: {e}")
        else:
            print(f"Failed to download file for integer {i}")
    
    # Return the final list of all URLs
    return all_urls

# Call the function to get all URLs
urls = download_and_parse_all_xml()

# Print or process the collected URLs
# for url in urls:
#     print(url)
