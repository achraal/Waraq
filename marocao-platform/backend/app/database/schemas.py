from pydantic import BaseModel, EmailStr, Field
from typing import Optional, Union
from enum import Enum

# --- AUTHENTIFICATION ---
class UserRegister(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=6)

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str
    role: str


# --- PROFILS JURIDIQUES (MAROCAO) ---

class BaseCompanyProfileInput(BaseModel):
    manager_name: str
    address: str
    phone: Optional[str] = None
    fax: Optional[str] = None
    email_contact: Optional[EmailStr] = None
    ice: Optional[str] = None
    tax_professionnelle: str
    rib: str = Field(..., min_length=24, max_length=24)
    bank_name: str

class PhysicalPersonProfileCreate(BaseCompanyProfileInput):
    cin_number: str
    auto_entrepreneur_card_number: Optional[str] = None
    rc_number: Optional[str] = None
    rc_locality: Optional[str] = None

class LegalPersonProfileCreate(BaseCompanyProfileInput):
    company_name: str
    rc_number: str
    rc_locality: str
    cnss_number: Optional[str] = None
    cooperative_register_number: Optional[str] = None

# Schéma global reçu par l'endpoint /profile
class ProfilePayload(BaseModel):
    structure_type: str  # Doit correspondre aux valeurs de votre énumération StructureType
    profile_data: Union[PhysicalPersonProfileCreate, LegalPersonProfileCreate]