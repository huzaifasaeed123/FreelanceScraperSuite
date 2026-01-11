"""
AXA Insurance Scraper
Based on original axa.py - fetches quotations from AXA Morocco API
"""

import requests
import json
from datetime import datetime, timedelta
from typing import Dict, Any, List

from .base import BaseScraper, InsurancePlan


class AXAScraper(BaseScraper):
    """AXA Morocco insurance quotation scraper"""
    
    PROVIDER_NAME = "AXA Assurance"
    PROVIDER_LOGO = "https://upload.wikimedia.org/wikipedia/commons/thumb/9/90/Logo_of_AXA.svg/1280px-Logo_of_AXA.svg.png"
    PROVIDER_COLOR = "#00008F"
    
    API_URL = "https://axa.ma/bff/website/v1/quotation"
    
    PLAN_NAMES = [
        "Tiers Simple",
        "Tiers Étendu", 
        "Tous Risques Basic",
        "Tous Risques Premium"
    ]
    
    PLAN_COLORS = ["#00008F", "#0066CC", "#3399FF", "#66B2FF"]
    
    def __init__(self):
        super().__init__()
        self.session = requests.Session()
    
    def _build_payload(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Build API payload with user parameters"""
        future_date = (datetime.now() + timedelta(days=1)).strftime("%d-%m-%Y")
        
        return {
            "contrat": {
                "codeIntermediaire": 474,
                "codeProduit": 115,
                "nombreFraction": 0,
                "typeFractionnement": "f",
                "typeAvenant": 1,
                "sousAvenant": 1,
                "dateEffet": future_date,
                "typeContrat": "DF",
                "modePaiement": "12",
                "dateEcheance": "0",
                "dateExpiration": "0",
                "typePersonne": "P",
                "assureEstConducteur": "O",
                "identifiant": "a0",
                "dateNaissanceConducteur": "10-01-2001",
                "isFonctionnaire": "N",
                "codeConvention": 0,
                "newClient": "O",
                "nom": "Saeed",
                "prenom": "Muhammad",
                "dateNaissanceAssure": "10-01-2001",
                "tauxReduction": 0
            },
            "vehicule": {
                "codeUsage": "1B",
                "dateMisCirculation": "06-01-2026",
                "matricule": "123",
                "valeurNeuf": params.get("valeur_neuf", 65000),
                "valeurVenale": params.get("valeur_venale", 49999),
                "valeurAmenagement": 0,
                "energie": "G",
                "puissanceFiscale": 12,
                "codeCarrosserie": "B1",
                "codeMarque": 16,
                "nombrePlace": 5,
                "dateMutation": "0"
            },
            "leadInfos": {
                "city": "CASABLANCA",
                "phoneNumber": "0661776677",
                "licenceDate": "20-01-2017",
                "brandName": "BMW",
                "intermediateName": "A.S ASSURANCES",
                "marketingConsent": True,
                "cguConsent": True
            }
        }
    
    def _get_headers(self) -> Dict[str, str]:
        """Get request headers"""
        return {
            "accept": "application/json, text/plain, */*",
            "accept-encoding": "gzip, deflate, br, zstd",
            "accept-language": "en-US,en;q=0.9",
            "connection": "keep-alive",
            "content-type": "application/json",
            "host": "axa.ma",
            "origin": "https://axa.ma",
            "referer": "https://axa.ma/website-transactional/affaire-nouvelle",
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36",
        }
    
    def fetch_quotes(self, params: Dict[str, Any]) -> List[InsurancePlan]:
        """Fetch insurance quotes from AXA"""
        try:
            payload = self._build_payload(params)
            
            response = self.session.post(
                self.API_URL,
                json=payload,
                headers=self._get_headers(),
                timeout=30
            )
            response.raise_for_status()
            
            self.raw_response = response.json()
            return self._parse_response(self.raw_response)
            
        except requests.exceptions.RequestException as e:
            self.last_error = f"AXA API Error: {str(e)}"
            return []
        except Exception as e:
            self.last_error = f"AXA Parse Error: {str(e)}"
            return []
    
    def _parse_response(self, response_data: Any) -> List[InsurancePlan]:
        """Parse AXA API response into InsurancePlan objects"""
        plans = []
        
        if not isinstance(response_data, list):
            return plans
        
        for idx, quote in enumerate(response_data):
            plan_name = self.PLAN_NAMES[idx] if idx < len(self.PLAN_NAMES) else f"Plan {idx + 1}"
            color = self.PLAN_COLORS[idx] if idx < len(self.PLAN_COLORS) else self.PROVIDER_COLOR
            
            plan = InsurancePlan(
                provider=self.PROVIDER_NAME,
                plan_name=plan_name,
                annual_premium=quote.get("primeNetAnnuel", 0),
                taxes=quote.get("taxesAnnuel", 0),
                total_price=quote.get("primeTotaleAnnuel", 0),
                guarantees=[
                    "Responsabilité Civile",
                    "Défense et Recours",
                    "CNPAC"
                ],
                color=color,
                is_promoted=(idx == 1),
                extra_info={
                    "quotation_id": quote.get("idQuotation"),
                    "expiration_date": quote.get("dateExpiration"),
                    "cnpac": quote.get("cnpacAnnuel", 0),
                    "accessoire": quote.get("accessoireAnnuel", 0),
                    "lead_id": quote.get("idLead")
                }
            )
            plans.append(plan)
        
        return plans
