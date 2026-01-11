"""
Base scraper class providing common functionality for all insurance scrapers.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List
from dataclasses import dataclass
import json


@dataclass
class InsurancePlan:
    """Standardized insurance plan representation"""
    provider: str
    plan_name: str
    annual_premium: float
    taxes: float
    total_price: float
    guarantees: List[str]
    color: str = "#3B82F6"
    is_promoted: bool = False
    extra_info: Dict[str, Any] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "provider": self.provider,
            "plan_name": self.plan_name,
            "annual_premium": self.annual_premium,
            "taxes": self.taxes,
            "total_price": self.total_price,
            "guarantees": self.guarantees,
            "color": self.color,
            "is_promoted": self.is_promoted,
            "extra_info": self.extra_info or {}
        }


class BaseScraper(ABC):
    """Abstract base class for all insurance scrapers"""
    
    PROVIDER_NAME: str = "Unknown"
    PROVIDER_LOGO: str = ""
    PROVIDER_COLOR: str = "#3B82F6"
    
    def __init__(self):
        self.last_error: str = None
        self.raw_response: Dict = None
    
    @abstractmethod
    def fetch_quotes(self, params: Dict[str, Any]) -> List[InsurancePlan]:
        """
        Fetch insurance quotes based on provided parameters.
        
        Args:
            params: Dictionary containing:
                - valeur_neuf: New vehicle value
                - valeur_venale: Current vehicle value
                
        Returns:
            List of InsurancePlan objects
        """
        pass
    
    @abstractmethod
    def _parse_response(self, response_data: Any) -> List[InsurancePlan]:
        """Parse API response into standardized InsurancePlan objects"""
        pass
    
    def get_provider_info(self) -> Dict[str, str]:
        """Get provider metadata"""
        return {
            "name": self.PROVIDER_NAME,
            "logo": self.PROVIDER_LOGO,
            "color": self.PROVIDER_COLOR
        }
