import json, os, logging
from typing import List, Dict, Any
from sqlalchemy.orm import Session
from backend.app.database.models import TenderDocument
from backend.app.modules.ai_processor.rules import nettoyer_nom_type


logger = logging.getLogger(__name__)

class WaraqLearningEngine:
    
    @staticmethod
    def creer_extrait_representatif(texte: str, max_chars: int = 8000):
        if not texte:
            return ""

        if len(texte) <= max_chars:
            return texte

        tiers = max_chars // 3
        debut = texte[:tiers]
        milieu_start = len(texte)//2 - tiers//2
        milieu = texte[milieu_start:milieu_start+tiers]
        fin = texte[-tiers:]

        return f"""
        [DEBUT DOCUMENT]
        {debut}
        [MILIEU DOCUMENT]
        {milieu}
        [FIN DOCUMENT]
        {fin}
        """
    
    # =========================================================================
    # OPTION A : DYNAMIC FEW-SHOT (Recommandé pour ton PC actuel)
    # =========================================================================
    @staticmethod
    def obtenir_exemples_few_shot(db: Session, limite: int = 5, type_document: str = None,) -> str:
        """
        Va chercher les documents qui ont été CORRIGÉS par l'humain en BDD
        et génère un bloc de texte d'exemples à injecter directement dans le prompt.
        """
        # On cherche les documents corrigés (historique des erreurs de l'IA)
        #documents_corriges = (
            #db.query(TenderDocument)
            #.filter(TenderDocument.is_classified == True)
            #.all()
        #)
        logger.info(
            "Nombre total de TenderDocument = %s",
            db.query(TenderDocument).count()
        )
        logger.info(
            "Documents classifiés = %s",
            db.query(TenderDocument)
              .filter(TenderDocument.is_classified == True)
              .count()
        )

        logger.info(
            "Documents avec extracted_text = %s",
            db.query(TenderDocument)
              .filter(TenderDocument.extracted_text.isnot(None))
              .count()
        )

        logger.info(
            "Documents classifiés + extracted_text = %s",
            db.query(TenderDocument)
              .filter(
                  TenderDocument.is_classified == True,
                  TenderDocument.extracted_text.isnot(None)
              )
              .count()
        )
        
        documents_corriges = (
            db.query(TenderDocument)
            .filter(
                TenderDocument.is_classified == True,
                TenderDocument.extracted_text.isnot(None)
            )
            .order_by(TenderDocument.classified_at.desc())
            .all()
        ) 
        logger.info("=" * 80)
        logger.info("[LEARNING] Chargement des corrections historiques")
        logger.info("[LEARNING] Limite Few-Shot = %s", limite)
        logger.info(
            "[LEARNING] %s documents classifiés récupérés depuis la base.",
            len(documents_corriges)
        )
        
        # Filtrer en Python pour analyser le contenu du JSON metadata
        erreurs_historiques = []
        for doc in documents_corriges:
            meta = doc.analysis_metadata or {}
            if meta.get("validation_status") == "CORRECTED":
                logger.info(
                    "[LEARNING] Correction trouvée | ID=%s | Type=%s",
                    doc.id,
                    doc.file_type
                )
                if type_document is not None:
                    if nettoyer_nom_type(doc.file_type) != nettoyer_nom_type(type_document):
                        continue
                        
                erreurs_historiques.append(doc)
                
                logger.info(
                    "[LEARNING] --> Ajoutée au Few-Shot (%s)",
                    len(erreurs_historiques)
                )
                #if len(erreurs_historiques) >= limite:
                if limite is not None and len(erreurs_historiques) >= limite:
                    logger.info(
                        "[LEARNING] Limite atteinte (%s exemples).",
                        limite
                    )
                    break
        if type_document is not None and len(erreurs_historiques) == 0:
            logger.info(
                "[LEARNING] Aucun exemple du type %s trouvé.",
                type_document
            )

        if not erreurs_historiques:
            return "Aucun exemple correctif historique disponible pour le moment."

        bloc_exemples = "Voici des exemples de corrections manuelles apportées par les experts (sers-t'en pour éviter les erreurs):\n"
        for i, doc in enumerate(erreurs_historiques, 1):
            # On prend un extrait significatif du texte extrait (OCR) pour le prompt
            #extrait_texte = doc.extracted_text[:400] if doc.extracted_text else "Texte indisponible"
            extrait_texte = WaraqLearningEngine.creer_extrait_representatif(
                doc.extracted_text,
                max_chars=6000
            )
            meta = doc.analysis_metadata or {}
            bloc_exemples += f"\n--- EXEMPLE CORRECTIF {i} ---\n"
            bloc_exemples += f"Extrait du document : \"{extrait_texte}...\"\n"
            bloc_exemples += f"Erreur passée de l'IA : Le modèle avait classifié ce document à tort.\n"
            bloc_exemples += f"CORRECTION HUMAINE REQUISE -> Type exact : {doc.file_type}\n"
            
        logger.info("[LEARNING] %s exemples injectés.", len(erreurs_historiques))
        logger.info("[LEARNING] Taille du contexte = %s caractères", len(bloc_exemples))
        logger.info("=" * 80)
        logger.info("[LEARNING] Résumé")
        logger.info("Documents analysés      : %s", len(documents_corriges))
        logger.info("Corrections trouvées    : %s", len(erreurs_historiques))
        logger.info("Exemples injectés       : %s", len(erreurs_historiques))
        logger.info("Longueur du prompt      : %s caractères", len(bloc_exemples))
        logger.info("=" * 80)
            
        return bloc_exemples

    # =========================================================================
    # OPTION B : FINE-TUNING DÉPORTÉ (Génération du dataset pour Colab)
    # =========================================================================
    @staticmethod
    def exporter_dataset_jsonl(db: Session, dossier_export: str = "exports") -> str:
        """
        Génère un fichier au format .jsonl compatible avec les formats d'entraînement
        standards (Hugging Face / ChatML) pour l'importer facilement sur Google Colab.
        """
        os.makedirs(dossier_export, exist_ok=True)
        chemin_fichier = os.path.join(dossier_export, "waraq_dataset.jsonl")
        
        # On extrait tous les documents validés ou corrigés par l'humain (données fiables)
        documents_valides = (
            db.query(TenderDocument)
            .filter(TenderDocument.is_classified == True)
            .all()
        )
        
        compteur = 0
        with open(chemin_fichier, "w", encoding="utf-8") as f:
            for doc in documents_valides:
                if not doc.extracted_text or not doc.file_type:
                    continue
                    
                # Format standard ChatML (System / User / Assistant) pour fine-tuner Qwen
                structure_chatml = {
                    "messages": [
                        {"role": "system", "content": "Tu es l'IA experte du projet Waraq. Ton rôle est de classifier les documents de marchés publics."},
                        {"role": "user", "content": f"Classifie ce document d'appel d'offres basé sur son texte : {doc.extracted_text[:1500]}"},
                        {"role": "assistant", "content": f"{doc.file_type}"}
                    ]
                }
                f.write(json.dumps(structure_chatml, ensure_ascii=False) + "\n")
                compteur += 1
                
        return f"Succès : {compteur} lignes exportées dans {chemin_fichier}. Prêt pour Google Colab !"

    # =========================================================================
    # OPTION C : FINE-TUNING LOCAL (En attente de GPU)
    # =========================================================================
    @staticmethod
    def executer_fine_tuning_local_mock() -> Dict[str, Any]:
        """
        Simule l'exécution de l'entraînement local. Ce code lève une exception 
        proactive si aucune carte graphique compatible CUDA n'est détectée.
        """
        # Simulation d'un check hardware préalable
        import torch # Prévu dans l'environnement global
        
        if not torch.cuda.is_available():
            raise RuntimeError(
                "Impossible d'exécuter l'Option C : Aucun GPU NVIDIA détecté via CUDA. "
                "Bascule sur l'Option A (Few-Shot) ou l'Option B (Google Colab)."
            )
            
        # Structure théorique de ton script d'entraînement local (ex: via TRL / Unsloth)
        training_logs = {
            "status": "initialized",
            "info": "GPU détecté avec succès. Prêt à instancier un SFTTrainer (Supervised Fine-Tuning).",
            "parameters_preview": {
                "base_model": "Qwen/Qwen2.5-7B-Instruct",
                "per_device_train_batch_size": 2,
                "gradient_accumulation_steps": 4,
                "learning_rate": 2e-4,
                "optimizer": "adamw_8bit" # Idéal pour économiser de la VRAM
            }
        }
        return training_logs