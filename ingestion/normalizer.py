# ingestion/normalizer.py

def normaliser(offre_brute: dict, source: str) -> dict:
    if source == "francetravail":
        return normaliser_francetravail(offre_brute)
    elif source == "indeed":
        return normaliser_indeed(offre_brute)
    elif source == "welcometothejungle":
        return normaliser_wttj(offre_brute)
    elif source == "apec":
        return normaliser_apec(offre_brute)
    else:
        raise ValueError(f"Source inconnue : {source}")