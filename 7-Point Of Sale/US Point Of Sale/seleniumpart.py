
import dataset
from seleniumbase import Driver
from time import sleep
import random
from parsel import Selector
driver = Driver(uc=True)
# driver.get("https://www.capterra.com/p/135040/Revel-iPad-POS/reviews/")
# sleep(10)
# sleep(10)
def check_for_blocks(driver):
    sleep(3)
    block_sel = Selector(text=driver.page_source)
    if 'www.capterra.com' in block_sel.xpath('//h1/text()').get(default='') != '':
        input('bypass any blocks')

    block_sel = Selector(text=driver.page_source)
    if block_sel.xpath('//div[@class="px-captcha-header"]/text()').get(default='') == 'Before we continue...':
        input('bypass any blocks')

    block_sel = Selector(text=driver.page_source)
    
    # Check for the h2 tag with the text "See how this software works with your current tools"
    if block_sel.xpath('//h2[contains(text(), "See how this software works with your current tools")]').get() is not None:
        input('bypass any blocks')
db = dataset.connect('sqlite:///webpages2.db')

# Table to store the URLs and HTML content
table = db['pages']
review_table = db['review']
unscraped_rows = table.all(scraped=False,type=1)
for product in unscraped_rows:
    url=f"https://www.capterra.com/{product['url']}"
    print(url)
    if product['id']>7:
        print(f"Processing {product['url']}")
        url=f"https://www.capterra.com/{product['url']}"
        driver.get(url)
        check_for_blocks(driver)
        # print("Huzaifa Saeed")
        iteration=int(product['total_rating']/25)+2
        print(f"Total Iteration is:{iteration} and total Rating is {product['total_rating']}")
        for i in range(1,iteration):
            check_for_blocks(driver)
            print(f"Iteration No:  {i}")
            try:
                random_number = random.randint(7, 15)
                sleep(random_number)
                print(f"Random Sleep Number: {random_number}")
                button = driver.find_element("css selector", '[data-testid="show-more-reviews"]')
                button.click()
            except Exception as e:
                print(e)
                continue
        random_number = random.randint(1,3)
        sleep(random_number)
        # Store html in the database after the element has appeared
        db["review"].upsert({"url": product["url"], "html": driver.page_source}, ["url"])
        # Mark the product as scraped
        product.update({"scraped": True})
        table.update(product, ["id"])

