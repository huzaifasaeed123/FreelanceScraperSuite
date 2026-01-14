"""
RMA Assurance Scraper
Fetches quotations from RMA API with complete plan details
"""

import requests
import time
from typing import Dict, Any, List

from .base import (
    BaseScraper, InsurancePlan, Guarantee
)


class RMAScraper(BaseScraper):
    """RMA Assurance insurance quotation scraper"""
    
    PROVIDER_NAME = "RMA Assurance"
    PROVIDER_CODE = "rma"
    PROVIDER_LOGO = "https://direct.rmaassurance.com/assets/images/logo-rma.svg"
    PROVIDER_COLOR = "#1E3A8A"
    
    TOKEN_URL = "https://direct.rmaassurance.com/canaldirect/auth/api/token"
    OFFERS_URL = "https://direct.rmaassurance.com/canaldirect/offer/api/offers"
    
    # Plan colors based on RMA website
    PLAN_COLORS = {
        "BASIQUE OTO": "#6366F1",
        "OPTIMAL OTO": "#F59E0B", 
        "CONFORT OTO": "#3B82F6",
        "TOUS RISQUE OTO": "#10B981"
    }
    
    def __init__(self):
        super().__init__()
        self.session = requests.Session()
        self.access_token = None
        self.token_expiry = 0
    
    def _get_access_token(self) -> bool:
        """Get JWT access token"""
        params = {"csrt": "10651071086600842364"}
        
        headers = {
            "User-Agent": "Mozilla/5.0",
            "Accept": "*/*",
            "X-Ts-Ajax-Request": "true",
            "X-Security-Csrf-Token": "08553bbd45ab28005d86670b015bbbef2fb54e2a9d8594b3b1d3723b8159ff014c78580f30e2b3b41d94d0813e29e1dc",
            "Referer": "https://direct.rmaassurance.com/souscrire",
        }
        
        try:
            response = self.session.get(
                self.TOKEN_URL,
                headers=headers,
                params=params,
                timeout=30
            )
            response.raise_for_status()
            
            data = response.json()
            self.access_token = data["accessToken"]
            self.token_expiry = time.time() + data.get("expiresIn", 7200)
            return True
            
        except Exception as e:
            self.last_error = f"RMA Token Error: {str(e)}"
            return False
    
    def _ensure_token(self) -> bool:
        """Ensure we have a valid access token"""
        if not self.access_token or time.time() >= self.token_expiry - 60:
            return self._get_access_token()
        return True
    
    def _build_payload(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Build API payload with user parameters"""
        return {
            "nomOrRaisonSociale": "Huzaifa",
            "prenom": "Saeed",
            "titreCivilite": "1",
            "typePieceIdentite": "1",
            "situationFamiliale": "C",
            "telephone": "0661776677",
            "dateNaissance": "17-01-1969",
            "idVilleAdresse": "6",
            "dateObtentionPermis": "08-01-2017",
            "sexeConducteur": "M",
            "sexe": "M",
            "idPaysPermisConducteur": "212",
            "idPaysPermis": "212",
            "professionConducteur": "99",
            "profession": "99",
            "numeroClient": "308252166",
            "numeroClientConducteur": "308252166",
            "telephoneConducteur": "0661776677",
            "nomOrRaisonSocialeConducteur": "Huzaifa",
            "prenomConducteur": "Saeed",
            "situationFamilialeConducteur": "C",
            "dateNaissanceConducteur": "17-01-1969",
            "idVilleAdresseConducteur": "6",
            "titreCiviliteConducteur": "1",
            "dateObtentionPermisConducteur": "08-01-2017",
            "typePieceIdentiteConducteur": "1",
            "nombreEnfant": "0",
            "codeUsageVehicule": "1",
            "idGenre": "1",
            "typeImmatriculation": "3",
            "immatriculation": "00000-F-00",
            "tauxCRM": 1,
            "crmFMSAR": 1,
            "carburant": "2",
            "puissanceFiscale": "11",
            "dateMiseEnCirculation": "08-01-2017",
            "heureMiseEnCirculation": "04",
            "nombrePlace": 5,
            "valeurANeuf": str(params.get("valeur_neuf", 65000)),
            "valeurVenale": str(params.get("valeur_venale", 45000)),
            "referenceCRMFMSAR": "14E9999/26/19599",
            "avecBaremeConventionnel": "off",
            "natureContrat": "F",
            "dateEffet": "08-01-2026",
            "heureEffet": 6,
            "dateEcheance": "08-01-2027",
            "heureEcheance": 6,
            "dateEvenement": "08-01-2026",
            "heureEvenement": 6,
            "duree": "12",
            "dureeContratEnJour": 365,
            "dateEtablissement": "08-01-2026",
            "typeContrat": 1,
            "modePaiement": "8",
            "modePaiementCanalDirect": "8",
            "typeLivraison": "home",
            "typeCouverture": "1",
            "clientConducteur": "on",
            "vehiculeAgarage": "off",
            "avecDelegation": "off",
            "dateEffetInitiale": "08-01-2026",
            "formatAttestation": "3",
            "avecReductionSaharienne": "off",
            "typeCanal": 3,
            "idUtilisateur": 3405,
            "idProduit": "1",
            "idIntermediaire": "8714",
            "typeClient": "1",
            "typeConducteur": "1",
            "numeroDevis": "202026013227",
            "typeEvenement": "100",
            "avecAntivole": "on",
            "intermediaryChanged": "off",
            "specialOffer": "Z200-AA"
        }
    
    def _get_request_headers(self) -> Dict[str, str]:
        """Get request headers for offers API"""
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Origin": "https://direct.rmaassurance.com",
            "Referer": "https://direct.rmaassurance.com/souscrire",
            "User-Agent": "Mozilla/5.0",
            "X-Ts-Ajax-Request": "true",
            "X-Security-Csrf-Token": "08553bbd45ab2800849d2efccc6dbf865ac80ec883891a2d12bf6d0a9ce1a81c89e1ce5da3891083e93786eabaa721e9",
        }
    
    def fetch_quotes(self, params: Dict[str, Any]) -> List[InsurancePlan]:
        """Fetch insurance quotes from RMA"""
        start_time = time.time()
        
        try:
            # Ensure we have a valid token
            if not self._ensure_token():
                self.fetch_time = time.time() - start_time
                return []
            
            payload = self._build_payload(params)
            
            response = self.session.post(
                self.OFFERS_URL,
                headers=self._get_request_headers(),
                params={"csrt": "1104538121806306204"},
                json=payload,
                timeout=30
            )
            response.raise_for_status()
            
            self.raw_response = response.json()
            self.fetch_time = time.time() - start_time
            return self._parse_response(self.raw_response)
            
        except requests.exceptions.RequestException as e:
            self.last_error = f"RMA API Error: {str(e)}"
            self.fetch_time = time.time() - start_time
            return []
        except Exception as e:
            self.last_error = f"RMA Parse Error: {str(e)}"
            self.fetch_time = time.time() - start_time
            return []
    
    def _parse_guarantees(self, garanties: List[Dict]) -> List[Guarantee]:
        """Parse guarantees from garanties array"""
        guarantees = []
        
        for g_data in garanties:
            # Skip if not included
            if not g_data.get("included", False):
                continue
                
            guarantee = Guarantee(
                name=g_data.get("libelle", ""),
                code=g_data.get("codeGarantie", ""),
                capital=float(g_data.get("capitalGarantie", 0)) if g_data.get("capitalGarantie") else None,
                franchise=g_data.get("franchise"),
                prime_annual=g_data.get("primeAnnuelle", 0),
                is_included=g_data.get("included", False),
                is_obligatory=g_data.get("obligatoire", False),
                is_optional=g_data.get("optionnelle", False),
                order=g_data.get("ordre", 0)
            )
            guarantees.append(guarantee)
        
        # Sort by order
        guarantees.sort(key=lambda x: x.order)
        return guarantees
    
    def _parse_response(self, response_data: Any) -> List[InsurancePlan]:
        """Parse RMA API response into InsurancePlan objects"""
        plans = []
        
        if not isinstance(response_data, list):
            return plans
        
        for idx, offer in enumerate(response_data):
            plan_name = offer.get("libelle", f"Plan {idx + 1}")
            
            # Parse guarantees
            guarantees = self._parse_guarantees(offer.get("garanties", []))
            
            # Check eligibility
            is_eligible = offer.get("eligible", True)
            
            # Get pricing
            prime_net_annual = offer.get("primeAnnuelleHT", 0) or 0
            taxes = offer.get("taxes", 0) or 0
            tax_parafiscal = offer.get("taxeParafiscal", 0) or 0
            prime_total_annual = offer.get("primeAnnuelleTTC", 0) or 0
            cnpac = offer.get("taxeCNPAC", 0) or 0
            accessoires = offer.get("accessoires", 0) or 0
            timbre = offer.get("timbre", 0) or 0
            
            # Prorata values (for semi-annual estimation)
            prime_prorata = offer.get("primeProrataHT", 0) or 0
            taxes_prorata = offer.get("taxesProrata", 0) or 0
            prime_total_prorata = offer.get("primeProrataTTC", 0) or 0
            
            # Calculate semi-annual (roughly half + admin)
            semi_annual_factor = 0.52
            
            plan = InsurancePlan(
                provider=self.PROVIDER_NAME,
                provider_code=self.PROVIDER_CODE,
                plan_name=plan_name,
                plan_code=str(offer.get("id", "")),
                
                # Annual pricing
                prime_net_annual=prime_net_annual,
                taxes_annual=taxes + tax_parafiscal,
                prime_total_annual=prime_total_annual,
                cnpac=cnpac,
                accessoires=accessoires,
                timbre=timbre,
                tax_parafiscal=tax_parafiscal,
                
                # Semi-annual pricing (estimate)
                prime_net_semi_annual=round(prime_net_annual * semi_annual_factor, 2),
                taxes_semi_annual=round((taxes + tax_parafiscal) * semi_annual_factor, 2),
                prime_total_semi_annual=round(prime_total_annual * semi_annual_factor, 2),
                
                # Guarantees
                guarantees=guarantees,
                
                # Display
                color=self.PLAN_COLORS.get(plan_name, self.PROVIDER_COLOR),
                is_promoted=(plan_name == "OPTIMAL OTO"),
                is_eligible=is_eligible,
                order=idx,
                
                # Extra info
                extra_info={
                    "id": offer.get("id"),
                    "avec_mode_confort": offer.get("avecModeConfort", False),
                    "constraints": offer.get("constraints", []),
                    "base_prime_annual": offer.get("basePrimeAnnuelle", 0),
                    "compl_prime_annual": offer.get("complPrimeAnnuelle", 0)
                }
            )
            plans.append(plan)
        
        return plans
