import requests
from parse import search, findall
from parsel import Selector
import dataset
from loguru import logger
from seleniumbase import Driver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from time import sleep
from bs4 import BeautifulSoup
import pandas as pd
import os


def retrive_span(soup, databind):
    span = soup.find("span", {"data-bind": f"text: {databind}"})
    if span:
        span_text = span.text.strip()
        return span_text
    return ""
def get_product_urls():
    sitemap_urls = [
        "https://www.bradleycaldwell.com/productSitemap.xml",
        "https://www.bradleycaldwell.com/productSitemap-2.xml",
    ]

    for url in sitemap_urls:
        logger.debug(f"Processing {url}")
        r = requests.get(url)
        for product_url in findall("<url><loc><![CDATA[{}]]></loc>", r.text):
            logger.info(f"Processing {product_url[0]}")
            db["products"].upsert({"url": product_url[0]}, ["url"])


database = "target_db3.db"
db = dataset.connect(f"sqlite:///{database}")
if not os.path.exists(database):
    print(
        f"DataBase with Named {database} have not been found For Url,So Now Scraping For Xml has been start"
    )
    get_product_urls()

unscraped_rows = list(db["products"].find(scraped=None))
print(f"Total Urls Remaining For Scraping{len(unscraped_rows)}")
db["products"].create_column_by_example("scraped", True)


driver = Driver(uc=True)
driver.get("https://www.bradleycaldwell.com/login")
sleep(10)
driver.find_element(By.LINK_TEXT, "SIGN IN").click()
sleep(10)


driver.find_element(By.ID, "side-login-1").send_keys("email")
driver.find_element(By.ID, "side-login-2").send_keys("password")
driver.find_element(By.LINK_TEXT, "LOGIN").click()

# get_product_urls()
# print(f"Here is the Total Length: {len(url_list)}")

while True:
    product = db["products"].find_one(scraped=None)
    if not product:
        break

    unscraped_rows = list(db["products"].find(scraped=None))

    # Get the length of those rows
    print(len(unscraped_rows))
    logger.info(f"Processing {product['url']}")
    driver.get(product["url"])

    # Wait for the <h1 class="product-name"> element to appear
    try:
        WebDriverWait(driver, 30).until(
            EC.presence_of_element_located((By.CLASS_NAME, "product-name"))
        )
    except Exception as e:
        logger.error(f"Error waiting for product element: {e}")
        continue
    sleep(2)
    # Store html in the database after the element has appeared
    db["data"].upsert({"url": product["url"], "html": driver.page_source}, ["url"])

    # Mark the product as scraped
    product.update({"scraped": True})
    db["products"].update(product, ["id"])



main_list = []
index = 0
for data in db["data"]:
    url = data["url"]
    index = index + 1
    print(index)
    # if index==100:
    #     break
    # print(url)
    html = data["html"]
    soup = BeautifulSoup(html, "html.parser")
    span_price_old = soup.find("span", class_="price-old")
    if span_price_old:
        old_price = span_price_old.text
    span_price_new = soup.find("span", class_="price-new")
    if span_price_new:
        new_price = span_price_new.text
    id = retrive_span(soup, "id")
    max_order_limit = retrive_span(soup, "x_bciOrderLimit")
    manufItemNumber = retrive_span(soup, "manufItemNumber")
    type = retrive_span(soup, "colorDesc")
    size = retrive_span(soup, "sizeDesc")
    upc_code = retrive_span(soup, "upcCode")
    orderMultQty = int(retrive_span(soup, "orderMultQty"))

    uom = retrive_span(soup, "uom")
    caseQty = retrive_span(soup, "caseQty")
    palletQty = retrive_span(soup, "palletQty")
    updated_div = soup.find("div", {"data-bind": "with: product"})
    all_p = updated_div.find_all("p")
    quantityonHand = map = suggested_retail = ""
    for p in all_p:
        # print("hi")
        if "Quantity on hand:" in p.text:
            span = p.find("span", recusive=False)
            if span:
                quantityonHand = span.text
        if "MAP:" in p.text:
            span = p.find("span", recusive=False)
            if span:
                map = span.text
        if "Suggested Retail:" in p.text:
            span = p.find("span", recusive=False)
            if span:
                suggested_retail = span.text
    h1 = soup.find("h1", class_="product-name")
    heading_name = ""
    if h1:
        heading_name = h1.text.strip()
    description = f"{heading_name} {type} {size}"
    if suggested_retail == "" or "$" not in suggested_retail:
        suggested_retail = "$0"
    if old_price == "" or "$" not in old_price:
        old_price = "$0"
    if new_price == "" or "$" not in new_price:
        new_price = "$0"
    total_retail = (
        float(suggested_retail.replace("$", "").replace(",", "")) * orderMultQty
    )
    total_dealer = float(old_price.replace("$", "").replace(",", "")) * orderMultQty
    total_show = float(new_price.replace("$", "").replace(",", "")) * orderMultQty
    obj = {
        "URL": url,
        "BCI": id,
        "MFG": manufItemNumber,
        "UPC": upc_code,
        "Qty": orderMultQty,
        "UOM": uom,
        "Description": description,
        "Retail": suggested_retail,
        "Total_Retail": f"${total_retail}",
        "Dealer": old_price,
        "Total_Dealer": f"${total_dealer}",
        "Show": new_price,
        "Total_Show": f"${total_show}",
        # Additonal Details if required
        "Maximum Order Quantity": max_order_limit,
        "Type": type,
        "Size": size,
        "Case Pack": caseQty,
        "Pallet Quantity": palletQty,
        "Quantity on Hand": quantityonHand,
        "MAP": map,
    }
    main_list.append(obj)

df = pd.DataFrame(main_list)
df.to_csv("BradelyData.csv", index=False)
df.to_excel("BradellyData.xlsx",index=False)
