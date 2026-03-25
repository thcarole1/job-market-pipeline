# job-market-pipeline
End-to-end data pipeline for job market analysis - FranceTravail API, scraping, MongoDB, Airflow, FastAPI

## Description
Pipeline de données pour analyser le marché de l'emploi
en France — sources : API FranceTravail + scraping Indeed.

## Stack technique
- Python 3.10
- MongoDB
- Apache Airflow
- FastAPI
- Docker

## Installation
1. Cloner le dépôt
2. Créer l'environnement virtuel : `python3 -m venv venv`
3. L'activer : `source venv/bin/activate`
4. Installer les dépendances : `pip install -r requirements.txt`
5. Copier `.env.example` en `.env` et renseigner vos clés API

## Structure du projet
(résultat de tree -L 2)
.
├── README.md
├── data
│   ├── processed
│   └── raw
├── ingestion
│   ├── francetravail
│   └── indeed
├── notebooks
│   ├── 01_exploration_francetravail.ipynb
│   ├── 02_exploration_indeed.ipynb
│   ├── 03_normalisation.ipynb
│   └── 04_prototype_ml.ipynb
├── requirements.txt
├── structure.txt