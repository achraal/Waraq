from fastapi import APIRouter, Depends, status, HTTPException
from sqlalchemy.orm import Session
from typing import Dict, Any

from backend.app.database.connection import get_db
from backend.app.modules.telemetry.metrics_service import collecter_et_sauvegarder_metriques

router = APIRouter(
    prefix="/telemetry",
    tags=["System Telemetry & Health Checks"]
)

@router.post("/collect-now", status_code=status.HTTP_201_CREATED, response_model=Dict[str, str])
def forcer_collecte_metriques(db: Session = Depends(get_db)) -> Dict[str, str]:
    """
    Force l'exécution immédiate du pipeline de collecte des métriques système, 
    matérielles, base de données et IA, puis l'enregistre en BDD.
    """
    try:
        collecter_et_sauvegarder_metriques(db)
        return {
            "status": "success",
            "message": "Snapshot de télémétrie collecté et enregistré en base de données avec succès."
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la collecte manuelle des métriques : {str(e)}"
        )