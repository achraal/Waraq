from fastapi import APIRouter, UploadFile, File, HTTPException, BackgroundTasks, Depends, status, Query
import os, shutil, math, logging
from typing import Dict, Any, Optional, List
from sqlalchemy.orm import Session
from sqlalchemy import func
from uuid import UUID
from backend.app.database.connection import get_db, SessionLocal
from backend.app.database.models import TenderDocument, RAGAnalysisResult, RAGStatus, Tender, RAGLog
from backend.app.modules.rag_engine.rag_service import rag_pipeline_service
from backend.app.modules.rag_engine.vector_store import chroma_manager
from backend.app.modules.rag_engine.schemas import TenderRAGAnalysisResult, TenderRAGSummary, RAGLogResponse, RAGLogsPaginatedResponse, RAGStatsResponse, VectorPoint3D, Visualization3DResponse
from pydantic import ValidationError

logger = logging.getLogger("waraq.rag.routes")
router = APIRouter(prefix="/v1/documents",tags=["Documents"])

UPLOAD_DIR = "./uploaded_files"
os.makedirs(UPLOAD_DIR, exist_ok=True)

router_rag = APIRouter(prefix="/rag",tags=["RAG & Intelligence Métier"])

# TÂCHE DE FOND RAG

async def _run_rag_background(document_id: str):
    """
    Crée une nouvelle session DB dédiée à la tâche RAG.
    IMPORTANT :
    On ne réutilise jamais la session DB provenant
    directement de la requête HTTP.
    """
    db = SessionLocal()
    try:
        await rag_pipeline_service.execute_rag_pipeline(db=db, document_id=document_id)
    except Exception:
        # Le service RAG possède déjà son propre traitement
        # d'erreur et ses logs.
        raise
    finally:
        db.close()

