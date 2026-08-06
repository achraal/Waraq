from pydantic import BaseModel, Field
from typing import List, Optional

class ImportantDates(BaseModel):
    date_limite_depot: Optional[str] = Field(None, description="Date et heure limite de remise des offres")
    date_visite_lieux: Optional[str] = Field(None, description="Date de la visite guidée / réunion")
    date_ouverture_plis: Optional[str] = Field(None, description="Date d'ouverture des plis")

class RequiredDocuments(BaseModel):
    pieces_administratives: List[str] = Field(default_factory=list)
    pieces_techniques: List[str] = Field(default_factory=list)

class TenderRAGAnalysisResult(BaseModel):
    objet_appel_offres: Optional[str] = None
    maitre_douvrage: Optional[str] = None
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