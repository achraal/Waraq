# backend/app/modules/scraper/routes.py
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.orm import Session
from backend.app.database.connection import get_db
from backend.app.database.models import Tender
from backend.app.modules.scraper.utils import sync_local_tenders_to_db, export_all_tenders_to_excel
from openpyxl import load_workbook
import os, threading
from backend.app.modules.scraper.portal_scraper import run_scraper 

# État global pour suivre le scraper (optionnel, pour éviter les doublons)
scraper_status = {"is_running": False}

router = APIRouter(prefix="/scraper", tags=["Scraper & Data Sync"])
DATA_STORAGE_DIR = r"C:\Users\achra\Desktop\Intern\Project\marocao-platform\data_storage"
EXCEL_PATH = os.path.join(DATA_STORAGE_DIR, "tenders_export.xlsx")

@router.post("/sync")
def trigger_sync(db: Session = Depends(get_db)):
    results = sync_local_tenders_to_db(db)
    inserted = results.get("inserted", 0)
    msg = f"Synchronisation terminée. {inserted} nouvelles offres ajoutées." if inserted > 0 else "Base de données déjà à jour."
    return {"status": "success", "message": msg, "details": results}

@router.post("/export-excel")
def trigger_excel_export(db: Session = Depends(get_db)):
    try:
        # 1. Compter les offres en base
        count_db = db.query(Tender).count()
        
        # 2. Vérifier si le fichier existe et compter les lignes (hors header)
        count_excel = 0
        if os.path.exists(EXCEL_PATH):
            wb = load_workbook(EXCEL_PATH, read_only=True)
            ws = wb.active
            # ws.max_row compte toutes les lignes, on enlève 1 pour l'en-tête
            if ws.max_row > 1:
                count_excel = ws.max_row - 1
            wb.close()

        # 3. Comparer et décider
        if count_db > 0 and count_db == count_excel:
            return {
                "status": "success", 
                "message": "Le fichier Excel est déjà à jour (toutes les offres sont présentes).",
                "count": count_db
            }
        
        # 4. Sinon, on effectue l'export
        export_all_tenders_to_excel(db)
        
        return {
            "status": "success", 
            "message": f"Export Excel généré avec succès. {count_db} offres ont été synchronisées.",
            "count": count_db
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur lors de l'export : {str(e)}")

def run_scraper_task():
    scraper_status["is_running"] = True
    try:
        run_scraper()
    finally:
        scraper_status["is_running"] = False

@router.post("/start-scraping")
def start_scraping(background_tasks: BackgroundTasks):
    if scraper_status["is_running"]:
        raise HTTPException(status_code=400, detail="Le scraper est déjà en cours d'exécution.")
    
    # Lancement en arrière-plan via FastAPI
    background_tasks.add_task(run_scraper_task)
    return {"status": "success", "message": "Scraping démarré en arrière-plan."}

@router.get("/scraper-status")
def get_status():
    return scraper_status

@router.post("/run-pipeline")
def run_full_pipeline(background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    if scraper_status["is_running"]:
        raise HTTPException(status_code=400, detail="Une tâche est déjà en cours.")

    def execute_pipeline():
        scraper_status["is_running"] = True
        # On crée une session propre à ce thread d'arrière-plan
        db = SessionLocal()
        try:
            print("--- Étape 1 : Démarrage du Scraper ---")
            run_scraper()
            
            print("--- Étape 2 : Synchronisation des données ---")
            sync_local_tenders_to_db(db)
            
            print("--- Étape 3 : Export Excel ---")
            export_all_tenders_to_excel(db)
            
            print("--- Pipeline terminé avec succès ---")
        except Exception as e:
            print(f"--- Erreur dans le pipeline : {e} ---")
        finally:
            db.close() # Important : On ferme la session manuellement ici
            scraper_status["is_running"] = False

    background_tasks.add_task(execute_pipeline)
    return {"status": "success", "message": "Le pipeline complet a été lancé en arrière-plan."}