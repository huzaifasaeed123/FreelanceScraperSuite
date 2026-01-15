"""
Field Mapper for Insurance Quotation Forms
Maps form fields to provider-specific requirements with transformations
"""

from typing import Dict, Any
from datetime import datetime
import random
import string

# ============ BRAND MAPPING ============
BRAND_CODE_MAPPING = {
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

# ============ RANDOM EMAIL GENERATOR ============
def generate_random_email() -> str:
    """Generate a dummy random email"""
    random_id = ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))
    return f"user_{random_id}@dummy-insurance.test"

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

        # Dummy/Hardcoded values as mentioned
        return {
            "driver": {
                "licenseNumber": "1111111111",
                "licenseDate": format_date(form_data.get('date_permis'), "YYYY-MM-DD"),
                "licenseCategory": "B",
                "lastName": form_data.get('nom', 'Client'),
                "firstName": form_data.get('prenom', 'Test'),
                "birthDate": format_date(form_data.get('date_naissance'), "YYYY-MM-DD"),
                "CIN": "BJ1111111",  # Dummy/Hardcoded
                "sex": "M",  # Dummy/Hardcoded
                "nature": "1",  # Dummy/Hardcoded
                "adress": "sample address",  # Dummy/Hardcoded
                "city": form_data.get('ville', 'AIN AICHA'),
                "phoneNumber": form_data.get('telephone', '+212661652022'),
                "title": "0",  # Dummy/Hardcoded
                "profession": "12",  # Dummy/Hardcoded
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
                "adress": "sample address",
                "city": form_data.get('ville', 'AIN AICHA'),
                "phoneNumber": form_data.get('telephone', '+212661652022'),
                "licenseNumber": "1111111111",
                "licenseDate": format_date(form_data.get('date_permis'), "YYYY-MM-DD"),
                "licenseCategory": "B",
                "profession": "12",
                "postalCode": "20300",
                "sex": "M"
            },
            "vehicle": {
                "registrationNumber": form_data.get('immatriculation', '11111-A-7'),
                "brand": BRAND_CODE_MAPPING.get(form_data.get('marque', 'renault').lower(), "2078"),
                "horsePower": str(form_data.get('puissance_fiscale', 6)),
                "model": form_data.get('modele', 'Autres'),
                "usageCode": "1",  # Dummy/Hardcoded
                "registrationFormat": PLATE_TYPE_MAPPING['sanlam'].get(form_data.get('type_plaque', 'standard'), "3"),
                "newValue": int(form_data.get('valeur_neuf', 650000)),
                "combustion": FUEL_MAPPING['sanlam'].get(fuel, 'D'),
                "circulationDate": format_date(form_data.get('date_mec'), "YYYY-MM-DD"),
                "marketValue": int(form_data.get('valeur_actuelle', 650000)),
                "seatsNumber": form_data.get('nombre_places', 5)
            },
            "policy": {
                "startDate": datetime.now().strftime("%Y-%m-%d"),
                "endDate": "2026-12-31",
                "maturityContractType": "2",
                "duration": 12
            },
            "agent": {
                "agentkey": "68103"  # Dummy/Hardcoded
            },
            "recaptcha": ""
        }

    @staticmethod
    def map_to_axa(form_data: Dict[str, Any]) -> Dict[str, Any]:
        """Map form data to AXA API payload"""
        fuel = form_data.get('carburant', 'diesel').lower()
        future_date = datetime.now().strftime("%d-%m-%Y")

        return {
            "contrat": {
                "codeIntermediaire": 474,  # Dummy/Hardcoded
                "codeProduit": 115,  # Dummy/Hardcoded
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
                "identifiant": "a0"
            },
            "vehiculeInfos": {
                "marque": form_data.get('marque', 'Renault'),
                "modele": form_data.get('modele', 'Clio'),
                "carburant": FUEL_MAPPING['axa'].get(fuel, 'G'),
                "nbPlaces": form_data.get('nombre_places', 5),
                "puissanceFiscale": form_data.get('puissance_fiscale', 6),
                "dateMiseEnCirculation": format_date(form_data.get('date_mec'), "DD-MM-YYYY"),
                "typePlaque": PLATE_TYPE_MAPPING['axa'].get(form_data.get('type_plaque', 'standard'), 'FX'),
                "immatriculation": form_data.get('immatriculation', 'WW378497'),
                "valeurNeuf": int(form_data.get('valeur_neuf', 200000)),
                "valeurVenale": int(form_data.get('valeur_actuelle', 150000))
            },
            "assurerInfos": {
                "nomAssure": form_data.get('nom', 'Client'),
                "prenomAssure": form_data.get('prenom', 'Test'),
                "telephoneAssure": form_data.get('telephone', '0661652022'),
                "emailAssure": form_data.get('email', generate_random_email()),
                "dateNaissance": format_date(form_data.get('date_naissance'), "DD-MM-YYYY"),
                "codeVille": CITY_CODE_MAPPING.get(form_data.get('ville', 'Casablanca'), "1")
            },
            "conducteurInfos": {
                "dateObtentionPermis": format_date(form_data.get('date_permis'), "DD-MM-YYYY")
            }
        }

    @staticmethod
    def map_to_rma(form_data: Dict[str, Any]) -> Dict[str, Any]:
        """Map form data to RMA API payload"""
        fuel = form_data.get('carburant', 'diesel').lower()

        return {
            "nomOrRaisonSociale": form_data.get('nom', 'Client'),
            "prenom": form_data.get('prenom', 'Test'),
            "titreCivilite": "1",  # Dummy/Hardcoded
            "typePieceIdentite": "1",  # Dummy/Hardcoded
            "situationFamiliale": "C",  # Dummy/Hardcoded (Single)
            "telephone": form_data.get('telephone', '0661652022'),
            "dateNaissance": format_date(form_data.get('date_naissance'), "DD-MM-YYYY"),
            "idVilleAdresse": CITY_CODE_MAPPING.get(form_data.get('ville', 'Casablanca'), "1"),
            "dateObtentionPermis": format_date(form_data.get('date_permis'), "DD-MM-YYYY"),
            "sexeConducteur": "M",  # Dummy/Hardcoded
            "sexe": "M",  # Dummy/Hardcoded
            "idPaysPermisConducteur": "212",  # Morocco code
            "idPaysPermis": "212",  # Morocco code
            "professionConducteur": "99",  # Dummy/Hardcoded
            "profession": "99",  # Dummy/Hardcoded
            "numeroClient": "308252166",  # Dummy/Hardcoded
            "numeroClientConducteur": "308252166",  # Dummy/Hardcoded
            "telephoneConducteur": form_data.get('telephone', '0661652022'),
            "nomOrRaisonSocialeConducteur": form_data.get('nom', 'Client'),
            "prenomConducteur": form_data.get('prenom', 'Test'),
            "situationFamilialeConducteur": "C",  # Dummy/Hardcoded
            "dateNaissanceConducteur": format_date(form_data.get('date_naissance'), "DD-MM-YYYY"),
            "marque": form_data.get('marque', 'Renault'),
            "modele": form_data.get('modele', 'Clio'),
            "carburant": FUEL_MAPPING['rma'].get(fuel, '2'),
            "nombrePlaces": form_data.get('nombre_places', 5),
            "puissanceFiscale": form_data.get('puissance_fiscale', 6),
            "dateCirculation": format_date(form_data.get('date_mec'), "DD-MM-YYYY"),
            "typePlaque": PLATE_TYPE_MAPPING['rma'].get(form_data.get('type_plaque', 'standard'), 'FX'),
            "immatriculation": form_data.get('immatriculation', 'WW378497'),
            "valeurNeuve": int(form_data.get('valeur_neuf', 200000)),
            "valeurVenale": int(form_data.get('valeur_actuelle', 150000))
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
