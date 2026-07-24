from fastapi import APIRouter, Depends, status, HTTPException
from sqlalchemy.orm import Session
from typing import Dict, Any
from backend.app.database.models import SystemMetric
from backend.app.database.connection import get_db
from backend.app.modules.telemetry.metrics_service import collecter_et_sauvegarder_metriques
from sqlalchemy import desc
from typing import List

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
        
@router.get("/metrics/latest", status_code=status.HTTP_200_OK)
def obtenir_dernieres_metriques(db: Session = Depends(get_db)):
    """
    Récupère le tout dernier snapshot de métriques système enregistré en BDD.
    """
    metric = db.query(SystemMetric).order_by(desc(SystemMetric.timestamp)).first()
    if not metric:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Aucune métrique système enregistrée pour le moment."
        )
    return metric


@router.get("/metrics/history", status_code=status.HTTP_200_OK)
def obtenir_historique_metriques(limit: int = 24, db: Session = Depends(get_db)):
    """
    Récupère l'historique des snapshots de métriques (par défaut les 24 derniers).
    """
    metrics = (
        db.query(SystemMetric)
        .order_by(desc(SystemMetric.timestamp))
        .limit(limit)
        .all()
    )
    return {
        "count": len(metrics),
        "data": metrics
    }
    
@router.get("/metrics/all", status_code=status.HTTP_200_OK)
def obtenir_toutes_les_metriques(db: Session = Depends(get_db)):
    """
    Récupère la totalité des enregistrements de métriques système
    classés du plus récent au plus ancien.
    """
    metrics = (
        db.query(SystemMetric)
        .order_by(desc(SystemMetric.timestamp))
        .all()
    )
    return {
        "count": len(metrics),
        "data": metrics
    }