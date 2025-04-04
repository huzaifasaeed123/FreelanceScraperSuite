from botasaurus.request import request, Request
from botasaurus import bt
from loguru import logger
from parsel import Selector
import dataset
import pandas as pd

logger.info('building database dataframe')
db = dataset.connect('sqlite:///scraped_data.db')

@request(
    output_formats=[bt.Formats.EXCEL],
    parallel=5,
    cache=True,
    proxy='http://5.79.66.2:13010',
    max_retry=3,
    retry_wait=2
)
def add_management(request: Request, link):
    logger.info(link)
    r = request.get(link)
    sel = Selector(r.text)

    item = dict()
    item['url'] = link
    try:
        item['name'] = sel.xpath('//h1/text()').get(default='').strip()
        item['neueste Verwaltungsräte'] = ', '.join(sel.xpath('//h4[text()="neueste Verwaltungsräte"]/following-sibling::p/a/text()').getall())
        logger.info(f"{item['name']}: {item['neueste Verwaltungsräte']}")
        db['mh_management'].upsert(item, ['url'])
    except Exception as e:
        logger.error(f"Error parsing: {link}: {e}")
        item['neueste Mitglieder der Verwaltung'] = None

    return item


# urls = 'https://www.moneyhouse.ch/de/company/adp-toiture-sa-11979961541'
while True:
    q = """select * from MoneyHouse left join main.mh_management mm on MoneyHouse.Url = mm.url where mm.name is null;"""
    df = pd.DataFrame([x for x in db.query(q)])
    logger.debug(f"Found {len(df)} records")
    urls = df['Url'].tolist()
    try:
        add_management(urls)
    except Exception as e:
        logger.error(f"Error: {e}")
