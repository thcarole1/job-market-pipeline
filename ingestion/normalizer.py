# ingestion/normalizer.py
"""
Normalizer — point de convergence des deux sources de données.

Ce script est l'étape finale de l'ingestion. Il prend en entrée
les offres déjà parsées (nettoyées individuellement par parser_offre_ft
et parser_offre_wttj) et les traduit vers un schéma commun unique.

Flux complet :
    FranceTravail : api_client.py → extractor.py → parser_offre_ft()  ┐
                                                                        ├→ normalizer.py → schéma commun
    WTTJ          : scraper.py   → extractor.py → parser_offre_wttj() ┘

Après normalisation, toutes les offres ont exactement la même structure,
quelle que soit leur source d'origine. C'est ce schéma commun qui sera
inséré dans MongoDB, Elasticsearch et PostgreSQL.
"""

import json
import re
from datetime import datetime
from pathlib import Path


# ─────────────────────────────────────────────────────────────────────
# SCHÉMA COMMUN — RÉFÉRENCE
# ─────────────────────────────────────────────────────────────────────
# Voici tous les champs du schéma normalisé, classés par priorité.
# Cette section sert de documentation : si on ajoute un champ,
# on l'ajoute ici ET dans la fonction de normalisation correspondante.
#
# Niveau 1 — Obligatoires (toujours présents)
#   id, source, titre, entreprise, description, competences,
#   localisation_ville, type_contrat, date_publication, url
#
# Niveau 2 — Recommandés (présents si disponibles)
#   salaire_min, salaire_max, experience_min, teletravail,
#   secteur, localisation_dept, latitude, longitude,
#   nb_employes, missions
#
# Niveau 3 — Optionnels (spécifiques à une source)
#   avantages, sous_secteur, qualification, rome_code,
#   salaire_devise, date_extraction
# ─────────────────────────────────────────────────────────────────────


# ─────────────────────────────────────────────────────────────────────
# TABLES DE CORRESPONDANCE
# ─────────────────────────────────────────────────────────────────────

# Correspondance des types de contrat vers un vocabulaire commun.
# FranceTravail utilise déjà "CDI", "CDD" etc.
# WTTJ utilise "full_time", "part_time", "internship" etc.
# On unifie tout vers : CDI, CDD, Alternance, Stage, Freelance
CONTRATS = {
    # Valeurs WTTJ → valeur normalisée
    "full_time":       "CDI",
    "part_time":       "CDI temps partiel",
    "internship":      "Stage",
    "apprenticeship":  "Alternance",
    "freelance":       "Freelance",
    "temporary":       "CDD",
    # Valeurs FranceTravail (déjà lisibles, on les conserve telles quelles)
    "CDI":             "CDI",
    "CDD":             "CDD",
    "MIS":             "Mission intérimaire",
    "SAI":             "Saisonnier",
}

# Correspondance des modalités de télétravail vers un vocabulaire commun.
# WTTJ utilise "full", "partial", "none".
# FranceTravail ne fournit généralement pas cette information.
TELETRAVAIL = {
    "full":    "remote",   # 100% télétravail
    "partial": "hybrid",   # télétravail partiel
    "none":    "onsite",   # présentiel uniquement
}


# ─────────────────────────────────────────────────────────────────────
# NORMALISATION FRANCETRAVAIL
# ─────────────────────────────────────────────────────────────────────

