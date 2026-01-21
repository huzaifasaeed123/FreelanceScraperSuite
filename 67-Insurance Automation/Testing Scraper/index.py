import json
from scrapers.mcma_scraper import scrape_mcma_with_options
# from scrapers.rma_scraper import scrape_rma
from scrapers.axa_scraper import scrape_axa
from scrapers.sanlam_scraper import scrape_sanlam


def save_result(website_name, data):
    filename = f"{website_name}_result.json"
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)
    print(f"[SUCCESS] {website_name} result saved to {filename}")


def run_all_scrapers(payload):
    print("\nStarting all scrapers...\n")

    print("=" * 50)
    print("Running MCMA Scraper (with options)...")
    print("=" * 50)
    try:
        mcma_result = scrape_mcma_with_options(payload)
        if mcma_result:
            save_result("mcma", mcma_result)
        else:
            print("[FAILED] MCMA scraper failed")
    except Exception as e:
        print(f"[ERROR] MCMA error: {str(e)}")

    print("\n" + "=" * 50)
    print("Running RMA Scraper...")
    print("=" * 50)
    # try:
    #     rma_result = scrape_rma(payload)
    #     if rma_result:
    #         save_result("rma", rma_result)
    #     else:
    #         print("[FAILED] RMA scraper failed")
    # except Exception as e:
    #     print(f"[ERROR] RMA error: {str(e)}")

    print("\n" + "=" * 50)
    print("Running AXA Scraper...")
    print("=" * 50)
    try:
        axa_result = scrape_axa(payload)
        if axa_result:
            save_result("axa", axa_result)
        else:
            print("[FAILED] AXA scraper failed")
    except Exception as e:
        print(f"[ERROR] AXA error: {str(e)}")

    print("\n" + "=" * 50)
    print("Running Sanlam Scraper...")
    print("=" * 50)
    try:
        sanlam_result = scrape_sanlam(payload)
        if sanlam_result:
            save_result("sanlam", sanlam_result)
        else:
            print("[FAILED] Sanlam scraper failed")
    except Exception as e:
        print(f"[ERROR] Sanlam error: {str(e)}")

    print("\n" + "=" * 50)
    print("All scrapers completed!")
    print("=" * 50)


if __name__ == "__main__":
    test_payload = {
        "marque": "mercedes",
        "modele": "fdsfd",
        "carburant": "diesel",
        "nombre_places": 5,
        "puissance_fiscale": 6,
        "date_mec": "2023-01-01",
        "type_plaque": "standard",
        "immatriculation": "00000-F-00",
        "valeur_neuf": 400000,
        "valeur_actuelle": 300000,
        "nom": "Huzaifa",
        "prenom": "Saeed",
        "telephone": "0566666666",
        "email": "FA21-BCS-020@cuiatd.edu.pk",
        "date_naissance": "1991-01-01",
        "date_permis": "2012-01-01",
        "ville": "EL KELAA DES SRAGHNA",
        "agent_key": "50519",
        "assureur_actuel": "gffd",
        "consent": True
    }

    run_all_scrapers(test_payload)