@router_rag.post("/analyze-document/{document_id}",status_code=status.HTTP_202_ACCEPTED)
async def analyser_document_rag(document_id: UUID, background_tasks: BackgroundTasks, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """
    Déclenche manuellement l'analyse RAG d'un document.
    Pipeline :
        Extraction RAG indépendante -> Chunking -> BGE-M3 -> ChromaDB -> Recherche sémantique -> Granite 4.1:3B
    """
    doc = (db.query(TenderDocument).filter(TenderDocument.id == document_id).first())
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Document {document_id} introuvable.")

    # IMPORTANT :
    # On transmet uniquement l'ID.
    # La tâche crée sa propre session DB.
    
    rag_entry = (
        db.query(RAGAnalysisResult)
        .filter(RAGAnalysisResult.document_id == doc.id)
        .first()
    )

    if (
        doc.rag_processed
        and rag_entry
        and rag_entry.status == RAGStatus.COMPLETED
    ):
        return {
            "status": "already_processed",
            "message": (
                f"Le document '{doc.file_name}' a déjà été traité "
                f"avec succès par le pipeline RAG. "
                f"Aucune nouvelle analyse n'a été lancée."
            ),
            "document_id": str(document_id),
            "file_type": doc.file_type,
            "rag_processed": True,
            "rag_status": rag_entry.status.value
                if hasattr(rag_entry.status, "value")
                else str(rag_entry.status)
        }
    
    background_tasks.add_task(_run_rag_background, str(document_id))

    return {
        "status": "processing",
        "message": (
            f"Le pipeline RAG a été lancé pour le document "
            f"'{doc.file_name}'."
        ),
        "document_id": str(document_id),
        "file_type": doc.file_type,
        "rag_processed": bool(doc.rag_processed),
        "rag_status": (
            rag_entry.status.value
            if rag_entry and hasattr(rag_entry.status, "value")
            else str(rag_entry.status)
            if rag_entry
            else None
        )
    }

@router_rag.post("/analyze-tender/{tender_id}",status_code=status.HTTP_202_ACCEPTED)
async def analyser_tender_complet_rag(tender_id: UUID, background_tasks: BackgroundTasks, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """
    Déclenche manuellement l'analyse RAG des documents stratégiques d'un tender.
    """

    docs = (
        db.query(TenderDocument)
        .filter(TenderDocument.tender_id == tender_id,TenderDocument.file_type.in_(["CPS", "RC", "BDP"]))
        .all()
    )

    if not docs:
        return {
            "status": "completed",
            "message": (
                "Aucun document stratégique "
                "(CPS, RC, BDP) trouvé pour cet appel d'offres."
            ),
            "documents_found": 0,
            "documents_queued": 0,
            "documents_already_processed": 0
        }

    documents_queued = []
    documents_already_processed = []

    for doc in docs:
        rag_entry = (db.query(RAGAnalysisResult).filter(RAGAnalysisResult.document_id == doc.id).first())

        # Déjà traité avec succès → NE PAS relancer
        if doc.rag_processed and rag_entry and rag_entry.status == RAGStatus.COMPLETED:
            documents_already_processed.append({
                "document_id": str(doc.id),
                "file_name": doc.file_name,
                "file_type": doc.file_type
            })
            continue

        # Nouveau traitement
        background_tasks.add_task(_run_rag_background, str(doc.id))

        documents_queued.append({
            "document_id": str(doc.id),
            "file_name": doc.file_name,
            "file_type": doc.file_type
        })

    # Aucun nouveau traitement nécessaire
    if not documents_queued:
        return {
            "status": "already_processed",
            "message": (
                f"Tous les documents stratégiques du tender "
                f"{tender_id} ont déjà été traités par le pipeline RAG. "
                f"Aucune nouvelle analyse n'a été lancée."
            ),
            "tender_id": str(tender_id),
            "documents_found": len(docs),
            "documents_queued": 0,
            "documents_already_processed": len(
                documents_already_processed
            ),
            "already_processed": documents_already_processed
        }

    return {
        "status": "processing",
        "message": (
            f"Analyse RAG lancée pour "
            f"{len(documents_queued)} document(s) stratégique(s) "
            f"du tender {tender_id}. "
            f"{len(documents_already_processed)} document(s) "
            f"déjà traité(s) ont été ignoré(s)."
        ),
        "tender_id": str(tender_id),
        "documents_found": len(docs),
        "documents_queued": len(documents_queued),
        "documents_already_processed": len(
            documents_already_processed
        ),
        "queued_documents": documents_queued,
        "already_processed": documents_already_processed
    }

@router_rag.get("/stats/{tender_id}", status_code=status.HTTP_200_OK)
async def obtenir_stats_rag(tender_id: UUID,db: Session = Depends(get_db)) -> Dict[str, Any]:
    """
    Retourne les statistiques du pipeline RAG pour un tender.
    IMPORTANT :
    Cet endpoint est purement consultatif.
    Il ne lance AUCUN traitement RAG.
    """

    docs = (db.query(TenderDocument).filter(TenderDocument.tender_id == tender_id,TenderDocument.file_type.in_(["CPS", "RC", "BDP"])).all())

    if not docs:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,detail=f"Aucun document RAG trouvé pour le tender {tender_id}.")

    document_ids = [doc.id for doc in docs]

    rag_entries = (db.query(RAGAnalysisResult).filter(RAGAnalysisResult.document_id.in_(document_ids)).all())
    rag_by_document = {str(entry.document_id): entry for entry in rag_entries}
    total_documents = len(docs)
    completed = 0
    processing = 0
    failed = 0
    not_processed = 0
    total_chunks = 0
    indexing_durations = []
    retrieval_durations = []
    generation_durations = []
    total_durations = []
    documents_stats = []

    for doc in docs:
        rag_entry = rag_by_document.get(str(doc.id))
        if not rag_entry:
            status_value = "NOT_PROCESSED"
            not_processed += 1
        else:
            status_value = (rag_entry.status.value if hasattr(rag_entry.status, "value") else str(rag_entry.status))
            if status_value == RAGStatus.COMPLETED.value:
                completed += 1
            elif status_value in [RAGStatus.INDEXING.value,RAGStatus.ANALYZING.value]:
                processing += 1
            elif status_value == RAGStatus.FAILED.value:
                failed += 1
            else:
                not_processed += 1
            if rag_entry.chunk_count:
                total_chunks += rag_entry.chunk_count
            if rag_entry.embedding_duration_sec is not None:
                indexing_durations.append(rag_entry.embedding_duration_sec)
            if getattr(rag_entry,"retrieval_duration_sec",None) is not None:
                retrieval_durations.append(rag_entry.retrieval_duration_sec)
            if getattr(rag_entry,"generation_duration_sec",None) is not None:
                generation_durations.append(rag_entry.generation_duration_sec)
            if rag_entry.total_rag_duration_sec is not None:
                total_durations.append(rag_entry.total_rag_duration_sec)

        documents_stats.append({
            "document_id": str(doc.id),
            "file_name": doc.file_name,
            "file_type": doc.file_type,
            "rag_processed": bool(doc.rag_processed),
            "status": status_value,
            "chunk_count": (rag_entry.chunk_count if rag_entry else 0)
        })

    def moyenne(values):
        if not values:
            return None
        return round(sum(values) / len(values), 3)

    if completed == total_documents:
        global_status = "COMPLETED"
    elif failed == total_documents:
        global_status = "FAILED"
    elif processing > 0:
        global_status = "PROCESSING"
    elif completed > 0:
        global_status = "PARTIAL"
    else:
        global_status = "NOT_PROCESSED"

    return {
        "tender_id": str(tender_id),
        "status": global_status,
        "documents": {
            "total": total_documents,
            "completed": completed,
            "processing": processing,
            "failed": failed,
            "not_processed": not_processed
        },
        "indexing": {
            "total_chunks": total_chunks,
            "average_duration_sec": moyenne(indexing_durations)
        },
        "retrieval": {
            "average_duration_sec": moyenne(retrieval_durations)
        },
        "generation": {
            "average_duration_sec": moyenne(generation_durations)
        },
        "pipeline": {
            "average_total_duration_sec": moyenne(total_durations)
        },
        "documents_details": documents_stats
    }

@router_rag.get("/summary/{document_id}", response_model=TenderRAGSummary,status_code=status.HTTP_200_OK,)
async def obtenir_resume_rag(document_id: UUID, db: Session = Depends(get_db),) -> TenderRAGSummary:
    """
    Retourne le résumé métier RAG déjà généré pour un document.

    Aucun appel à Granite.
    Aucun appel à GLM-OCR.
    Aucun recalcul.
    Aucun appel ChromaDB.
    """

    document = (
        db.query(TenderDocument)
        .filter(TenderDocument.id == document_id)
        .first()
    )

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document introuvable.",
        )

    rag_entry = (
        db.query(RAGAnalysisResult)
        .filter(
            RAGAnalysisResult.document_id == document.id,
            RAGAnalysisResult.status == RAGStatus.COMPLETED,
        )
        .first()
    )

    if not rag_entry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Aucune analyse RAG terminée disponible pour ce document.",
        )

    summary = rag_entry.summary

    if not summary:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Aucun résumé métier disponible pour ce document.",
        )

    try:
        return TenderRAGSummary.model_validate(summary)

    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "message": "Résumé RAG présent mais invalide.",
                "errors": exc.errors(),
            },
        )
        
