# backend/app/modules/scraper/routes.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from backend.app.database.connection import get_db
from backend.app.database.models import Tender
from backend.app.modules.scraper.utils import sync_local_tenders_to_db, export_all_tenders_to_excel
from openpyxl import load_workbook
import os

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