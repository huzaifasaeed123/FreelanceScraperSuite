"""
Scrapers package
Contains individual scraper modules for each betting site
"""

from .netbet_genybet_olybet import scrape_netbet, scrape_genybet, scrape_olybet
from .betsson import scrape_betsson
from .parionssport import scrape_psel
from .pmu import scrape_pmu
from .unibet import scrape_unibet
from .winamax import scrape_winamax
from .browser_manager import browser_manager

__all__ = [
    'scrape_netbet',
    'scrape_genybet',
    'scrape_olybet',
    'scrape_betsson',
    'scrape_psel',
    'scrape_pmu',
    'scrape_unibet',
    'scrape_winamax',
    'browser_manager'
]
