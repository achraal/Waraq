import os, shutil, mimetypes
from datetime import timezone
from pathlib import Path
from pypdf import PdfReader, PdfWriter
from fastapi import APIRouter, Depends, BackgroundTasks, HTTPException, status, Query
from sqlalchemy.orm import Session
from pypdf.errors import PdfStreamError
from typing import Dict, Any, List, Optional
from collections import defaultdict
from uuid import UUID
from datetime import datetime, time
from sqlalchemy import func, case
from backend.app.database.connection import get_db
from backend.app.database.models import TenderDocument, ClassificationAuditLog
from backend.app.modules.ai_processor.classification_service import executer_classification_post_scraping
from backend.app.modules.ai_processor.schemas import DocumentValidationUpdate, TenderDocumentResponse, TenderDocumentUpdate, TenderDocumentListResponse, ValidateDocumentRequest, LatestClassifiedPaginatedResponse, ClassificationStatsResponse, ClassificationReasonGroup, DocumentStatItem
from backend.app.modules.ai_processor.learning_service import WaraqLearningEngine
from fastapi.responses import FileResponse

router = APIRouter(
    prefix="/classifier",
    tags=["Tenders Classification & Management"]
)

@router.post("/classify-documents", status_code=status.HTTP_202_ACCEPTED, response_model=Dict[str, Any])
async def piloter_classification_documents(
    background_tasks: BackgroundTasks, 
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Déclenche le traitement intelligent (IDP) en tâche de fond pour tous les documents 
    d'appels d'offres synchronisés en base mais non encore classifiés (is_classified = False).
    Analyse les caractéristiques de la file d'attente pour fournir une estimation précise.
    """
    try:
        # 1. Requête rapide pour analyser les fichiers en attente
        docs_a_traiter = db.query(TenderDocument).filter(TenderDocument.is_classified == False).all()
        total_docs = len(docs_a_traiter)
        
        if total_docs == 0:
            return {
                "status": "completed",
                "message": "Aucun document en attente de classification.",
                "metrics": {
                    "total_documents_queued": 0,
                    "total_tenders_affected": 0,
                    "heavy_files_count_ocr_llm": 0,
                    "light_files_count_fast": 0
                },
                "estimation": {
                    "duration_seconds": 0.0,
                    "duration_minutes": 0.0,
                    "formatted_estimation": "0 minutes."
                }
            }
            
        # Nombre de dossiers d'appels d'offres distincts impactés
        total_tenders = len(set(doc.tender_id for doc in docs_a_traiter))

        # 2. Algorithme d'estimation basé sur les extensions (OCR vs Primitives)
        # 2. Récupération de la moyenne historique réelle (si disponible)
        temps_moyen_historique = db.query(func.avg(TenderDocument.response_time)).filter(
            TenderDocument.response_time.isnot(None)
        ).scalar()
        
        # Fallback de base si aucun historique (ex: 5.0 secondes par défaut pour un PDF standard)
        base_time = temps_moyen_historique if temps_moyen_historique and temps_moyen_historique > 1.0 else 5.0

        duree_estimee_sec = 0.0
        compte_pdf_docx = 0
        compte_primitifs = 0

        # 3. Algorithme d'estimation adaptatif (basé sur la taille réelle du fichier)
        for doc in docs_a_traiter:
            if not doc.file_name:
                duree_estimee_sec += 0.1
                compte_primitifs += 1
                continue
                
            _, ext = os.path.splitext(doc.file_name.lower().strip())
            
            if ext in [".pdf", ".docx"]:
                # Vérification du poids réel du fichier sur le disque pour affiner l'estimation
                file_size_kb = 0
                chemin_cible = doc.classified_file_path or doc.file_path
                if chemin_cible and os.path.exists(chemin_cible):
                    try:
                        file_size_kb = os.path.getsize(chemin_cible) / 1024
                    except Exception:
                        pass
                
                if file_size_kb > 0:
                    # Pondération intelligente : un fichier léger (~100Ko) prend moins de temps qu'un gros CPS (>2Mo)
                    # Formule : base_time + facteur proportionnel au poids (plafonné entre 3s et 25s par document)
                    facteur_poids = max(3.0, min(file_size_kb / 150.0, 25.0))
                    duree_estimee_sec += facteur_poids
                else:
                    duree_estimee_sec += base_time
                
                compte_pdf_docx += 1
                
            elif ext in [".xlsx", ".xls"]:
                duree_estimee_sec += 0.05
                compte_primitifs += 1
            else:
                duree_estimee_sec += 0.1
                compte_primitifs += 1

        duree_estimee_min = round(duree_estimee_sec / 60, 2)

        # 3. Lancement asynchrone de la tâche de fond
        background_tasks.add_task(executer_classification_post_scraping)
        
        return {
            "status": "processing",
            "message": "Le pipeline de classification (OCR + LLM) a été initié en tâche de fond pour les documents non traités.",
            "metrics": {
                "total_documents_queued": total_docs,
                "total_tenders_affected": total_tenders,
                "heavy_files_count_ocr_llm": compte_pdf_docx,
                "light_files_count_fast": compte_primitifs
            },
            "estimation": {
                "duration_seconds": round(duree_estimee_sec, 2),
                "duration_minutes": duree_estimee_min,
                "formatted_estimation": f"Environ {duree_estimee_min} minutes requises pour traiter {total_docs} documents ({compte_pdf_docx} fichiers complexes à analyser)."
            }
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors du démarrage du service de classification : {str(e)}"
        )

@router.get("/status", response_model=Dict[str, Any])
def obtenir_statut_classification(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """
    Retourne la progression en temps réel avec UNE SEULE requête d'agrégation ultra-rapide
    pour ne pas verrouiller la base pendant le traitement.
    """
    try:
        # Agrégation en 1 seule requête au lieu de 3 requêtes .count() distinctes
        resultat = db.query(
            func.count(TenderDocument.id).label("total"),
            func.sum(case((TenderDocument.is_classified == True, 1), else_=0)).label("classifies")
        ).first()

        total_docs = resultat.total or 0
        docs_classifies = resultat.classifies or 0
        docs_en_attente = total_docs - docs_classifies

        progression_pourcentage = round((docs_classifies / total_docs * 100), 2) if total_docs > 0 else 100.0

        return {
            "total_documents": total_docs,
            "classified_documents": docs_classifies,
            "pending_documents": docs_en_attente,
            "progress_percentage": progression_pourcentage,
            "status": "idle" if docs_en_attente == 0 else "processing"
        }
    finally:
        # On ferme/libère la session de suite pour ne pas encombrer le pool
        db.close()

@router.get("/stats", response_model=Dict[str, Any])
def obtenir_statistiques_globales(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """
    Génère les métriques de classification.
    """
    try:
        # 1. Répartition par type
        repartition_types = (
            db.query(TenderDocument.file_type, func.count(TenderDocument.id))
            .filter(TenderDocument.is_classified == True)
            .group_by(TenderDocument.file_type)
            .all()
        )
        stats_types = {str(t): count for t, count in repartition_types if t}

        # 2. Temps moyen
        temps_moyen = db.query(func.avg(TenderDocument.response_time)).filter(TenderDocument.response_time.isnot(None)).scalar()

        return {
            "document_types_distribution": stats_types,
            "average_real_processing_time_seconds": round(temps_moyen, 2) if temps_moyen else 0.0,
            "generated_at": datetime.now(timezone.utc).isoformat()
        }
    finally:
        db.close()
        
@router.get(
    "/documents/latest-classified", 
    response_model=LatestClassifiedPaginatedResponse, 
    status_code=status.HTTP_200_OK
)
def get_latest_classified_documents(
    limit: Optional[int] = Query(default=None, ge=1, description="Nombre maximal de documents à retourner (Optionnel)"),
    db: Session = Depends(get_db)
):
    """
    Récupère les documents classifiés AUJOURD'HUI, triés par date décroissante, 
    ainsi que le nombre total de documents classifiés aujourd'hui.
    """
    # Définir l'intervalle de la journée courante (ex: 2026-07-23 00:00:00 -> 2026-07-23 23:59:59.999999)
    today_start = datetime.combine(datetime.utcnow().date(), time.min)
    today_end = datetime.combine(datetime.utcnow().date(), time.max)

    # Requête de base filtrée sur is_classified et la date d'aujourd'hui
    base_query = db.query(TenderDocument).filter(
        TenderDocument.is_classified == True,
        TenderDocument.classified_at >= today_start,
        TenderDocument.classified_at <= today_end
    )

    # 1. Calculer le total avant d'appliquer le limit
    total_count = base_query.count()

    # 2. Récupérer les documents triés par date décroissante
    query = base_query.order_by(TenderDocument.classified_at.desc())

    if limit is not None:
        query = query.limit(limit)

    documents = query.all()

    # 3. Retourner la réponse structurée
    return {
        "total_count": total_count,
        "documents": documents
    }

@router.post("/documents/{document_id}/validate", status_code=status.HTTP_200_OK)
def validate_or_correct_document(
    document_id: UUID,
    payload: ValidateDocumentRequest,
    db: Session = Depends(get_db)
):
    # 1. Récupérer le document cible
    doc = db.query(TenderDocument).filter(TenderDocument.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document non trouvé")

    # --------------------------------------------------------------------------
    # MODIF 1 : RETROUVER LE PÈRE ORIGINAL SI L'ID TRANSMIS EST UN ENFANT
    # --------------------------------------------------------------------------
    nom_fichier_source = os.path.basename(doc.file_path)

    doc_parent = db.query(TenderDocument).filter(
        TenderDocument.tender_id == doc.tender_id,
        TenderDocument.file_name == nom_fichier_source
    ).first()

    if doc_parent:
        doc = doc_parent

    # --------------------------------------------------------------------------
    # MODIF 2 : NETTOYAGE SYSTÉMATIQUE DES ENFANTS (Securisé avec endswith)
    # --------------------------------------------------------------------------
    # Recherche stricte par fin de chaîne
    anciens_splits = db.query(TenderDocument).filter(
        TenderDocument.tender_id == doc.tender_id,
        TenderDocument.id != doc.id,
        TenderDocument.file_name.endswith(doc.file_name)
    ).all()

    for old_child in anciens_splits:
        # Suppression physique sur disque
        chemin_enfant = old_child.classified_file_path or old_child.file_path
        
        if chemin_enfant and os.path.exists(chemin_enfant) and chemin_enfant != doc.file_path:
            try:
                os.remove(chemin_enfant)
            except Exception as e:
                print(f"Erreur suppression fichier enfant {chemin_enfant}: {e}")
        
        # Suppression BDD
        db.delete(old_child)
    
    db.flush()

    # 3. TRAITEMENT DE LA DÉCISION HUMAINE

    # --------------------------------------------------------------------------
    # CAS A : Annulation du découpage IA
    # --------------------------------------------------------------------------
    if payload.undo_split:
        doc.is_classified = True
        doc.is_validated = True
        doc.validation_status = "CORRECTED" if not payload.is_correct else "VALIDATED"
        doc.file_type = payload.corrected_type or doc.file_type or "DOCUMENT_UNIQUE"
        doc.classification_reason = "ANNULATION_DECOUPAGE_IA"
        doc.classification_description = "L'humain a annulé le découpage généré par l'IA. Le document est réintégré comme document unique."
        doc.classified_at = datetime.utcnow()

    ## --------------------------------------------------------------------------
    # CAS B : Découpage manuel (avec regroupement des types identiques)
    # --------------------------------------------------------------------------
    elif payload.is_split_required and payload.splits:
        if not os.path.exists(doc.file_path):
            raise HTTPException(status_code=400, detail="Fichier source original introuvable sur le disque.")

        #reader = PdfReader(doc.file_path)
        try:
            reader = PdfReader(doc.file_path)
        except (PdfStreamError, Exception) as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid or corrupted PDF file at {doc.file_path}: {str(e)}",
            )
        total_pages = len(reader.pages)
        dossier_parent = os.path.dirname(doc.classified_file_path or doc.file_path)

        # 1. Regrouper les intervalles de pages par file_type
        # Exemple : {"CPS": [range(0, 11), range(23, 24)], "BORDEREAU_PRIX": [range(11, 23)]}
        grouped_splits: Dict[str, List[int]] = {}

        for split_info in payload.splits:
            if split_info.start_page < 1 or split_info.end_page > total_pages or split_info.start_page > split_info.end_page:
                raise HTTPException(
                    status_code=400, 
                    detail=f"Intervalle invalide ({split_info.start_page}-{split_info.end_page}) pour un total de {total_pages} pages."
                )
            
            ftype = split_info.file_type.upper().strip()
            if ftype not in grouped_splits:
                grouped_splits[ftype] = []
            
            # On ajoute les index de pages (0-based)
            grouped_splits[ftype].extend(list(range(split_info.start_page - 1, split_info.end_page)))

        # 2. Générer UN SEUL fichier PDF par type de document
        idx = 1
        # FIX CHEMIN : Remonter d'un dossier pour cibler le sous-dossier du VRAI type (ex: BORDEREAU_PRIX)
        dossier_base_classified = os.path.dirname(os.path.dirname(doc.classified_file_path or doc.file_path))
        for ftype, page_indices in grouped_splits.items():
            writer = PdfWriter()
            
            # On conserve l'ordre naturel des pages et on évite les doublons si chevauchement
            unique_sorted_pages = sorted(list(set(page_indices)))
            
            for page_num in unique_sorted_pages:
                writer.add_page(reader.pages[page_num])

            nom_clean = ftype.lower().replace(" ", "_")
            nouveau_nom_fichier = f"{nom_clean.upper()}_{idx}_{doc.file_name}"
            # FIX CHEMIN : Créer dynamiquement le sous-dossier correspondant à ftype (ex: .../BORDEREAU_PRIX/)
            dossier_cible = os.path.join(dossier_base_classified, ftype)
            os.makedirs(dossier_cible, exist_ok=True)
            
            nouveau_chemin_fichier = os.path.join(dossier_cible, nouveau_nom_fichier)

            with open(nouveau_chemin_fichier, "wb") as f_out:
                writer.write(f_out)

            # Détail explicatif des pages assemblées pour la traçabilité
            pages_humaines = [p + 1 for p in unique_sorted_pages]

            nouveau_doc_child = TenderDocument(
                tender_id=doc.tender_id,
                file_name=nouveau_nom_fichier,
                file_type=ftype,
                file_path=doc.file_path,
                classified_file_path=nouveau_chemin_fichier,
                is_classified=True,
                is_validated=True,
                classification_reason="DECOUPAGE_MANUEL_VALIDE",
                classification_description=f"Découpé et assemblé manuellement (Pages {pages_humaines})",
                classified_at=datetime.utcnow()
            )
            db.add(nouveau_doc_child)
            db.flush()  # Génère l'ID (UUID) du nouveau_doc_child immédiatement
            # FIX AUDIT LOG ENFANT : Enregistrer la traçabilité de cet enfant
            audit_enfant = ClassificationAuditLog(
                document_id=nouveau_doc_child.id,
                predicted_type=ftype,
                classification_reason="Créé via découpage manuel humain",
                model_used="HUMAN_VALIDATION",
                validation_status="VALIDATED",
                is_correct=True,
                created_at=datetime.utcnow()
            )
            db.add(audit_enfant)
            idx += 1

        doc.is_validated = True
        doc.validation_status = "CORRECTED" if not payload.is_correct else "VALIDATED"
        doc.classification_reason = "DECOUPE_PAR_HUMAIN"
        doc.is_classified = True
        doc.classification_description = f"Document découpé et regroupé en {len(grouped_splits)} fichiers distincts."
        doc.classified_at = datetime.utcnow()

    # --------------------------------------------------------------------------
    # CAS C : Validation simple ou Correction simple
    # --------------------------------------------------------------------------
    else:
        doc.is_classified = True
        doc.is_validated = True  
        doc.validation_status = "CORRECTED" if not payload.is_correct else "VALIDATED"  # <--- AJOUTER ICI
        if not payload.is_correct and payload.corrected_type:
            doc.file_type = payload.corrected_type
            #doc.classification_reason = "CORRIGE_PAR_HUMAIN"
            doc.classification_description = f"Type de document corrigé manuellement en {payload.corrected_type}."
        else:
            #doc.classification_reason = "VALIDE_PAR_HUMAIN"
            doc.classification_description = "Classification validée conforme par l'humain."
        
        doc.classified_at = datetime.utcnow()

    # 4. MISE À JOUR DE L'AUDIT LOG
    audit_log = db.query(ClassificationAuditLog).filter(
        ClassificationAuditLog.document_id == doc.id
    ).order_by(ClassificationAuditLog.created_at.desc()).first()

    if audit_log:
        if payload.is_correct:
            audit_log.validation_status = "VALIDATED"
            audit_log.is_correct = True
            audit_log.corrected_type = None
        else:
            audit_log.validation_status = "CORRECTED"
            audit_log.is_correct = False
            
            if payload.undo_split:
                audit_log.corrected_type = f"ANNULATION_SPLIT ({payload.corrected_type or doc.file_type})"
            elif payload.is_split_required:
                audit_log.corrected_type = "DECOUPAGE_MANUEL"
            else:
                audit_log.corrected_type = payload.corrected_type
                
    # 4.bis MISE À JOUR DE L'ANALYSIS_METADATA (Champ JSON dans TenderDocument)
    if doc.analysis_metadata:
        # Copie du dictionnaire existant pour forcer SQLAlchemy à détecter la modification
        metadata_dict = dict(doc.analysis_metadata)
        metadata_dict["is_validated"] = True
        
        if payload.is_correct:
            metadata_dict["validation_status"] = "VALIDATED"
            metadata_dict["is_correct"] = True
            metadata_dict["corrected_type"] = None
        else:
            metadata_dict["validation_status"] = "CORRECTED"
            metadata_dict["is_correct"] = False
            
            if payload.undo_split:
                metadata_dict["corrected_type"] = f"ANNULATION_SPLIT ({payload.corrected_type or doc.file_type})"
            elif payload.is_split_required:
                metadata_dict["corrected_type"] = "DECOUPAGE_MANUEL"
            else:
                metadata_dict["corrected_type"] = payload.corrected_type
                
        # Réassignation de l'objet pour trigger l'UPDATE SQL
        doc.analysis_metadata = metadata_dict
        
        # NOTE : Les enfants créés (CAS B) n'ont pas de metadata IA, ce qui est normal 
        # puisqu'ils ont été créés manuellement. Si on annulait (CAS A), on met bien
        # à jour le parent ressuscité.

    # 5. COMMIT GLOBAL
    db.commit()

    return {
        "status": "success",
        "message": "Validation/Correction enregistrée avec succès",
        "document_id": str(doc.id)
    }




# @router.post("/documents/{document_id}/validate", status_code=status.HTTP_200_OK)
# def valider_ou_corriger_document(
    # document_id: UUID, 
    # payload: DocumentValidationUpdate, 
    # db: Session = Depends(get_db)
# ):
    # """
    # Permet à un utilisateur de valider ou corriger manuellement la classification.
    # Met à jour la colonne principale, les métriques de performance et déplace le fichier sur le disque si nécessaire.
    # """
    # doc = db.query(TenderDocument).filter(TenderDocument.id == document_id).first()
    # if not doc:
        # raise HTTPException(status_code=404, detail="Document introuvable.")

    # ancien_type = doc.file_type
    # nouveau_type = payload.correct_type.upper().strip().replace(":", " ").replace("/", " ").split()[0]
    
    # 1. Récupération ou initialisation des métriques JSON
    # metriques = dict(doc.analysis_metadata) if doc.analysis_metadata else {}

    # 2. Si l'humain a corrigé le type et que le type change effectivement
    # if not payload.is_correct and ancien_type != nouveau_type:
        # chemin_actuel = doc.classified_file_path
        
        # if chemin_actuel and os.path.exists(chemin_actuel):
            # try:
                # On calcule le nouveau dossier cible en remplaçant l'ancien type dans le chemin
                # Exemple : .../classified/dossier_abc/AVIS/doc.pdf -> .../classified/dossier_abc/CPS/doc.pdf
                # path_obj = Path(chemin_actuel)
                
                # Le parent direct est le dossier du type (ex: AVIS). Le parent du parent est le dossier de l'appel d'offres.
                # dossier_tender = path_obj.parent.parent
                # nouveau_dossier_type = dossier_tender / nouveau_type
                
                # Création du nouveau dossier s'il n'existe pas
                # os.makedirs(nouveau_dossier_type, exist_ok=True)
                
                # nouveau_chemin_fichier = os.path.join(nouveau_dossier_type, path_obj.name)
                
                # Déplacement physique du fichier
                # shutil.move(chemin_actuel, nouveau_chemin_fichier)
                
                # Mise à jour du chemin dans le document
                # doc.classified_file_path = nouveau_chemin_fichier
            # except Exception as e:
                # On log l'erreur mais on ne bloque pas la mise à jour BDD
                # print(f"[ERREUR DÉPLACEMENT] Impossible de déplacer physiquement le fichier : {e}")

    # 3. Mise à jour de la colonne principale de l'application
    # doc.file_type = nouveau_type

    # 4. Enregistrement de l'état de contrôle qualité dans le JSON
    # metriques["validation_status"] = "VALIDATED" if payload.is_correct else "CORRECTED"
    # metriques["is_correct"] = payload.is_correct
    # if not payload.is_correct:
        # metriques["corrected_type"] = nouveau_type

    # doc.analysis_metadata = metriques
    
    # audit_log = (
        # db.query(ClassificationAuditLog)
        # .filter(
            # ClassificationAuditLog.document_id == document_id,
            # ClassificationAuditLog.validation_status == "PENDING"
        # )
        # .order_by(ClassificationAuditLog.created_at.desc())
        # .first()
    # )

    # if audit_log:
        # audit_log.validation_status = metriques["validation_status"]
        # audit_log.is_correct = payload.is_correct
        # audit_log.corrected_type = nouveau_type if not payload.is_correct else None
    
    # db.commit()

    # return {
        # "message": f"Document ID {document_id} mis à jour avec succès.",
        # "final_type": doc.file_type,
        # "status": metriques["validation_status"],
        # "physical_path": doc.classified_file_path
    # }

@router.get("/documents", response_model=TenderDocumentListResponse)
def get_all_tender_documents(db: Session = Depends(get_db)):
    """Récupère la liste de tous les documents de soumission enregistrés ainsi que le compte total."""
    total = db.query(TenderDocument).count()
    documents = db.query(TenderDocument).all()

    return {"total": total, "items": documents}  

@router.get("/documents/{document_id}", response_model=TenderDocumentResponse)
def get_tender_document_by_id(document_id: UUID, db: Session = Depends(get_db)):
    """
    Récupère un document spécifique par son ID.
    """
    document = db.query(TenderDocument).filter(TenderDocument.id == document_id).first()
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Le document avec l'ID {document_id} n'existe pas."
        )
    return document

