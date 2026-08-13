import enum, uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Float, DateTime, Enum, ForeignKey, Text, JSON, Boolean, Integer, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from backend.app.database.connection import Base
from sqlalchemy.dialects.postgresql import JSONB

# --- ENUMS (Héritant de str pour une parfaite compatibilité JSON/PostgreSQL) ---
class UserRole(str, enum.Enum):
    CANDIDATE = "CANDIDATE"
    ADMIN = "ADMIN"

class StructureType(str, enum.Enum):
    INDIVIDUAL_PROPER = "INDIVIDUAL_PROPER"      # Personne physique - propre compte
    AUTO_ENTREPRENEUR = "AUTO_ENTREPRENEUR"      # Auto-entrepreneur
    COMPANY = "COMPANY"                          # Société (SARL, SA, SAS...)
    PUBLIC_INSTITUTION = "PUBLIC_INSTITUTION"    # Établissement public
    COOPERATIVE = "COOPERATIVE"                  # Coopérative

class ScrapingStatus(str, enum.Enum):
    SUCCESS = "SUCCESS"
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    SELENIUM_ERROR = "SELENIUM_ERROR"
    DOWNLOAD_ERROR = "DOWNLOAD_ERROR"

class RAGStatus(str, enum.Enum):
    PENDING = "PENDING"
    INDEXING = "INDEXING"
    ANALYZING = "ANALYZING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"

class GeneratedDocType(str, enum.Enum):
    ACTE_ENGAGEMENT = "ACTE_ENGAGEMENT"
    DECLARATION_HONNEUR = "DECLARATION_HONNEUR"
    BDP_COMPLETED = "BDP_COMPLETED"
    SYNTHESE_CONFORMITE = "SYNTHESE_CONFORMITE"

class PreparationDocumentStatus(str, enum.Enum):
    DETECTED = "DETECTED"
    VALID = "VALID"
    INVALID = "INVALID"
    DELETED = "DELETED"
    GENERATED = "GENERATED"
    FILLED = "FILLED"
    SIGNED = "SIGNED"
    READY = "READY"

class PreparationStatus(str, enum.Enum):
    PENDING = "PENDING"
    SCANNING = "SCANNING"
    REVIEW = "REVIEW"
    READY = "READY"
    FINALIZED = "FINALIZED"
    FAILED = "FAILED"

