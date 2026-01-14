"""
AXA Insurance Scraper
Fetches quotations from AXA Morocco API with complete plan details
"""

import requests
import time
from datetime import datetime, timedelta
from typing import Dict, Any, List

from .base import (
    BaseScraper, InsurancePlan, Guarantee
)


class AXAScraper(BaseScraper):
    """AXA Morocco insurance quotation scraper"""
    
    PROVIDER_NAME = "AXA Assurance"
    PROVIDER_CODE = "axa"
    PROVIDER_LOGO = "https://upload.wikimedia.org/wikipedia/commons/thumb/9/90/Logo_of_AXA.svg/1280px-Logo_of_AXA.svg.png"
    PROVIDER_COLOR = "#00008F"
    
    API_URL = "https://axa.ma/bff/website/v1/quotation"
    
    # Plan details based on AXA's offerings
    PLAN_DETAILS = {
        0: {
            "name": "Basique",
            "color": "#6B7280",
            "guarantees": [
                {"name": "Responsabilité Civile", "code": "RC", "is_obligatory": True},
                {"name": "Défense et Recours", "code": "DR"},
                {"name": "CNPAC", "code": "CNPAC"}
            ]
        },
        1: {
            "name": "Basique+",
            "color": "#4B5563",
            "guarantees": [
                {"name": "Responsabilité Civile", "code": "RC", "is_obligatory": True},
                {"name": "Défense et Recours", "code": "DR"},
                {"name": "Protection Conducteur", "code": "PC"},
                {"name": "CNPAC", "code": "CNPAC"}
            ]
        },
        2: {
            "name": "Optimale",
            "color": "#F59E0B",
            "guarantees": [
                {"name": "Responsabilité Civile", "code": "RC", "is_obligatory": True},
                {"name": "Défense et Recours", "code": "DR"},
                {"name": "Protection Conducteur", "code": "PC"},
                {"name": "Vol", "code": "VOL"},
                {"name": "Incendie", "code": "INC"},
                {"name": "Bris de Glaces", "code": "BDG"},
                {"name": "CNPAC", "code": "CNPAC"}
            ]
        },
        3: {
            "name": "Premium",
            "color": "#EC4899",
            "guarantees": [
                {"name": "Responsabilité Civile", "code": "RC", "is_obligatory": True},
                {"name": "Défense et Recours", "code": "DR"},
                {"name": "Protection Conducteur", "code": "PC"},
                {"name": "Vol", "code": "VOL"},
                {"name": "Incendie", "code": "INC"},
                {"name": "Bris de Glaces", "code": "BDG"},
                {"name": "Dommages Tous Accidents", "code": "DTA"},
                {"name": "Assistance Premium", "code": "ASSIST"},
                {"name": "CNPAC", "code": "CNPAC"}
            ]
        }
    }
    
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
        start_time = time.time()
        
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
            self.fetch_time = time.time() - start_time
            return self._parse_response(self.raw_response)
            
        except requests.exceptions.RequestException as e:
            self.last_error = f"AXA API Error: {str(e)}"
            self.fetch_time = time.time() - start_time
            return []
        except Exception as e:
            self.last_error = f"AXA Parse Error: {str(e)}"
            self.fetch_time = time.time() - start_time
            return []
    
    def _parse_response(self, response_data: Any) -> List[InsurancePlan]:
        """Parse AXA API response into InsurancePlan objects"""
        plans = []
        
        if not isinstance(response_data, list):
            return plans
        
        for idx, quote in enumerate(response_data):
            plan_info = self.PLAN_DETAILS.get(idx, {
                "name": f"Plan {idx + 1}",
                "color": self.PROVIDER_COLOR,
                "guarantees": []
            })
            
            # Parse guarantees
            guarantees = []
            for g_idx, g_data in enumerate(plan_info.get("guarantees", [])):
                guarantees.append(Guarantee(
                    name=g_data.get("name", ""),
                    code=g_data.get("code", ""),
                    is_included=True,
                    is_obligatory=g_data.get("is_obligatory", False),
                    order=g_idx
                ))
            
            # Annual pricing
            prime_net_annual = quote.get("primeNetAnnuel", 0)
            taxes_annual = quote.get("taxesAnnuel", 0)
            prime_total_annual = quote.get("primeTotaleAnnuel", 0)
            cnpac = quote.get("cnpacAnnuel", 0)
            accessoires = quote.get("accessoireAnnuel", 0)
            
            # Semi-annual pricing (comptant = cash/immediate)
            prime_net_semi = quote.get("primeNetComptant", 0)
            taxes_semi = quote.get("taxesComptant", 0)
            prime_total_semi = quote.get("primeTotaleComptant", 0)
            
            # Estimate semi-annual as roughly half of annual (AXA shows same values)
            # In reality, semi-annual might have slight difference
            semi_annual_factor = 0.52  # Slightly more than half due to admin fees
            
            plan = InsurancePlan(
                provider=self.PROVIDER_NAME,
                provider_code=self.PROVIDER_CODE,
                plan_name=plan_info["name"],
                plan_code=f"axa_plan_{idx}",
                
                # Annual pricing
                prime_net_annual=prime_net_annual,
                taxes_annual=taxes_annual,
                prime_total_annual=prime_total_annual,
                cnpac=cnpac,
                accessoires=accessoires,
                
                # Semi-annual pricing (estimate)
                prime_net_semi_annual=round(prime_net_annual * semi_annual_factor, 2),
                taxes_semi_annual=round(taxes_annual * semi_annual_factor, 2),
                prime_total_semi_annual=round(prime_total_annual * semi_annual_factor, 2),
                
                # Guarantees
                guarantees=guarantees,
                
                # Display
                color=plan_info["color"],
                is_promoted=(idx == 1),  # Basique+ is typically recommended
                is_eligible=True,
                order=idx,
                
                # Extra info
                extra_info={
                    "quotation_id": quote.get("idQuotation"),
                    "expiration_date": quote.get("dateExpiration"),
                    "lead_id": quote.get("idLead")
                }
            )
            plans.append(plan)
        
        return plans
