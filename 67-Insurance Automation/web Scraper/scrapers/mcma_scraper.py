"""
MCMA Insurance Scraper
Based on original mcma.py - fetches quotations from MAMDA-MCMA API
"""

import requests
import json
from typing import Dict, Any, List

from .base import BaseScraper, InsurancePlan


class MCMAScraper(BaseScraper):
    """MAMDA-MCMA insurance quotation scraper"""
    
    PROVIDER_NAME = "MAMDA-MCMA"
    PROVIDER_LOGO = "https://www.mamda-mcma.ma/themes/custom/mamda/logo.svg"
    PROVIDER_COLOR = "#2fd0a7"
    
    SUBSCRIPTION_URL = "https://bo-sel.mamda-mcma.ma/api/subscriptions"
    
    def __init__(self):
        super().__init__()
        self.session = requests.Session()
        self.subscription_id = None
        self.auth_token = None
    
    def _get_headers(self) -> Dict[str, str]:
        """Get base request headers"""
        return {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "Mozilla/5.0"
        }
    
    def _get_auth_headers(self) -> Dict[str, str]:
        """Get authenticated request headers"""
        return {
            "Authorization": f"Bearer {self.auth_token}",
            "Accept": "application/json",
            "User-Agent": "Mozilla/5.0",
            "Origin": "https://souscription-en-ligne.mamda-mcma.ma",
            "Referer": "https://souscription-en-ligne.mamda-mcma.ma/",
            "Connection": "keep-alive"
        }
    
    def _create_subscription(self, params: Dict[str, Any]) -> bool:
        """Step 1: Create subscription and get auth token"""
        payload = {
            "dateOfCirculation": "2023-02-15",
            "horsePower": 6,
            "fuel": "Diesel",
            "valueOfVehicle": params.get("valeur_venale", 30000),
            "valueOfNewVehicle": params.get("valeur_neuf", 80000),
            "agreeToTerms": True
        }
        
        try:
            response = self.session.post(
                self.SUBSCRIPTION_URL,
                headers=self._get_headers(),
                json=payload,
                timeout=30
            )
            response.raise_for_status()
            
            data = response.json()
            self.subscription_id = data["subscription"]["id"]
            self.auth_token = data["token"]
            return True
            
        except Exception as e:
            self.last_error = f"MCMA Subscription Error: {str(e)}"
            return False
    
    def _get_packs(self) -> Dict[str, Any]:
        """Step 2: Fetch available packs using subscription ID"""
        url = f"{self.SUBSCRIPTION_URL}/{self.subscription_id}/packs"
        
        try:
            response = self.session.get(
                url,
                headers=self._get_auth_headers(),
                timeout=30
            )
            response.raise_for_status()
            return response.json()
            
        except Exception as e:
            self.last_error = f"MCMA Packs Error: {str(e)}"
            return None
    
    def fetch_quotes(self, params: Dict[str, Any]) -> List[InsurancePlan]:
        """Fetch insurance quotes from MCMA"""
        try:
            # Step 1: Create subscription
            if not self._create_subscription(params):
                return []
            
            # Step 2: Get packs
            packs_data = self._get_packs()
            if not packs_data:
                return []
            
            self.raw_response = packs_data
            return self._parse_response(packs_data)
            
        except Exception as e:
            self.last_error = f"MCMA Error: {str(e)}"
            return []
    
    def _parse_response(self, response_data: Dict[str, Any]) -> List[InsurancePlan]:
        """Parse MCMA API response into InsurancePlan objects"""
        plans = []
        
        pack_order = ["essentielle", "confort", "optimale", "tout_risque"]
        
        for pack_key in pack_order:
            if pack_key not in response_data:
                continue
                
            pack = response_data[pack_key]
            
            # Extract guarantees from privileges
            guarantees = []
            if "privileges" in pack:
                for privilege in pack["privileges"]:
                    guarantees.append(privilege.get("title", ""))
            
            annual_price = pack.get("annualBasePrice", 0)
            # Estimate taxes (approximately 15-17% based on sample data)
            taxes = round(annual_price * 0.165, 2)
            total = round(annual_price + taxes, 2)
            
            plan = InsurancePlan(
                provider=self.PROVIDER_NAME,
                plan_name=pack.get("title", pack_key.title()),
                annual_premium=annual_price,
                taxes=taxes,
                total_price=total,
                guarantees=guarantees,
                color=pack.get("color", self.PROVIDER_COLOR),
                is_promoted=pack.get("promoted", False),
                extra_info={
                    "key": pack.get("key"),
                    "semi_annual_price": pack.get("semiAnnualBasePrice", 0),
                    "disabled": pack.get("disabled", False),
                    "selects": pack.get("selects", {})
                }
            )
            plans.append(plan)
        
        return plans
