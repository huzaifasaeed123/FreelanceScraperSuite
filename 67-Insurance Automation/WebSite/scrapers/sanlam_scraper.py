"""
Sanlam Insurance Scraper
Fetches quotations from Sanlam Morocco API with complete plan details
Supports both 6-month and 12-month (annual) pricing
"""

import requests
import time
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from typing import Dict, Any, List, Optional

from .base import (
    BaseScraper, InsurancePlan, Guarantee,
    SelectableField, SelectOption
)


class SanlamScraper(BaseScraper):
    """Sanlam Morocco insurance quotation scraper"""
    
    PROVIDER_NAME = "Sanlam Assurance"
    PROVIDER_CODE = "sanlam"
    PROVIDER_LOGO = "https://www.sanlam.ma/themes/custom/flavor/logo.svg"
    PROVIDER_COLOR = "#0066B3"
    
    PRICING_URL = "https://souscription-en-ligne.sanlam.ma/api/auto/recalculate-pricing"
    FORMULA_URL = "https://souscription-en-ligne.sanlam.ma/api/auto/formula-pricing"
    
    # Plan colors
    PLAN_COLORS = {
        "Formule initiale": "#6B7280",
        "Formule essentielle": "#0066B3",
        "Formule premium": "#F59E0B"
    }
    
    def __init__(self):
        super().__init__()
        self.session = requests.Session()
    
    def _get_headers(self) -> Dict[str, str]:
        """Get request headers"""
        return {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "Mozilla/5.0"
        }
    
    def _calculate_end_date(self, start_date: datetime, duration_months: int) -> str:
        """Calculate end date exactly N months minus 1 day"""
        end_date = start_date + relativedelta(months=duration_months) - timedelta(days=1)
        return end_date.strftime("%Y-%m-%d")
    
    def _build_payload(self, params: Dict[str, Any], duration_months: int = 12) -> Dict[str, Any]:
        """
        Build API payload with user parameters.
        Field ordering in policy object matters!
        """
        # Calculate dates
        start_date = datetime.now() + timedelta(days=1)
        start_date_str = start_date.strftime("%Y-%m-%d")
        end_date_str = self._calculate_end_date(start_date, duration_months)
        
        # Build policy object with correct field order based on duration
        if duration_months == 6:
            # For 6 months: duration comes BEFORE maturityContractType
            policy = {
                "startDate": start_date_str,
                "endDate": end_date_str,
                "duration": 6,
                "maturityContractType": "2"
            }
        else:
            # For 12 months: maturityContractType comes BEFORE duration
            policy = {
                "startDate": start_date_str,
                "endDate": end_date_str,
                "maturityContractType": "2",
                "duration": 12
            }
        payload={
            "driver": {
                "licenseNumber": "1111111111",
                "licenseDate": "2026-01-13",
                "licenseCategory": "B",
                "lastName": "Client",
                "firstName": "Test",
                "birthDate": "2005-02-08",
                "CIN": "BJ1111111",
                "sex": "M",
                "nature": "1",
                "adress": "sample addresse",
                "city": "AIN AICHA",
                "phoneNumber": "+212522435939",
                "title": "0",
                "profession": "12",
                "isDriver": True
            },
            "subscriber": {
                "isDriver": True,
                "nature": "1",
                "CIN": "BJ1111111",
                "civility": "0",
                "lastName": "Client",
                "firstName": "Test",
                "birthDate": "2005-02-08",
                "adress": "sample addresse",
                "city": "AIN AICHA",
                "phoneNumber": "+212522435939",
                "licenseNumber": "1111111111",
                "licenseDate": "2026-01-13",
                "licenseCategory": "B",
                "profession": "12",
                "postalCode": "20300",
                "sex": "M"
            },
            "vehicle": {
                "registrationNumber": "11111-A-7",
                "brand": "2078",
                "horsePower": "6",
                "model": "Autres",
                "usageCode": "1",
                "registrationFormat": "3",
                "newValue": int(params.get("valeur_neuf", 650000)),
                "combustion": "L",
                "circulationDate": "2026-01-05",
                "marketValue": int(params.get("valeur_venale", 650000)),
                "seatsNumber": 5
            },
            "policy": policy,
            "agent": {
                "agentkey": "68103"
            },
            "recaptcha": ""
        }
        print(f"Payload for :  {payload}")
        return payload
    
    def _fetch_pricing_and_formulas(self, params: Dict[str, Any], duration_months: int) -> List[Dict]:
        """
        Fetch pricing and then get details for each formula.
        Returns list of formula pricing details.
        """
        payload = self._build_payload(params, duration_months)
        headers = self._get_headers()
        
        # Step 1: Get initial pricing with formulas list
        try:
            response = self.session.post(
                self.PRICING_URL,
                json=payload,
                headers=headers,
                timeout=60
            )
            response.raise_for_status()
            pricing_json = response.json()
        except Exception as e:
            print(f"Sanlam Pricing Error ({duration_months}m): {str(e)}")
            return []
        
        if pricing_json.get("status") != 200:
            print(f"Sanlam API returned status: {pricing_json.get('status')} for {duration_months}m")
            return []
        
        data = pricing_json.get("data", {})
        formulas = data.get("formulas", [])
        policy_id = data.get("savedPolicy", {}).get("id")
        
        if not policy_id or not formulas:
            print(f"No policy ID or formulas returned for {duration_months}m")
            return []
        
        # Step 2: Fetch detailed pricing for each formula
        formula_details = []
        
        for formula in formulas:
            # Build formula payload exactly like original code
            formula_payload = {
                "formula": formula,
                "agent": {"agentkey": "68103"},
                "id": policy_id
            }
            
            try:
                resp = self.session.post(
                    self.FORMULA_URL,
                    json=formula_payload,
                    headers=headers,
                    timeout=60
                )
                resp.raise_for_status()
                result_json = resp.json()
                
                if result_json.get("status") == 200:
                    formula_details.append(result_json.get("data", {}).get("pricing", {}))
                else:
                    print(f"Formula {formula.get('name')} returned status: {result_json.get('status')}")
                    
            except Exception as e:
                print(f"Error fetching formula {formula.get('name', 'unknown')}: {e}")
            
            time.sleep(1)
        
        return formula_details
    
    def _clean_coverage_name(self, name: str) -> str:
        """Clean up coverage name from encoding issues"""
        if not name:
            return ""
        replacements = {
            "ResponsabilitÃ©": "Responsabilité",
            "Ã©": "é",
            "Ã ": "à",
            "Ã¨": "è",
            "Ã´": "ô",
            "Ãª": "ê",
            "Ã®": "î",
            "vÃ©tustÃ©": "vétusté",
            "rÃ©troviseurs": "rétroviseurs",
            "complÃ©mentaire": "complémentaire",
            "vÃ©hicule": "véhicule",
            "adossÃ©e": "adossée"
        }
        result = name
        for old, new in replacements.items():
            result = result.replace(old, new)
        return result
    
    def _parse_coverages(self, coverages: List[Dict]) -> tuple:
        """Parse coverages into guarantees and selectable fields"""
        guarantees = []
        selectable_fields = []
        
        for idx, cov in enumerate(coverages):
            name = self._clean_coverage_name(cov.get("coverageName", ""))
            is_checked = cov.get("checked", False)
            
            guarantee = Guarantee(
                name=name,
                code=cov.get("coverageCode", ""),
                is_included=is_checked,
                is_obligatory=not cov.get("isModifiable", True),
                is_optional=cov.get("isModifiable", False),
                order=idx
            )
            
            # Check for selectable options
            options = cov.get("options", [])
            if options and len(options) > 0:
                guarantee.has_options = True
                selected_option = cov.get("option")
                
                select_options = []
                for opt in options:
                    select_options.append(SelectOption(
                        id=opt.get("key"),
                        label=opt.get("label", ""),
                        is_default=(str(opt.get("key")) == str(selected_option))
                    ))
                
                guarantee.options = select_options
                guarantee.selected_option = selected_option
                
                if cov.get("isOptionModifiable", False):
                    selectable_fields.append(SelectableField(
                        name=f"coverage_{cov.get('coverageCode', '')}",
                        title=name,
                        options=select_options
                    ))
            
            guarantees.append(guarantee)
        
        return guarantees, selectable_fields
    
    def _parse_assistance(self, assistance_list: List[Dict]) -> List[SelectableField]:
        """Parse assistance options as selectable fields"""
        fields = []
        
        for assist in assistance_list:
            name = self._clean_coverage_name(assist.get("coverageName", ""))
            options = assist.get("options", [])
            
            if options:
                select_options = [
                    SelectOption(
                        id=opt.get("key"),
                        label=opt.get("label", ""),
                        is_default=False
                    ) for opt in options
                ]
                
                fields.append(SelectableField(
                    name=f"assistance_{assist.get('coverageCode', '')}",
                    title=name,
                    options=select_options
                ))
        
        return fields
    
    def fetch_quotes(self, params: Dict[str, Any]) -> List[InsurancePlan]:
        """Fetch insurance quotes from Sanlam for both durations"""
        start_time = time.time()
        
        try:
            # Fetch SEMI-ANNUAL (6 months) first - this works
            print("Fetching Sanlam 6-month pricing...")
            semi_annual_formulas = self._fetch_pricing_and_formulas(params, 6)
            
            # Fetch ANNUAL (12 months)
            print("Fetching Sanlam 12-month pricing...")
            annual_formulas = self._fetch_pricing_and_formulas(params, 12)
            
            # Store raw response
            self.raw_response = {
                "annual": annual_formulas,
                "semi_annual": semi_annual_formulas
            }
            
            # Parse into InsurancePlan objects
            plans = self._parse_response(annual_formulas, semi_annual_formulas)
            
            self.fetch_time = time.time() - start_time
            
            if not plans:
                self.last_error = "No plans returned from Sanlam"
            
            return plans
            
        except Exception as e:
            self.last_error = f"Sanlam Error: {str(e)}"
            self.fetch_time = time.time() - start_time
            return []
    
    def _parse_response(self, annual_formulas: List[Dict], semi_annual_formulas: List[Dict]) -> List[InsurancePlan]:
        """Parse formula responses into InsurancePlan objects"""
        plans = []
        
        # Use whichever has data - prefer semi_annual if annual failed
        primary_formulas = annual_formulas if annual_formulas else semi_annual_formulas
        secondary_formulas = semi_annual_formulas if annual_formulas else annual_formulas
        
        if not primary_formulas:
            return plans
        
        # Create lookup for secondary by name
        secondary_lookup = {}
        for formula in secondary_formulas:
            name = formula.get("name", "")
            if name:
                secondary_lookup[name] = formula
        
        for idx, primary_pricing in enumerate(primary_formulas):
            if not primary_pricing:
                continue
            
            formula_name = primary_pricing.get("name", f"Formule {idx + 1}")
            secondary_pricing = secondary_lookup.get(formula_name, {})
            
            # Determine which is annual and which is semi-annual
            if annual_formulas:
                annual_pricing = primary_pricing
                semi_pricing = secondary_pricing
            else:
                annual_pricing = secondary_pricing
                semi_pricing = primary_pricing
            
            # Parse coverages and assistance from primary
            coverages = primary_pricing.get("coverages", [])
            guarantees, selectable_fields = self._parse_coverages(coverages)
            
            assistance = primary_pricing.get("assistance", [])
            assistance_fields = self._parse_assistance(assistance)
            selectable_fields.extend(assistance_fields)
            
            # Get pricing - Annual
            annual_ttc = annual_pricing.get("priceTTC", 0) if annual_pricing else 0
            annual_ht = annual_pricing.get("priceHT", 0) if annual_pricing else 0
            annual_taxes = round(annual_ttc - annual_ht, 2) if annual_ttc and annual_ht else 0
            
            # Get pricing - Semi-annual
            semi_ttc = semi_pricing.get("priceTTC", 0) if semi_pricing else 0
            semi_ht = semi_pricing.get("priceHT", 0) if semi_pricing else 0
            semi_taxes = round(semi_ttc - semi_ht, 2) if semi_ttc and semi_ht else 0
            
            # Estimate missing values if needed
            if not annual_ttc and semi_ttc:
                annual_ttc = round(semi_ttc / 0.52, 2)
                annual_ht = round(semi_ht / 0.52, 2)
                annual_taxes = round(semi_taxes / 0.52, 2)
            elif not semi_ttc and annual_ttc:
                semi_ttc = round(annual_ttc * 0.52, 2)
                semi_ht = round(annual_ht * 0.52, 2)
                semi_taxes = round(annual_taxes * 0.52, 2)
            
            plan = InsurancePlan(
                provider=self.PROVIDER_NAME,
                provider_code=self.PROVIDER_CODE,
                plan_name=formula_name,
                plan_code=f"sanlam_{idx}",
                
                prime_net_annual=annual_ht,
                taxes_annual=annual_taxes,
                prime_total_annual=annual_ttc,
                
                prime_net_semi_annual=semi_ht,
                taxes_semi_annual=semi_taxes,
                prime_total_semi_annual=semi_ttc,
                
                guarantees=guarantees,
                selectable_fields=selectable_fields,
                
                color=self.PLAN_COLORS.get(formula_name, self.PROVIDER_COLOR),
                is_promoted=(formula_name == "Formule essentielle"),
                is_eligible=True,
                order=idx,
                
                extra_info={
                    "crm": primary_pricing.get("crm", 100),
                    "start_date": primary_pricing.get("startDate"),
                    "end_date": primary_pricing.get("endDate"),
                    "selected": primary_pricing.get("selected", False)
                }
            )
            plans.append(plan)
        
        return plans


# ===== STANDALONE TEST =====
if __name__ == "__main__":
    print("=" * 60)
    print("SANLAM SCRAPER TEST")
    print("=" * 60)
    
    scraper = SanlamScraper()
    
    params = {
        "valeur_neuf": 650000,
        "valeur_venale": 650000
    }
    
    print(f"\nTest parameters:")
    print(f"  Valeur à neuf: {params['valeur_neuf']} MAD")
    print(f"  Valeur vénale: {params['valeur_venale']} MAD")
    print("\nFetching quotes...")
    
    plans = scraper.fetch_quotes(params)
    
    if scraper.last_error:
        print(f"\n❌ Error: {scraper.last_error}")
    
    print(f"\n✅ Found {len(plans)} plans in {scraper.fetch_time:.2f}s\n")
    
    for plan in plans:
        print(f"{'='*50}")
        print(f"📋 {plan.plan_name}")
        print(f"  💰 Annual:     {plan.prime_total_annual:,.2f} DH TTC")
        print(f"  💰 Semi-annual: {plan.prime_total_semi_annual:,.2f} DH TTC")
        included = [g for g in plan.guarantees if g.is_included]
        print(f"  ✓ Garanties: {len(included)} incluses")
        print()