# --- TABLE : UTILISATEURS ---
class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String, unique=True, nullable=False, index=True)
    password_hash = Column(String, nullable=False)
    role = Column(Enum(UserRole), default=UserRole.CANDIDATE, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    # Relation 1-to-1 avec cascade de suppression propre
    company_profile = relationship("CompanyProfile", back_populates="user", uselist=False, cascade="all, delete-orphan")


# --- HÉRITAGE DE TABLES : PROFIL ENTREPRISE ---
class CompanyProfile(Base):
    __tablename__ = "company_profiles"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    structure_type = Column(Enum(StructureType), nullable=False)    
    # Champs Communs demandés dans les documents (Acte engagement & Déclaration sur l'honneur)
    manager_name = Column(String, nullable=False)  # Nom, prénom et qualité
    address = Column(String, nullable=False)       # Domicile élu
    phone = Column(String, nullable=True)
    fax = Column(String, nullable=True)
    email_contact = Column(String, nullable=True)    
    # Mis à nullable=True car optionnel pour les purs auto-entrepreneurs/personnes physiques
    ice = Column(String, nullable=True, unique=True) 
    tax_professionnelle = Column(String, nullable=False) # Patente
    rib = Column(String, nullable=False)           # RIB à 24 positions
    bank_name = Column(String, nullable=False)     # Banque, Poste ou TGR
    # Colonne technique pour gérer l'héritage SQLAlchemy
    type_discriminator = Column(String, nullable=False)
    capital_social = Column(Float, nullable=True)
    __mapper_args__ = {
        "polymorphic_on": type_discriminator,
        "polymorphic_identity": "base_profile",
    }

    user = relationship("User", back_populates="company_profile")


class PhysicalPersonProfile(CompanyProfile):
    __tablename__ = "physical_person_profiles"

    id = Column(UUID(as_uuid=True), ForeignKey("company_profiles.id"), primary_key=True)    
    # Spécifique Personnes physiques / Auto-entrepreneurs
    cin_number = Column(String, nullable=False)
    auto_entrepreneur_card_number = Column(String, nullable=True) 
    rc_number = Column(String, nullable=True)     
    rc_locality = Column(String, nullable=True)

    __mapper_args__ = {
        "polymorphic_identity": "physical_person",
    }


class LegalPersonProfile(CompanyProfile):
    __tablename__ = "legal_person_profiles"

    id = Column(UUID(as_uuid=True), ForeignKey("company_profiles.id"), primary_key=True)
    
    # Spécifique Sociétés, Établissements publics, Coopératives
    company_name = Column(String, nullable=False) # Raison sociale
    rc_number = Column(String, nullable=False)    # Registre du commerce obligatoire
    rc_locality = Column(String, nullable=False)
    cnss_number = Column(String, nullable=True)   
    cooperative_register_number = Column(String, nullable=True) 
    legal_authorization_text = Column(String, nullable=True)

    __mapper_args__ = {
        "polymorphic_identity": "legal_person",
    }

# --- TABLES : APPELS D'OFFRES ET DOCUMENTS ---
class Tender(Base):
    __tablename__ = "tenders"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    reference = Column(String, unique=True, nullable=False, index=True)
    title = Column(Text, nullable=False)                               # Correspond à "objet"
    buyer = Column(String, nullable=False)                               # Correspond à "acheteur"
    
    # --- TOUS LES CHAMPS DE TES MÉTADONNÉES MAROCAINES ---
    type_annonce = Column(Text, nullable=True)
    procedure = Column(Text, nullable=True)
    categorie = Column(Text, nullable=True, index=True)
    allotissement = Column(Text, nullable=True)
    lieu_execution = Column(Text, nullable=True)
    estimated_budget = Column(Text, nullable=True)                   # Correspond à "budget"
    reserve_pme = Column(Text, nullable=True)
    domaines_activite = Column(Text, nullable=True)
    adresse_retrait = Column(Text, nullable=True)
    adresse_depot = Column(Text, nullable=True)
    lieu_ouverture = Column(Text, nullable=True)
    prix_acquisition = Column(String, nullable=True)
    provisional_caution = Column(Text, nullable=True)                # Correspond à "caution"
    qualifications = Column(Text, nullable=True)
    agrements = Column(Text, nullable=True)
    variante = Column(String, nullable=True)
    deadline = Column(String, nullable=True, index=True)
    prospectus_notices = Column(Text, nullable=True)
    reunion = Column(Text, nullable=True)
    visite_lieux = Column(Text, nullable=True)
    contact_administratif = Column(Text, nullable=True) 
    nbr_lots = Column(Integer, default=0)
    
    # Métriques système
    local_zip_path = Column(String, nullable=True)
    metadata_json = Column(JSON, nullable=True)                          # Copie de sauvegarde brute
    created_at = Column(DateTime, default=datetime.utcnow)
    extraction_date = Column(DateTime, index=True) # Date réelle d'extraction du site web
    is_consulted = Column(Boolean, default=False, nullable=False, index=True)
    nbr_documents = Column(Integer, default=0, nullable=False)
    is_recursive = Column(Boolean, default=False, nullable=False)
    scraping_status = Column(Enum(ScrapingStatus), default=ScrapingStatus.PENDING, nullable=False, index=True)
    scraping_duration_sec = Column(Float, nullable=True)
    is_zip_corrupted = Column(Boolean, default=False, nullable=False, index=True)
    
    #Optionnel : pour garder le message d'erreur précis si besoin
    scraping_error_message = Column(Text, nullable=True)
 
    lots = relationship("TenderLot", back_populates="tender", cascade="all, delete-orphan")
    documents = relationship("TenderDocument", back_populates="tender", cascade="all, delete-orphan")

class TenderDocument(Base):
    __tablename__ = "tender_documents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tender_id = Column(UUID(as_uuid=True), ForeignKey("tenders.id"), nullable=False)
    file_name = Column(Text, nullable=False)
    file_type = Column(String, nullable=False)                           # CPS, RC, AVIS ou Nom/Extension dynamique
    file_path = Column(Text, nullable=False)
    extracted_text = Column(Text, nullable=True)                         # Réservé pour ton moteur OCR / RAG
    is_classified = Column(Boolean, default=False, nullable=False, index=True)
    rag_processed = Column(Boolean, nullable=False, default=False, server_default="false")
    classification_reason = Column(Text, nullable=True)
    classification_description = Column(Text, nullable=True)  # Text permet de stocker de longues phrases d'explications de l'IA
    classified_at = Column(DateTime, nullable=True)
    classified_file_path = Column(Text, nullable=True)
    response_time = Column(Float, nullable=True, comment="Temps de traitement/réponse en secondes")
    page_count = Column(Integer, nullable=True, comment="Nombre total de pages du document")
    word_count = Column(Integer, nullable=True, comment="Nombre de mots extraits")
    file_size_mb = Column(Float, nullable=True, comment="Taille du document en Mo")
    ocr_duration_sec = Column(Float, nullable=True, comment="Temps consacré à l'OCR en secondes")
    analysis_metadata = Column(JSON, nullable=True, comment="Métriques et détails techniques de la classification IA")
    is_validated = Column(Boolean, default=False, nullable=False, server_default="false", doc="Indique si la classification a été revue/validée par un utilisateur humain")
    validation_status = Column(String(50), nullable=True, doc="Statut de validation humaine : PENDING, VALIDATED, ou CORRECTED") 
    administrative_zones = Column(JSONB,nullable=True,default=list)   

    tender = relationship("Tender", back_populates="documents") 
    audit_logs = relationship("ClassificationAuditLog", back_populates="document", cascade="all, delete-orphan")
    rag_result = relationship("RAGAnalysisResult", back_populates="document", uselist=False, cascade="all, delete-orphan")

class TenderLot(Base):
    __tablename__ = "tender_lots"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tender_id = Column(UUID(as_uuid=True), ForeignKey("tenders.id"), nullable=False)
    
    # Identifiants et description
    lot_number = Column(String, nullable=True) 
    title = Column(Text, nullable=True)        
    description = Column(Text, nullable=True)  # La description détaillée
    
    # Données financières et conditions
    estimated_budget = Column(String, nullable=True)
    provisional_caution = Column(String, nullable=True)
    variante = Column(String, nullable=True)
    
    # Champs spécifiques manquants
    qualifications = Column(Text, nullable=True)
    agrements = Column(Text, nullable=True)
    prospectus_notices = Column(Text, nullable=True)
    reunion = Column(Text, nullable=True)
    visite_lieux = Column(Text, nullable=True)
    
    # Autres
    env_considerations = Column(Text, nullable=True)
    reserve_pme = Column(String, nullable=True)

    tender = relationship("Tender", back_populates="lots")

class EmailNotification(Base):
    __tablename__ = "email_notifications"
    id = Column(Integer, primary_key=True, index=True)
    mail_uid = Column(String, unique=True) # ID unique fourni par le serveur IMAP
    subject = Column(String)
    sender = Column(String, default="noreply-marchespublics@tgr.gov.ma")
    content = Column(Text) # Le corps de l'email
    received_at = Column(DateTime)
    is_read = Column(Boolean, default=False)

class SystemMetric(Base):
    __tablename__ = "system_metrics"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, server_default=func.now(), index=True)
    
    # Nos 4 blocs logiques flexibles
    server_and_hardware_health = Column(JSONB, nullable=False)
    database_status = Column(JSONB, nullable=False)
    scraping_metrics = Column(JSONB, nullable=False)
    ai_metrics = Column(JSONB, nullable=False)
    ai_and_pipeline = Column(JSONB, nullable=False)
    
