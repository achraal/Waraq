# backend/app/config.py
import os
from dotenv import load_dotenv
from pydantic import EmailStr

# Chargement explicite du fichier .env
load_dotenv()

class Settings:
    PROJECT_NAME: str = "MarocAO API"
    VERSION: str = "1.0.0"
    
    # Récupération des variables du .env avec valeurs de secours (fallbacks)
    DATABASE_URL: str = os.getenv("DATABASE_URL")
    JWT_SECRET: str = os.getenv("JWT_SECRET")
    JWT_ALGORITHM: str = os.getenv("JWT_ALGORITHM")
    ADMIN_FIRST_EMAIL: EmailStr = os.getenv("ADMIN_FIRST_EMAIL")
    ADMIN_FIRST_PASSWORD: str = os.getenv("ADMIN_FIRST_PASSWORD")
    
    # Durée de validité d'un token d'accès (ex: 1440 minutes = 24 heures)
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 

    # Scraping & Messagerie
    EMAIL_USER: str = os.getenv("EMAIL_USER")
    EMAIL_PASSWORD: str = os.getenv("EMAIL_PASSWORD")
    EMAIL_IMAP_SERVER: str = os.getenv("EMAIL_IMAP_SERVER")

    # Infrastructure Locale (Ollama)
    OLLAMA_BASE_URL: str = os.getenv("OLLAMA_BASE_URL")
    OLLAMA_MODEL: str = os.getenv("OLLAMA_MODEL")

settings = Settings()