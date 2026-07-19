from unicodedata import category
from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.orm import Session, joinedload, selectinload
from sqlalchemy import cast, Date, Time
from typing import List, Optional
from datetime import datetime
from backend.app.database.connection import get_db
from backend.app.database.models import Tender, User
from backend.app.modules.tenders.schemas import TenderDelete, TenderFilter
from backend.app.auth.routes import get_current_admin
from dateutil import parser


router = APIRouter(prefix="/tenders", tags=["Tenders Management"])

# GET : Lister toutes les offres avec leurs documents
# 1. GET : Toutes les offres (avec documents)
@router.get("/")
def get_tenders(
    skip: Optional[int] = None, 
    limit: Optional[int] = None, 
    db: Session = Depends(get_db)
):
    query = db.query(Tender).options(selectinload(Tender.documents), 
        selectinload(Tender.lots)).order_by(Tender.created_at.desc())
    
    # Si limit est fourni, on pagine
    if limit is not None:
        query = query.offset(skip or 0).limit(limit)
    
    tenders = query.all()
    total = db.query(Tender).count()
    
    return {
        "total": total,
        "count": len(tenders),
        "data": tenders
    }

# 2. POST : Filtrage des offres complètes
@router.post("/filter")
def filter_tenders(filters: TenderFilter, db: Session = Depends(get_db)):
    query = db.query(Tender).options(joinedload(Tender.documents), 
        joinedload(Tender.lots))

    if filters.is_consulted is not None:
        query = query.filter(Tender.is_consulted == filters.is_consulted)
    
    if filters.deadline: 
        query = query.filter(Tender.deadline.contains(filters.deadline))

    if filters.category:
        # On utilise .ilike pour une recherche insensible à la casse 
        # (ex: "Travaux" trouvera aussi "TRAVAUX")
        query = query.filter(Tender.categorie.ilike(f"%{filters.category}%"))
        
    if filters.extraction_date:
        try:
            # 1. On parse la donnée
            dt = parser.parse(filters.extraction_date)
            
            # 2. Si l'input ne contient pas de date (pas de '-', '/', ou 'T')
            # On force le filtrage SQL uniquement sur l'heure (Time)
            if not any(c in filters.extraction_date for c in ["/", "-", "T"]):
                # On compare l'heure de la base avec l'heure fournie
                query = query.filter(cast(Tender.extraction_date, Time) >= dt.time())
            else:
                # 3. Sinon, c'est une date complète (avec ou sans heure), on compare normalement
                query = query.filter(Tender.extraction_date >= dt)
                
        except (ValueError, TypeError):
            raise HTTPException(status_code=400, detail="Format de date invalide.")
    
    results = query.all()
    return {"count": len(results), "data": results}

# 3. GET : Liste simplifiée (sans documents)
@router.get("/minimal")
def get_tenders_minimal(
    skip: Optional[int] = None,
    limit: Optional[int] = None,
    db: Session = Depends(get_db)
):
    query = db.query(Tender.id, Tender.reference, Tender.title, Tender.categorie, Tender.buyer, Tender.deadline)
    
    # Si limit est fourni, on applique la pagination
    if limit is not None:
        query = query.offset(skip or 0).limit(limit)
        
    tenders = query.all()
    # On reconstruit les dictionnaires
    data = [{"id": t.id, "reference": t.reference, "title": t.title, "categorie": t.categorie, "buyer": t.buyer, "deadline": t.deadline} for t in tenders]
    
    return {"count": len(data), "data": data}

# 4. POST : Filtrage des offres minimales
@router.post("/minimal/filter")
def filter_tenders_minimal(filters: TenderFilter, db: Session = Depends(get_db)):
    query = db.query(Tender.id, Tender.reference, Tender.title, Tender.buyer, Tender.deadline)

    if filters.is_consulted is not None:
        query = query.filter(Tender.is_consulted == filters.is_consulted)
    
    if filters.deadline: 
        query = query.filter(Tender.deadline.contains(filters.deadline))

    if filters.category:
        # On utilise .ilike pour une recherche insensible à la casse 
        # (ex: "Travaux" trouvera aussi "TRAVAUX")
        query = query.filter(Tender.categorie.ilike(f"%{filters.category}%"))
        
    if filters.extraction_date:
        try:
            # 1. On parse la donnée
            dt = parser.parse(filters.extraction_date)
            
            # 2. Si l'input ne contient pas de date (pas de '-', '/', ou 'T')
            # On force le filtrage SQL uniquement sur l'heure (Time)
            if not any(c in filters.extraction_date for c in ["/", "-", "T"]):
                # On compare l'heure de la base avec l'heure fournie
                query = query.filter(cast(Tender.extraction_date, Time) >= dt.time())
            else:
                # 3. Sinon, c'est une date complète (avec ou sans heure), on compare normalement
                query = query.filter(Tender.extraction_date >= dt)
                
        except (ValueError, TypeError):
            raise HTTPException(status_code=400, detail="Format de date invalide.")
    
    tenders = query.all()
    # On reconstruit les dictionnaires proprement
    data = [
        {"id": t.id, "reference": t.reference, "title": t.title, "buyer": t.buyer, "deadline": t.deadline} 
        for t in tenders
    ]
    return {"count": len(data), "data": data}

