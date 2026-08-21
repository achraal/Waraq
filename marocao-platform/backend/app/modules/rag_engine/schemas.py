from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime
from uuid import UUID
from fastapi import Query

class ImportantDates(BaseModel):
    date_limite_depot: Optional[str] = Field(default=None, description="Date et heure limite de remise des offres")
    date_visite_lieux: Optional[str] = Field(default=None, description="Date de la visite des lieux ou réunion")
    date_ouverture_plis: Optional[str] = Field(default=None, description="Date d'ouverture des plis")

class RequiredDocuments(BaseModel):
    pieces_administratives: List[str] = Field(default_factory=list)
    pieces_techniques: List[str] = Field(default_factory=list)

class TenderRAGAnalysisResult(BaseModel):
    """
    Structure unique produite par Granite
    pour l'analyse métier d'un document d'appel d'offres.
    """
    objet_appel_offres: Optional[str] = None
    maitre_d_ouvrage: Optional[str] = None
    numero_reference: Optional[str] = None
    estimation_financiere: Optional[str] = None
    caution_provisoire: Optional[str] = None
    delai_execution: Optional[str] = None
    dates_importantes: ImportantDates = Field(default_factory=ImportantDates)
    pieces_a_fournir: RequiredDocuments = Field(default_factory=RequiredDocuments)
    clauses_administratives_clefs: List[str] = Field(default_factory=list)
    clauses_techniques_clefs: List[str] = Field(default_factory=list)
    criteres_evaluation: List[str] = Field(default_factory=list)
    penalites_retard: Optional[str] = None
    garanties_exigees: Optional[str] = None
    specifications_techniques: List[str] = Field(default_factory=list)
    
class TenderRAGSummary(BaseModel):
    """
    Résumé métier lisible produit à partir :
    - des données structurées extraites ;
    - du contexte RAG pertinent.
    """
    resume_executif: Optional[str] = None
    identification: Optional[str] = None
    objet_et_prestations: Optional[str] = None
    donnees_financieres: Optional[str] = None
    calendrier: Optional[str] = None
    conditions_participation: Optional[str] = None
    exigences_administratives: Optional[str] = None
    exigences_techniques: Optional[str] = None
    evaluation: Optional[str] = None
    execution: Optional[str] = None
    garanties_et_penalites: Optional[str] = None
    points_vigilance: List[str] = Field(default_factory=list)
    synthese_decisionnelle: Optional[str] = None

class RAGLogResponse(BaseModel):
    id: UUID
    document_id: Optional[UUID] = None
    tender_id: Optional[UUID] = None
    level: str
    stage: Optional[str] = None
    event: Optional[str] = None
    message: str
    details: Optional[dict] = None
    duration_sec: Optional[float] = None
    created_at: datetime

    class Config:
        from_attributes = True

class RAGLogsPaginatedResponse(BaseModel):
    total_count: int
    data: List[RAGLogResponse]

class RAGStatsResponse(BaseModel):
    total_logs: int
    error_count: int
    warning_count: int
    avg_duration_sec: Optional[float] = 0.0

class VectorPoint3D(BaseModel):
    id: Optional[str]
    x: float
    y: float
    z: float
    coordinates: List[float]
    document_id: Optional[str] = None
    file_name: Optional[str] = None
    doc_type: Optional[str] = None
    chunk_index: Optional[int] = None
    text_preview: Optional[str] = None
    document: Optional[str] = None

class Visualization3DResponse(BaseModel):
    collection: str
    tender_reference: str
    document_id: Optional[str] = None
    count: int
    dimensions_originales: int
    dimensions_visualisation: int = 3
    method_used: str
    points: List[VectorPoint3D]