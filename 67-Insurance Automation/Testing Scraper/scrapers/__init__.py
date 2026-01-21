"""
Insurance Scrapers Package
Contains scrapers for AXA, MCMA, RMA, and Sanlam insurance providers.
Simple functional style - each scraper has a main function to call.
"""

# Import the main scraper functions
from .axa_scraper import scrape_axa, fetch_axa_quotation
from .mcma_scraper import scrape_mcma, create_mcma_subscription, get_mcma_packs
# from .rma_scraper import scrape_rma, fetch_rma_offers
from .sanlam_scraper import scrape_sanlam, fetch_all_formulas

# Import base classes (kept for compatibility with existing code)
from .base import (
    BaseScraper,
    InsurancePlan,
    Guarantee,
    SelectableField,
    SelectOption,
    DurationType
)

# Registry of scraper functions
SCRAPER_FUNCTIONS = {
    'axa': scrape_axa,
    'mcma': scrape_mcma,
    # 'rma': scrape_rma,
    'sanlam': scrape_sanlam,
}

def get_scraper_function(provider_code: str):
    """Get a specific scraper function by provider code"""
    return SCRAPER_FUNCTIONS.get(provider_code.lower())

def get_all_scraper_codes():
    """Get all available scraper provider codes"""
    return list(SCRAPER_FUNCTIONS.keys())

__all__ = [
    # Base classes
    'BaseScraper',
    'InsurancePlan',
    'Guarantee',
    'SelectableField',
    'SelectOption',
    'DurationType',

    # Scraper functions
    'scrape_axa',
    'scrape_mcma',
    'scrape_rma',
    'scrape_sanlam',

    # Individual scraper functions
    'fetch_axa_quotation',
    'create_mcma_subscription',
    'get_mcma_packs',
    'fetch_rma_offers',
    'fetch_all_formulas',

    # Registry
    'SCRAPER_FUNCTIONS',
    'get_scraper_function',
    'get_all_scraper_codes'
]
