# backend/app/main.py
from fastapi import FastAPI
from backend.app.database.connection import engine, Base
from backend.app.database import models
from backend.app.auth.routes import router as auth_router
from backend.app.auth.security import SecurityManager
from backend.app.database.models import User, UserRole
from backend.app.config import settings
from backend.app.database.connection import get_db
from contextlib import asynccontextmanager

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
    yield

app = FastAPI(
    title="MarocAO API",
    lifespan=lifespan # Utiliser lifespan au lieu d'appeler create_all en dehors
)

# Inclusion du routeur sous le préfixe général de l'API
app.include_router(auth_router, prefix="/api")

@app.get("/")
def health_check():
    return {"status": "healthy", "project": "MarocAO"}