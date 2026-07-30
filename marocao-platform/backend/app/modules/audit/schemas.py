from datetime import datetime
from typing import List, Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict


class AuditLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    document_id: UUID

    # Prédication
    predicted_type: str
    classification_reason: Optional[str] = None
    confidence_score: Optional[int] = None
    detected_language: Optional[str] = None
    extracted_keywords: Optional[List[str]] = None

    # Performance & LLM
    model_used: str
    execution_duration_sec: Optional[float] = None
    ollama_total_duration: Optional[float] = None
    prompt_tokens: Optional[int] = None
    generated_tokens: Optional[int] = None

    # Texte
    text_length_chars: Optional[int] = None
    text_word_count: Optional[int] = None
    has_uncertainty_keywords: bool = False

    # Validation humaine
    validation_status: str
    is_correct: Optional[bool] = None
    corrected_type: Optional[str] = None

    created_at: datetime


class AuditListResponse(BaseModel):
    total_count: int
    page: int
    limit: int
    data: List[AuditLogResponse]


class AuditStatsResponse(BaseModel):
    total_logs: int
    pending_count: int
    validated_count: int
    corrected_count: int
    accuracy_rate_percentage: Optional[float] = None


class AuditSearchFilter(BaseModel):
    """
    Paramètres pour rechercher et filtrer les logs d'audit via POST.
    """
    validation_status: Optional[str] = None  # PENDING, VALIDATED, CORRECTED
    skip: int = 0
    limit: int = 20