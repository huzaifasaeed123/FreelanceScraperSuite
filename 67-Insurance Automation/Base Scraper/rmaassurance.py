import requests
import time
import json
from pathlib import Path

BASE_DIR = Path(__file__).parent

class RMAClient:
    def __init__(self):
        self.session = requests.Session()
        self.access_token = None
        self.token_expiry = 0  # unix timestamp

    # -------------------------------------------------
    # 1️⃣ Get JWT Token
    # -------------------------------------------------
    def get_access_token(self):
        url = "https://direct.rmaassurance.com/canaldirect/auth/api/token"
        params = {
            "csrt": "10651071086600842364"
        }

        headers = {
            "User-Agent": "Mozilla/5.0",
            "Accept": "*/*",
            "X-Ts-Ajax-Request": "true",
            "X-Security-Csrf-Token": "08553bbd45ab28005d86670b015bbbef2fb54e2a9d8594b3b1d3723b8159ff014c78580f30e2b3b41d94d0813e29e1dc",
            "Referer": "https://direct.rmaassurance.com/souscrire",
        }

        response = self.session.get(url, headers=headers, params=params)
        response.raise_for_status()

        data = response.json()

        self.access_token = data["accessToken"]
        self.token_expiry = time.time() + data.get("expiresIn", 7200)

        print("✅ Access token fetched")
        print("⏳ Expires in:", data.get("expiresIn"), "seconds")

        return self.access_token

    # -------------------------------------------------
    # 2️⃣ Ensure Token Is Valid
    # -------------------------------------------------
    def ensure_token(self):
        if not self.access_token or time.time() >= self.token_expiry - 60:
            print("🔄 Fetching new token...")
            self.get_access_token()

    # -------------------------------------------------
    # 3️⃣ Call Offers API
    # -------------------------------------------------
    def fetch_offers(self):
        self.ensure_token()

        url = "https://direct.rmaassurance.com/canaldirect/offer/api/offers"
        params = {
            "csrt": "1104538121806306204"
        }

        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Origin": "https://direct.rmaassurance.com",
            "Referer": "https://direct.rmaassurance.com/souscrire",
            "User-Agent": "Mozilla/5.0",
            "X-Ts-Ajax-Request": "true",
            "X-Security-Csrf-Token": "08553bbd45ab2800849d2efccc6dbf865ac80ec883891a2d12bf6d0a9ce1a81c89e1ce5da3891083e93786eabaa721e9",
        }

        payload = {
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
            "valeurANeuf": "65000",
            "valeurVenale": "45000",
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

        response = self.session.post(
            url,
            headers=headers,
            params=params,
            json=payload
        )

        response.raise_for_status()
        data = response.json()

        # Save locally
        output_file = BASE_DIR / "offers_response.json"
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        print("✅ Offers fetched successfully")
        print(json.dumps(data, indent=2))

        return data





# -------------------------------------------------
# 🚀 Run
# -------------------------------------------------
if __name__ == "__main__":
    client = RMAClient()
    client.fetch_offers()
