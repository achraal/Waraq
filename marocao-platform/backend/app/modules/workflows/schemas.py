from typing import Any, Dict, List, Optional
from uuid import UUID
from pydantic import BaseModel, Field

class PreparationDocumentResponse(BaseModel):
    """Représente une pièce du dossier de préparation."""
    id: UUID
    document_type: str
    file_name: str
    file_path: str
    status: str
    is_required: bool
    is_generated: bool
    is_signed: bool
    is_filled: bool
    validation_message: Optional[str] = None

class PreparationResponse(BaseModel):
    """Réponse globale décrivant l'état de préparation d'un AO."""
    tender_id: UUID
    tender_reference: str
    status: str
    total_documents: int
    valid_documents: int
    invalid_documents: int
    can_finalize: bool
    missing_documents: List[str] = Field(default_factory=list)
    actions_required: List[str] = Field(default_factory=list)
    documents: List[PreparationDocumentResponse] = Field(default_factory=list)

class BDPField(BaseModel):
    """Champ d'une ligne BDP devant être rempli par l'utilisateur."""
    item_number: str
    description: str
    unit: Optional[str] = None
    quantity: Optional[float] = None
    unit_price: Optional[float] = None
    total_price_ht: Optional[float] = None

class BDPFillRequest(BaseModel):
    """Données saisies par l'utilisateur pour compléter le BDP."""
    values: List[BDPField]

class AdminField(BaseModel):
    """Champ détecté dans un acte ou une déclaration."""
    field_name: str
    label: str
    value: Optional[str] = None
    required: bool = True

class AdminFieldsFillRequest(BaseModel):
    """Valeurs fournies par l'utilisateur pour une pièce administrative."""
    values: Dict[str, Any]

class DocumentValidationRequest(BaseModel):
    """Demande de validation manuelle d'une pièce."""
    valid: bool
    message: Optional[str] = None