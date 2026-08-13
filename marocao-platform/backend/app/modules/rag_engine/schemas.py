from typing import List, Optional
from pydantic import BaseModel, Field

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