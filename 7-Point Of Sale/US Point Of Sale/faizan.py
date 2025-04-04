import requests
from bs4 import BeautifulSoup
import time

# Proxy credentials and server
proxy_username = 'geonode_UORFX4YaMz'
proxy_password = '76c2002d-e7ad-4bce-a31f-2c04ee0d93a2'
proxy_host = 'dedicate-residential.geonode.com'
proxy_port = 1000

# Proxy URL with authentication
proxy_url = f"http://{proxy_username}:{proxy_password}@{proxy_host}:{proxy_port}"

# Proxies dictionary for requests
proxies = {
    'http': proxy_url,
    'https': proxy_url,
}

for i in range(0, 100):
    try:
        # Make the request through the proxy
        response = requests.get('http://httpbin.org/ip', proxies=proxies)
        response.raise_for_status()  # Ensure successful response

        # Parse the IP from the response
        ip_soup = BeautifulSoup(response.text, 'html.parser')
        ip_text = ip_soup.text
        print(f"IP Address for session {i}: {ip_text}")

    except requests.exceptions.RequestException as e:
        print(f"Error during request for session {i}: {e}")

    time.sleep(2)
