# from fastapi import APIRouter, Depends, BackgroundTasks, HTTPException, status
# from sqlalchemy.orm import Session
# from typing import Dict

# from backend.app.database.connection import get_db  # Votre générateur de session SQLAlchemy
# from backend.app.modules.ai_processor.classification_service import executer_classification_post_scraping

# router = APIRouter(
#     prefix="/classifier",
#     tags=["Tenders Classification & Management"]
# )

# @router.post("/classify-documents", status_code=status.HTTP_202_ACCEPTED)
# async def piloter_classification_documents(
#     background_tasks: BackgroundTasks, 
#     db: Session = Depends(get_db)
# ) -> Dict[str, str]:
#     """
#     Déclenche le traitement intelligent (IDP) en tâche de fond pour tous les documents 
#     d'appels d'offres synchronisés en base mais non encore classifiés (is_classified = False).
#     """
#     try:
#         # Lancement asynchrone pour libérer immédiatement le client HTTP (et le scraper)
#         background_tasks.add_task(executer_classification_post_scraping, db)
        
#         return {
#             "status": "processing",
#             "message": "Le pipeline de classification (OCR + LLM) a été initié en tâche de fond pour les documents non traités."
#         }
#     except Exception as e:
#         raise HTTPException(
#             status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
#             detail=f"Erreur lors du démarrage du service de classification : {str(e)}"
#         )


