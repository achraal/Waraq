from fastapi import APIRouter, UploadFile, File, HTTPException, BackgroundTasks, Depends, status
import os, shutil
from typing import Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import func
from uuid import UUID
from backend.app.database.connection import get_db, SessionLocal
from backend.app.database.models import TenderDocument, RAGAnalysisResult, RAGStatus
from backend.app.modules.rag_engine.rag_service import rag_pipeline_service

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

@router_rag.get("/summary/{tender_id}", status_code=status.HTTP_200_OK)
async def obtenir_resume_rag(tender_id: UUID, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """
    Retourne le résumé métier RAG déjà présent en base.
    IMPORTANT :
    Aucun appel à GLM-OCR, BGE ou Granite n'est effectué ici.
    """
    docs = (db.query(TenderDocument).filter(TenderDocument.tender_id == tender_id,TenderDocument.file_type.in_(["CPS", "RC", "BDP"])).all())

    if not docs:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,detail=f"Aucun document stratégique trouvé pour le tender {tender_id}.")

    document_ids = [doc.id for doc in docs]

    rag_entries = (db.query(RAGAnalysisResult).filter(RAGAnalysisResult.document_id.in_(document_ids)).all())

    analyses = []
    for entry in rag_entries:
        if entry.status != RAGStatus.COMPLETED:
            continue
        if not entry.rag_analysis:
            continue
        analyses.append({"document_id": str(entry.document_id),"analysis": entry.rag_analysis})

    if not analyses:
        return {
            "tender_id": str(tender_id),
            "status": "NOT_READY",
            "message": (
                "Aucune analyse RAG complète n'est encore disponible."
            ),
            "documents_analyzed": 0,
            "summary": None
        }

    # VALEURS PAR DÉFAUT
    summary = {
        "objet_appel_offres": None,
        "maitre_d_ouvrage": None,
        "numero_reference": None,
        "delai_execution": None,
        "dates_importantes": {
            "date_limite_depot": None,
            "date_visite_lieux": None,
            "date_ouverture_plis": None
        },
        "garanties_exigees": None,
        "caution_provisoire": None,
        "pieces_a_fournir": {"pieces_techniques": [],"pieces_administratives": []},
        "criteres_evaluation": [],
        "estimation_financiere": None,
        "clauses_techniques_clefs": [],
        "clauses_administratives_clefs": []
    }
    # FONCTIONS D'AGRÉGATION

    def remplir_si_vide(cle, valeur):
        if valeur is not None and valeur != "":
            if summary.get(cle) in [None, "", [], {}]:
                summary[cle] = valeur

    def ajouter_liste_unique(destination, valeurs):
        if not valeurs:
            return
        if not isinstance(valeurs, list):
            valeurs = [valeurs]
        for valeur in valeurs:
            if valeur and valeur not in destination:
                destination.append(valeur)

    # AGRÉGATION DES DOCUMENTS
    for item in analyses:
        analysis = item["analysis"]
        if not isinstance(analysis, dict):
            continue

        # Champs simples
        remplir_si_vide("objet_appel_offres",analysis.get("objet_appel_offres"))
        remplir_si_vide("maitre_d_ouvrage",analysis.get("maitre_d_ouvrage"))
        remplir_si_vide("numero_reference",analysis.get("numero_reference"))
        remplir_si_vide("delai_execution",analysis.get("delai_execution"))
        remplir_si_vide("garanties_exigees",analysis.get("garanties_exigees"))
        remplir_si_vide("caution_provisoire",analysis.get("garanties_exigees"))
        remplir_si_vide("caution_provisoire",analysis.get("caution_provisoire"))
        remplir_si_vide("estimation_financiere",analysis.get("estimation_financiere"))
        # Dates
        dates = analysis.get("dates_importantes",{})
        if isinstance(dates, dict):
            for date_key in ["date_limite_depot","date_visite_lieux","date_ouverture_plis"]:
                if summary["dates_importantes"].get(date_key) is None and dates.get(date_key):
                    summary["dates_importantes"][date_key] = dates.get(date_key)
        # Pièces
        pieces = analysis.get("pieces_a_fournir",{})
        if isinstance(pieces, dict):
            ajouter_liste_unique(summary["pieces_a_fournir"]["pieces_techniques"],pieces.get("pieces_techniques"))
            ajouter_liste_unique(summary["pieces_a_fournir"]["pieces_administratives"],pieces.get("pieces_administratives"))
        # Critères
        ajouter_liste_unique(summary["criteres_evaluation"],analysis.get("criteres_evaluation"))
        # Clauses techniques
        ajouter_liste_unique(summary["clauses_techniques_clefs"],analysis.get("clauses_techniques_clefs"))
        # Clauses administratives
        ajouter_liste_unique(summary["clauses_administratives_clefs"],analysis.get("clauses_administratives_clefs"))

    return {
        "tender_id": str(tender_id),
        "status": "COMPLETED",
        "documents_analyzed": len(analyses),
        "documents_available": len(docs),
        "summary": summary
    }

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