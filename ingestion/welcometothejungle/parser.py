# ingestion/welcometothejungle/parser.py

import re
from datetime import datetime


def parser_offre_wttj(offre_brute: dict) -> dict:
    """
    Nettoie et structure une offre brute WTTJ (JSON Algolia).
    Entrée  : dict brut retourné par scraper.py
    Sortie  : dict propre et structuré, prêt pour normalizer.py
    """
    return {
        # Identifiants
        "id":                   offre_brute.get("objectID", ""),
        "slug":                 offre_brute.get("slug", ""),
        "url":                  _construire_url(offre_brute),

        # Contenu de l'offre
        "titre":                offre_brute.get("name", ""),
        "description":          _construire_description(offre_brute),
        "missions":             offre_brute.get("key_missions", []),

        # Contrat
        "type_contrat":         _normaliser_contrat(offre_brute.get("contract_type", "")),
        "teletravail":          _normaliser_teletravail(offre_brute.get("remote", "")),

        # Salaire
        "salaire_min":          offre_brute.get("salary_minimum"),
        "salaire_max":          offre_brute.get("salary_maximum"),
        "salaire_devise":       offre_brute.get("salary_currency", "EUR"),

        # Expérience
        "experience_min":       offre_brute.get("experience_level_minimum"),

        # Localisation
        "localisation_ville":   _get_nested(offre_brute, "offices", 0, "city"),
        "localisation_region":  _get_nested(offre_brute, "offices", 0, "local_state"),
        "pays":                 _get_nested(offre_brute, "offices", 0, "country"),
        "latitude":             _get_geoloc(offre_brute, "lat"),
        "longitude":            _get_geoloc(offre_brute, "lng"),

        # Entreprise
        "entreprise":           _get_dict(offre_brute, "organization", "name"),
        "entreprise_slug":      _get_dict(offre_brute, "organization", "slug"),
        "nb_employes":          _get_dict(offre_brute, "organization", "nb_employees"),
        "entreprise_desc":      _get_dict(offre_brute, "organization", "summary"),

        # Secteurs
        "secteur":              _get_nested(offre_brute, "sectors", 0, "parent_name"),
        "sous_secteur":         _get_nested(offre_brute, "sectors", 0, "name"),

        # Avantages
        "avantages":            offre_brute.get("benefits", []),

        # Métier
        "metier":               _get_dict(offre_brute, "new_profession", "pivot_name"),
        "categorie_metier":     _get_dict(offre_brute, "new_profession", "sub_category_name"),

        # Dates
        "date_publication":     _normaliser_date(offre_brute.get("published_at_date", "")),
        "date_extraction":      datetime.now().isoformat(),

        # Source
        "source": "welcometothejungle",
    }


# ── Fonctions utilitaires ─────────────────────────────────

def _construire_url(offre: dict) -> str:
    """Reconstruit l'URL complète de l'offre depuis le slug."""
    org_slug = _get_dict(offre, "organization", "slug")
    job_slug = offre.get("slug", "")
    if org_slug and job_slug:
        return f"https://www.welcometothejungle.com/fr/companies/{org_slug}/jobs/{job_slug}"
    return ""


def _construire_description(offre: dict) -> str:
    """
    Concatène summary et profile pour constituer
    la description complète — base du modèle ML.
    """
    summary = _nettoyer_html(offre.get("summary", ""))
    profile = _nettoyer_html(offre.get("profile", ""))
    parties = [p for p in [summary, profile] if p]
    return "\n\n".join(parties)


def _nettoyer_html(texte: str) -> str:
    """Supprime les balises HTML et nettoie les espaces."""
    if not texte:
        return ""
    texte = re.sub(r"<[^>]+>", " ", texte)       # supprime les balises
    texte = re.sub(r"\s+", " ", texte)            # normalise les espaces
    return texte.strip()


def _normaliser_contrat(contract_type: str) -> str:
    """Traduit les types de contrat WTTJ vers un format commun."""
    mapping = {
        "full_time":  "CDI",
        "part_time":  "CDI temps partiel",
        "internship": "Stage",
        "apprenticeship": "Alternance",
        "freelance":  "Freelance",
        "temporary":  "CDD",
    }
    return mapping.get(contract_type, contract_type)


def _normaliser_teletravail(remote: str) -> str:
    """Traduit les valeurs de télétravail WTTJ."""
    mapping = {
        "full":    "remote",
        "partial": "hybrid",
        "none":    "onsite",
    }
    return mapping.get(remote, remote or "")


def _normaliser_date(date_str: str) -> str:
    """S'assure que la date est au format YYYY-MM-DD."""
    if not date_str:
        return ""
    # published_at_date est déjà au bon format chez WTTJ
    if re.match(r"\d{4}-\d{2}-\d{2}", date_str):
        return date_str[:10]
    return date_str


def _get_dict(offre: dict, cle: str, sous_cle: str):
    """Extrait une valeur dans un sous-dictionnaire."""
    return (offre.get(cle) or {}).get(sous_cle)


def _get_nested(offre: dict, cle_liste: str, index: int, sous_cle: str):
    """Extrait une valeur dans une liste de dictionnaires."""
    liste = offre.get(cle_liste, [])
    if liste and len(liste) > index:
        return liste[index].get(sous_cle)
    return None


def _get_geoloc(offre: dict, axe: str):
    """Extrait lat ou lng depuis _geoloc."""
    geoloc = offre.get("_geoloc", [])
    if geoloc and len(geoloc) > 0:
        return geoloc[0].get(axe)
    return None


if __name__ == "__main__":
    # Test rapide sur une offre fictive
    import json
    from pprint import pprint
    from ingestion.welcometothejungle.scraper import scraper_wttj
    import asyncio

    offres_brutes = asyncio.run(scraper_wttj(nb_pages=1))
    if offres_brutes:
        offre_parsee = parser_offre_wttj(offres_brutes[0])
        print("Offre parsée :")
        pprint(offre_parsee)


'''

## Le flux complet avec ce fichier en place
```
scraper.py      → offres brutes JSON Algolia (60+ champs dont _highlightResult)
    ↓
parser.py       → offre propre (25 champs utiles, HTML nettoyé, URL reconstruite)
    ↓
normalizer.py   → schéma commun identique à FranceTravail
'''