# ingestion/francetravail/extractor.py

import json
import time
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent.parent / ".env")

from ingestion.francetravail.api_client import FranceTravailClient
from ingestion.francetravail.parser import parser_offre_ft

# Nombre maximum d'offres par page autorisé par l'API FranceTravail
PAGE_SIZE = 100


# ─────────────────────────────────────────────────────────────────────
# ÉTAPE 1 — EXTRACTION BRUTE
# ─────────────────────────────────────────────────────────────────────

def extraire_offres(
    mots_cles:    str  = "data engineer",
    nb_pages_max: int  = 10,
    avec_details: bool = False,
) -> list:
    """
    Extrait les offres FranceTravail pour un mot-clé donné.

    mots_cles    : termes de recherche
    nb_pages_max : nombre de pages à parcourir (100 offres par page)
    avec_details : si True, récupère le détail complet de chaque offre
                   (description complète + toutes les compétences)

    Retourne une liste de dictionnaires bruts tels que retournés par l'API.
    """
    client = FranceTravailClient()
    offres = []
    page   = 0

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

        # Optionnel : enrichir chaque offre avec son détail complet
        # Utile pour récupérer la description longue et toutes les compétences
        if avec_details:
            resultats = _enrichir_avec_details(client, resultats)

        offres.extend(resultats)
        page += 1

        # Délai poli entre les pages pour respecter le rate limit
        time.sleep(0.5)

    print(f"\nTotal extrait : {len(offres)} offres")
    return offres


def _enrichir_avec_details(
    client:    FranceTravailClient,
    resultats: list,
) -> list:
    """
    Pour chaque offre de la liste, récupère son détail complet via l'API.
    Si la récupération échoue, conserve la version partielle sans planter.
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
            time.sleep(0.2)  # respecter le rate limit entre chaque appel
        except Exception as e:
            print(f"Impossible de récupérer le détail {offre_id} : {e}")
            enrichis.append(offre)  # on garde la version partielle

    return enrichis


# ─────────────────────────────────────────────────────────────────────
# ÉTAPE 2 — SAUVEGARDE BRUTE
# ─────────────────────────────────────────────────────────────────────

def sauvegarder_brut(offres: list, mots_cles: str = "", timestamp: str = None) -> str:
    """
    Sauvegarde les données brutes dans data/raw/francetravail/
    avec un timestamp dans le nom de fichier.

    On conserve toujours les données brutes avant transformation.
    Si le parsing est à revoir, on peut relancer sans refaire l'extraction.

    Retourne le chemin du fichier créé.
    """
    Path("data/raw/francetravail").mkdir(parents=True, exist_ok=True)

    if not timestamp:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
    slug      = mots_cles.replace(" ", "_") if mots_cles else "offres"
    chemin    = f"data/raw/francetravail/{slug}_{timestamp}.json"

    with open(chemin, "w", encoding="utf-8") as f:
        json.dump(offres, f, ensure_ascii=False, indent=2)

    print(f"Brut sauvegardé : {chemin} ({len(offres)} offres)")
    return chemin


# ─────────────────────────────────────────────────────────────────────
# ÉTAPE 3 — PARSING
# ─────────────────────────────────────────────────────────────────────

def parser_et_sauvegarder(offres_brutes: list) -> list:
    """
    Parse toutes les offres brutes via parser_offre_ft().
    Les erreurs de parsing sont loguées sans interrompre le traitement —
    une offre mal formée ne doit pas bloquer les suivantes.

    Retourne la liste des offres parsées et structurées.
    """
    offres_parsees = []
    erreurs        = 0

    for i, offre in enumerate(offres_brutes):
        try:
            offres_parsees.append(parser_offre_ft(offre))
        except Exception as e:
            print(f"Erreur parsing offre {i} (id: {offre.get('id', '?')}) : {e}")
            erreurs += 1

    print(f"Parsing terminé : {len(offres_parsees)} offres OK, {erreurs} erreurs")
    return offres_parsees


# ─────────────────────────────────────────────────────────────────────
# ÉTAPE 4 — SAUVEGARDE PROCESSED
# ─────────────────────────────────────────────────────────────────────

def sauvegarder_processed(offres: list, timestamp: str) -> str:
    """
    Sauvegarde les offres parsées dans data/processed/francetravail/.
    Le timestamp est partagé avec la sauvegarde brute pour retrouver
    facilement les deux fichiers correspondant à la même extraction.

    Retourne le chemin du fichier créé.
    """
    Path("data/processed/francetravail").mkdir(parents=True, exist_ok=True)

    chemin = f"data/processed/francetravail/offres_{timestamp}.json"

    with open(chemin, "w", encoding="utf-8") as f:
        json.dump(offres, f, ensure_ascii=False, indent=2)

    print(f"Processed sauvegardé : {chemin} ({len(offres)} offres)")
    return chemin


# ─────────────────────────────────────────────────────────────────────
# PIPELINE COMPLET
# ─────────────────────────────────────────────────────────────────────

def pipeline_complet(
    mots_cles:    str  = "data engineer",
    nb_pages_max: int  = 5,
    avec_details: bool = False,
):
    """
    Pipeline complet : extraction → sauvegarde brute → parsing → sauvegarde processed.

    Le timestamp est généré une seule fois et partagé entre les deux fichiers
    de sortie — ce qui permet de faire le lien entre brut et processed.
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # ── Étape 1 : Extraction brute ────────────────────────
    print("=== ÉTAPE 1 : Extraction ===")
    offres_brutes = extraire_offres(
        mots_cles    = mots_cles,
        nb_pages_max = nb_pages_max,
        avec_details = avec_details,
    )

    if not offres_brutes:
        print("Aucune offre récupérée. Arrêt.")
        return

    # ── Étape 2 : Sauvegarde brute ────────────────────────
    print("\n=== ÉTAPE 2 : Sauvegarde brute ===")
    sauvegarder_brut(offres_brutes, mots_cles, timestamp)

    # ── Étape 3 : Parsing ─────────────────────────────────
    print("\n=== ÉTAPE 3 : Parsing ===")
    offres_parsees = parser_et_sauvegarder(offres_brutes)

    # ── Étape 4 : Sauvegarde processed ───────────────────
    print("\n=== ÉTAPE 4 : Sauvegarde processed ===")
    sauvegarder_processed(offres_parsees, timestamp)

    # ── Résumé ────────────────────────────────────────────
    print(f"""
╔══════════════════════════════════════╗
  Pipeline FranceTravail terminé
  Offres brutes   : {len(offres_brutes)}
  Offres parsées  : {len(offres_parsees)}
  Timestamp       : {timestamp}
╚══════════════════════════════════════╝
    """)

    return offres_parsees


# ─────────────────────────────────────────────────────────────────────
# POINT D'ENTRÉE
# ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    pipeline_complet(
        mots_cles    = "data engineer",
        nb_pages_max = 5,
        avec_details = False,  # passer à True pour les descriptions complètes
    )