def normaliser_offre_ft(offre_parsee: dict) -> dict:
    """
    Traduit une offre FranceTravail parsée vers le schéma commun.

    Entrée  : dict produit par parser_offre_ft() — déjà nettoyé
    Sortie  : dict conforme au schéma normalisé commun

    Correspondances clés :
        appellationlibelle → titre
        entreprise.nom     → entreprise (déjà aplati par le parser)
        lieuTravail.libelle→ localisation_ville (déjà extrait par le parser)
        typeContrat        → type_contrat (via table CONTRATS)
        dateCreation       → date_publication (déjà tronqué par le parser)
        salaire.libelle    → salaire_min / salaire_max (déjà extraits)
        competences[].libelle → competences (déjà extraites par le parser)
    """
    return {
        # ── Identifiants ──────────────────────────────────────────────
        # On préfixe l'id avec "ft_" pour garantir l'unicité globale.
        # Sans préfixe, un id "12345" de FT pourrait entrer en collision
        # avec un id "12345" de WTTJ.
        "id":     f"ft_{offre_parsee.get('id', '')}",
        "source": "francetravail",
        "url":    offre_parsee.get("url", ""),

        # ── Contenu principal ─────────────────────────────────────────
        "titre":       offre_parsee.get("titre", ""),
        "entreprise":  offre_parsee.get("entreprise", ""),
        "description": offre_parsee.get("description", ""),

        # ── Compétences ───────────────────────────────────────────────
        # FranceTravail fournit une liste structurée — directement utilisable.
        # WTTJ ne la fournit pas — elle sera extraite par text mining (étape 3).
        "competences": offre_parsee.get("competences", []),

        # ── Localisation ──────────────────────────────────────────────
        "localisation_ville": offre_parsee.get("localisation_ville", ""),
        "localisation_dept":  offre_parsee.get("localisation_dept", ""),
        "latitude":           offre_parsee.get("latitude"),
        "longitude":          offre_parsee.get("longitude"),

        # ── Contrat ───────────────────────────────────────────────────
        # On passe par la table CONTRATS pour uniformiser.
        # Si la valeur n'est pas dans la table, on la conserve telle quelle
        # plutôt que de perdre l'information.
        "type_contrat": CONTRATS.get(
            offre_parsee.get("type_contrat", ""),
            offre_parsee.get("type_contrat", "")
        ),

        # ── Télétravail ───────────────────────────────────────────────
        # FranceTravail ne fournit généralement pas cette information.
        # On met None plutôt qu'une valeur inventée.
        "teletravail": None,

        # ── Salaire ───────────────────────────────────────────────────
        # Déjà extrait en entiers par le parser via regex.
        # Le parser a géré le cas "Annuel de 35000.0 Euros sur 12.0 mois".
        "salaire_min":   offre_parsee.get("salaire_min"),
        "salaire_max":   offre_parsee.get("salaire_max"),
        "salaire_devise": "EUR",  # FranceTravail est toujours en euros

        # ── Expérience ────────────────────────────────────────────────
        # Déjà extrait en entier par le parser depuis "3 An(s)".
        "experience_min": offre_parsee.get("experience_min"),

        # ── Secteur et métier ─────────────────────────────────────────
        "secteur":      offre_parsee.get("secteur", ""),
        "sous_secteur": "",  # non disponible chez FranceTravail
        "rome_code":    offre_parsee.get("rome_code", ""),

        # ── Entreprise ────────────────────────────────────────────────
        "nb_employes": offre_parsee.get("nb_employes", ""),

        # ── Missions et avantages ─────────────────────────────────────
        # FranceTravail ne structure pas les missions séparément —
        # elles sont dans la description libre.
        "missions":   [],
        "avantages":  [],  # non disponible chez FranceTravail

        # ── Qualification ─────────────────────────────────────────────
        # Spécifique à FranceTravail (ex: "Cadre", "Employé").
        # Absent chez WTTJ — on le conserve car utile pour le ML.
        "qualification": offre_parsee.get("qualification", ""),

        # ── Dates ─────────────────────────────────────────────────────
        # date_publication : déjà au format YYYY-MM-DD grâce au parser.
        # date_extraction  : moment où le script a tourné — utile pour
        #                    tracer l'historique des extractions Airflow.
        "date_publication": offre_parsee.get("date_publication", ""),
        "date_extraction":  datetime.now().isoformat(),
    }


# ─────────────────────────────────────────────────────────────────────
# NORMALISATION WELCOME TO THE JUNGLE
# ─────────────────────────────────────────────────────────────────────

