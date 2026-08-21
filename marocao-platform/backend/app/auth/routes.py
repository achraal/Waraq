# backend/app/auth/routes.py
from sqlalchemy.orm import joinedload
from sqlalchemy.sql.functions import current_user
from fastapi import Body, APIRouter, Depends, HTTPException, status, Depends
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
import jwt
from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from backend.app.config import settings
from backend.app.database.connection import get_db
from backend.app.database.models import User, UserRole, StructureType, CompanyProfile, PhysicalPersonProfile, LegalPersonProfile
from backend.app.database import schemas
from backend.app.auth.security import SecurityManager

router = APIRouter(prefix="/auth", tags=["Authentication & Profile"])

# Déclaration du protocole OAuth2 pour l'extraction du token Bearer dans le header Authorization
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login-form-url")

# Dépendance pour récupérer l'utilisateur connecté via son JWT
def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Session expirée ou jeton invalide.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    payload = SecurityManager.decode_access_token(token)
    if payload is None:
        raise credentials_exception
    
    user_id: str = payload.get("user_id")
    if user_id is None:
        raise credentials_exception
        
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise credentials_exception
    return user

# --- ENDPOINT : INSCRIPTION ---
@router.post("/register", status_code=status.HTTP_201_CREATED)
def register_user(user_data: schemas.UserRegister, db: Session = Depends(get_db)):
    # 1. Vérifier si l'email existe D'ABORD
    existing_user = db.query(User).filter(User.email == user_data.email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cet email est déjà associé à un compte."
        )

    # 2. Créer et enregistrer l'utilisateur en BDD
    new_user = User(
        email=user_data.email,
        password_hash=SecurityManager.hash_password(user_data.password),
        role=UserRole.CANDIDATE
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)  # Récupère l'ID généré par la BDD

    # 3. Générer le token d'accès AVEC LA MÊME STRUCTURE QUE LOGIN
    token_data = {
        "sub": new_user.email,
        "role": new_user.role,
        "user_id": str(new_user.id)
    }
    access_token = SecurityManager.create_access_token(data=token_data)

    # 4. Retourner la réponse avec le token
    return {
        "message": "Compte créé avec succès",
        "user_id": str(new_user.id),
        "access_token": access_token,
        "token_type": "bearer",
        "role": new_user.role
    }

# --- ENDPOINT : CONNEXION ---
@router.post("/login", response_model=schemas.Token)
def login_user(credentials: schemas.UserLogin, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == credentials.email).first()
    if not user or not SecurityManager.verify_password(credentials.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Identifiants incorrects."
        )
    
    token_data = {"sub": user.email, "role": user.role, "user_id": str(user.id)}
    access_token = SecurityManager.create_access_token(data=token_data)
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "role": user.role
    }

def get_current_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Accès réservé aux administrateurs."
        )
    return current_user

# --- ENDPOINT SECURISÉ : CONFIGURER SON PROFIL JURIDIQUE ---
@router.post("/profile", status_code=status.HTTP_201_CREATED)
def create_or_update_profile(
    structure_type: StructureType = Body(...),
    profile_data: dict = Body(...), # Pydantic parsé manuellement ou par route dynamique selon le type
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Sécurité : Empêcher l'admin d'avoir un profil entreprise
    if current_user.role == UserRole.ADMIN:
        raise HTTPException(status_code=400, detail="Les administrateurs ne peuvent pas avoir de profil.")
    # Supprime l'ancien profil s'il existe pour éviter les conflits
    if current_user.company_profile:
        db.delete(current_user.company_profile)
        db.commit()

    try:
        if structure_type in [StructureType.INDIVIDUAL_PROPER, StructureType.AUTO_ENTREPRENEUR]:
            # Validation via le schéma Personne Physique
            validated_data = schemas.PhysicalPersonProfileCreate(**profile_data)
            new_profile = PhysicalPersonProfile(
                user_id=current_user.id,
                structure_type=structure_type,
                manager_name=validated_data.manager_name,
                address=validated_data.address,
                phone=validated_data.phone,
                fax=validated_data.fax,
                email_contact=validated_data.email_contact,
                ice=validated_data.ice,
                tax_professionnelle=validated_data.tax_professionnelle,
                rib=validated_data.rib,
                bank_name=validated_data.bank_name,
                cin_number=validated_data.cin_number,
                auto_entrepreneur_card_number=validated_data.auto_entrepreneur_card_number,
                rc_number=validated_data.rc_number,
                rc_locality=validated_data.rc_locality
            )
        else:
            # Validation via le schéma Personne Morale (Sociétés, Coopératives...)
            validated_data = schemas.LegalPersonProfileCreate(**profile_data)
            new_profile = LegalPersonProfile(
                user_id=current_user.id,
                structure_type=structure_type,
                manager_name=validated_data.manager_name,
                address=validated_data.address,
                phone=validated_data.phone,
                fax=validated_data.fax,
                email_contact=validated_data.email_contact,
                ice=validated_data.ice,
                tax_professionnelle=validated_data.tax_professionnelle,
                rib=validated_data.rib,
                bank_name=validated_data.bank_name,
                company_name=validated_data.company_name,
                rc_number=validated_data.rc_number,
                rc_locality=validated_data.rc_locality,
                cnss_number=validated_data.cnss_number,
                cooperative_register_number=validated_data.cooperative_register_number
            )
        
        db.add(new_profile)
        db.commit()
        return {"message": f"Profil juridique ({structure_type.value}) configuré avec succès."}
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"Erreur de validation des données de l'entreprise : {str(e)}")

