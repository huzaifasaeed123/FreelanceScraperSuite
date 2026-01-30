"""
Field Mapper for Insurance Quotation Forms
Maps form fields to provider-specific requirements with transformations
"""

from typing import Dict, Any
from datetime import datetime, timedelta
try:
    from zoneinfo import ZoneInfo
except ImportError:
    # Fallback for Python < 3.9
    from pytz import timezone as ZoneInfo
import random
import string

# ============ BRAND MAPPING ============
BRAND_CODE_MAPPING = {
    "sanlam": {
        "renault": "2078",
        "peugeot": "3016",
        "citroen": "2054",
        "volkswagen": "2900",
        "ford": "2300",
        "bmw": "1976",
        "mercedes": "10819",
        "audi": "2003",
        "hyundai": "2500",
        "kia": "2700",
        "toyota": "2860",
        "dacia": "2100",
        "fiat": "2200",
        "nissan": "2800",
        "mazda": "2700",
    },
    "other": {
        "renault": "2078",
        "peugeot": "3016",
        "citroen": "2054",
        "volkswagen": "2900",
        "ford": "2300",
        "bmw": "1976",
        "mercedes": "2750",
        "audi": "2003",
        "hyundai": "2500",
        "kia": "2700",
        "toyota": "2860",
        "dacia": "2100",
        "fiat": "2200",
        "nissan": "2800",
        "mazda": "2700",
    }
}

# ============ FUEL TYPE MAPPING ============
FUEL_MAPPING = {
    "sanlam": {
        "essence": "E",
        "diesel": "D",
        "hybrid-e": "S",  # Hybrid Essence
        "hybrid-d": "M",  # Hybrid Diesel
        "electrique": "L"  # Electric
    },
    "axa": {
        "essence": "E",
        "diesel": "G",  # AXA uses G for Diesel
        "hybrid-e": "E",  # Map hybrid-e to essence
        "hybrid-d": "G",  # Map hybrid-d to diesel
        "electrique": "W"  # AXA uses W for Electric
    },
    "rma": {
        "essence": "1",       # RMA position 1
        "diesel": "2",        # RMA position 2
        "hybrid-e": "4",      # RMA position 4
        "hybrid-d": "5",      # RMA position 5
        "electrique": "3"     # RMA position 3 (electric)
    },
    "mcma": {
        "essence": "Essence",
        "diesel": "Diesel",
        "hybrid-e": "Essence",
        "hybrid-d": "Diesel",
        "electrique": None  # MCMA doesn't support electric - return None to skip
    }
}

# ============ PLATE TYPE MAPPING ============
PLATE_TYPE_MAPPING = {
    "sanlam": {
        "standard": "3",
        "ww": "2"
    },
    "axa": {
        "standard": "FX",
        "ww": "WW"
    },
    "rma": {
        "standard": "FX",
        "ww": "WW"
    },
    "mcma": {}  # MCMA doesn't need plate type
}

# ============ CITY CODE MAPPING (DUMMY/HARDCODED) ============
CITY_CODE_MAPPING = {
    "Casablanca": "1",
    "Rabat": "2",
    "Fès": "3",
    "Marrakech": "4",
    "Agadir": "5",
    "Tanger": "6",
    "Oujda": "7",
    "Meknès": "9",
    "Kénitra": "10",
    "Salé": "11",
    "Tétouan": "12",
    "Settat": "13",
    "El Jadida": "14",
    "Essaouira": "15",
    "Khemisset": "16"
}
# ============ RANDOM IDENTITY GENERATOR ============
def generate_random_identity():
    # Random phone: 06 + 8 digits
    phone = "06" + "".join(random.choices(string.digits, k=8))
    # Random plate: 5 digits - F/A - 2 digits (e.g. 00012-F-34)
    five_digits = "".join(random.choices(string.digits, k=5))
    letter = random.choice(["F", "A"])
    two_digits = "".join(random.choices(string.digits, k=2))
    plate = f"{five_digits}-{letter}-{two_digits}"

    # WW + 6 digits (e.g. WW123456)

    return {
        "phone": phone,
        "plate": plate,
    }

