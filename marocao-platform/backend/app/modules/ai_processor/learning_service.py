# backend/app/modules/ai_processor/learning_service.py
import json
import os
from typing import List, Dict, Any
from sqlalchemy.orm import Session
from backend.app.database.models import TenderDocument

class WaraqLearningEngine:
    
    # =========================================================================
    # OPTION A : DYNAMIC FEW-SHOT (Recommandé pour ton PC actuel)
    # =========================================================================
    @staticmethod
    def obtenir_exemples_few_shot(db: Session, limite: int = 3) -> str:
        """
        Va chercher les documents qui ont été CORRIGÉS par l'humain en BDD
        et génère un bloc de texte d'exemples à injecter directement dans le prompt.
        """
        # On cherche les documents corrigés (historique des erreurs de l'IA)
        documents_corriges = (
            db.query(TenderDocument)
            .filter(TenderDocument.is_classified == True)
            .all()
        )
        
        # Filtrer en Python pour analyser le contenu du JSON metadata
        erreurs_historiques = []
        for doc in documents_corriges:
            meta = doc.analysis_metadata or {}
            if meta.get("validation_status") == "CORRECTED":
                erreurs_historiques.append(doc)
                if len(erreurs_historiques) >= limite:
                    break

        if not erreurs_historiques:
            return "Aucun exemple correctif historique disponible pour le moment."

        bloc_exemples = "Voici des exemples de corrections manuelles apportées par les experts (sers-t'en pour éviter les erreurs):\n"
        for i, doc in enumerate(erreurs_historiques, 1):
            # On prend un extrait significatif du texte extrait (OCR) pour le prompt
            extrait_texte = doc.extracted_text[:400] if doc.extracted_text else "Texte indisponible"
            meta = doc.analysis_metadata or {}
            
            bloc_exemples += f"\n--- EXEMPLE CORRECTIF {i} ---\n"
            bloc_exemples += f"Extrait du document : \"{extrait_texte}...\"\n"
            bloc_exemples += f"Erreur passée de l'IA : Le modèle avait classifié ce document à tort.\n"
            bloc_exemples += f"CORRECTION HUMAINE REQUISE -> Type exact : {doc.file_type}\n"
            
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