# --- GET : OBTENIR L'UTILISATEUR COURANT ---
@router.get("/me")
def get_me(current_user: User = Depends(get_current_user)):
    return {
        "id": str(current_user.id),
        "email": current_user.email,
        "role": current_user.role
    }

# --- GET : VOIR SON PROFIL ---
@router.get("/profile")
def get_my_profile(current_user: User = Depends(get_current_user)):
    # Si c'est un admin, retourner directement un statut sans chercher de profil
    if current_user.role == UserRole.ADMIN:
        return {"is_admin": True, "message": "Les administrateurs n'ont pas de profil entreprise."}
        
    if not current_user.company_profile:
        raise HTTPException(status_code=404, detail="Aucun profil configuré.")
        
    return current_user.company_profile

# --- ADMIN : LISTER TOUS LES UTILISATEURS AVEC LEURS PROFILS ---
@router.get("/admin/users")
def get_all_users(db: Session = Depends(get_db), admin: User = Depends(get_current_admin)):
    # Récupère tous les utilisateurs et leurs profils associés
    # .options(joinedload(User.company_profile)) force le chargement du profil
    # Cela inclut les colonnes spécifiques de la table enfant via le polymorphisme
    return db.query(User).options(joinedload(User.company_profile)).all()

# --- ADMIN : VOIR LES DÉTAILS COMPLETS D'UN UTILISATEUR ---
@router.get("/admin/users/{user_id}")
def get_user_details(
    user_id: str, 
    db: Session = Depends(get_db), 
    admin: User = Depends(get_current_admin)
):
    # On récupère l'utilisateur avec son profil complet chargé
    user = db.query(User).options(joinedload(User.company_profile)).filter(User.id == user_id).first()
    
    if not user:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable.")
    
    return user

# --- ADMIN : SUPPRIMER UN UTILISATEUR ---
@router.delete("/admin/users/{user_id}")
def delete_user(user_id: str, db: Session = Depends(get_db), admin: User = Depends(get_current_admin)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable.")
    db.delete(user)
    db.commit()
    return {"message": "Utilisateur et son profil supprimés avec succès."}

# --- ADMIN : MODIFIER LE MOT DE PASSE D'UN UTILISATEUR ---
@router.patch("/admin/users/{user_id}/password")
def update_user_password(
    user_id: str, 
    new_password: str = Body(..., embed=True), 
    db: Session = Depends(get_db), 
    admin: User = Depends(get_current_admin)
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable.")
    
    user.password_hash = SecurityManager.hash_password(new_password)
    db.commit()
    return {"message": "Mot de passe utilisateur mis à jour par l'admin."}

# --- ADMIN : MODIFIER LE PROFIL D'UN UTILISATEUR ---
@router.put("/admin/users/{user_id}/profile", status_code=status.HTTP_200_OK)
def admin_update_user_profile(
    user_id: str,
    structure_type: StructureType = Body(...),
    profile_data: dict = Body(...),
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin)
):
    # 1. Trouver l'utilisateur cible
    target_user = db.query(User).filter(User.id == user_id).first()
    if not target_user:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable.")
    
    # 2. Supprimer l'ancien profil s'il existe
    if target_user.company_profile:
        db.delete(target_user.company_profile)
        db.commit()

    # 3. Utiliser la logique de création (via ta fonction de sauvegarde)
    # Note : Si tu n'as pas factorisé en fonction, recopie ici le try/except de création
    # en remplaçant 'current_user.id' par 'target_user.id'
    try:
        if structure_type in [StructureType.INDIVIDUAL_PROPER, StructureType.AUTO_ENTREPRENEUR]:
            # Validation via le schéma Personne Physique
            validated_data = schemas.PhysicalPersonProfileCreate(**profile_data)
            new_profile = PhysicalPersonProfile(
                user_id=target_user.id,
                structure_type=structure_type,
                manager_name=validated_data.manager_name,
                address=validated_data.address,
                phone=validated_data.phone,
                fax=validated_data.fax,
                email_contact=validated_data.email_contact,
                ice=validated_data.ice,
                tax_professionnelle=validated_data.tax_professionnelle,
                rib=validated_data.rib,
                bank_name=validated_data.bank_name,
                cin_number=validated_data.cin_number,
                auto_entrepreneur_card_number=validated_data.auto_entrepreneur_card_number,
                rc_number=validated_data.rc_number,
                rc_locality=validated_data.rc_locality
            )
        else:
            # Validation via le schéma Personne Morale (Sociétés, Coopératives...)
            validated_data = schemas.LegalPersonProfileCreate(**profile_data)
            new_profile = LegalPersonProfile(
                user_id=target_user.id,
                structure_type=structure_type,
                manager_name=validated_data.manager_name,
                address=validated_data.address,
                phone=validated_data.phone,
                fax=validated_data.fax,
                email_contact=validated_data.email_contact,
                ice=validated_data.ice,
                tax_professionnelle=validated_data.tax_professionnelle,
                rib=validated_data.rib,
                bank_name=validated_data.bank_name,
                company_name=validated_data.company_name,
                rc_number=validated_data.rc_number,
                rc_locality=validated_data.rc_locality,
                cnss_number=validated_data.cnss_number,
                cooperative_register_number=validated_data.cooperative_register_number
            )
        
        db.add(new_profile)
        db.commit()
        return {"message": f"Profil mis à jour avec succès pour l'utilisateur {target_user.email}."}
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"Erreur de modification : {str(e)}")