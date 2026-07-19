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
from backend.app.modules.ai_processor.routes import router as classification_router
from backend.app.modules.scraper.email_monitor import fetch_marche_publics, save_emails_to_db
import os
from backend.app.modules.telemetry.routes import router as telemetry_router
from backend.app.modules.telemetry.metrics_service import collecter_et_sauvegarder_metriques
from backend.app.database.connection import SessionLocal
from apscheduler.schedulers.background import BackgroundScheduler

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

def execute_cron_telemetrie():
    """Ouvre une connexion propre chaque heure pour enregistrer les métriques."""
    db = SessionLocal()
    try:
        collecter_et_sauvegarder_metriques(db)
        print("[CRON] Snapshot de télémétrie enregistré avec succès.")
    except Exception as e:
        print(f"[CRON ERROR] Échec de l'enregistrement automatique des métriques : {e}")
    finally:
        db.close()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Création des tables au démarrage
    Base.metadata.create_all(bind=engine)
    # Création de l'admin initial
    create_initial_admin()

    # Initialisation et démarrage du BackgroundScheduler ---
    scheduler = BackgroundScheduler()
    scheduler.add_job(execute_cron_telemetrie, 'interval', minutes=60)
    scheduler.start()
    print("[SCHEDULER] Le planificateur de métriques horaires a démarré.")

    # 3. Synchronisation des fichiers locaux vers la table "tenders"
    # Synchro automatique
    print("Lancement de la synchronisation au démarrage...")
    db = next(get_db())
    try:
        result = sync_local_tenders_to_db(db)
        print(f"Sync terminée : {result['inserted']} nouveaux tenders.")

        # Synchro Emails
        print("Synchronisation des emails PMMP en cours...")
        raw_emails = fetch_marche_publics()
        count = save_emails_to_db(db, raw_emails)
        print(f"Sync Emails terminée : {count} nouveaux messages importés.")

        # 2. On s'assure que l'Excel est à jour avec tout le contenu de la BDD
        if not os.path.exists(EXCEL_PATH):
            export_all_tenders_to_excel(db)
    except Exception as e:
        print(f"Erreur lors de la synchronisation au démarrage : {e}") 
    finally:
        db.close()
    yield

    # Arrêt propre du scheduler à la fermeture de l'application
    scheduler.shutdown()
    print("[SCHEDULER] Le planificateur de métriques a été arrêté proprement.")

app = FastAPI(
    title="MarocAO API",
    lifespan=lifespan # Utiliser lifespan au lieu d'appeler create_all en dehors
)

# Inclusion du routeur sous le préfixe général de l'API
app.include_router(auth_router, prefix="/api")
app.include_router(scraper_router, prefix="/api")
app.include_router(tenders_router, prefix="/api")
app.include_router(classification_router, prefix="/api")
app.include_router(telemetry_router, prefix="/api")

@app.get("/")
def health_check():
    return {"status": "healthy", "project": "MarocAO"}