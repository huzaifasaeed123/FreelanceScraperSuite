import requests

proxy = "Write Your PRoxy Here"
proxies = {
    "http": f"http://{proxy}",
    "https": f"http://{proxy}"
}

def test_proxy(proxies):
    try:
        response = requests.get("http://saeedmdcat.com", proxies=proxies, timeout=10)
        response.raise_for_status()  # Raises an HTTPError for bad responses
        print("Proxy connection successful. Status code:", response.status_code)
    except requests.RequestException as e:
        print("Proxy connection failed. Error:", e)

if __name__ == "__main__":
    test_proxy(proxies)
