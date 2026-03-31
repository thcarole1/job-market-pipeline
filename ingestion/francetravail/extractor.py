# ingestion/francetravail/extractor.py

import json
import time
from datetime import datetime
from pathlib import Path
from ingestion.francetravail.api_client import FranceTravailClient

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent.parent / ".env")

# Nombre maximum d'offres par page autorisé par l'API
PAGE_SIZE = 100

def extraire_offres(
    mots_cles:    str = "data engineer",
    nb_pages_max: int = 10,
    avec_details: bool = False,
) -> list:
    """
    Extrait les offres FranceTravail pour un mot-clé donné.

    mots_cles    : termes de recherche
    nb_pages_max : nombre de pages à parcourir (100 offres par page)
    avec_details : si True, récupère le détail complet de chaque offre

    Retourne une liste de dictionnaires bruts.
    """
    client  = FranceTravailClient()
    offres  = []
    page    = 0

    while page < nb_pages_max:
        debut = page * PAGE_SIZE
        fin   = debut + PAGE_SIZE - 1

        params = {
            "motsCles": mots_cles,
            "range":    f"{debut}-{fin}",
            "sort":     "1",  # tri par date de publication
        }

        print(f"Page {page + 1} — offres {debut} à {fin}...")

        try:
            data = client.rechercher_offres(params)
        except Exception as e:
            print(f"Erreur page {page + 1} : {e}")
            break

        resultats = data.get("resultats", [])

        if not resultats:
            print("Plus d'offres disponibles, arrêt.")
            break

        # Optionnel : enrichir avec le détail complet de chaque offre
        if avec_details:
            resultats = _enrichir_avec_details(client, resultats)

        offres.extend(resultats)
        page += 1

        # Délai poli entre les pages
        time.sleep(0.5)

    print(f"\nTotal extrait : {len(offres)} offres")
    return offres


def _enrichir_avec_details(
    client:    FranceTravailClient,
    resultats: list,
) -> list:
    """
    Pour chaque offre de la liste, récupère son détail complet.
    Utile pour avoir la description complète et toutes les compétences.
    """
    enrichis = []
    for offre in resultats:
        offre_id = offre.get("id")
        if not offre_id:
            enrichis.append(offre)
            continue
        try:
            detail = client.get_offre(offre_id)
            enrichis.append(detail)
            time.sleep(0.2)  # respecter le rate limit
        except Exception as e:
            print(f"Impossible de récupérer le détail {offre_id} : {e}")
            enrichis.append(offre)  # on garde la version partielle
    return enrichis


def sauvegarder_brut(offres: list, mots_cles: str = "") -> str:
    """
    Sauvegarde les données brutes dans data/raw/francetravail/
    avec un timestamp dans le nom de fichier.
    Retourne le chemin du fichier créé.
    """
    Path("data/raw/francetravail").mkdir(parents=True, exist_ok=True)

    timestamp   = datetime.now().strftime("%Y%m%d_%H%M%S")
    slug        = mots_cles.replace(" ", "_") if mots_cles else "offres"
    chemin      = f"data/raw/francetravail/{slug}_{timestamp}.json"

    with open(chemin, "w", encoding="utf-8") as f:
        json.dump(offres, f, ensure_ascii=False, indent=2)

    print(f"Sauvegardé : {chemin}")
    return chemin


if __name__ == "__main__":
    # Point d'entrée — lance l'extraction directement
    mots_cles = "data engineer"

    offres = extraire_offres(
        mots_cles    = mots_cles,
        nb_pages_max = 5,
        avec_details = False,  # passer à True pour les descriptions complètes
    )

    sauvegarder_brut(offres, mots_cles)