# GET : Une offre spécifique avec ses documents
@router.get("/{tender_id}")
def get_tender(tender_id: str, db: Session = Depends(get_db)):
    tender = db.query(Tender).options(joinedload(Tender.documents), 
        joinedload(Tender.lots)).filter(Tender.id == tender_id).first()
    if not tender:
        raise HTTPException(status_code=404, detail="Offre non trouvée")
    return tender

# PATCH : Modification d'un champ
@router.patch("/{tender_id}")
def update_tender(tender_id: str, update_data: dict, db: Session = Depends(get_db), admin: User = Depends(get_current_admin)):
    tender = db.query(Tender).options(joinedload(Tender.lots)).filter(Tender.id == tender_id).first()
    if not tender:
        raise HTTPException(status_code=404, detail="Offre non trouvée")
    
    # Liste des champs autorisés à la modification
    allowed_fields = ["title", "buyer", "estimated_budget", "deadline", "contact_administratif", "is_consulted"]
    
    for key, value in update_data.items():
        if key in allowed_fields and hasattr(tender, key):
            setattr(tender, key, value)
    
    db.commit()
    db.refresh(tender) # Recharger l'objet mis à jour
    return tender

# DELETE : Suppression simple ou multiple
@router.post("/delete-multiple")
def delete_tenders(
    payload: TenderDelete, 
    db: Session = Depends(get_db), 
    admin: User = Depends(get_current_admin)
):
    # 1. On récupère les objets en mémoire au lieu de faire un delete direct
    tenders_to_delete = db.query(Tender).filter(Tender.id.in_(payload.ids)).all()
    
    if not tenders_to_delete:
        raise HTTPException(status_code=404, detail="Aucune offre trouvée avec ces IDs")

    # 2. On supprime chaque objet. 
    # Comme ils sont chargés en mémoire, le cascade="all, delete-orphan" 
    # sera automatiquement appliqué par SQLAlchemy.
    for tender in tenders_to_delete:
        db.delete(tender)
    
    # 3. On valide la transaction
    db.commit()
    
    return {"status": "success", "message": f"{len(tenders_to_delete)} offres et leurs documents associés supprimés"}

# PATCH : Marquer une offre comme consultée
@router.patch("/{tender_id}/mark-consulted")
def mark_tender_as_consulted(tender_id: str, db: Session = Depends(get_db), admin: User = Depends(get_current_admin)):
    tender = db.query(Tender).filter(Tender.id == tender_id).first()
    if not tender:
        raise HTTPException(status_code=404, detail="Offre non trouvée")
    
    tender.is_consulted = True
    db.commit()
    db.refresh(tender)
    return {"status": "success", "is_consulted": True}

# PATCH : Marquer une offre comme non consultée
@router.patch("/{tender_id}/mark-unconsulted")
def mark_tender_as_unconsulted(tender_id: str, db: Session = Depends(get_db), admin: User = Depends(get_current_admin)):
    tender = db.query(Tender).filter(Tender.id == tender_id).first()
    if not tender:
        raise HTTPException(status_code=404, detail="Offre non trouvée")
    
    tender.is_consulted = False
    db.commit()
    db.refresh(tender)
    return {"status": "success", "is_consulted": False}

# GET : Rechercher une offre par sa référence (recherche exacte ou partielle)
@router.get("/search/reference")
def search_by_reference(
    payload: dict = Body(...), 
    db: Session = Depends(get_db)
):
    ref = payload.get("reference")
    # Utilisation de .ilike pour une recherche insensible à la casse
    # On retourne la première correspondance trouvée
    tender = db.query(Tender).options(
        joinedload(Tender.documents), 
        joinedload(Tender.lots)
    ).filter(Tender.reference.ilike(f"%{ref}%")).first()
    
    if not tender:
        raise HTTPException(status_code=404, detail="Aucune offre trouvée avec cette référence")
    
    return tender