def normaliser_offre_wttj(offre_parsee: dict) -> dict:
    """
    Traduit une offre WTTJ parsée vers le schéma commun.

    Entrée  : dict produit par parser_offre_wttj() — déjà nettoyé
    Sortie  : dict conforme au schéma normalisé commun

    Correspondances clés :
        objectID           → id (préfixé "wttj_")
        name               → titre
        organization.name  → entreprise (déjà aplati par le parser)
        offices[0].city    → localisation_ville (déjà extrait)
        contract_type      → type_contrat (via table CONTRATS)
        published_at_date  → date_publication (déjà au bon format)
        salary_minimum     → salaire_min (déjà en entier)
        salary_maximum     → salaire_max (déjà en entier)
        remote             → teletravail (via table TELETRAVAIL)
        tags[].name        → competences (approximation — text mining à l'étape 3)
    """
    return {
        # ── Identifiants ──────────────────────────────────────────────
        # Même logique que FT : préfixe "wttj_" pour garantir l'unicité.
        "id":     f"wttj_{offre_parsee.get('id', '')}",
        "source": "welcometothejungle",
        "url":    offre_parsee.get("url", ""),

        # ── Contenu principal ─────────────────────────────────────────
        "titre":       offre_parsee.get("titre", ""),
        "entreprise":  offre_parsee.get("entreprise", ""),

        # WTTJ sépare le résumé (summary) du profil recherché (profile).
        # Le parser les a déjà concaténés en une seule description.
        # C'est cette description qui alimentera le modèle ML.
        "description": offre_parsee.get("description", ""),

        # ── Compétences ───────────────────────────────────────────────
        # WTTJ ne fournit pas de liste de compétences structurée.
        # Les tags Algolia sont une approximation acceptable pour l'instant.
        # L'extraction fine se fera par text mining à l'étape 3 du projet.
        "competences": [],  # sera rempli à l'étape 3 par NLP

        # ── Localisation ──────────────────────────────────────────────
        "localisation_ville": offre_parsee.get("localisation_ville", ""),
        "localisation_dept":  offre_parsee.get("localisation_region", ""),
        "latitude":           offre_parsee.get("latitude"),
        "longitude":          offre_parsee.get("longitude"),

        # ── Contrat ───────────────────────────────────────────────────
        # WTTJ utilise "full_time", "internship" etc.
        # La table CONTRATS les traduit vers "CDI", "Stage" etc.
        "type_contrat": CONTRATS.get(
            offre_parsee.get("type_contrat", ""),
            offre_parsee.get("type_contrat", "")
        ),

        # ── Télétravail ───────────────────────────────────────────────
        # WTTJ fournit "partial", "full" ou "none".
        # La table TELETRAVAIL les traduit vers "hybrid", "remote", "onsite".
        "teletravail": TELETRAVAIL.get(
            offre_parsee.get("teletravail", ""),
            offre_parsee.get("teletravail", "")
        ) or None,

        # ── Salaire ───────────────────────────────────────────────────
        # WTTJ fournit directement des entiers — pas besoin de regex.
        # Le parser les a déjà extraits proprement.
        "salaire_min":    offre_parsee.get("salaire_min"),
        "salaire_max":    offre_parsee.get("salaire_max"),
        "salaire_devise": offre_parsee.get("salaire_devise", "EUR"),

        # ── Expérience ────────────────────────────────────────────────
        # WTTJ fournit directement un entier (ex: 5 pour "5 ans+").
        "experience_min": offre_parsee.get("experience_min"),

        # ── Secteur et métier ─────────────────────────────────────────
        # WTTJ structure les secteurs en parent/enfant.
        # Ex: parent = "Tech", enfant = "Intelligence artificielle / ML"
        "secteur":      offre_parsee.get("secteur", ""),
        "sous_secteur": offre_parsee.get("sous_secteur", ""),
        "rome_code":    "",  # non disponible chez WTTJ

        # ── Entreprise ────────────────────────────────────────────────
        # WTTJ fournit un entier, FT fournit une tranche texte.
        # On conserve les deux formats dans le même champ —
        # la normalisation fine se fera si besoin lors de l'analyse.
        "nb_employes": offre_parsee.get("nb_employes"),

        # ── Missions et avantages ─────────────────────────────────────
        # WTTJ structure les missions dans un champ dédié — rare et précieux.
        # Les avantages (télétravail, team building...) aussi.
        "missions":  offre_parsee.get("missions", []),
        "avantages": offre_parsee.get("avantages", []),

        # ── Qualification ─────────────────────────────────────────────
        # Non disponible chez WTTJ.
        "qualification": "",

        # ── Dates ─────────────────────────────────────────────────────
        "date_publication": offre_parsee.get("date_publication", ""),
        "date_extraction":  datetime.now().isoformat(),
    }


# ─────────────────────────────────────────────────────────────────────
# POINT D'ENTRÉE UNIFIÉ
# ─────────────────────────────────────────────────────────────────────

def normaliser(offre_parsee: dict) -> dict:
    """
    Point d'entrée unique de la normalisation.

    Détecte automatiquement la source de l'offre via le champ "source"
    et appelle la fonction de normalisation correspondante.

    Entrée  : dict parsé — doit contenir un champ "source"
    Sortie  : dict normalisé conforme au schéma commun
    Raises  : ValueError si la source est inconnue

    Utilisation :
        offre_normalisee = normaliser(offre_parsee)
    """
    source = offre_parsee.get("source", "")

    if source == "francetravail":
        return normaliser_offre_ft(offre_parsee)

    elif source == "welcometothejungle":
        return normaliser_offre_wttj(offre_parsee)

    else:
        # On lève une erreur explicite plutôt que de retourner
        # silencieusement un dict vide — plus facile à déboguer.
        raise ValueError(
            f"Source inconnue : '{source}'. "
            f"Valeurs acceptées : 'francetravail', 'welcometothejungle'."
        )


