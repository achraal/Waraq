# backend/app/database/connection.py
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from backend.app.config import settings

# Création du moteur de base de données en utilisant l'URL de config
engine = create_engine(settings.DATABASE_URL)

# Générateur de sessions locales
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Classe de base ORM dont héritent les modèles
Base = declarative_base()

# Dépendance pour injecter la session de BDD dans les routes FastAPI
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()