import dataset
from seleniumbase import Driver
from time import sleep
import random
from parsel import Selector

driver = Driver(uc=True)

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

url = f"https://www.capterra.com/p/275802/Square-Point-of-Sale/reviews/"
driver.get(url)
check_for_blocks(driver)
input("Select Filter of any")
total_rating = 9170
iteration = int(total_rating / 25) + 2
print(f"Total Iteration is: {iteration} and total Rating is ")

for i in range(1, iteration):
    check_for_blocks(driver)
    print(f"Iteration No: {i}")
    
    try:
        random_number = random.randint(5, 7)
        sleep(random_number)
        print(f"Random Sleep Number: {random_number}")
        
        button = driver.find_element("css selector", '[data-testid="show-more-reviews"]')
        button.click()
        
        # Save the HTML content of the page after clicking the button
        html_content = driver.page_source
        with open("squarepoint.html", "w", encoding="utf-8") as f:
            f.write(html_content)
        print(f"HTML content saved to index4.html for iteration {i}")
        
    except Exception as e:
        print(e)
        continue
