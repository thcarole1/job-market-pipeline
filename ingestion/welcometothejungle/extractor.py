# ingestion/welcometothejungle/extractor.py

import json
import asyncio
from datetime import datetime
from pathlib import Path

from ingestion.welcometothejungle.scraper import scraper_wttj, sauvegarder_brut
from ingestion.welcometothejungle.parser import parser_offre_wttj


def sauvegarder_processed(offres: list, timestamp: str = None) -> str:
    """
    Sauvegarde les offres parsées dans data/processed/welcometothejungle/.
    Retourne le chemin du fichier créé.
    """
    Path("data/processed/welcometothejungle").mkdir(parents=True, exist_ok=True)

    if not timestamp:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    chemin = f"data/processed/welcometothejungle/offres_{timestamp}.json"

    with open(chemin, "w", encoding="utf-8") as f:
        json.dump(offres, f, ensure_ascii=False, indent=2)

    print(f"Processed sauvegardé : {chemin} ({len(offres)} offres)")
    return chemin


def parser_et_sauvegarder(offres_brutes: list) -> list:
    """
    Parse toutes les offres brutes et sauvegarde le résultat.
    Retourne la liste des offres parsées.
    """
    offres_parsees = []
    erreurs = 0

    for i, offre_brute in enumerate(offres_brutes):
        try:
            offre_parsee = parser_offre_wttj(offre_brute)
            offres_parsees.append(offre_parsee)
        except Exception as e:
            print(f"Erreur parsing offre {i} : {e}")
            erreurs += 1
            continue

    print(f"\nParsing terminé : {len(offres_parsees)} offres OK, {erreurs} erreurs")
    return offres_parsees


async def pipeline_complet(mots_cles: str = "data engineer", nb_pages: int = 3):
    """
    Pipeline complet : scraping → parsing → sauvegarde.

    1. Scrape les offres brutes
    2. Sauvegarde les données brutes dans data/raw/
    3. Parse chaque offre
    4. Sauvegarde les données parsées dans data/processed/
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # ── Étape 1 : Scraping ────────────────────────────────
    print("=== ÉTAPE 1 : Scraping ===")
    offres_brutes = await scraper_wttj(nb_pages=nb_pages)

    if not offres_brutes:
        print("Aucune offre récupérée. Arrêt.")
        return

    # ── Étape 2 : Sauvegarde brute ────────────────────────
    print("\n=== ÉTAPE 2 : Sauvegarde brute ===")
    sauvegarder_brut(offres_brutes)

    # ── Étape 3 : Parsing ─────────────────────────────────
    print("\n=== ÉTAPE 3 : Parsing ===")
    offres_parsees = parser_et_sauvegarder(offres_brutes)

    # ── Étape 4 : Sauvegarde processed ───────────────────
    print("\n=== ÉTAPE 4 : Sauvegarde processed ===")
    sauvegarder_processed(offres_parsees, timestamp)

    # ── Résumé ────────────────────────────────────────────
    print(f"""
╔══════════════════════════════════════╗
  Pipeline WTTJ terminé
  Offres brutes   : {len(offres_brutes)}
  Offres parsées  : {len(offres_parsees)}
  Timestamp       : {timestamp}
╚══════════════════════════════════════╝
    """)

    return offres_parsees


if __name__ == "__main__":
    asyncio.run(pipeline_complet(
        mots_cles="data engineer",
        nb_pages=3,
    ))

'''
## Ce que ça donne dans le terminal quand tu le lances
```
=== ÉTAPE 1 : Scraping ===
Page 1/3...
  → 20 offres, 847 au total
Page 2/3...
  → 20 offres, 847 au total
Page 3/3...
  → 20 offres, 847 au total

=== ÉTAPE 2 : Sauvegarde brute ===
Sauvegardé : data/raw/welcometothejungle/offres_20260401_143022.json (60 offres)

=== ÉTAPE 3 : Parsing ===
Parsing terminé : 60 offres OK, 0 erreurs

=== ÉTAPE 4 : Sauvegarde processed ===
Processed sauvegardé : data/processed/welcometothejungle/offres_20260401_143022.json (60 offres)

╔══════════════════════════════════════╗
  Pipeline WTTJ terminé
  Offres brutes   : 60
  Offres parsées  : 60
  Timestamp       : 20260401_143022
╚══════════════════════════════════════╝

'''

'''
python -m ingestion.welcometothejungle.extractor
```

---

## La structure finale du dossier `ingestion/welcometothejungle/`
```
ingestion/welcometothejungle/
├── scraper.py      ← scrape et sauvegarde le brut
├── parser.py       ← nettoie une offre brute
└── extractor.py    ← orchestre le pipeline complet
'''