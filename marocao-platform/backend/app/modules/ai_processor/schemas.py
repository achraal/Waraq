from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, Any, List, Dict
from datetime import datetime
from uuid import UUID 

# Définition du schéma pour la correction manuelle
class DocumentValidationUpdate(BaseModel):
    correct_type: str
    is_correct: bool

class TenderDocumentResponse(BaseModel):
    """Schéma de retour (GET) calqué exactement sur ton modèle SQLAlchemy"""
    id: UUID
    tender_id: UUID
    file_name: str
    file_type: str
    file_path: str
    extracted_text: Optional[str] = None
    is_classified: bool
    
    # --- LES CHAMPS MANQUANTS QU'IL FALLAIT AJOUTER ---
    rag_processed: bool
    is_validated: bool
    validation_status: Optional[str] = None
    page_count: Optional[int] = None
    word_count: Optional[int] = None
    file_size_mb: Optional[float] = None
    ocr_duration_sec: Optional[float] = None
    administrative_zones: Optional[list] = None
    # --------------------------------------------------

    classification_reason: Optional[str] = None
    classification_description: Optional[str] = None
    classified_at: Optional[datetime] = None
    classified_file_path: Optional[str] = None
    response_time: Optional[float] = None
    analysis_metadata: Optional[dict] = None 

    # Configuration Pydantic v2 pour lire directement les objets SQLAlchemy
    model_config = ConfigDict(from_attributes=True)


class TenderDocumentUpdate(BaseModel):
    """Schéma pour la modification dynamique (PATCH).
    Tous les champs sont optionnels pour te permettre de ne passer 
    que ce que tu veux modifier dans le body.
    """
    tender_id: Optional[UUID] = None
    file_name: Optional[str] = None
    file_type: Optional[str] = None
    file_path: Optional[str] = None
    extracted_text: Optional[str] = None
    is_classified: Optional[bool] = None
    
    # --- AJOUTÉS POUR LE PATCH ---
    rag_processed: Optional[bool] = None
    is_validated: Optional[bool] = None
    validation_status: Optional[str] = None
    page_count: Optional[int] = None
    word_count: Optional[int] = None
    file_size_mb: Optional[float] = None
    ocr_duration_sec: Optional[float] = None
    administrative_zones: Optional[list] = None
    # -----------------------------

    classification_reason: Optional[str] = None
    classification_description: Optional[str] = None
    classified_file_path: Optional[str] = None
    response_time: Optional[float] = None
    analysis_metadata: Optional[dict] = None

    # Bloque les champs inconnus pour éviter les erreurs d'inattention
    model_config = ConfigDict(extra="forbid")
    
class TenderDocumentListResponse(BaseModel):
    total: int
    items: List[TenderDocumentResponse]
    
class PageRangeSplit(BaseModel):
    file_type: str        # Ex: "CPS", "RC", "AVIS"
    start_page: int       # Ex: 1
    end_page: int         # Ex: 12

class ValidateDocumentRequest(BaseModel):
    is_correct: bool               # True si validation conforme IA, False si correction
    corrected_type: Optional[str] = None # Utile si on annule le split ou change le type

    # CAS 1 : Annuler un découpage fait par l'IA et déclarer le document comme unifié
    undo_split: bool = False       

    # CAS 2 : Refaire ou faire un découpage manuel
    is_split_required: bool = False
    splits: Optional[List[PageRangeSplit]] = None
    
class LatestClassifiedPaginatedResponse(BaseModel):
    total_count: int
    documents: List[TenderDocumentResponse]

    class Config:
        from_attributes = True
        
class DocumentStatItem(BaseModel):
    id: UUID
    file_name: str
    file_type: Optional[str]
    classified_file_path: Optional[str]
    is_validated: bool
    validation_status: Optional[str]
    classified_at: Optional[datetime]

    class Config:
        from_attributes = True

class ClassificationReasonGroup(BaseModel):
    reason: str
    count: int
    documents: List[DocumentStatItem]

class ClassificationStatsResponse(BaseModel):
    total_documents: int
    by_reason: List[ClassificationReasonGroup]
    
class UnclassifyDocumentsRequest(BaseModel):
    document_ids: List[UUID]

class UnclassifyDocumentsResponse(BaseModel):
    message: str
    updated_count: int
    updated_document_ids: List[UUID]