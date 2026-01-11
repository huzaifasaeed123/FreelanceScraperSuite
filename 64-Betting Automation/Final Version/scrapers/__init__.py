"""
Scrapers package
Contains individual scraper modules for each betting site
"""

from .netbet_genybet_olybet import scrape_netbet, scrape_genybet, scrape_olybet
from .betsson import scrape_betsson
from .parionssport import scrape_parionssport
from .pmu import scrape_pmu
from .unibet import scrape_unibet
from .winamax import scrape_winamax

__all__ = [
    'scrape_netbet',
    'scrape_genybet', 
    'scrape_olybet',
    'scrape_betsson',
    'scrape_parionssport',
    'scrape_pmu',
    'scrape_unibet',
    'scrape_winamax'
]
