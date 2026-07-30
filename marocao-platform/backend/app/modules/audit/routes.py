from typing import Optional, List
from uuid import UUID
from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime, time, timezone

from backend.app.database.connection import get_db  # Adapte selon ton import
from backend.app.database.models import ClassificationAuditLog  # Adapte l'import
from backend.app.modules.audit.schemas import (
    AuditLogResponse,
    AuditListResponse,
    AuditStatsResponse,
    AuditSearchFilter
)

router = APIRouter(prefix="/audit-logs", tags=["Classification Audit Logs"])


@router.get("/", response_model=AuditListResponse)
def get_all_audit_logs(
    skip: Optional[int] = Query(0, ge=0, description="Nombre d'éléments à sauter (Optionnel, défaut: 0)"),
    limit: Optional[int] = Query(20, ge=1, le=100, description="Nombre d'éléments à récupérer (Optionnel, défaut: 20)"),
    validation_status: Optional[str] = Query(None, description="Filtrer par statut: PENDING, VALIDATED, CORRECTED"),
    db: Session = Depends(get_db)
):
    """
    GET : Récupère la liste brute de tous les logs avec comptage total.
    skip et limit sont optionnels.
    """
    # Valeurs par défaut si envoyés à None
    actual_skip = skip if skip is not None else 0
    actual_limit = limit if limit is not None else 20
    query = db.query(ClassificationAuditLog)
    
    # Filtrage par validation_status si fourni
    if validation_status:
        query = query.filter(
            ClassificationAuditLog.validation_status == validation_status.upper().strip()
        )

    total_count = query.count()
    logs = (
        query.order_by(ClassificationAuditLog.created_at.desc())
        .offset(actual_skip)
        .limit(actual_limit)
        .all()
    )

    page = (actual_skip // actual_limit) + 1 if actual_limit > 0 else 1

    return {
        "total_count": total_count,
        "page": page,
        "limit": actual_limit,
        "data": logs
    }


@router.get("/latest", response_model=List[AuditLogResponse])
def get_latest_audit_logs(
    limit: Optional[int] = Query(10, ge=1, le=50, description="Nombre de derniers logs (Optionnel, défaut: 10)"),
    today_only: bool = Query(True, description="Si True, ne retourne que les logs créés aujourd'hui"),
    db: Session = Depends(get_db)
):
    """
    GET : Récupère les N derniers logs.
    limit est optionnel.
    """
    actual_limit = limit if limit is not None else 10
    query = db.query(ClassificationAuditLog)
    
    if today_only:
        # Calcule le début de la journée courante (ex: 2026-07-23 00:00:00)
        today_start = datetime.combine(datetime.now(timezone.utc).date(), time.min)
        query = query.filter(ClassificationAuditLog.created_at >= today_start)

    return query.order_by(ClassificationAuditLog.created_at.desc()).limit(actual_limit).all()

@router.get("/stats", response_model=AuditStatsResponse)
def get_audit_stats(db: Session = Depends(get_db)):
    """
    Renvoie les métriques clés, comptages et taux d'exactitude (Accuracy) du modèle IA.
    """
    total_logs = db.query(ClassificationAuditLog).count()
    pending_count = db.query(ClassificationAuditLog).filter(ClassificationAuditLog.validation_status == "PENDING").count()
    validated_count = db.query(ClassificationAuditLog).filter(ClassificationAuditLog.validation_status == "VALIDATED").count()
    corrected_count = db.query(ClassificationAuditLog).filter(ClassificationAuditLog.validation_status == "CORRECTED").count()

    total_evaluated = validated_count + corrected_count
    accuracy = (validated_count / total_evaluated * 100.0) if total_evaluated > 0 else None

    return {
        "total_logs": total_logs,
        "pending_count": pending_count,
        "validated_count": validated_count,
        "corrected_count": corrected_count,
        "accuracy_rate_percentage": round(accuracy, 2) if accuracy is not None else None
    }

@router.get("/document/{document_id}", response_model=List[AuditLogResponse])
def get_audit_logs_by_document_id(
    document_id: UUID,
    db: Session = Depends(get_db)
):
    """
    GET : Récupère tout l'historique d'audit lié à un document spécifique.
    """
    logs = (
        db.query(ClassificationAuditLog)
        .filter(ClassificationAuditLog.document_id == document_id)
        .order_by(ClassificationAuditLog.created_at.desc())
        .all()
    )

    if not logs:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Aucun log d'audit trouvé pour le document_id {document_id}"
        )

    return logs


@router.get("/{audit_id}", response_model=AuditLogResponse)
def get_audit_log_by_id(
    audit_id: UUID,
    db: Session = Depends(get_db)
):
    """
    GET : Récupère un log d'audit unique via son ID.
    """
    audit_log = db.query(ClassificationAuditLog).filter(ClassificationAuditLog.id == audit_id).first()

    if not audit_log:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Log d'audit introuvable avec l'ID {audit_id}"
        )

    return audit_log

@router.post("/search", response_model=AuditListResponse)
def search_audit_logs(
    filters: AuditSearchFilter,
    db: Session = Depends(get_db)
):
    """
    POST : Filtrage avancé (validation_status, pagination) via Body JSON.
    """
    query = db.query(ClassificationAuditLog)

    if filters.validation_status:
        query = query.filter(
            ClassificationAuditLog.validation_status == filters.validation_status.upper().strip()
        )

    total_count = query.count()
    logs = (
        query.order_by(ClassificationAuditLog.created_at.desc())
        .offset(filters.skip)
        .limit(filters.limit)
        .all()
    )

    page = (filters.skip // filters.limit) + 1 if filters.limit > 0 else 1

    return {
        "total_count": total_count,
        "page": page,
        "limit": filters.limit,
        "data": logs
    }