class ClassificationAuditLog(Base):
    __tablename__ = "classification_audit_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id = Column(UUID(as_uuid=True), ForeignKey("tender_documents.id", ondelete="CASCADE"), nullable=False)

    # Résultat de la tentative
    predicted_type = Column(String, nullable=False)
    classification_reason = Column(String, nullable=True)
    confidence_score = Column(Integer, nullable=True)
    detected_language = Column(String(10), nullable=True)
    extracted_keywords = Column(JSON, nullable=True)  # Liste de mots-clés
    # Métriques de performance & LLM
    model_used = Column(String, nullable=False)
    execution_duration_sec = Column(Float, nullable=True)
    ollama_total_duration = Column(Float, nullable=True)
    prompt_tokens = Column(Integer, nullable=True)
    generated_tokens = Column(Integer, nullable=True)    
    # Propriétés du texte analysé
    text_length_chars = Column(Integer, nullable=True)
    text_word_count = Column(Integer, nullable=True)
    has_uncertainty_keywords = Column(Boolean, default=False)    
    # Workflow de validation humaine
    validation_status = Column(String, default="PENDING")  # PENDING, VALIDATED, CORRECTED
    is_correct = Column(Boolean, nullable=True)
    is_scanned = Column(Boolean, default=False, nullable=True)
    inspection_method = Column(String, nullable=True)
    corrected_type = Column(String, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)

    # Relation vers le document parent
    document = relationship("TenderDocument", back_populates="audit_logs")
   
