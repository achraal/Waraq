import time, logging, httpx, json, os, fitz, re
from typing import Dict, Any, List
from pathlib import Path
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from backend.app.database.models import TenderDocument, RAGAnalysisResult, RAGStatus
from backend.app.modules.rag_engine.embeddings import embedding_service
from backend.app.modules.rag_engine.vector_store import chroma_manager
from backend.app.modules.rag_engine.schemas import TenderRAGAnalysisResult
from backend.app.modules.rag_engine.chunker import DocumentChunker
from backend.app.modules.rag_engine.prompts import GLM_OCR_PROMPT
from backend.app.modules.rag_engine.prompts import GRANITE_EXTRACTION_PROMPT
from backend.app.modules.rag_engine.rag_document_extractor import traiter_extraction_rag
from backend.app.config import settings

logger = logging.getLogger("waraq.rag.orchestrator")
BASE_STORAGE_DIR = Path(
    r"C:\Users\achra\Desktop\Intern\Project\marocao-platform\data_storage"
)

class RAGPipelineService:
    def __init__(self):
        self.chunker = DocumentChunker(chunk_size=800, overlap=150)

    async def _call_glm_ocr(self, file_path: str, raw_text: str = "") -> str:
        """
        Étape 1 du Pipeline RAG : Compréhension visuelle, extraction intelligente, structure des tableaux et nettoyage FR & AR via GLM-OCR.
        """
        logger.info("Début de l'extraction enrichie via GLM-OCR...")
        prompt = f"""
        {GLM_OCR_PROMPT}
        
        IMPORTANT :
        - Tu dois conserver toutes les informations importantes du document.
        - Ne résume pas le document.
        - Ne supprime aucune date, référence, article, montant, clause,
          condition, obligation ou information administrative.
        - Ne remplace pas plusieurs sections par une simple synthèse.
        - Le résultat doit être une transcription/enrichissement fidèle.
        - Si une information est déjà correctement extraite dans le texte,
          conserve-la.
        - Ne produis aucune explication sur le document.
        - Retourne uniquement le contenu documentaire enrichi.

        Contenu initial :
        {raw_text}
        """
        
        payload = {
            "model": settings.MODEL_VISION_OCR,  
            "prompt": f"{prompt}\n\nContenu initial / brut:\n{raw_text}",
            "stream": False,
            "keep_alive": settings.OLLAMA_KEEP_ALIVE  # Libération RAM (16 GB optim)
        }

        # Si vous passez des images/pages au VLM via base64 :
        # if file_path and os.path.exists(file_path):
        #     payload["images"] = [self._encode_image(file_path)]

        async with httpx.AsyncClient(timeout=180.0) as client:
            response = await client.post(
                f"{settings.OLLAMA_BASE_URL}/api/generate",
                json=payload
            )
            if response.status_code == 200:
                extracted = response.json().get("response", "")
                return extracted if extracted.strip() else raw_text
            
            logger.error(f"Échec GLM-OCR (Status {response.status_code}), fallback sur le texte brut.")
            return raw_text

    async def _call_granite_model(self, context: str, doc_type: str) -> dict:
        """
        Étape 2 du Pipeline RAG : Analyse métier et extraction JSON structuré via Granite 4.1:3B.
        """
        #prompt = f"""
        #{GRANITE_EXTRACTION_PROMPT}

        #Contenu initial :
        #{context}
        #"""
        prompt = GRANITE_EXTRACTION_PROMPT.format(
            doc_type=doc_type or "UNKNOWN",
            context=context
        )
        logger.info(
            "[RAG][GRANITE] Prompt final : %d caractères",
            len(prompt)
        )
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                f"{settings.OLLAMA_BASE_URL}/api/generate",
                json={
                    "model": settings.MODEL_RAG_ANALYSIS,
                    "prompt": prompt,
                    "format": "json",
                    "stream": False,
                    "keep_alive": settings.OLLAMA_KEEP_ALIVE  # Libération RAM (16 GB optim)
                }
            )
            if response.status_code == 200:
                try:
                    return json.loads(response.json().get("response", "{}"))
                except json.JSONDecodeError:
                    logger.error("Erreur de décodage JSON depuis Granite 4.1.")
                    return {}
            return {}

    async def execute_rag_pipeline(self, db: Session, document_id: str):
        start_time = time.time()

        # 1. Récupération du document
        doc = (db.query(TenderDocument).filter(TenderDocument.id == document_id).first())

        if not doc:
            logger.warning("[RAG] Document %s introuvable.", document_id)
            return

        # 2. Récupération de l'analyse RAG existante
        rag_entry = (db.query(RAGAnalysisResult).filter(RAGAnalysisResult.document_id == doc.id).first())

        # 3. PROTECTION CONTRE LE DOUBLE TRAITEMENT
        if (doc.rag_processed is True and rag_entry is not None and rag_entry.status == RAGStatus.COMPLETED):
            logger.info("[RAG] Document %s déjà traité. " "Analyse existante conservée.", document_id)
            return

        # 4. Création de l'entrée RAG si nécessaire
        if rag_entry is None:
            rag_entry = RAGAnalysisResult(document_id=doc.id, status=RAGStatus.INDEXING)
            db.add(rag_entry)

        else:
            rag_entry.status = RAGStatus.INDEXING
            rag_entry.error_message = None

        db.commit()

        try:
            # 2. Traitement Vision Language Model & Nettoyage du texte
            #ocr_start = time.time()
            #enhanced_text = await self._call_glm_ocr(
                #file_path=getattr(doc, 'file_path', None),
                #raw_text=doc.extracted_text
            #)
            #ocr_duration = time.time() - ocr_start
            
            # Mise à jour du texte enrichi dans la base
            #rag_entry.extracted_text = enhanced_text
            #db.commit()
            
            rag_extract_start = time.time()

            source_path = (
                doc.classified_file_path
                or doc.file_path
            )

            if not source_path or not os.path.exists(source_path):
                raise FileNotFoundError(f"[RAG] Source documentaire introuvable : {source_path}")

            date_ref = (
                doc.tender.extraction_date
                or datetime.now(timezone.utc)
            )

            annee = date_ref.strftime("%Y")
            mois = date_ref.strftime("%m")
            jour = date_ref.strftime("%d")
            ref_propre = (doc.tender.reference.strip().replace("/", "-").replace("\\", "-"))
            ref_propre = re.sub(r'[?:"<>|*]', "_", ref_propre)
            nom_dossier_offre = ref_propre
            tender_relative_path = os.path.join(annee, mois, jour, nom_dossier_offre)
            extracted_root = str(BASE_STORAGE_DIR / "rag_extracted")

            # Extraction complète indépendante du Learning Service
            rag_extraction = traiter_extraction_rag(
                file_path=source_path,
                extracted_root=extracted_root,
                tender_relative_path=tender_relative_path,
            )

            # Ce texte provient exclusivement de l'extracteur RAG. On ne lit PAS doc.extracted_text ici.

            rag_text = rag_extraction.get("text", "")
            if not rag_text.strip():
                raise ValueError("[RAG] L'extracteur RAG n'a extrait aucun texte.")

            rag_extract_duration = time.time() - rag_extract_start

            logger.info("[RAG] Extraction indépendante terminée : %s caractères | types=%s | durée=%.2fs", len(rag_text), rag_extraction.get("detected_types"), rag_extract_duration)

            # 3. ENRICHISSEMENT VISUEL CIBLÉ PAR GLM-OCR
            glm_start = time.time()
            enhanced_text = rag_text
            try:
                # GLM-OCR reçoit le texte produit par LE RAG. Il ne dépend donc pas de doc.extracted_text.
                #enhanced_text = await self._call_glm_ocr(file_path=source_path, raw_text=rag_text)
                if not enhanced_text or not enhanced_text.strip():
                    logger.warning("[RAG][GLM-OCR] Aucun enrichissement retourné. " "Conservation du texte extrait par le RAG.")
                    enhanced_text = rag_text

            except Exception as e:
                logger.error("[RAG][GLM-OCR] Échec de l'enrichissement : %s", e, exc_info=True)
                # Le RAG doit continuer même si GLM-OCR échoue.
                enhanced_text = rag_text

            glm_duration = time.time() - glm_start
            logger.info("[RAG][GLM-OCR] Enrichissement terminé : %s caractères | durée=%.2fs", len(enhanced_text), glm_duration)

            # 4. PERSISTENCE DU TEXTE PROPRE AU RAG
            rag_entry.extracted_text = enhanced_text
            db.commit()
            logger.info("[RAG] Texte RAG sauvegardé : %s caractères", len(enhanced_text))

            # 3. Chunking
            chunk_objects = self.chunker.create_chunks(
                text=enhanced_text
            )

            if not chunk_objects:
                raise ValueError("Aucun chunk n'a été généré à partir du texte enrichi.")

            chunks = [
                chunk["content"]
                for chunk in chunk_objects
            ]

            logger.info( "Document %s : %d chunks générés.", document_id, len(chunk_objects))
            
            # ==========================================
            # INDEXATION : Chunk -> Embedding -> ChromaDB
            # ==========================================
            indexing_start = time.time()
            emb_start = time.time()
            embeddings = await embedding_service.generate_embeddings(chunks)
            emb_duration = time.time() - emb_start

            tender_ref = doc.tender.reference

            metadatas = [
                {
                    "tender_reference": tender_ref,
                    "document_id": str(doc.id),
                    "file_name": doc.file_name,
                    "doc_type": doc.file_type or "UNKNOWN",
                    "chunk_index": i
                }
                for i in range(len(chunks))
            ]

            chroma_manager.store_document_chunks(
                tender_reference=tender_ref,
                document_id=str(doc.id),
                chunks=chunks,
                embeddings=embeddings,
                metadatas=metadatas
            )

            indexing_duration = time.time() - indexing_start

            logger.info(
                "[RAG][INDEXING] Document %s indexé : %d chunks | durée=%.2fs",
                document_id,
                len(chunks),
                indexing_duration
            )

            #llm_start = time.time()

            #query_prompt = "Objet, dates importantes, pièces administratives et techniques, clauses, critères d'évaluation et pénalités."

            #query_emb = (await embedding_service.generate_embeddings([query_prompt]))[0]

            #relevant_chunks = chroma_manager.query_tender_context(
                #tender_reference=tender_ref,
                #query_embedding=query_emb,
                #top_k=6
            #)

            #context = "\n---\n".join(relevant_chunks)

            # ==========================================
            # RETRIEVAL SEMANTIQUE
            # ==========================================
            retrieval_start = time.time()

            query_prompt = f"""
            Analyse du document de type {doc.file_type}.

            Rechercher les informations pertinentes concernant :
            - objet
            - identification
            - parties
            - références
            - dates
            - articles
            - clauses
            - obligations
            - montants
            - conditions
            - informations spécifiques au type {doc.file_type}
            """

            query_emb = (
                await embedding_service.generate_embeddings([query_prompt])
            )[0]

            relevant_chunks = chroma_manager.query_tender_context(
                tender_reference=tender_ref,
                query_embedding=query_emb,
                top_k=6,
                document_id=str(doc.id)
            )

            context = "\n---\n".join(relevant_chunks)

            retrieval_duration = time.time() - retrieval_start

            logger.info(
                "[RAG][RETRIEVAL] Tender=%s | chunks récupérés=%d | durée=%.2fs",
                tender_ref,
                len(relevant_chunks),
                retrieval_duration
            )

            # 6. Analyse Métier via Granite 4.1:3B
            rag_entry.status = RAGStatus.ANALYZING
            db.commit()
            
            generation_start = time.time()
            extracted_json = await self._call_granite_model(context, doc.file_type)
            logger.info(
                "[RAG][GRANITE][INPUT] doc_type=%s | context_chars=%d | context_words=%d",
                doc.file_type,
                len(context),
                len(context.split())
            )

            logger.info(
                "[RAG][GRANITE][INPUT] context_preview=%s",
                context[:3000].replace("\n", " ")
            )
            #llm_duration = time.time() - llm_start
            generation_duration = time.time() - generation_start

            # 7. Sauvegarde finale et Métriques
            rag_entry.status = RAGStatus.COMPLETED
            rag_entry.rag_analysis = extracted_json
            doc.rag_processed = True
            rag_entry.chroma_collection_name = chroma_manager._sanitize_collection_name(tender_ref)
            rag_entry.indexing_duration_sec = indexing_duration
            rag_entry.retrieval_duration_sec = retrieval_duration
            rag_entry.generation_duration_sec = generation_duration
            rag_entry.chunk_count = len(chunks)
            rag_entry.embedding_duration_sec = emb_duration
            rag_entry.llm_extraction_duration_sec = generation_duration + rag_extract_duration
            rag_entry.total_rag_duration_sec = time.time() - start_time
            db.commit()

            logger.info(f"Pipeline RAG (GLM-OCR -> Granite 4.1 -> BGE -> ChromaDB) terminé avec succès pour le document {document_id}")

        except Exception as e:
            logger.error(f"Erreur durant l'exécution du RAG: {str(e)}", exc_info=True)
            doc.rag_processed = False
            rag_entry.status = RAGStatus.FAILED
            rag_entry.error_message = str(e)
            db.commit()

rag_pipeline_service = RAGPipelineService()