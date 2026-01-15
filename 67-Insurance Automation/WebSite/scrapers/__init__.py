"""
Insurance Scrapers Package
Contains scrapers for AXA, MCMA, RMA, and Sanlam insurance providers.
Easy to extend - just add new scrapers following the BaseScraper pattern.
"""

from .base import (
    BaseScraper, 
    InsurancePlan, 
    Guarantee,
    SelectableField,
    SelectOption,
    DurationType
)
from .axa_scraper import AXAScraper
from .mcma_scraper import MCMAScraper
from .rma_scraper import RMAScraper
from .sanlam_scraper import SanlamScraper

# Registry of all available scrapers
# Add new scrapers here to automatically include them
SCRAPER_REGISTRY = {
    'axa': AXAScraper,
    'mcma': MCMAScraper,
    'rma': RMAScraper,
    'sanlam': SanlamScraper,
}

def get_all_scrapers():
    """Get instances of all registered scrapers"""
    return [scraper_class() for scraper_class in SCRAPER_REGISTRY.values()]

def get_scraper(provider_code: str):
    """Get a specific scraper by provider code"""
    scraper_class = SCRAPER_REGISTRY.get(provider_code.lower())
    if scraper_class:
        return scraper_class()
    return None

__all__ = [
    # Base classes
    'BaseScraper',
    'InsurancePlan', 
    'Guarantee',
    'SelectableField',
    'SelectOption',
    'DurationType',
    
    # Scrapers
    'AXAScraper',
    'MCMAScraper',
    'RMAScraper',
    'SanlamScraper',
    
    # Registry and functions
    'SCRAPER_REGISTRY',
    'get_all_scrapers',
    'get_scraper'
]
