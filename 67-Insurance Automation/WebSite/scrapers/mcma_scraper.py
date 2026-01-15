"""
MCMA Insurance Scraper
Fetches quotations from MAMDA-MCMA API with complete plan details
"""

import requests
import time
from typing import Dict, Any, List
from html import unescape
import re

from .base import (
    BaseScraper, InsurancePlan, Guarantee, 
    SelectableField, SelectOption
)


class MCMAScraper(BaseScraper):
    """MAMDA-MCMA insurance quotation scraper"""
    
    PROVIDER_NAME = "MAMDA-MCMA"
    PROVIDER_CODE = "mcma"
    PROVIDER_LOGO = "https://www.mamda-mcma.ma/themes/custom/mamda/logo.svg"
    PROVIDER_COLOR = "#2fd0a7"
    
    SUBSCRIPTION_URL = "https://bo-sel.mamda-mcma.ma/api/subscriptions"
    
    # Plan colors matching the website
    PLAN_COLORS = {
        "essentielle": "#2fd0a7",
        "confort": "#ff8772",
        "optimale": "#4bc1e1",
        "tout_risque": "#b21c71"
    }
    
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
    
    def _clean_html(self, html_text: str) -> str:
        """Clean HTML entities and tags from description"""
        if not html_text:
            return ""
        # Decode HTML entities
        text = unescape(html_text)
        # Remove HTML tags
        text = re.sub(r'<[^>]+>', ' ', text)
        # Clean up whitespace
        text = ' '.join(text.split())
        return text
    
    def _parse_selectable_fields(self, selects: Dict) -> List[SelectableField]:
        """Parse selectable options (like Bris de glace amounts)"""
        fields = []
        
        if not selects:
            return fields
            
        for key, select_data in selects.items():
            options = []
            for opt in select_data.get("options", []):
                options.append(SelectOption(
                    id=opt.get("id"),
                    label=opt.get("option", ""),
                    is_default=opt.get("default", False)
                ))
            
            fields.append(SelectableField(
                name=select_data.get("name", key),
                title=select_data.get("title", key),
                options=options
            ))
        
        return fields
    
    def _parse_guarantees(self, privileges: List[Dict]) -> List[Guarantee]:
        """Parse guarantees from privileges array"""
        guarantees = []
        
        for idx, priv in enumerate(privileges):
            guarantee = Guarantee(
                name=priv.get("title", ""),
                code=priv.get("key", ""),
                description=self._clean_html(priv.get("description", "")),
                is_included=True,
                is_obligatory=priv.get("key") == "public_liability",
                order=idx
            )
            guarantees.append(guarantee)
        
        return guarantees
    
    def fetch_quotes(self, params: Dict[str, Any]) -> List[InsurancePlan]:
        """Fetch insurance quotes from MCMA"""
        start_time = time.time()
        
        try:
            # Step 1: Create subscription
            if not self._create_subscription(params):
                self.fetch_time = time.time() - start_time
                return []
            
            # Step 2: Get packs
            packs_data = self._get_packs()
            if not packs_data:
                self.fetch_time = time.time() - start_time
                return []
            
            self.raw_response = packs_data
            self.fetch_time = time.time() - start_time
            return self._parse_response(packs_data)
            
        except Exception as e:
            self.last_error = f"MCMA Error: {str(e)}"
            self.fetch_time = time.time() - start_time
            return []
    
    def _fetch_pack_details(self, pack_key: str, query_params: str = "") -> Dict[str, Any]:
        """Fetch detailed pack information with selected options"""
        url = f"{self.SUBSCRIPTION_URL}/{self.subscription_id}/packs/{pack_key}"
        if query_params:
            url += f"?{query_params}"

        try:
            response = self.session.get(
                url,
                headers=self._get_auth_headers(),
                timeout=30
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            return None

    def _build_query_params(self, selects: Dict, selected_options: Dict) -> str:
        """Build query parameters for pack API from selected options"""
        params = []
        for select_key, select_data in selects.items():
            if select_key in selected_options:
                # Map select key to parameter name
                param_name = select_data.get("name", select_key)
                # Convert snake_case to camelCase or match actual API parameter name
                if param_name == "broken-glass":
                    param_name = "brokenGlassValue"
                elif param_name == "damage-collision":
                    param_name = "damageAndCollision"
                elif param_name == "franchise-tierce":
                    param_name = "franchise"

                params.append(f"{param_name}={selected_options[select_key]}")

        return "&".join(params)

    def _generate_option_combinations(self, selects: Dict) -> List[Dict[str, int]]:
        """Generate all possible combinations of selectable options"""
        if not selects:
            return [{}]

        import itertools

        select_keys = list(selects.keys())
        select_options = []

        for key in select_keys:
            options = []
            for opt in selects[key].get("options", []):
                options.append({
                    "key": key,
                    "id": opt.get("id"),
                    "is_default": opt.get("default", False)
                })
            select_options.append(options)

        # Generate all combinations
        combinations = []
        for combo in itertools.product(*select_options):
            combo_dict = {}
            for opt in combo:
                combo_dict[opt["key"]] = opt["id"]
            combinations.append(combo_dict)

        return combinations

    def _fetch_all_option_combinations(self, pack_key: str, selects: Dict) -> Dict[str, Any]:
        """Fetch pricing for all option combinations for a pack"""
        combinations_pricing = {}

        if not selects:
            return combinations_pricing

        # Generate all possible combinations
        all_combinations = self._generate_option_combinations(selects)

        for combo_dict in all_combinations:
            # Build query parameters
            query_params = self._build_query_params(selects, combo_dict)
            combination_key = "_".join([f"{k}_{v}" for k, v in sorted(combo_dict.items())])

            # Fetch details for this combination
            pack_data = self._fetch_pack_details(pack_key, query_params)

            if pack_data:
                # Extract pricing from response
                annual_price = pack_data.get("annualBasePrice", 0)
                semi_annual_price = pack_data.get("semiAnnualBasePrice", 0)

                annual_taxes = round(annual_price * 0.165, 2)
                semi_annual_taxes = round(semi_annual_price * 0.165, 2)

                combinations_pricing[combination_key] = {
                    "params": query_params,
                    "prime_net_annual": annual_price,
                    "taxes_annual": annual_taxes,
                    "prime_total_annual": round(annual_price + annual_taxes, 2),
                    "prime_net_semi_annual": semi_annual_price,
                    "taxes_semi_annual": semi_annual_taxes,
                    "prime_total_semi_annual": round(semi_annual_price + semi_annual_taxes, 2),
                    "options": combo_dict
                }

        return combinations_pricing

    def _parse_response(self, response_data: Dict[str, Any]) -> List[InsurancePlan]:
        """Parse MCMA API response into InsurancePlan objects with detailed pricing"""
        plans = []

        # Process packs in specific order
        pack_order = ["essentielle", "confort", "optimale", "tout_risque"]

        for order, pack_key in enumerate(pack_order):
            if pack_key not in response_data:
                continue

            pack = response_data[pack_key]

            if pack.get("disabled", False):
                continue

            # Parse guarantees from privileges
            guarantees = self._parse_guarantees(pack.get("privileges", []))

            # Parse selectable fields
            selectable_fields = self._parse_selectable_fields(pack.get("selects", {}))

            # Get base pricing (default option)
            annual_price = pack.get("annualBasePrice", 0)
            semi_annual_price = pack.get("semiAnnualBasePrice", 0)

            # Calculate taxes (approximately 16.5% based on observed data)
            annual_taxes = round(annual_price * 0.165, 2)
            semi_annual_taxes = round(semi_annual_price * 0.165, 2)

            # Fetch all option combinations if this pack has selectable fields
            option_combinations_pricing = {}
            if pack.get("selects"):
                option_combinations_pricing = self._fetch_all_option_combinations(
                    pack.get("key", pack_key),
                    pack.get("selects", {})
                )

            plan = InsurancePlan(
                provider=self.PROVIDER_NAME,
                provider_code=self.PROVIDER_CODE,
                plan_name=pack.get("title", pack_key.title()),
                plan_code=pack.get("key", pack_key),

                # Annual pricing
                prime_net_annual=annual_price,
                taxes_annual=annual_taxes,
                prime_total_annual=round(annual_price + annual_taxes, 2),

                # Semi-annual pricing
                prime_net_semi_annual=semi_annual_price,
                taxes_semi_annual=semi_annual_taxes,
                prime_total_semi_annual=round(semi_annual_price + semi_annual_taxes, 2),

                # Guarantees
                guarantees=guarantees,

                # Selectable fields
                selectable_fields=selectable_fields,

                # Display
                color=pack.get("color", self.PLAN_COLORS.get(pack_key, self.PROVIDER_COLOR)),
                is_promoted=pack.get("promoted", False),
                is_eligible=not pack.get("disabled", False),
                order=order,

                # Extra info
                extra_info={
                    "key": pack.get("key"),
                    "has_selects": len(selectable_fields) > 0,
                    "pack_data": pack,  # Store full pack data for later use
                    "option_combinations": option_combinations_pricing  # All option pricing combinations
                }
            )
            plans.append(plan)

        return plans
