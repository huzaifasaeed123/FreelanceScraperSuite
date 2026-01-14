"""
Base Scraper Module
Provides base classes and data structures for all insurance scrapers
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from enum import Enum
import json


class DurationType(Enum):
    """Duration type for insurance coverage"""
    ANNUAL = "annual"  # 12 months
    SEMI_ANNUAL = "semi_annual"  # 6 months


@dataclass
class SelectOption:
    """Represents a selectable option (e.g., different coverage amounts)"""
    id: Any
    label: str
    is_default: bool = False
    
    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "label": self.label,
            "is_default": self.is_default
        }


@dataclass
class SelectableField:
    """Represents a field with multiple selectable options"""
    name: str
    title: str
    options: List[SelectOption] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        return {
            "name": self.name,
            "title": self.title,
            "options": [opt.to_dict() for opt in self.options]
        }


@dataclass
class Guarantee:
    """Represents a single guarantee/coverage"""
    name: str
    code: str = None
    description: str = None
    capital: float = None
    franchise: str = None
    prime_annual: float = 0
    is_included: bool = True
    is_obligatory: bool = False
    is_optional: bool = False
    order: int = 0
    
    # For guarantees with selectable options
    has_options: bool = False
    options: List[SelectOption] = field(default_factory=list)
    selected_option: Any = None
    
    def to_dict(self) -> Dict:
        result = {
            "name": self.name,
            "code": self.code,
            "description": self.description,
            "capital": self.capital,
            "franchise": self.franchise,
            "prime_annual": self.prime_annual,
            "is_included": self.is_included,
            "is_obligatory": self.is_obligatory,
            "is_optional": self.is_optional,
            "order": self.order
        }
        
        if self.has_options:
            result["has_options"] = True
            result["options"] = [opt.to_dict() for opt in self.options]
            result["selected_option"] = self.selected_option
            
        return result


@dataclass
class InsurancePlan:
    """
    Complete insurance plan representation with all details
    """
    provider: str
    provider_code: str
    plan_name: str
    plan_code: str = None
    
    # Annual pricing (12 months)
    prime_net_annual: float = 0
    taxes_annual: float = 0
    prime_total_annual: float = 0
    
    # Semi-annual pricing (6 months)
    prime_net_semi_annual: float = 0
    taxes_semi_annual: float = 0
    prime_total_semi_annual: float = 0
    
    # Additional fees
    cnpac: float = 0
    accessoires: float = 0
    timbre: float = 0
    tax_parafiscal: float = 0
    
    # Guarantees
    guarantees: List[Guarantee] = field(default_factory=list)
    
    # Selectable fields (e.g., Bris de glace amount)
    selectable_fields: List[SelectableField] = field(default_factory=list)
    
    # Display properties
    color: str = "#3B82F6"
    is_promoted: bool = False
    is_eligible: bool = True
    order: int = 0
    
    # Extra metadata
    extra_info: Dict[str, Any] = field(default_factory=dict)
    
    def get_price(self, duration: DurationType = DurationType.ANNUAL) -> float:
        """Get total price based on duration"""
        if duration == DurationType.SEMI_ANNUAL:
            return self.prime_total_semi_annual
        return self.prime_total_annual
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "provider": self.provider,
            "provider_code": self.provider_code,
            "plan_name": self.plan_name,
            "plan_code": self.plan_code,
            
            # Annual pricing
            "annual": {
                "prime_net": self.prime_net_annual,
                "taxes": self.taxes_annual,
                "prime_total": self.prime_total_annual,
                "cnpac": self.cnpac,
                "accessoires": self.accessoires,
                "timbre": self.timbre,
                "tax_parafiscal": self.tax_parafiscal
            },
            
            # Semi-annual pricing
            "semi_annual": {
                "prime_net": self.prime_net_semi_annual,
                "taxes": self.taxes_semi_annual,
                "prime_total": self.prime_total_semi_annual
            },
            
            # Guarantees
            "guarantees": [g.to_dict() for g in self.guarantees],
            
            # Selectable fields
            "selectable_fields": [sf.to_dict() for sf in self.selectable_fields],
            
            # Display
            "color": self.color,
            "is_promoted": self.is_promoted,
            "is_eligible": self.is_eligible,
            "order": self.order,
            
            # Extra
            "extra_info": self.extra_info
        }
    
    def to_db_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for database storage"""
        return {
            "provider_name": self.provider,
            "plan_name": self.plan_name,
            "plan_code": self.plan_code,
            "prime_net_annual": self.prime_net_annual,
            "taxes_annual": self.taxes_annual,
            "prime_total_annual": self.prime_total_annual,
            "prime_net_semi_annual": self.prime_net_semi_annual,
            "taxes_semi_annual": self.taxes_semi_annual,
            "prime_total_semi_annual": self.prime_total_semi_annual,
            "cnpac": self.cnpac,
            "accessoires": self.accessoires,
            "timbre": self.timbre,
            "is_promoted": self.is_promoted,
            "is_eligible": self.is_eligible,
            "color": self.color,
            "plan_order": self.order
        }


class BaseScraper(ABC):
    """
    Abstract base class for all insurance scrapers.
    New scrapers should inherit from this class.
    """
    
    # Override these in subclasses
    PROVIDER_NAME: str = "Unknown"
    PROVIDER_CODE: str = "unknown"
    PROVIDER_LOGO: str = ""
    PROVIDER_COLOR: str = "#3B82F6"
    
    def __init__(self):
        self.last_error: Optional[str] = None
        self.raw_response: Any = None
        self.fetch_time: float = 0
    
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
            "code": self.PROVIDER_CODE,
            "logo": self.PROVIDER_LOGO,
            "color": self.PROVIDER_COLOR
        }
    
    def get_raw_response(self) -> Any:
        """Get the raw API response for database storage"""
        return self.raw_response