@router_rag.get("/vectors/tender/{tender_id}", response_model=Visualization3DResponse, status_code=status.HTTP_200_OK)
async def visualiser_vecteurs_tender(tender_id: UUID, max_points: int = Query(default=300, ge=10, le=1000),
    method: str = Query(default="tsne", pattern="^(tsne|pca)$"), db: Session = Depends(get_db)):
    try:
        tender = db.query(Tender).filter(Tender.id == tender_id).first()

        if not tender:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Tender introuvable : {tender_id}"
            )

        return await chroma_manager.visualiser_vecteurs_async(
            tender_reference=tender.reference,
            document_id=None,
            max_points=max_points,
            method=method
        )

    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except Exception as exc:
        logger.exception("[RAG][VISUALIZATION][TENDER] Erreur")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur visualisation ChromaDB : {str(exc)}"
        )

@router_rag.get("/vectors/document/{document_id}", response_model=Visualization3DResponse, status_code=status.HTTP_200_OK)
async def visualiser_vecteurs_document(
    document_id: UUID,
    max_points: int = Query(default=300, ge=10, le=1000),
    method: str = Query(default="tsne", pattern="^(tsne|pca)$"),
    db: Session = Depends(get_db)):
    try:
        document = db.query(TenderDocument).filter(TenderDocument.id == document_id).first()

        if not document:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Document introuvable : {document_id}"
            )

        tender = document.tender
        if not tender:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Tender associé introuvable pour le document : {document_id}"
            )

        return await chroma_manager.visualiser_vecteurs_async(
            tender_reference=tender.reference,
            document_id=str(document_id),
            max_points=max_points,
            method=method
        )

    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except Exception as exc:
        logger.exception("[RAG][VISUALIZATION][DOCUMENT] Erreur")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur visualisation ChromaDB : {str(exc)}"
        )

@router.post("/upload")
async def upload_document(file: UploadFile = File(...)):
    """Upload un fichier PDF sur le serveur."""

    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Seuls les fichiers PDF sont acceptés.")
    file_path = os.path.join(UPLOAD_DIR,file.filename)

    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file,buffer)
        return {
            "status": "success",
            "filename": file.filename,
            "path": file_path
        }
    except Exception as e:
        raise HTTPException(status_code=500,detail=f"Erreur d'upload : {str(e)}")

