# backend/app/config.py
import os
from pathlib import Path
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
    MODEL_VISION_OCR: str = os.getenv("MODEL_VISION_OCR")
    MODEL_RAG_ANALYSIS: str = os.getenv("MODEL_RAG_ANALYSIS")
    MODEL_EMBEDDINGS: str = os.getenv("MODEL_EMBEDDINGS")
    # Rétention en mémoire (0 pour libérer la VRAM/RAM immédiatement)
    OLLAMA_KEEP_ALIVE: int = int(os.getenv("OLLAMA_KEEP_ALIVE"))
    
    # Chemin vers le dossier chroma_db
    CHROMA_PERSIST_DIR: Path = Path(os.getenv("CHROMA_PERSIST_DIR"))
    LIBREOFFICE_PATH: str = r"C:\Program Files\LibreOffice\program\soffice.exe"  

     # Racine unique de data_storage
    DATA_STORAGE_PATH: Path = Path(os.getenv("DATA_STORAGE_PATH",
            r"C:\Users\achra\Desktop\Intern\Project\marocao-platform\data_storage"))

    # Alias pour compatibilité avec le code existant
    STORAGE_ROOT: Path = DATA_STORAGE_PATH

    # Dossiers métier
    RAG_EXTRACTED_DIR: Path = DATA_STORAGE_PATH / "rag_extracted"
    GENERATED_DIR: Path = DATA_STORAGE_PATH / "generated"
    TEMPLATES_DIR: Path = DATA_STORAGE_PATH / "templates"  

settings = Settings()