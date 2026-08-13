import logging
from pathlib import Path
from uuid import UUID
from fastapi import (APIRouter,Body,Depends,HTTPException,)
from sqlalchemy.orm import Session
from backend.app.database.connection import get_db
from backend.app.database.models import User, TenderDocument
from backend.app.modules.workflows.schemas import (BDPFillRequest,AdminFieldsFillRequest,DocumentValidationRequest,)
from backend.app.modules.workflows.preparation_service import TenderPreparationService
from backend.app.modules.workflows.document_signer import DocumentSigner
# Branche ici ton vrai moteur OCR existant.
from backend.app.modules.ai_processor.fast_ocr_engine import (FastOCREngine)
from backend.app.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/workflows", tags=["Workflows"])

# INITIALISATION DES SERVICES
STORAGE_ROOT: Path = settings.DATA_STORAGE_PATH
RAG_EXTRACTED_DIR: Path = settings.RAG_EXTRACTED_DIR
GENERATED_DIR: Path = settings.GENERATED_DIR
TEMPLATES_DIR: Path = settings.TEMPLATES_DIR

ocr_engine = FastOCREngine()
ocr_service = __import__("backend.app.modules.workflows.document_ocr",fromlist=["WorkflowOCRService"]).WorkflowOCRService(ocr_engine)
preparation_service = TenderPreparationService(storage_root=STORAGE_ROOT,templates_dir=TEMPLATES_DIR,ocr_service=ocr_service)

# PRÉPARATION
@router.post("/tenders/{tender_id}/preparation/scan")
def scan_tender(tender_id: UUID,user_id: UUID = Body(..., embed=True),db: Session = Depends(get_db)):
    """Analyse les documents du tender et construit son inventaire."""
    try:
        return preparation_service.scan_tender(db=db,tender_id=tender_id,user_id=user_id)

    except Exception as exc:
        logger.exception("Erreur scan préparation | tender=%s",tender_id)
        raise HTTPException(status_code=500,detail=str(exc))

@router.get("/tenders/{tender_id}/preparation")
def get_preparation(tender_id: UUID,db: Session = Depends(get_db)):
    """Retourne l'état actuel de préparation d'un tender."""
    try:
        return preparation_service.get_preparation(db,tender_id)
    except Exception as exc:
        logger.exception("Erreur récupération préparation | tender=%s",tender_id)
        raise HTTPException(status_code=404,detail=str(exc))

# VALIDATION / SUPPRESSION

@router.post("/preparation/documents/{document_id}/validate")
def validate_document(document_id: UUID,payload: DocumentValidationRequest,db: Session = Depends(get_db)):
    """Valide ou invalide manuellement une pièce."""
    try:
        document = preparation_service.validate_document(db=db,preparation_document_id=document_id,valid=payload.valid,message=payload.message)
        return {"status": "validated","document_id": str(document.id),"valid": payload.valid}
    except Exception as exc:
        logger.exception("Erreur validation document | id=%s",document_id)
        raise HTTPException(status_code=404,detail=str(exc))

@router.delete("/preparation/documents/{document_id}")
def delete_document(document_id: UUID,db: Session = Depends(get_db)):
    """Supprime une pièce incorrecte du workflow."""
    try:
        return preparation_service.delete_document(db=db,preparation_document_id=document_id)
    except Exception as exc:
        logger.exception("Erreur suppression document | id=%s",document_id)
        raise HTTPException(status_code=404,detail=str(exc))

# BDP

@router.post("/tenders/{tender_id}/bdp/analyze")
def analyze_bdp(tender_id: UUID,db: Session = Depends(get_db)):
    """Analyse le BDP et retourne les champs à remplir."""
    try:
        return preparation_service.analyze_bdp(db,tender_id)
    except Exception as exc:
        logger.exception("Erreur analyse BDP | tender=%s",tender_id)
        raise HTTPException(status_code=500,detail=str(exc))

