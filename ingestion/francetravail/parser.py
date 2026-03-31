# ingestion/francetravail/parser.py

import re
from datetime import datetime


def parser_offre_ft(offre_brute: dict) -> dict:
    """
    Nettoie et structure une offre brute FranceTravail.
    Entrée  : dict brut retourné par extractor.py
    Sortie  : dict propre et structuré, prêt pour normalizer.py
    """
    return {
        # Identifiants
        "id": offre_brute.get("id", ""),
        "url": _get_nested(offre_brute, "origineOffre", "urlOrigine"),

        # Contenu de l'offre
        "titre":               offre_brute.get("appellationlibelle", "")
                                or offre_brute.get("intitule", ""),
        "description":          offre_brute.get("description", ""),

        # Entreprise
        "entreprise":           _get_nested(offre_brute, "entreprise", "nom"),
        "nb_employes":          offre_brute.get("trancheEffectifEtab"),

        # Contrat
        "type_contrat":         offre_brute.get("typeContrat", ""),
        "type_contrat_libelle": offre_brute.get("typeContratLibelle", ""),
        "alternance":           offre_brute.get("alternance", False),
        "nombre_postes":        offre_brute.get("nombrePostes", 1),

        # Durée du travail
        "temps_travail":        offre_brute.get("dureeTravailLibelleConverti", ""),

        # Salaire
        "salaire_min":          _extraire_salaire_min(offre_brute),
        "salaire_max":          _extraire_salaire_max(offre_brute),
        "salaire_texte":        _get_nested(offre_brute, "salaire", "libelle"),

        # Expérience
        "experience_exige":     offre_brute.get("experienceExige", ""),
        "experience_min":       _extraire_experience(offre_brute),

        # Qualification
        "qualification":        offre_brute.get("qualificationLibelle", ""),

        # Localisation
        "localisation_ville":   _extraire_ville(offre_brute),
        "localisation_dept":    _get_nested(offre_brute, "lieuTravail", "codePostal"),
        "commune":              _get_nested(offre_brute, "lieuTravail", "commune"),
        "latitude":             _get_nested(offre_brute, "lieuTravail", "latitude"),
        "longitude":            _get_nested(offre_brute, "lieuTravail", "longitude"),

        # Télétravail — rarement fourni par FT
        "teletravail":          None,

        # Secteur
        "secteur":              offre_brute.get("secteurActiviteLibelle", ""),
        "code_naf":             offre_brute.get("codeNAF", ""),

        # Métier
        "rome_code":            offre_brute.get("romeCode", ""),
        "rome_libelle":         offre_brute.get("romeLibelle", ""),

        # Compétences
        "competences":          _extraire_competences(offre_brute),

        # Langues
        "langues":              _extraire_langues(offre_brute),

        # Qualités professionnelles
        "qualites":             _extraire_qualites(offre_brute),

        # Contact
        "url_postulation":      _get_nested(offre_brute, "contact", "urlPostulation"),

        # Dates
        "date_publication":     _normaliser_date(offre_brute.get("dateCreation", "")),
        "date_actualisation":   _normaliser_date(offre_brute.get("dateActualisation", "")),
        "date_extraction":      datetime.now().isoformat(),

        # Source
        "source": "francetravail",
    }


# ── Fonctions utilitaires ─────────────────────────────────

def _get_nested(offre: dict, cle: str, sous_cle: str):
    """Extrait une valeur dans un sous-dictionnaire."""
    return (offre.get(cle) or {}).get(sous_cle)


def _extraire_ville(offre: dict) -> str:
    """
    Extrait la ville depuis lieuTravail.libelle.
    Format FT : "75 - PARIS 15" → "Paris"
    """
    libelle = _get_nested(offre, "lieuTravail", "libelle") or ""
    # Supprimer le préfixe département "75 - "
    if " - " in libelle:
        libelle = libelle.split(" - ", 1)[1]
    return libelle.title().strip()


def _extraire_salaire_min(offre: dict) -> int | None:
    """
    Extrait le salaire minimum depuis le texte libre FranceTravail.
    Exemple : "Annuel de 35000.0 Euros sur 12.0 mois" → 35000
    """
    libelle = _get_nested(offre, "salaire", "libelle") or ""
    match = re.search(r"de\s+([\d]+(?:\.\d+)?)", libelle)
    if match:
        return int(float(match.group(1)))
    return None


def _extraire_salaire_max(offre: dict) -> int | None:
    """
    Extrait le salaire maximum depuis le texte libre FranceTravail.
    Exemple : "Annuel de 35000.0 à 45000.0 Euros" → 45000
    """
    libelle = _get_nested(offre, "salaire", "libelle") or ""
    # Cherche le pattern "à X" ou "a X"
    match = re.search(r"[àa]\s+([\d]+(?:\.\d+)?)", libelle)
    if match:
        return int(float(match.group(1)))
    # Si pas de max distinct, le min est aussi le max
    return _extraire_salaire_min(offre)


def _extraire_experience(offre: dict) -> int | None:
    """
    Extrait l'expérience minimum en années.
    Exemple : "3 An(s)" → 3
    """
    libelle = offre.get("experienceLibelle", "") or ""
    match = re.search(r"(\d+)\s+an", libelle, re.IGNORECASE)
    if match:
        return int(match.group(1))
    return None


def _extraire_competences(offre: dict) -> list:
    """
    Extrait la liste des compétences depuis le champ structuré FT.
    Retourne une liste de chaînes de caractères.
    """
    competences = offre.get("competences", []) or []
    return [c.get("libelle", "") for c in competences if c.get("libelle")]


def _extraire_langues(offre: dict) -> list:
    """Extrait la liste des langues requises."""
    langues = offre.get("langues", []) or []
    return [l.get("libelle", "") for l in langues if l.get("libelle")]


def _extraire_qualites(offre: dict) -> list:
    """Extrait les qualités professionnelles requises."""
    qualites = offre.get("qualitesProfessionnelles", []) or []
    return [q.get("libelle", "") for q in qualites if q.get("libelle")]


def _normaliser_date(date_str: str) -> str:
    """
    Normalise la date au format YYYY-MM-DD.
    FT retourne : "2026-03-31T17:01:37.982Z" → "2026-03-31"
    """
    if not date_str:
        return ""
    return date_str[:10]


if __name__ == "__main__":
    from pprint import pprint
    # Test sur une offre fictive pour vérifier le parsing
    offre_test = {
        "id": "206HBDG",
        "appellationlibelle": "Data engineer",
        "description": "Nous recherchons un Data Engineer...",
        "dateCreation": "2026-03-31T17:01:37.982Z",
        "typeContrat": "CDI",
        "typeContratLibelle": "CDI",
        "experienceLibelle": "3 An(s)",
        "entreprise": {"nom": "MONBUILDING &CO"},
        "lieuTravail": {"libelle": "75 - PARIS 15", "codePostal": "75015",
                        "latitude": 48.841401, "longitude": 2.300274},
        "salaire": {"libelle": "Annuel de 35000.0 Euros sur 12.0 mois"},
        "competences": [{"libelle": "Analyser, exploiter, structurer des données"}],
        "langues": [{"libelle": "Anglais"}, {"libelle": "Français"}],
        "origineOffre": {"urlOrigine": "https://candidat.francetravail.fr/..."},
    }
    pprint(parser_offre_ft(offre_test))


'''
## La structure complète de `ingestion/francetravail/` devient
```
ingestion/francetravail/
├── api_client.py   ← connexion OAuth2 + appels API
├── extractor.py    ← orchestre scraping + sauvegarde brut
└── parser.py       ← nettoie et structure chaque offre

'''