from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, Any
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
    classification_reason: Optional[str] = None
    classification_description: Optional[str] = None
    classified_at: Optional[datetime] = None
    classified_file_path: Optional[str] = None
    response_time: Optional[float] = None
    analysis_metadata: Optional[dict] = None  # Représente le champ JSON

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
    classification_reason: Optional[str] = None
    classification_description: Optional[str] = None
    classified_file_path: Optional[str] = None
    response_time: Optional[float] = None
    analysis_metadata: Optional[dict] = None

    # Bloque les champs inconnus pour éviter les erreurs d'inattention
    model_config = ConfigDict(extra="forbid")