# ─────────────────────────────────────────────────────────────────────
# NORMALISATION EN BATCH
# ─────────────────────────────────────────────────────────────────────

def normaliser_batch(offres_parsees: list) -> list:
    """
    Normalise une liste d'offres parsées en une seule opération.

    Les erreurs de normalisation sont loguées sans interrompre
    le traitement — une offre mal formée ne bloque pas les suivantes.

    Entrée  : liste de dicts parsés (toutes sources mélangées acceptées)
    Sortie  : liste de dicts normalisés
    """
    offres_normalisees = []
    erreurs            = 0

    for i, offre in enumerate(offres_parsees):
        try:
            offres_normalisees.append(normaliser(offre))
        except Exception as e:
            print(f"Erreur normalisation offre {i} "
                  f"(source: {offre.get('source', '?')}, "
                  f"id: {offre.get('id', '?')}) : {e}")
            erreurs += 1

    print(f"Normalisation terminée : "
          f"{len(offres_normalisees)} offres OK, {erreurs} erreurs")

    return offres_normalisees


# ─────────────────────────────────────────────────────────────────────
# SAUVEGARDE
# ─────────────────────────────────────────────────────────────────────

def sauvegarder_normalise(offres: list, timestamp: str = None) -> str:
    """
    Sauvegarde les offres normalisées dans data/processed/normalise/.

    On crée un dossier dédié pour les données normalisées, distinct
    des dossiers par source (francetravail/, welcometothejungle/).
    Cela permet de retrouver facilement les données prêtes à insérer
    en base, quelle que soit leur source d'origine.

    Retourne le chemin du fichier créé.
    """
    Path("data/processed/normalise").mkdir(parents=True, exist_ok=True)

    if not timestamp:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    chemin = f"data/processed/normalise/offres_{timestamp}.json"

    with open(chemin, "w", encoding="utf-8") as f:
        json.dump(offres, f, ensure_ascii=False, indent=2)

    print(f"Normalisé sauvegardé : {chemin} ({len(offres)} offres)")
    return chemin


# ─────────────────────────────────────────────────────────────────────
# VALIDATION OPTIONNELLE
# ─────────────────────────────────────────────────────────────────────

def valider_offre(offre: dict) -> list:
    """
    Vérifie qu'une offre normalisée respecte le schéma commun.

    Retourne une liste d'erreurs (vide si l'offre est valide).
    Permet de détecter les anomalies avant insertion en base de données.

    Règles vérifiées :
        - Champs obligatoires présents et non vides
        - salaire_min <= salaire_max si les deux sont présents
        - date_publication au format YYYY-MM-DD
        - source dans les valeurs connues
    """
    erreurs = []

    # Champs obligatoires — doivent être présents et non vides
    champs_obligatoires = [
        "id", "source", "titre", "entreprise",
        "description", "localisation_ville",
        "type_contrat", "date_publication", "url"
    ]
    for champ in champs_obligatoires:
        if not offre.get(champ):
            erreurs.append(f"Champ obligatoire manquant ou vide : '{champ}'")

    # Cohérence du salaire
    sal_min = offre.get("salaire_min")
    sal_max = offre.get("salaire_max")
    if sal_min and sal_max and sal_min > sal_max:
        erreurs.append(
            f"salaire_min ({sal_min}) > salaire_max ({sal_max})"
        )

    # Format de la date
    date = offre.get("date_publication", "")
    if date and not re.match(r"\d{4}-\d{2}-\d{2}", date):
        erreurs.append(
            f"date_publication '{date}' n'est pas au format YYYY-MM-DD"
        )

    # Source connue
    sources_connues = {"francetravail", "welcometothejungle"}
    if offre.get("source") not in sources_connues:
        erreurs.append(
            f"Source inconnue : '{offre.get('source')}'"
        )

    return erreurs


def valider_batch(offres: list) -> dict:
    """
    Valide toutes les offres normalisées et retourne un rapport.

    Retourne un dictionnaire avec :
        - "valides"  : nombre d'offres sans erreur
        - "invalides": nombre d'offres avec au moins une erreur
        - "erreurs"  : liste détaillée des erreurs par offre
    """
    rapport = {"valides": 0, "invalides": 0, "erreurs": []}

    for i, offre in enumerate(offres):
        erreurs = valider_offre(offre)
        if erreurs:
            rapport["invalides"] += 1
            rapport["erreurs"].append({
                "index":  i,
                "id":     offre.get("id", "?"),
                "source": offre.get("source", "?"),
                "detail": erreurs
            })
        else:
            rapport["valides"] += 1

    return rapport


