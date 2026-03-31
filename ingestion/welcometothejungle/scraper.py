# ingestion/welcometothejungle/scraper.py

import json
import asyncio
from datetime import datetime
from pathlib import Path
from playwright.async_api import async_playwright


async def scraper_wttj(nb_pages: int = 3) -> list:
    """
    Scrape les offres Welcome to the Jungle via l'API Algolia interne.
    Simule un vrai navigateur Chrome pour contourner les restrictions CORS.

    nb_pages : nombre de pages à récupérer (20 offres par page)
    Retourne une liste de dictionnaires bruts.
    """
    toutes_offres = []

    async with async_playwright() as p:

        browser = await p.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled"]
        )

        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1920, "height": 1080},
            locale="fr-FR",
        )

        await context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
        """)

        page = await context.new_page()

        await page.goto(
            "https://www.welcometothejungle.com/fr/jobs?"
            "refinementList%5Boffice_country_codes%5D%5B%5D=FR"
            "&query=data+engineer",
            wait_until="domcontentloaded"
        )

        await page.wait_for_timeout(2000)

        for numero_page in range(nb_pages):
            print(f"Page {numero_page + 1}/{nb_pages}...")

            try:
                resultats = await page.evaluate(f"""
                    async () => {{
                        const response = await fetch(
                            "https://CSEKHVMS53-dsn.algolia.net/1/indexes/wttj_jobs_production_fr/query",
                            {{
                                method: "POST",
                                headers: {{
                                    "X-Algolia-Application-Id": "CSEKHVMS53",
                                    "X-Algolia-API-Key": "4bd8f6215d0cc52b26430765769e65a0",
                                    "Content-Type": "application/json"
                                }},
                                body: JSON.stringify({{
                                    query: "data engineer",
                                    hitsPerPage: 20,
                                    page: {numero_page}
                                }})
                            }}
                        );
                        return await response.json();
                    }}
                """)

            except Exception as e:
                print(f"Erreur page {numero_page + 1} : {e}")
                break

            hits    = resultats.get("hits", [])
            nb_hits = resultats.get("nbHits", 0)

            print(f"  → {len(hits)} offres, {nb_hits} au total")

            if not hits:
                print("Plus d'offres disponibles, arrêt.")
                break

            toutes_offres.extend(hits)
            await page.wait_for_timeout(500)

        await browser.close()

    return toutes_offres


def sauvegarder_brut(offres: list) -> str:
    """
    Sauvegarde les offres brutes dans data/raw/welcometothejungle/
    avec un timestamp dans le nom de fichier.
    Retourne le chemin du fichier créé.
    """
    Path("data/raw/welcometothejungle").mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    chemin    = f"data/raw/welcometothejungle/offres_{timestamp}.json"

    with open(chemin, "w", encoding="utf-8") as f:
        json.dump(offres, f, ensure_ascii=False, indent=2)

    print(f"Sauvegardé : {chemin} ({len(offres)} offres)")
    return chemin


if __name__ == "__main__":
    # asyncio.run() remplace le await direct — obligatoire hors notebook
    offres = asyncio.run(scraper_wttj(nb_pages=3))

    print(f"\nTotal : {len(offres)} offres récupérées")

    '''
    if offres:
        print("\nClés disponibles :")
        print(list(offres[0].keys()))
    '''

    sauvegarder_brut(offres)