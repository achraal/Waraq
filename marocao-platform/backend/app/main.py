# backend/app/main.py
from argon2 import exceptions
from fastapi import FastAPI
from backend.app.database.connection import engine, Base
from backend.app.database import models
from backend.app.auth.routes import router as auth_router
from backend.app.auth.security import SecurityManager
from backend.app.database.models import User, UserRole
from backend.app.config import settings
from backend.app.database.connection import get_db
from contextlib import asynccontextmanager
from backend.app.modules.scraper.routes import router as scraper_router
from backend.app.modules.scraper.utils import sync_local_tenders_to_db, EXCEL_PATH, export_all_tenders_to_excel
from backend.app.modules.tenders.routes import router as tenders_router
import os



def create_initial_admin():
    """Génère l'administrateur initial si aucun admin n'existe en base."""
    session = next(get_db())
    try:
        admin_exists = session.query(User).filter(User.role == UserRole.ADMIN).first()
        if not admin_exists:
            print("Aucun administrateur détecté. Création du compte administrateur initial...")
            hashed_pwd = SecurityManager.hash_password(settings.ADMIN_FIRST_PASSWORD)
            initial_admin = User(
                email=settings.ADMIN_FIRST_EMAIL,
                password_hash=hashed_pwd,
                role=UserRole.ADMIN
            )
            session.add(initial_admin)
            session.commit()
            print(f"Administrateur initial créé avec succès : {settings.ADMIN_FIRST_EMAIL}")
    except Exception as e:
        session.rollback()
        print(f"Erreur lors de la création de l'admin initial : {str(e)}")
    finally:
        session.close()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Création des tables au démarrage
    Base.metadata.create_all(bind=engine)
    # Création de l'admin initial
    create_initial_admin()
# 3. Synchronisation des fichiers locaux vers la table "tenders"
    # Synchro automatique
    print("Lancement de la synchronisation au démarrage...")
    db = next(get_db())
    try:
        result = sync_local_tenders_to_db(db)
        print(f"Sync terminée : {result['inserted']} nouveaux tenders.")

        # 2. On s'assure que l'Excel est à jour avec tout le contenu de la BDD
        if not os.path.exists(EXCEL_PATH):
            export_all_tenders_to_excel(db)
    finally:
        db.close()

    yield

app = FastAPI(
    title="MarocAO API",
    lifespan=lifespan # Utiliser lifespan au lieu d'appeler create_all en dehors
)

# Inclusion du routeur sous le préfixe général de l'API
app.include_router(auth_router, prefix="/api")
app.include_router(scraper_router, prefix="/api")
app.include_router(tenders_router, prefix="/api")

@app.get("/")
def health_check():
    return {"status": "healthy", "project": "MarocAO"}