import os, shutil
from datetime import timezone
from pathlib import Path
from fastapi import APIRouter, Depends, BackgroundTasks, HTTPException, status
from sqlalchemy.orm import Session
from typing import Dict, Any, List
from uuid import UUID
from datetime import datetime
from sqlalchemy import func
from backend.app.database.connection import get_db
from backend.app.database.models import TenderDocument
from backend.app.modules.ai_processor.classification_service import executer_classification_post_scraping
from backend.app.modules.ai_processor.schemas import DocumentValidationUpdate, TenderDocumentResponse, TenderDocumentUpdate
from backend.app.modules.ai_processor.learning_service import WaraqLearningEngine

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
        duree_estimee_sec = 0.0
        compte_pdf_docx = 0
        compte_primitifs = 0

        for doc in docs_a_traiter:
            if not doc.file_name:
                duree_estimee_sec += 0.1
                compte_primitifs += 1
                continue
                
            _, ext = os.path.splitext(doc.file_name.lower().strip())
            
            # Cas 1 : Documents soumis à l'extraction de texte + classification IA
            if ext in [".pdf", ".docx"]:
                duree_estimee_sec += 3.5  # Constante moyenne par document (OCR PaddleOCR + Inférence Qwen)
                compte_pdf_docx += 1
            # Cas 2 : Règles primitives ultra-rapides (Fichiers Excel ou nom déjà explicite)
            elif ext in [".xlsx", ".xls"]:
                duree_estimee_sec += 0.05
                compte_primitifs += 1
            # Cas 3 : Autres fallbacks légers
            else:
                duree_estimee_sec += 0.1
                compte_primitifs += 1

        duree_estimee_min = round(duree_estimee_sec / 60, 2)

        # 3. Lancement asynchrone de la tâche de fond
        background_tasks.add_task(executer_classification_post_scraping, db)
        
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
    Retourne la progression en temps réel du pipeline de classification.
    """
    total_docs = db.query(TenderDocument).count()
    docs_classifies = db.query(TenderDocument).filter(TenderDocument.is_classified == True).count()
    docs_en_attente = db.query(TenderDocument).filter(TenderDocument.is_classified == False).count()
    
    progression_pourcentage = round((docs_classifies / total_docs * 100), 2) if total_docs > 0 else 100.0

    return {
        "total_documents": total_docs,
        "classified_documents": docs_classifies,
        "pending_documents": docs_en_attente,
        "progress_percentage": progression_pourcentage,
        "status": "idle" if docs_en_attente == 0 else "processing"
    }

@router.get("/stats", response_model=Dict[str, Any])
def obtenir_statistiques_globales(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """
    Génère des insights sur les types de documents détectés et les performances de l'IA.
    """
    # Répartition par types de documents (CPS, RC, etc.)
    repartition_types = (
        db.query(TenderDocument.file_type, func.count(TenderDocument.id))
        .filter(TenderDocument.is_classified == True)
        .group_by(TenderDocument.file_type)
        .all()
    )
    stats_types = {str(t): count for t, count in repartition_types if t}

    # Temps de traitement moyen constaté sur l'OCR + LLM
    temps_moyen = db.query(func.avg(TenderDocument.response_time)).filter(TenderDocument.response_time.isnot(None)).scalar()

    return {
        "document_types_distribution": stats_types,
        "average_real_processing_time_seconds": round(temps_moyen, 2) if temps_moyen else 0.0,
        "generated_at": datetime.now(timezone.utc).isoformat()
    }

@router.post("/documents/{document_id}/validate", status_code=status.HTTP_200_OK)
def valider_ou_corriger_document(
    document_id: UUID, 
    payload: DocumentValidationUpdate, 
    db: Session = Depends(get_db)
):
    """
    Permet à un utilisateur de valider ou corriger manuellement la classification.
    Met à jour la colonne principale, les métriques de performance et déplace le fichier sur le disque si nécessaire.
    """
    doc = db.query(TenderDocument).filter(TenderDocument.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document introuvable.")

    ancien_type = doc.file_type
    nouveau_type = payload.correct_type.upper().strip().replace(":", " ").replace("/", " ").split()[0]
    
    # 1. Récupération ou initialisation des métriques JSON
    metriques = dict(doc.analysis_metadata) if doc.analysis_metadata else {}

    # 2. Si l'humain a corrigé le type et que le type change effectivement
    if not payload.is_correct and ancien_type != nouveau_type:
        chemin_actuel = doc.classified_file_path
        
        if chemin_actuel and os.path.exists(chemin_actuel):
            try:
                # On calcule le nouveau dossier cible en remplaçant l'ancien type dans le chemin
                # Exemple : .../classified/dossier_abc/AVIS/doc.pdf -> .../classified/dossier_abc/CPS/doc.pdf
                path_obj = Path(chemin_actuel)
                
                # Le parent direct est le dossier du type (ex: AVIS). Le parent du parent est le dossier de l'appel d'offres.
                dossier_tender = path_obj.parent.parent
                nouveau_dossier_type = dossier_tender / nouveau_type
                
                # Création du nouveau dossier s'il n'existe pas
                os.makedirs(nouveau_dossier_type, exist_ok=True)
                
                nouveau_chemin_fichier = os.path.join(nouveau_dossier_type, path_obj.name)
                
                # Déplacement physique du fichier
                shutil.move(chemin_actuel, nouveau_chemin_fichier)
                
                # Mise à jour du chemin dans le document
                doc.classified_file_path = nouveau_chemin_fichier
            except Exception as e:
                # On log l'erreur mais on ne bloque pas la mise à jour BDD
                print(f"[ERREUR DÉPLACEMENT] Impossible de déplacer physiquement le fichier : {e}")

    # 3. Mise à jour de la colonne principale de l'application
    doc.file_type = nouveau_type

    # 4. Enregistrement de l'état de contrôle qualité dans le JSON
    metriques["validation_status"] = "VALIDATED" if payload.is_correct else "CORRECTED"
    metriques["is_correct"] = payload.is_correct
    if not payload.is_correct:
        metriques["corrected_type"] = nouveau_type

    doc.analysis_metadata = metriques
    db.commit()

    return {
        "message": f"Document ID {document_id} mis à jour avec succès.",
        "final_type": doc.file_type,
        "status": metriques["validation_status"],
        "physical_path": doc.classified_file_path
    }

@router.get("/documents", response_model=List[TenderDocumentResponse])
def get_all_tender_documents(db: Session = Depends(get_db)):
    """
    Récupère la liste de tous les documents de soumission (tender documents) enregistrés.
    """
    documents = db.query(TenderDocument).all()
    return documents

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