@router.post("/preparation/documents/{document_id}/bdp/fill")
def fill_bdp(document_id: UUID,payload: BDPFillRequest,db: Session = Depends(get_db)):
    """Enregistre les prix saisis et calcule les totaux BDP."""
    try:
        return preparation_service.fill_bdp(
            db=db,
            preparation_document_id=document_id,
            values=[item.model_dump() for item in payload.values]
        )

    except Exception as exc:
        logger.exception("Erreur remplissage BDP | id=%s", document_id)
        raise HTTPException(status_code=500,detail=str(exc))

# ACTE / DÉCLARATION

@router.post("/preparation/documents/{document_id}/admin/extract-fields")
def extract_admin_fields(document_id: UUID,db: Session = Depends(get_db)):
    """Extrait les champs d'un acte ou d'une déclaration."""
    try:
        return preparation_service.extract_admin_fields(db,document_id)
    except Exception as exc:
        logger.exception("Erreur extraction champs admin | id=%s", document_id)
        raise HTTPException(status_code=500,detail=str(exc))

@router.post("/preparation/documents/{document_id}/admin/fill")
def fill_admin_document(document_id: UUID,payload: AdminFieldsFillRequest,db: Session = Depends(get_db)):
    """ Remplit un document administratif avec les données fournies. """
    try:
        return preparation_service.fill_admin_document(
            db=db,
            preparation_document_id=document_id,
            values=payload.values
        )
    except Exception as exc:
        logger.exception("Erreur remplissage document admin | id=%s", document_id)
        raise HTTPException(status_code=500,detail=str(exc))

# SIGNATURE RC / CPS

@router.post("/tenders/{tender_id}/sign")
def sign_documents(tender_id: UUID,signer_name: str = Body(..., embed=True),db: Session = Depends(get_db)):
    """
    Signe graphiquement le RC et le CPS et ajoute la pagination.
    """
    try:
        return preparation_service.sign_documents(db=db,tender_id=tender_id,signer_name=signer_name)
    except Exception as exc:
        logger.exception("Erreur signature | tender=%s", tender_id)
        raise HTTPException(status_code=500,detail=str(exc))

@router.post("/sign-document/{document_id}")
def sign_document(
    document_id: str,
    user_id: str,
    signer_name: str,
    db: Session = Depends(get_db),
):
    """
    Signe un document RC/CPS à partir des zones administratives déjà détectées et sauvegardées en base.
    """
    document = (db.query(TenderDocument).filter(TenderDocument.id == document_id).first())
    if not document:
        raise HTTPException(status_code=404,detail="Document introuvable.",)

    if document.file_type.upper() not in {"RC", "CPS"}:
        raise HTTPException(status_code=400,detail="La signature automatique est réservée aux RC/CPS.",)
    zones = document.administrative_zones or []
    if not zones:
        raise HTTPException(status_code=400,detail="Aucune zone administrative détectée pour ce document.",)
    input_path = document.classified_file_path or document.file_path
    if not input_path:
        raise HTTPException(status_code=400,detail="Chemin du document introuvable.",)

    output_path = (
        f"backend/data_storage/generated/"
        f"{user_id}_{document.tender_id}_"
        f"{document.file_type.lower()}_signe.pdf"
    )

    try:
        generated_path = DocumentSigner.sign_pdf(
            input_path=input_path,
            output_path=output_path,
            signer_name=signer_name,
            administrative_zones=zones,
        )

        return {
            "status": "success",
            "document_id": str(document.id),
            "file_type": document.file_type,
            "output_path": str(generated_path),
        }

    except Exception as exc:
        logger.exception("Erreur signature document | document_id=%s",document_id)
        raise HTTPException(status_code=500,detail=f"Erreur pendant la signature : {exc}",)

# FINALISATION

@router.post("/tenders/{tender_id}/finalize")
def finalize_tender(tender_id: UUID,user_id: UUID = Body(..., embed=True),db: Session = Depends(get_db)):
    """
    Vérifie le dossier, convertit les documents en PDF et persiste les livrables finaux dans generated/.
    """
    try:
        return preparation_service.finalize(db=db,tender_id=tender_id,user_id=user_id)
    except Exception as exc:
        logger.exception("Erreur finalisation | tender=%s", tender_id)
        raise HTTPException(status_code=400,detail=str(exc))