# ANALYSE MÉTIER RAG ---
class RAGAnalysisResult(Base):
    __tablename__ = "rag_analysis_results"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id = Column(
        UUID(as_uuid=True), 
        ForeignKey("tender_documents.id", ondelete="CASCADE"), 
        unique=True, 
        nullable=False
    )    
    # Suivi d'état du traitement asynchrone
    status = Column(Enum(RAGStatus), default=RAGStatus.PENDING, nullable=False, index=True)
    error_message = Column(Text, nullable=True)
    extracted_text = Column(Text, nullable=True)
    # Données extraites structurées par Granite 4.1:3B (n'altère PAS extracted_text d'origine)
    rag_analysis = Column(JSONB, nullable=True)    
    # Métriques RAG pour Telemetry & Audit
    chunk_count = Column(Integer, nullable=True)
    indexing_duration_sec = Column(Float, nullable=True)
    retrieval_duration_sec = Column(Float, nullable=True)
    generation_duration_sec = Column(Float, nullable=True)
    total_rag_duration_sec = Column(Float, nullable=True)   
    embedding_duration_sec = Column(Float, nullable=True)
    llm_extraction_duration_sec = Column(Float, nullable=True)
    # Traçabilité des modèles
    model_used = Column(String, default="Granite 4.1:3B", nullable=False)
    embedding_model_used = Column(String, default="BAAI/bge-m3", nullable=False)
    chroma_collection_name = Column(String, nullable=True)
    summary = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relation vers TenderDocument
    document = relationship("TenderDocument", back_populates="rag_result")

class RAGLog(Base):
    __tablename__ = "rag_logs"

    id = Column(UUID(as_uuid=True),primary_key=True,default=uuid.uuid4)
    document_id = Column(UUID(as_uuid=True),ForeignKey("tender_documents.id",ondelete="CASCADE"),nullable=True,index=True)
    tender_id = Column(UUID(as_uuid=True),ForeignKey("tenders.id",ondelete="CASCADE"),nullable=True,index=True)
    level = Column(String(20),nullable=False,default="INFO")
    stage = Column(String(50),nullable=True,index=True)
    event = Column(String(100),nullable=True,index=True)
    message = Column(Text,nullable=False)
    details = Column(JSONB,nullable=True)
    duration_sec = Column(Float,nullable=True)
    created_at = Column(DateTime,default=lambda: datetime.now(timezone.utc),nullable=False,index=True)
    document = relationship("TenderDocument",foreign_keys=[document_id])
    tender = relationship("Tender",foreign_keys=[tender_id])