# ─────────────────────────────────────────────────────────────────────
# PIPELINE COMPLET
# ─────────────────────────────────────────────────────────────────────

def pipeline_normalisation(
    fichiers_processed: list,
    valider: bool = True
) -> list:
    """
    Pipeline complet de normalisation à partir de fichiers processed.

    Étapes :
        1. Charge les fichiers processed de chaque source
        2. Normalise toutes les offres vers le schéma commun
        3. Valide les données normalisées (optionnel)
        4. Sauvegarde dans data/processed/normalise/

    fichiers_processed : liste de chemins vers les fichiers JSON parsés
    valider            : si True, lance la validation et affiche le rapport

    Exemple d'utilisation :
        pipeline_normalisation([
            "data/processed/francetravail/offres_20260401.json",
            "data/processed/welcometothejungle/offres_20260401.json",
        ])
    """
    timestamp     = datetime.now().strftime("%Y%m%d_%H%M%S")
    toutes_offres = []

    # ── Étape 1 : Chargement ──────────────────────────────
    print("=== ÉTAPE 1 : Chargement des fichiers ===")
    for chemin in fichiers_processed:
        try:
            with open(chemin, "r", encoding="utf-8") as f:
                offres = json.load(f)
            print(f"  {chemin} → {len(offres)} offres")
            toutes_offres.extend(offres)
        except Exception as e:
            print(f"  Erreur chargement {chemin} : {e}")

    print(f"Total chargé : {len(toutes_offres)} offres\n")

    if not toutes_offres:
        print("Aucune offre à normaliser. Arrêt.")
        return []

    # ── Étape 2 : Normalisation ───────────────────────────
    print("=== ÉTAPE 2 : Normalisation ===")
    offres_normalisees = normaliser_batch(toutes_offres)

    # ── Étape 3 : Validation ──────────────────────────────
    if valider:
        print("\n=== ÉTAPE 3 : Validation ===")
        rapport = valider_batch(offres_normalisees)
        print(f"  Valides   : {rapport['valides']}")
        print(f"  Invalides : {rapport['invalides']}")
        if rapport["erreurs"]:
            print("  Détail des erreurs :")
            for err in rapport["erreurs"][:5]:  # affiche les 5 premières
                print(f"    Offre {err['id']} ({err['source']}) : "
                      f"{err['detail']}")

    # ── Étape 4 : Sauvegarde ──────────────────────────────
    print("\n=== ÉTAPE 4 : Sauvegarde ===")
    sauvegarder_normalise(offres_normalisees, timestamp)

    # ── Résumé ────────────────────────────────────────────
    ft_count   = sum(1 for o in offres_normalisees if o["source"] == "francetravail")
    wttj_count = sum(1 for o in offres_normalisees if o["source"] == "welcometothejungle")

    print(f"""
╔══════════════════════════════════════════╗
  Normalisation terminée
  FranceTravail       : {ft_count} offres
  Welcome to the Jungle: {wttj_count} offres
  Total               : {len(offres_normalisees)} offres
  Timestamp           : {timestamp}
╚══════════════════════════════════════════╝
    """)

    return offres_normalisees


# ─────────────────────────────────────────────────────────────────────
# POINT D'ENTRÉE
# ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    # Adapter les chemins selon les fichiers disponibles sur ta machine.
    # Le glob("*.json") prend automatiquement le fichier le plus récent
    # de chaque source grâce au tri alphabétique des timestamps.

    fichiers = []

    dossier_ft = Path("data/processed/francetravail")
    if dossier_ft.exists():
        fichiers_ft = sorted(dossier_ft.glob("*.json"))
        if fichiers_ft:
            fichiers.append(str(fichiers_ft[-1]))  # le plus récent

    dossier_wttj = Path("data/processed/welcometothejungle")
    if dossier_wttj.exists():
        fichiers_wttj = sorted(dossier_wttj.glob("*.json"))
        if fichiers_wttj:
            fichiers.append(str(fichiers_wttj[-1]))  # le plus récent

    if not fichiers:
        print("Aucun fichier processed trouvé.")
        print("Lance d'abord extractor.py pour FranceTravail et WTTJ.")
    else:
        pipeline_normalisation(fichiers, valider=True)
