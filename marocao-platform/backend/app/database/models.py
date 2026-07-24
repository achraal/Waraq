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
    classification_reason = Column(Text, nullable=True)
    classification_description = Column(Text, nullable=True)  # Text permet de stocker de longues phrases d'explications de l'IA
    classified_at = Column(DateTime, nullable=True)
    classified_file_path = Column(Text, nullable=True)
    response_time = Column(Float, nullable=True, comment="Temps de traitement/réponse en secondes")
    analysis_metadata = Column(JSON, nullable=True, comment="Métriques et détails techniques de la classification IA")
    is_validated = Column(
            Boolean, 
            default=False, 
            nullable=False, 
            server_default="false",
            doc="Indique si la classification a été revue/validée par un utilisateur humain"
        )
    
    validation_status = Column(
        String(50), 
        nullable=True, 
        doc="Statut de validation humaine : PENDING, VALIDATED, ou CORRECTED"
    )    

    tender = relationship("Tender", back_populates="documents") 
    audit_logs = relationship("ClassificationAuditLog", back_populates="document", cascade="all, delete-orphan")


class TenderLot(Base):
    __tablename__ = "tender_lots"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tender_id = Column(UUID(as_uuid=True), ForeignKey("tenders.id"), nullable=False)
    
    # Identifiants et description
    lot_number = Column(String, nullable=True) 
    title = Column(Text, nullable=True)        # "Gares de : ..."
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
    corrected_type = Column(String, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)

    # Relation vers le document parent
    document = relationship("TenderDocument", back_populates="audit_logs")