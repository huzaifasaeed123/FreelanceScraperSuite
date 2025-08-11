import dataset
import requests
from parsel import Selector  # This is a library for parsing HTML and XML documents. I use it rather than BS4 because it's faster.


def get_links():
    """
    Get all links from a website, adding the links to the database to scrape.
    """
    url = 'https://www.website.com'
    r = requests.get(url)
    sel = Selector(r.text)
    for link in sel.xpath('//a/@href').getall():
        db['pages'].upsert({'url': link}, ['url'])


def parse_page(html):
    """
    Parse all the data from each page, storing the data in the database.
    """
    sel = Selector(html)
    item = dict()
    item['title'] = sel.xpath('//title').get()

    db['data'].upsert(item, ['title'])


db = dataset.connect('sqlite:///database.db')
db['pages'].create_column_by_example('scraped', True)  # This makes sure the scraped column is in the database with the right type.
get_links()

# This works with a single thread, but if you are using threads, the for loop with cause problems.
for page in db['pages'].find(scraped=None):
    # We select the unscraped links from the database and parse them.
    response = requests.get(page['url'])
    parse_page(response.text)
    db['pages'].update({'url': page['url'], 'scraped': True}, ['url'])

# To access the database from multiple places at once (threads), it's better to select one item at a time.
while True:
    page = db['pages'].find_one(scraped=None)
    if page is None:
        break

    # We select the unscraped links from the database and parse them.
    response = requests.get(page['url'])
    parse_page(response.text)
    db['pages'].update({'url': page['url'], 'scraped': True}, ['url'])

"""
The idea behind this approach is that it records your progress as it's being scraped. 
When I give this code to a client, I don't know if they will have a bad internet connection, bad computer, etc. 
But, I do know that they can keep restarting the program until it finishes.
It keeps me from having to create a program and troubleshoot their computer issues.

In cases where the website is difficult to scrape, I will store the page html in a database, 
and separate the parse step so that it works with the stored html, and not the website directly.

In either case, storing the data in the database at each step is the key to making sure the program 
can be restarted at any time without lost efforts.
"""