# DOCUMENTS DE RÉPONSE GÉNÉRÉS ---
class GeneratedDocument(Base):
    __tablename__ = "generated_documents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True),ForeignKey("users.id",ondelete="CASCADE"),nullable=False)
    tender_id = Column(UUID(as_uuid=True),ForeignKey("tenders.id",ondelete="CASCADE"),nullable=False)
    source_document_id = Column(UUID(as_uuid=True),ForeignKey("tender_documents.id", ondelete="SET NULL"),nullable=True)
    doc_type = Column(Enum(GeneratedDocType), nullable=False)
    file_name = Column(String, nullable=False)
    file_path = Column(Text, nullable=False)
    is_custom_template = Column(Boolean, default=False, nullable=False)
    is_fallback_used = Column(Boolean, default=False, nullable=False)
    generation_metadata = Column(JSONB, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    user = relationship("User")
    tender = relationship("Tender")
    source_document = relationship("TenderDocument")

class TenderPreparation(Base):
    __tablename__ = "tender_preparations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tender_id = Column(UUID(as_uuid=True),ForeignKey("tenders.id", ondelete="CASCADE"),unique=True,nullable=False)
    user_id = Column(UUID(as_uuid=True),ForeignKey("users.id", ondelete="CASCADE"),nullable=False)
    status = Column(Enum(PreparationStatus),default=PreparationStatus.PENDING,nullable=False,index=True)
    can_finalize = Column(Boolean, default=False, nullable=False)
    validation_errors = Column(JSONB, nullable=True)
    created_at = Column(DateTime,default=lambda: datetime.now(timezone.utc),nullable=False)
    updated_at = Column(DateTime,default=lambda: datetime.now(timezone.utc),onupdate=lambda: datetime.now(timezone.utc),nullable=False)
    tender = relationship("Tender")
    user = relationship("User")
    documents = relationship("TenderPreparationDocument",back_populates="preparation",cascade="all, delete-orphan")

class TenderPreparationDocument(Base):
    __tablename__ = "tender_preparation_documents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    preparation_id = Column(UUID(as_uuid=True),ForeignKey("tender_preparations.id", ondelete="CASCADE"),nullable=False,index=True)
    document_id = Column(UUID(as_uuid=True),ForeignKey("tender_documents.id", ondelete="SET NULL"),nullable=True)
    generated_document_id = Column(UUID(as_uuid=True),ForeignKey("generated_documents.id", ondelete="SET NULL"),nullable=True)
    document_type = Column(String(100), nullable=False, index=True)
    file_name = Column(String, nullable=False)
    file_path = Column(Text, nullable=False)
    status = Column(Enum(PreparationDocumentStatus),default=PreparationDocumentStatus.DETECTED,nullable=False,index=True)
    is_required = Column(Boolean, default=False, nullable=False)
    is_user_provided = Column(Boolean, default=True, nullable=False)
    is_generated = Column(Boolean, default=False, nullable=False)
    is_signed = Column(Boolean, default=False, nullable=False)
    is_filled = Column(Boolean, default=False, nullable=False)
    validation_message = Column(Text, nullable=True)
    metadata_json = Column(JSONB, nullable=True)
    created_at = Column(DateTime,default=lambda: datetime.now(timezone.utc),nullable=False)
    updated_at = Column(DateTime,default=lambda: datetime.now(timezone.utc),onupdate=lambda: datetime.now(timezone.utc),nullable=False)
    preparation = relationship("TenderPreparation",back_populates="documents")
    document = relationship("TenderDocument")
    generated_document = relationship("GeneratedDocument")