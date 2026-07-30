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
from sqlalchemy import func, case, or_
from backend.app.database.connection import get_db
from backend.app.database.models import TenderDocument, ClassificationAuditLog
from backend.app.modules.ai_processor.classification_service import executer_classification_post_scraping
from backend.app.modules.ai_processor.schemas import DocumentValidationUpdate, TenderDocumentResponse, TenderDocumentUpdate, TenderDocumentListResponse, ValidateDocumentRequest, LatestClassifiedPaginatedResponse, ClassificationStatsResponse, ClassificationReasonGroup, DocumentStatItem, UnclassifyDocumentsResponse, UnclassifyDocumentsRequest
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
        
@router.post("/classify-documents/tender/{tender_id}", status_code=status.HTTP_202_ACCEPTED, response_model=Dict[str, Any])
async def piloter_classification_par_tender(
    tender_id: UUID,
    background_tasks: BackgroundTasks, 
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Déclenche le traitement IDP uniquement pour les documents d'un appel d'offres ciblé.
    Re-traite ou traite tous les documents non encore classifiés (ou réinitialisés) de ce tender.
    """
    try:
        # 1. Filtrage strict sur le tender_id
        docs_a_traiter = (
            db.query(TenderDocument)
            .filter(
                TenderDocument.tender_id == tender_id,
                TenderDocument.is_classified == False
            )
            .all()
        )
        total_docs = len(docs_a_traiter)
        
        if total_docs == 0:
            return {
                "status": "completed",
                "message": f"Aucun document en attente de classification pour cet appel d'offres ({tender_id}).",
                "metrics": {
                    "total_documents_queued": 0,
                    "total_tenders_affected": 0,
                    "heavy_files_count_ocr_llm": 0,
                    "light_files_count_fast": 0
                },
                "estimation": {
                    "duration_seconds": 0.0,
                    "duration_minutes": 0.0,
                    "formatted_estimation": "0 minute."
                }
            }

        # 2. Algorithme d'estimation
        temps_moyen_historique = db.query(func.avg(TenderDocument.response_time)).filter(
            TenderDocument.response_time.isnot(None)
        ).scalar()
        
        base_time = temps_moyen_historique if temps_moyen_historique and temps_moyen_historique > 1.0 else 5.0

        duree_estimee_sec = 0.0
        compte_pdf_docx = 0
        compte_primitifs = 0

        for doc in docs_a_traiter:
            if not doc.file_name:
                duree_estimee_sec += 0.1
                compte_primitifs += 1
                continue
                
            _, ext = os.path.splitext(doc.file_name.lower().strip())
            
            if ext in [".pdf", ".docx"]:
                file_size_kb = 0
                chemin_cible = doc.classified_file_path or doc.file_path
                if chemin_cible and os.path.exists(chemin_cible):
                    try:
                        file_size_kb = os.path.getsize(chemin_cible) / 1024
                    except Exception:
                        pass
                
                if file_size_kb > 0:
                    facteur_poids = max(3.0, min(file_size_kb / 150.0, 25.0))
                    duree_estimee_sec += facteur_poids
                else:
                    duree_estimee_sec += base_time
                
                compte_pdf_docx += 1
            else:
                duree_estimee_sec += 0.1
                compte_primitifs += 1

        duree_estimee_min = round(duree_estimee_sec / 60, 2)

        # 3. Lancement de la tâche ciblée
        # Note : On transmet tender_id à la tâche de fond
        background_tasks.add_task(executer_classification_post_scraping, target_tender_id=tender_id)
        
        return {
            "status": "processing",
            "message": f"Classification démarrée pour l'appel d'offres {tender_id}.",
            "metrics": {
                "total_documents_queued": total_docs,
                "total_tenders_affected": 1,
                "heavy_files_count_ocr_llm": compte_pdf_docx,
                "light_files_count_fast": compte_primitifs
            },
            "estimation": {
                "duration_seconds": round(duree_estimee_sec, 2),
                "duration_minutes": duree_estimee_min,
                "formatted_estimation": f"Environ {duree_estimee_min} minutes requises pour ce dossier ({compte_pdf_docx} fichiers à analyser)."
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
    # RÈGLE 1 : SUPPRESSION UNIQUEMENT SI UNDO_SPLIT OU RE-DÉCOUPAGE MANUEL
    # --------------------------------------------------------------------------
    if payload.undo_split or (payload.is_split_required and payload.splits):
        # Retrouver le père si l'ID transmis est un enfant
        nom_fichier_source = os.path.basename(doc.file_path)
        doc_parent = db.query(TenderDocument).filter(
            TenderDocument.tender_id == doc.tender_id,
            TenderDocument.file_name == nom_fichier_source
        ).first()

        if doc_parent:
            doc = doc_parent  # On réassigne doc au père pour la suite

        # Nettoyage strict des enfants existants
        anciens_splits = db.query(TenderDocument).filter(
            TenderDocument.tender_id == doc.tender_id,
            TenderDocument.id != doc.id,
            TenderDocument.file_name.endswith(doc.file_name)
        ).all()

        for old_child in anciens_splits:
            chemin_enfant = old_child.classified_file_path or old_child.file_path
            if chemin_enfant and os.path.exists(chemin_enfant) and chemin_enfant != doc.file_path:
                try:
                    os.remove(chemin_enfant)
                except Exception as e:
                    print(f"Erreur suppression fichier enfant {chemin_enfant}: {e}")
            
            db.delete(old_child)
        
        db.flush()

    # --------------------------------------------------------------------------
    # 2. TRAITEMENT DE LA DÉCISION HUMAINE
    # --------------------------------------------------------------------------

    # CAS A : Annulation du découpage IA (Le père est réintégré)
    if payload.undo_split:
        doc.is_classified = True
        doc.is_validated = True
        doc.validation_status = "CORRECTED" if not payload.is_correct else "VALIDATED"
        doc.file_type = payload.corrected_type or doc.file_type or "DOCUMENT_UNIQUE"
        doc.classification_reason = "ANNULATION_DECOUPAGE_IA"
        doc.classification_description = "L'humain a annulé le découpage généré par l'IA. Le document est réintégré comme document unique."
        doc.classified_at = datetime.utcnow()

    # CAS B : Découpage manuel (Génération de nouveaux enfants avec support DOCX)
    elif payload.is_split_required and payload.splits:
        if not os.path.exists(doc.file_path):
            raise HTTPException(status_code=400, detail="Fichier source original introuvable sur le disque.")

        ext_originale = os.path.splitext(doc.file_path)[1].lower()
        pdf_path_source = doc.file_path
        est_word_temp = False

        # Conversion temporaire si Word (.docx / .doc)
        if ext_originale in [".docx", ".doc"]:
            pdf_path_source = convertir_doc_en_pdf(doc.file_path)
            if not pdf_path_source or not os.path.exists(pdf_path_source):
                raise HTTPException(
                    status_code=500,
                    detail="Impossible de convertir le fichier Word source en PDF pour effectuer le découpage."
                )
            est_word_temp = True

        try:
            reader = PdfReader(pdf_path_source)
            total_pages = len(reader.pages)

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
                
                grouped_splits[ftype].extend(list(range(split_info.start_page - 1, split_info.end_page)))

            idx = 1
            dossier_base_classified = os.path.dirname(os.path.dirname(doc.classified_file_path or doc.file_path))
            for ftype, page_indices in grouped_splits.items():
                writer = PdfWriter()
                unique_sorted_pages = sorted(list(set(page_indices)))
                
                for page_num in unique_sorted_pages:
                    writer.add_page(reader.pages[page_num])

                nom_clean = ftype.lower().replace(" ", "_")
                nom_base_sans_ext = os.path.splitext(doc.file_name)[0]
                nouveau_nom_fichier = f"{nom_clean.upper()}_{idx}_{nom_base_sans_ext}.pdf"
                
                dossier_cible = os.path.join(dossier_base_classified, ftype)
                os.makedirs(dossier_cible, exist_ok=True)
                
                nouveau_chemin_fichier = os.path.join(dossier_cible, nouveau_nom_fichier)

                with open(nouveau_chemin_fichier, "wb") as f_out:
                    writer.write(f_out)

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
                db.flush()

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

        except (PdfStreamError, Exception) as e:
            if not isinstance(e, HTTPException):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Fichier PDF invalide ou corrompu à {pdf_path_source}: {str(e)}",
                )
            raise e

        finally:
            # Nettoyage systématique du PDF temporaire si conversion depuis Word
            if est_word_temp and os.path.exists(pdf_path_source):
                try:
                    os.remove(pdf_path_source)
                except Exception:
                    pass

        doc.is_validated = True
        doc.validation_status = "CORRECTED" if not payload.is_correct else "VALIDATED"
        doc.classification_reason = "DECOUPE_PAR_HUMAIN"
        doc.is_classified = True
        doc.classification_description = f"Document découpé et regroupé en {len(grouped_splits)} fichiers distincts."
        doc.classified_at = datetime.utcnow()

    # CAS C : Validation simple ou Correction de type (Conserve les enfants, déplace le fichier physique si besoin)
    else:
        doc.is_classified = True
        doc.is_validated = True  
        doc.validation_status = "CORRECTED" if not payload.is_correct else "VALIDATED"
        
        if not payload.is_correct and payload.corrected_type:
            nouveau_type = payload.corrected_type.upper().strip()
            
            # Déplacement physique du fichier si le type a changé et qu'il existe dans classified
            if nouveau_type != doc.file_type and doc.classified_file_path and os.path.exists(doc.classified_file_path):
                dossier_base = os.path.dirname(os.path.dirname(doc.classified_file_path))
                nouveau_dossier_cible = os.path.join(dossier_base, nouveau_type)
                os.makedirs(nouveau_dossier_cible, exist_ok=True)
                
                nouveau_chemin_fichier = os.path.join(nouveau_dossier_cible, os.path.basename(doc.classified_file_path))
                
                try:
                    os.rename(doc.classified_file_path, nouveau_chemin_fichier)
                    doc.classified_file_path = nouveau_chemin_fichier
                except Exception as e:
                    print(f"Erreur déplacement fichier {doc.classified_file_path}: {e}")

            doc.file_type = nouveau_type
            doc.classification_description = f"Type de document corrigé manuellement en {nouveau_type}."
        else:
            doc.classification_description = "Classification validée conforme par l'humain."
        
        doc.classified_at = datetime.utcnow()

    # --------------------------------------------------------------------------
    # 3. MISE À JOUR DE L'AUDIT LOG ET METADATA
    # --------------------------------------------------------------------------
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

    if doc.analysis_metadata:
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
                
        doc.analysis_metadata = metadata_dict

    # 4. COMMIT GLOBAL
    db.commit()

    return {
        "status": "success",
        "message": "Validation/Correction enregistrée avec succès",
        "document_id": str(doc.id)
    }

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
    
@router.post(
    "/unclassify",
    response_model=UnclassifyDocumentsResponse,
    status_code=status.HTTP_200_OK
)
def unclassify_documents_by_ids(
    payload: UnclassifyDocumentsRequest,
    db: Session = Depends(get_db)
):
    """
    POST : Réinitialise le statut de classification pour une liste de documents.
    Passe `is_classified` à False et remet à None le type et les raisons associées.
    """
    if not payload.document_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La liste des ID de documents ne peut pas être vide."
        )

    # 1. Récupération des documents existants
    documents = (
        db.query(TenderDocument)
        .filter(TenderDocument.id.in_(payload.document_ids))
        .all()
    )

    if not documents:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Aucun document trouvé pour les ID fournis."
        )

    # 2. Mise à jour des statuts
    updated_ids = []
    for doc in documents:
        doc.is_classified = False
        doc.classification_reason = None
        doc.validation_status = "PENDING"
        # Optionnel selon ta logique métier :
        # doc.file_type = None  
        updated_ids.append(doc.id)

    # 3. Sauvegarde en BDD
    db.commit()

    return {
        "message": f"{len(updated_ids)} document(s) réinitialisé(s) avec succès.",
        "updated_count": len(updated_ids),
        "updated_document_ids": updated_ids
    }
    
@router.get("/metrics/stats")
def get_ai_processor_stats(
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Retourne les statistiques et métriques globales sur la classification des documents
    directement calculées depuis la table `tender_documents`.
    """
    try:
        # 1. Totaux et volumes globaux
        total_documents = db.query(func.count(TenderDocument.id)).scalar() or 0
        total_classified = db.query(func.count(TenderDocument.id)).filter(TenderDocument.is_classified == True).scalar() or 0
        total_unclassified = total_documents - total_classified

        # 2. Métriques de performance
        avg_response_time = db.query(
            func.avg(TenderDocument.response_time)
        ).filter(
            TenderDocument.is_classified == True,
            TenderDocument.response_time.isnot(None)
        ).scalar() or 0.0

        # 3. Métriques de validation humaine
        validation_stats = db.query(
            func.count(case((TenderDocument.validation_status == "VALIDATED", 1))).label("validated_count"),
            func.count(case((TenderDocument.validation_status == "PENDING", 1))).label("pending_count"),
            func.count(case((TenderDocument.validation_status == "CORRECTED", 1))).label("corrected_count")
        ).filter(TenderDocument.is_classified == True).first()

        validated_count = validation_stats.validated_count if validation_stats else 0
        pending_count = validation_stats.pending_count if validation_stats else 0
        corrected_count = validation_stats.corrected_count if validation_stats else 0

        # 4. Répartition par Type
        by_file_type_query = db.query(
            TenderDocument.file_type,
            func.count(TenderDocument.id).label("count")
        ).group_by(TenderDocument.file_type).all()

        by_file_type = [
            {"file_type": f_type, "count": count} 
            for f_type, count in by_file_type_query
        ]

        # 5. Répartition par Raison
        by_reason_query = db.query(
            TenderDocument.classification_reason,
            func.count(TenderDocument.id).label("count")
        ).filter(
            TenderDocument.is_classified == True
        ).group_by(
            TenderDocument.classification_reason
        ).all()

        by_classification_reason = [
            {"reason": reason or "NON_SPÉCIFIÉ", "count": count}
            for reason, count in by_reason_query
        ]

        # 6. CALCULS DES POURCENTAGES (Couverture & Précision IA)
        
        # A. Taux d'avancement / Couverture (documents classifiés / total)
        coverage_rate = round((total_classified / total_documents * 100), 2) if total_documents > 0 else 0.0

        # B. Total des documents révisés par un humain (Validés + Corrigés)
        total_reviewed = validated_count + corrected_count

        # C. Taux de Précision IA / Accuracy (Sur les docs révisés, combien étaient corrects sans retouche)
        accuracy_rate = round((validated_count / total_reviewed * 100), 2) if total_reviewed > 0 else 0.0

        # D. Taux d'Erreur (Combien ont dû être corrigés par un humain)
        error_rate = round((corrected_count / total_reviewed * 100), 2) if total_reviewed > 0 else 0.0

        return {
            "overview": {
                "total_documents": total_documents,
                "classified_documents": total_classified,
                "unclassified_documents": total_unclassified,
                "classification_coverage_percentage": coverage_rate,
                "avg_response_time_seconds": round(avg_response_time, 2)
            },
            "accuracy_metrics": {
                "total_reviewed_by_human": total_reviewed,
                "accuracy_rate_percentage": accuracy_rate,  # Précision réelle du LLM
                "error_rate_percentage": error_rate        # Taux de correction utilisateur
            },
            "human_validation": {
                "total_validated": validated_count,
                "pending_validation": pending_count,
                "corrected_by_user": corrected_count
            },
            "distribution": {
                "by_file_type": by_file_type,
                "by_classification_reason": by_classification_reason
            }
        }

    except Exception as e:
        raise HTTPException(
            status_code=500, 
            detail=f"Erreur lors du calcul des métriques de classification: {str(e)}"
        )