@router_rag.get("/stats", response_model=RAGStatsResponse)
def get_rag_logs_stats(db: Session = Depends(get_db)):
    """
    Calcule les métriques globales du pipeline RAG (Total, Erreurs, Warnings, Durée moyenne).
    URL finale : GET /api/rag/stats
    """
    total_logs = db.query(func.count(RAGLog.id)).scalar() or 0
    error_count = db.query(func.count(RAGLog.id)).filter(RAGLog.level.ilike("ERROR")).scalar() or 0
    warning_count = db.query(func.count(RAGLog.id)).filter(RAGLog.level.ilike("WARNING")).scalar() or 0
    
    avg_duration = db.query(func.avg(RAGLog.duration_sec)).filter(RAGLog.duration_sec.isnot(None)).scalar()

    return {
        "total_logs": total_logs,
        "error_count": error_count,
        "warning_count": warning_count,
        "avg_duration_sec": round(avg_duration, 3) if avg_duration else 0.0
    }

@router_rag.get("/", response_model=RAGLogsPaginatedResponse)
def get_rag_logs(
    skip: int = Query(0, ge=0),
    limit: int = Query(15, ge=1, le=100),
    level: Optional[str] = Query(None, description="INFO, WARNING, ERROR"),
    stage: Optional[str] = Query(None, description="Filtre par étape de pipeline"),
    db: Session = Depends(get_db)
):
    """
    Récupère les logs RAG de manière paginée.
    URL finale : GET /api/rag/?skip=0&limit=15
    """
    query = db.query(RAGLog)

    if level:
        query = query.filter(RAGLog.level.ilike(level))
    if stage:
        query = query.filter(RAGLog.stage.ilike(f"%{stage}%"))

    total_count = query.count()
    logs = query.order_by(RAGLog.created_at.desc()).offset(skip).limit(limit).all()

    return {
        "total_count": total_count,
        "data": logs
    }

@router_rag.get("/tender/{tender_id}", response_model=List[RAGLogResponse])
def get_rag_logs_by_tender(
    tender_id: UUID,
    db: Session = Depends(get_db)
):
    """
    Récupère les logs RAG pour un appel d'offres spécifique.
    URL finale : GET /api/rag/tender/{tender_id}
    """
    logs = db.query(RAGLog).filter(
        RAGLog.tender_id == tender_id
    ).order_by(RAGLog.created_at.desc()).all()

    return logs

@router_rag.get("/document/{document_id}", response_model=List[RAGLogResponse])
def get_rag_logs_by_document(
    document_id: UUID,
    db: Session = Depends(get_db)
):
    """
    Récupère les logs RAG associés à un document précis.
    URL finale : GET /api/rag/document/{document_id}
    """
    logs = db.query(RAGLog).filter(
        RAGLog.document_id == document_id
    ).order_by(RAGLog.created_at.desc()).all()

    return logs

@router_rag.get("/{rag_id}", response_model=RAGLogResponse)
def get_rag_log_by_id(
    rag_id: UUID,
    db: Session = Depends(get_db)
):
    """
    Récupère un log RAG par son identifiant unique.
    URL finale : GET /api/rag/{rag_id}
    """
    log = db.query(RAGLog).filter(RAGLog.id == rag_id).first()
    if not log:
        raise HTTPException(status_code=404, detail="Log RAG non trouvé")
    return log

@router_rag.get("/vectors/lookup/tenders", status_code=status.HTTP_200_OK)
async def lookup_tenders(
    query: Optional[str] = None,
    page: int = 1,
    page_size: int = 10,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    stmt = db.query(Tender)
    if query:
        stmt = stmt.filter(Tender.reference.ilike(f"%{query}%"))
    
    total_count = stmt.count()
    total_pages = math.ceil(total_count / page_size) if total_count > 0 else 1
    
    tenders = stmt.offset((page - 1) * page_size).limit(page_size).all()
    
    return {
        "total": total_count,
        "page": page,
        "total_pages": total_pages,
        "items": [
            {
                "id": str(t.id),
                "reference": t.reference,
                "title": getattr(t, "title", "Sans titre")
            } 
            for t in tenders
        ]
    }

@router_rag.get("/vectors/lookup/documents", status_code=status.HTTP_200_OK)
async def lookup_documents(
    query: Optional[str] = None,
    page: int = 1,
    page_size: int = 10,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    stmt = db.query(TenderDocument)
    if query:
        stmt = stmt.filter(TenderDocument.file_name.ilike(f"%{query}%"))
        
    total_count = stmt.count()
    total_pages = math.ceil(total_count / page_size) if total_count > 0 else 1
    
    docs = stmt.offset((page - 1) * page_size).limit(page_size).all()
    
    return {
        "total": total_count,
        "page": page,
        "total_pages": total_pages,
        "items": [
            {
                "id": str(d.id),
                "filename": getattr(d, "file_name", "Document sans nom")
            } 
            for d in docs
        ]
    }