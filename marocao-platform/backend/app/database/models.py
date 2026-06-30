# backend/app/database/models.py
import enum
import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Float, DateTime, Enum, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from backend.app.database.connection import Base

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
    reference = Column(String, unique=True, nullable=False, index=True) # Ex: 04/2026
    title = Column(String, nullable=False)                              # Objet du marché
    buyer = Column(String, nullable=False)                              # Administration
    deadline = Column(DateTime, nullable=False)                         # Date limite dépôt
    estimated_budget = Column(Float, nullable=True)                     # Estimation globale
    provisional_caution = Column(Float, nullable=True)                  # Cautionnement provisoire
    local_zip_path = Column(String, nullable=True)                      # Path local vers le dossier DCE .zip
    created_at = Column(DateTime, default=datetime.utcnow)

    documents = relationship("TenderDocument", back_populates="tender", cascade="all, delete-orphan")


class TenderDocument(Base):
    __tablename__ = "tender_documents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tender_id = Column(UUID(as_uuid=True), ForeignKey("tenders.id"), nullable=False)
    file_name = Column(String, nullable=False)                          # Ex: CPS.pdf, RC.pdf
    file_type = Column(String, nullable=False)                          # CPS, RC, AVIS
    extracted_text = Column(String, nullable=True)                      # Texte brut récupéré par l'OCR

    tender = relationship("Tender", back_populates="documents")