# ingestion/francetravail/api_client.py

import requests
from datetime import datetime, timedelta
from dotenv import load_dotenv
import os

load_dotenv()

CLIENT_ID     = os.getenv("FRANCETRAVAIL_CLIENT_ID")
CLIENT_SECRET = os.getenv("FRANCETRAVAIL_CLIENT_SECRET")

TOKEN_URL = "https://entreprise.francetravail.fr/connexion/oauth2/access_token"
BASE_URL  = "https://api.francetravail.io/partenaire/offresdemploi/v2/offres"

class FranceTravailClient:
    """
    Client HTTP pour l'API FranceTravail.
    Gère l'authentification OAuth2 et les appels à l'API.
    """

    def __init__(self):
        self._token       = None
        self._token_expiry = None

    def _get_token(self) -> str:
        """
        Récupère un token OAuth2 valide.
        Si le token existant est encore valide, le réutilise.
        Sinon, en demande un nouveau.
        """
        # Réutiliser le token si encore valide
        if self._token and datetime.now() < self._token_expiry:
            return self._token

        response = requests.post(
            TOKEN_URL,
            params={"realm": "/partenaire"},
            data={
                "grant_type":    "client_credentials",
                "client_id":     CLIENT_ID,
                "client_secret": CLIENT_SECRET,
                "scope":         "api_offresdemploiv2 o2dsoffre",
            }
        )
        response.raise_for_status()
        data = response.json()

        self._token = data["access_token"]
        # Le token expire dans expires_in secondes — on retire 30s de marge
        self._token_expiry = datetime.now() + timedelta(
            seconds=data["expires_in"] - 30
        )
        return self._token

    def _headers(self) -> dict:
        """Retourne les headers HTTP avec le token valide."""
        return {
            "Authorization": f"Bearer {self._get_token()}",
            "Accept":        "application/json",
        }

    def rechercher_offres(self, params: dict) -> dict:
        """
        Appel à l'endpoint de recherche d'offres.
        params : dictionnaire des paramètres de recherche
        Retourne le JSON brut de la réponse.
        """
        response = requests.get(
            f"{BASE_URL}/search",
            headers=self._headers(),
            params=params,
        )
        response.raise_for_status()
        return response.json()

    def get_offre(self, offre_id: str) -> dict:
        """
        Récupère le détail complet d'une offre par son identifiant.
        """
        response = requests.get(
            f"{BASE_URL}/{offre_id}",
            headers=self._headers(),
        )
        response.raise_for_status()
        return response.json()