import requests
from bs4 import BeautifulSoup

# Define the range of integers
sitemap_range = range(1, 65)

# List to store all the URLs containing 'overviews'
url_list = []

# Base URL pattern
base_url = "https://www.ambitionbox.com/sitemap-{}-v0.xml"

# Iterate over each integer to generate the sitemap URL
for i in sitemap_range:
    # Generate the sitemap URL
    sitemap_url = base_url.format(i)
    
    # Request the sitemap XML
    response = requests.get(sitemap_url)
    print(sitemap_url)
    if response.status_code == 200:
        # Parse the XML using BeautifulSoup
        soup = BeautifulSoup(response.content, 'xml')
        
        # Extract all URLs from <loc> tags
        loc_tags = soup.find_all('loc')
        
        # Filter URLs that contain 'overviews'
        for loc in loc_tags:
            url = loc.text
            if 'ambitionbox.com/overview/' in url:
                url_list.append(url)
        print(len(url_list))
    else:
        print(f"Failed to retrieve {sitemap_url}")
print(len(url_list))
# Write all the collected URLs to a text file
with open('urls_with_overviews.txt', 'w') as file:
    for url in url_list:
        file.write(url + '\n')

print(f"Scraping complete! Collected {len(url_list)} URLs containing 'overviews'.")