@router.patch("/documents/{document_id}", response_model=TenderDocumentResponse)
def update_tender_document(
    document_id: UUID, 
    document_update: TenderDocumentUpdate, 
    db: Session = Depends(get_db)
):
    """
    Modifie dynamiquement un ou plusieurs champs d'un document.
    Passe uniquement les champs à modifier dans le body JSON.
    """
    db_document = db.query(TenderDocument).filter(TenderDocument.id == document_id).first()
    if not db_document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Impossible de modifier : le document avec l'ID {document_id} n'existe pas."
        )

    # Convertit le body en dictionnaire en excluant les valeurs non fournies (None par défaut)
    update_data = document_update.model_dump(exclude_unset=True)
    
    if not update_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Aucun champ valide n'a été fourni pour la modification."
        )

    # Application dynamique des modifications sur l'objet SQLAlchemy
    for key, value in update_data.items():
        setattr(db_document, key, value)

    try:
        db.commit()
        db.refresh(db_document)
        return db_document
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la mise à jour de la base de données : {str(e)}"
        )
        
@router.get("/documents/{document_id}/view", response_class=FileResponse)
def inspecter_document(
    document_id: UUID,
    db: Session = Depends(get_db)
):
    """
    Renvoie le fichier physique correspondant au document pour affichage/inspection
    directe dans le navigateur (ex: visionneuse PDF/Image).
    """
    doc = db.query(TenderDocument).filter(TenderDocument.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document introuvable en base.")

    # 1. Priorité au fichier classé, sinon fallback sur le fichier d'origine
    chemin_fichier = doc.classified_file_path or doc.file_path

    if not chemin_fichier or not os.path.exists(chemin_fichier):
        raise HTTPException(
            status_code=404, 
            detail=f"Fichier introuvable sur le disque local : {chemin_fichier}"
        )

    # 2. Détection dynamique du type MIME (ex: application/pdf, image/jpeg, etc.)
    mime_type, _ = mimetypes.guess_type(chemin_fichier)
    if not mime_type:
        mime_type = "application/octet-stream"

    # 3. Headers pour forcer la prévisualisation ('inline') au lieu de forcer le téléchargement ('attachment')
    headers = {
        "Content-Disposition": f'inline; filename="{doc.file_name}"'
    }

    return FileResponse(
        path=chemin_fichier,
        media_type=mime_type,
        headers=headers
    )

@router.get("/learning/few-shot-prompt", tags=["Waraq Intelligence Engine"])
def recuperer_contexte_few_shot(db: Session = Depends(get_db)):
    """
    [Option A] Visualise le bloc de texte correctif dynamique qui sera 
    injecté dans le prompt de classification de ton moteur IA.
    """
    contexte_dynamique = WaraqLearningEngine.obtenir_exemples_few_shot(db)
    return {"prompt_injection": contexte_dynamique}


@router.post("/learning/export-dataset", tags=["Waraq Intelligence Engine"])
def exporter_dataset_pour_colab(db: Session = Depends(get_db)):
    """
    [Option B] Génère le fichier waraq_dataset.jsonl dans le dossier 'exports/' 
    pour pouvoir aller le fine-tuner sur Google Colab.
    """
    try:
        resultat = WaraqLearningEngine.exporter_dataset_jsonl(db)
        return {"status": "success", "detail": resultat}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/learning/train-local", tags=["Waraq Intelligence Engine"])
def lancer_entrainement_local():
    """
    [Option C] Tente de lancer le réentraînement lourd directement en local.
    Échouera proprement si le PC n'a pas de GPU.
    """
    try:
        logs = WaraqLearningEngine.executer_fine_tuning_local_mock()
        return logs
    except RuntimeError as e:
        raise HTTPException(
            status_code=status.HTTP_412_PRECONDITION_FAILED,
            detail=f"Échec matériel (Hardware Restriction) : {str(e)}"
        )
        
@router.get(
    "/documents/stats/classification-reasons",
    response_model=ClassificationStatsResponse,
    status_code=status.HTTP_200_OK
)
def get_classification_reason_stats(db: Session = Depends(get_db)):
    """
    Retourne les statistiques des documents regroupés par classification_reason :
    - Le nombre total de documents traités
    - Le décompte (count) pour chaque raison
    - La liste des documents (avec leurs infos) associés à chaque raison
    """
    # 1. Récupération de tous les documents ayant une raison de classification
    documents = (
        db.query(TenderDocument)
        .filter(TenderDocument.classification_reason.isnot(None))
        .order_by(TenderDocument.classified_at.desc())
        .all()
    )

    # 2. Regroupement par classification_reason
    grouped_data = defaultdict(list)
    for doc in documents:
        reason_key = doc.classification_reason or "NON_SPECIFIE"
        grouped_data[reason_key].append(doc)

    # 3. Construction de la réponse structurée
    by_reason_list = []
    for reason, docs in grouped_data.items():
        by_reason_list.append(
            ClassificationReasonGroup(
                reason=reason,
                count=len(docs),
                documents=[DocumentStatItem.model_validate(d) for d in docs]
            )
        )

    # Tri par nombre de documents décroissant
    by_reason_list.sort(key=lambda x: x.count, reverse=True)

    return ClassificationStatsResponse(
        total_documents=len(documents),
        by_reason=by_reason_list
    )