# ============ DATE FORMATTER ============
def format_date(date_str: str, format_type: str = "YYYY-MM-DD") -> str:
    """
    Format date string to required format
    Inputs: YYYY-MM-DD (from HTML date input)
    Outputs: DD-MM-YYYY, YYYY-MM-DD, or as needed
    """
    if not date_str:
        return ""

    try:
        # Parse from YYYY-MM-DD
        date_obj = datetime.strptime(date_str, "%Y-%m-%d")

        if format_type == "DD-MM-YYYY":
            return date_obj.strftime("%d-%m-%Y")
        elif format_type == "YYYY-MM-DD":
            return date_obj.strftime("%Y-%m-%d")
        else:
            return date_str
    except Exception as e:
        print(f"Date format error: {e}")
        return date_str

# ============ FIELD MAPPER CLASS ============
class FieldMapper:
    """Maps form fields to provider-specific payloads"""

    @staticmethod
    def map_to_sanlam(form_data: Dict[str, Any]) -> Dict[str, Any]:
        """Map form data to Sanlam API payload"""
        fuel = form_data.get('carburant', 'diesel').lower()
        brand = form_data.get('marque', 'mercedes').lower()

        # Get dummy identity for phone/plate
        dummy = generate_random_identity()

        # Format phone for Sanlam (+212 format) - remove leading 0 from 06XXXXXXXX
        phone = dummy['phone']  # Format: 06XXXXXXXX
        if phone.startswith('0'):
            phone = '+212' + phone[1:]  # Remove the 0 and add +212
        elif not phone.startswith('+212'):
            phone = '+212' + phone

        # Get brand code for Sanlam
        brand_code = BRAND_CODE_MAPPING['sanlam'].get(brand, '10819')

        return {
            "driver": {
                "licenseNumber": "1111111111",
                "licenseDate": "2026-01-16",
                "licenseCategory": "B",
                "lastName": form_data.get('nom', 'Client'),
                "firstName": form_data.get('prenom', 'Test'),
                "birthDate": format_date(form_data.get('date_naissance'), "YYYY-MM-DD"),
                "CIN": "BJ1111111",
                "sex": "M",
                "nature": "1",
                "adress": "sample addresse",
                "city": form_data.get('ville', 'Casablanca'),
                "phoneNumber": phone,
                "title": "0",
                "profession": "12",
                "isDriver": True
            },
            "subscriber": {
                "isDriver": True,
                "nature": "1",
                "CIN": "BJ1111111",
                "civility": "0",
                "lastName": form_data.get('nom', 'Client'),
                "firstName": form_data.get('prenom', 'Test'),
                "birthDate": format_date(form_data.get('date_naissance'), "YYYY-MM-DD"),
                "adress": "sample addresse",
                "city": form_data.get('ville', 'Casablanca'),
                "phoneNumber": phone,
                "licenseNumber": "1111111111",
                "licenseDate": "2004-01-16",
                "licenseCategory": "B",
                "profession": "12",
                "postalCode": "20300",
                "sex": "M"
            },
            "vehicle": {
                "registrationNumber": dummy['plate'],
                "brand": "8",
                "horsePower": str(form_data.get('puissance_fiscale', 6)),
                "model": "Autres",
                "usageCode": "1",
                "registrationFormat": PLATE_TYPE_MAPPING['sanlam'].get(form_data.get('type_plaque', 'standard'), "3"),
                "newValue": int(form_data.get('valeur_neuf', 650000)),
                "combustion": FUEL_MAPPING['sanlam'].get(fuel, 'D'),
                "circulationDate": format_date(form_data.get('date_mec'), "YYYY-MM-DD"),
                "marketValue": int(form_data.get('valeur_actuelle', 650000)),
                "seatsNumber": 5
            },
            "policy": {
                "startDate": datetime.now().strftime("%Y-%m-%d"),
                "endDate": "2027-01-17",
                "maturityContractType": "2",
                "duration": 12
            },
            "agent": {
                "agentkey": form_data.get('agent_key', "40213")
            },
            "recaptcha": ""
        }

    @staticmethod
    def map_to_axa(form_data: Dict[str, Any]) -> Dict[str, Any]:
        """Map form data to AXA API payload"""
        fuel = form_data.get('carburant', 'diesel').lower()
        # Get today's date in Morocco timezone (Africa/Casablanca) - where AXA servers are located
        morocco_tz = ZoneInfo('Africa/Casablanca')
        morocco_now = datetime.now(morocco_tz)
        future_date = morocco_now.strftime("%d-%m-%Y")

        # Get dummy identity for phone/plate
        dummy = generate_random_identity()

        return {
            "contrat": {
                "codeIntermediaire": 592,
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
                "dateNaissanceConducteur": format_date(form_data.get('date_naissance'), "DD-MM-YYYY"),
                "isFonctionnaire": "N",
                "codeConvention": 0,
                "newClient": "O",
                "nom": form_data.get('nom', 'Client'),
                "prenom": form_data.get('prenom', 'Test'),
                "dateNaissanceAssure": format_date(form_data.get('date_naissance'), "DD-MM-YYYY"),
                "tauxReduction": 0
            },
            "vehicule": {
                "codeUsage": "1B",
                "dateMisCirculation": format_date(form_data.get('date_mec'), "DD-MM-YYYY"),
                "matricule": dummy['plate'],
                "valeurNeuf": int(form_data.get('valeur_neuf', 400000)),
                "valeurVenale": int(form_data.get('valeur_actuelle', 300000)),
                "valeurAmenagement": 0,
                "energie": FUEL_MAPPING['axa'].get(fuel, 'G'),
                "puissanceFiscale": form_data.get('puissance_fiscale', 6),
                "codeCarrosserie": "B1",
                "codeMarque": 7,
                "nombrePlace": form_data.get('nombre_places', 5),
                "dateMutation": "0"
            },
            "leadInfos": {
                "city": "CASABLANCA",
                "phoneNumber": dummy['phone'],
                "licenceDate": format_date(form_data.get('date_permis'), "DD-MM-YYYY"),
                "brandName": form_data.get('marque', 'RENAULT').upper(),
                "intermediateName": "AKER ASSURANCE",
                "marketingConsent": True,
                "cguConsent": True
            }
        }

    @staticmethod
    def map_to_rma(form_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Map form data to RMA browser-based scraper payload
        
        This function now maps website form data directly to RMA scraper parameters.
        The RMA scraper uses browser automation to fill the form, so we pass the form data
        directly without API payload transformation.
        
        Args:
            form_data: Form data from website
        
        Returns:
            Dictionary suitable for RMA scraper (rma_scraper.scrape_rma)
        """
        dummy = generate_random_identity()
        return {
            "nom": form_data.get('nom', 'Client'),
            "prenom": form_data.get('prenom', 'Test'),
            "carburant": form_data.get('carburant', 'diesel'),
            "puissance_fiscale": form_data.get('puissance_fiscale', 6),
            "date_mec": form_data.get('date_mec', '2020-01-01'),
            "type_plaque": "standard",
            "immatriculation": dummy['plate'],
            "valeur_neuf": form_data.get('valeur_neuf', 200000),
            "valeur_actuelle": form_data.get('valeur_actuelle', 150000),
            "nombre_places": form_data.get('nombre_places', 5),
            "date_naissance": form_data.get('date_naissance', '1990-01-01'),
            "telephone": dummy['phone'],
            "date_permis": form_data.get('date_permis', '2010-01-01'),
            "ville": form_data.get('ville', 'CASABLANCA')
        }

    @staticmethod
    def map_to_mcma(form_data: Dict[str, Any]) -> Dict[str, Any]:
        """Map form data to MCMA API payload"""
        fuel = form_data.get('carburant', 'diesel').lower()

        return {
            "dateOfCirculation": format_date(form_data.get('date_mec'), "YYYY-MM-DD"),
            "horsePower": form_data.get('puissance_fiscale', 6),
            "fuel": FUEL_MAPPING['mcma'].get(fuel, 'Diesel'),
            "valueOfVehicle": int(form_data.get('valeur_actuelle', 150000)),
            "valueOfNewVehicle": int(form_data.get('valeur_neuf', 200000)),
            "agreeToTerms": True
        }

    @staticmethod
    def map_for_scraper(form_data: Dict[str, Any], provider: str) -> Dict[str, Any]:
        """
        Main entry point to map form data to specific scraper payload

        Args:
            form_data: Complete form data from user
            provider: Provider code (sanlam, axa, rma, mcma)

        Returns:
            Provider-specific payload
        """
        provider_lower = provider.lower()

        if provider_lower == "sanlam":
            return FieldMapper.map_to_sanlam(form_data)
        elif provider_lower == "axa":
            return FieldMapper.map_to_axa(form_data)
        elif provider_lower == "rma":
            return FieldMapper.map_to_rma(form_data)
        elif provider_lower == "mcma":
            return FieldMapper.map_to_mcma(form_data)
        else:
            # Default fallback to form data
            return form_data
