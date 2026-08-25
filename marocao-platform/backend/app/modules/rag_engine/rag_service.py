from backend.app.modules.rag_engine import rag_document_extractor
import time, logging, httpx, json, os, fitz, re, requests, asyncio
from typing import Dict, Any, List
from pathlib import Path
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from backend.app.database.models import TenderDocument, RAGAnalysisResult, RAGStatus, RAGLog
from backend.app.modules.rag_engine.embeddings import embedding_service
from backend.app.modules.rag_engine.vector_store import chroma_manager
from backend.app.modules.rag_engine.chunker import DocumentChunker
from backend.app.modules.rag_engine.rag_document_extractor import traiter_extraction_rag
from backend.app.config import settings
from pydantic import ValidationError
from .schemas import TenderRAGAnalysisResult, TenderRAGSummary
from .prompts import GLM_OCR_PROMPT, build_granite_extraction_prompt, build_granite_summary_prompt

logger = logging.getLogger("waraq.rag.orchestrator")
BASE_STORAGE_DIR = Path(r"C:\Users\achra\Desktop\Intern\Project\marocao-platform\data_storage")

# --- DEBUT DU NOUVEAU CODE : Intercepteur de logs pour WebSocket ---
class AsyncWebSocketLogHandler(logging.Handler):
    def __init__(self):
        super().__init__()
        self.ws_manager = None  # Sera injecté depuis le routeur pour éviter les imports circulaires

    def emit(self, record):
        if not self.ws_manager:
            return
        try:
            # Formate le log (ex: "[17:41:37] [RAG][INDEXING] ...")
            msg = self.format(record)
            
            # Récupère l'event loop de FastAPI
            loop = asyncio.get_event_loop()
            
            # Lance l'envoi WebSocket en tâche de fond pour ne pas bloquer le RAG
            if loop.is_running():
                loop.create_task(self.ws_manager.broadcast(msg))
        except Exception:
            pass

# Instanciation et configuration du format pour l'Iframe
ws_handler = AsyncWebSocketLogHandler()
ws_handler.setFormatter(logging.Formatter('[%(asctime)s] %(message)s', datefmt='%H:%M:%S'))
# On ajoute notre "espion" au logger existant
logger.addHandler(ws_handler)

class RAGPipelineService:
    def __init__(self):
        self.chunker = DocumentChunker(chunk_size=800, overlap=150)

    @staticmethod
    def construire_query_metier(doc_type: str, detected_types: List[str] = None) -> str:
        """
        Construit une requête RAG globale. IMPORTANT :
        Un même fichier peut contenir plusieurs modèles : CPS + RC + BDP + ACTE_ENGAGEMENT.
        La recherche ne doit donc pas être limitée à doc_type.
        """

        detected_types = detected_types or []
        types = list(dict.fromkeys([doc_type] + detected_types))
        return """
        Rechercher dans le document toutes les informations métier
        explicitement présentes et utiles à l'analyse d'un marché public marocain.

        PRIORITÉS :

        1. objet du marché / appel d'offres
        2. intitulé de la consultation
        3. numéro ou référence
        4. maître d'ouvrage
        5. titulaire
        6. montant / estimation financière
        7. caution provisoire
        8. garanties
        9. délai d'exécution
        10. pénalités de retard
        11. date limite de dépôt
        12. date d'ouverture des plis
        13. visite des lieux
        14. pièces administratives
        15. pièces techniques
        16. pièces financières
        17. critères d'évaluation
        18. clauses administratives
        19. clauses techniques
        20. conditions de participation

        Le document peut contenir plusieurs types de pièces.

        Types détectés :
        """ + ", ".join(types) + """

        Retourner les passages les plus directement associés à ces informations.
        """

    async def recuperer_contexte_metier(self, tender_ref: str, document_id: str, detected_types: List[str], chunks: List[str],
    ) -> str:
        queries = [
            (
                "IDENTITE",
                """
                objet du marché, objet de l'appel d'offres,
                intitulé, référence, numéro, maître d'ouvrage,
                titulaire
                """
            ),
            (
                "DATES",
                """
                date limite de dépôt, date d'ouverture des plis,
                date de visite des lieux, délai d'exécution,
                ordre de service
                """
            ),
            (
                "FINANCES",
                """
                estimation financière, montant, caution provisoire,
                prix, montant du marché, garanties financières
                """
            ),
            (
                "PIECES",
                """
                pièces administratives, pièces techniques,
                pièces financières, documents à fournir,
                dossiers et enveloppes
                """
            ),
            (
                "EVALUATION",
                """
                critères d'évaluation, critères de jugement,
                conditions de participation
                """
            ),
            (
                "CLAUSES",
                """
                pénalités de retard, garanties, obligations,
                clauses administratives, clauses techniques,
                conditions d'exécution
                """
            ),
        ]

        # Pour un petit document :
        if len(chunks) <= 12:
            logger.info("[RAG][RETRIEVAL] Petit document : " "contexte complet utilisé (%d chunks).", len(chunks))
            return "\n\n--- CHUNK ---\n\n".join(chunks)
        retrieved = []
        for category, query in queries:
            query_full = f"""
            Document de marché public marocain.

            Types détectés :
            {", ".join(detected_types)}

            Rechercher explicitement :
            {query}

            Ne rechercher que des passages contenant
            réellement ces informations.
            """

            embedding = (await embedding_service.generate_embeddings([query_full]))[0]
            results = chroma_manager.query_tender_context(
                tender_reference=tender_ref,
                query_embedding=embedding,
                top_k=5,
                document_id=document_id
            )
            logger.info("[RAG][RETRIEVAL][%s] %d passages récupérés", category, len(results))
            retrieved.extend(results)

        # Déduplication
        unique_results = list(dict.fromkeys(retrieved))
        logger.info("[RAG][RETRIEVAL] %d passages uniques après fusion", len(unique_results))
        return "\n\n--- PASSAGE ---\n\n".join(unique_results)

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

        async with httpx.AsyncClient(timeout=None) as client:
            response = await client.post(
                f"{settings.OLLAMA_BASE_URL}/api/generate",
                json=payload
            )
            if response.status_code == 200:
                extracted = response.json().get("response", "")
                return extracted if extracted.strip() else raw_text
            
            logger.error(f"Échec GLM-OCR (Status {response.status_code}), fallback sur le texte brut.")
            return raw_text

    @staticmethod
    def nettoyer_resultat_granite(result: TenderRAGAnalysisResult,context: str) -> TenderRAGAnalysisResult:

        context_lower = context.lower()

        # DATE : rejeter les dates incomplètes
        dates = result.dates_importantes
        for field_name in ["date_limite_depot","date_visite_lieux","date_ouverture_plis"]:
            value = getattr(dates, field_name)
            if not value:
                continue
            value = str(value).strip()

            # Date manifestement incomplète
            if "..." in value or ".." in value or "xx" in value.lower() or "__" in value:
                logger.warning("[RAG][GUARD] %s=%r -> date incomplète -> null", field_name, value)
                setattr(dates, field_name, None)
                continue

            # La valeur doit exister dans le contexte
            if value.lower() not in context_lower:
                logger.warning("[RAG][GUARD] %s=%r absent du contexte -> null", field_name, value)
                setattr(dates, field_name, None)

        # REFERENCE
        if result.numero_reference:
            ref = str(result.numero_reference).strip()
            if "..." in ref or ".." in ref or len(ref) < 4 or ref.lower() not in context_lower:
                logger.warning("[RAG][GUARD] Référence suspecte=%r -> null", ref)
                result.numero_reference = None

        # DELAI EXECUTION
        if result.delai_execution:
            value = str(result.delai_execution).strip()
            value_lower = value.lower()
            termes_interdits = ["appel d'offres", "décret","article","arrêté","dématérialisation","procédure"]   
            if any(term in value_lower for term in termes_interdits):
                logger.warning("[RAG][GUARD] delai_execution suspect=%r -> null", value)
                result.delai_execution = None
        return result

    async def _call_granite_model(self, context: str, doc_type: str) -> TenderRAGAnalysisResult:
        """
        Appelle Granite avec le schéma métier unique TenderRAGAnalysisResult.
        La réponse est :
        1. produite par Granite ;
        2. contrainte par JSON Schema ;
        3. validée par Pydantic.
        """
        prompt = build_granite_extraction_prompt(enriched_text=context,doc_type=doc_type)
        schema = TenderRAGAnalysisResult.model_json_schema()
        payload = {
            "model": settings.MODEL_RAG_ANALYSIS,
            "prompt": prompt,
            "stream": False,
            "format": schema,
            "options": {"temperature": 0},
            "keep_alive": settings.OLLAMA_KEEP_ALIVE,
        }
        logger.info("[RAG][GRANITE] Appel Granite | model=%s | doc_type=%s",settings.MODEL_RAG_ANALYSIS,doc_type)

        try:
            async with httpx.AsyncClient(timeout=None) as client:
                response = await client.post(f"{settings.OLLAMA_BASE_URL}/api/generate",json=payload)
                response.raise_for_status()
            data = response.json()
            raw_content = data.get("response", "")
            logger.info("[RAG][GRANITE] Réponse brute : %d caractères",len(raw_content))
            logger.debug("[RAG][GRANITE] Raw response=%s",raw_content)

            if not raw_content or not raw_content.strip():
                raise ValueError("Granite a retourné une réponse vide.")
            
            result = TenderRAGAnalysisResult.model_validate_json(raw_content)
            logger.info("[RAG][GRANITE] JSON validé avec succès")
            logger.info("[RAG][GRANITE] objet_appel_offres=%s",result.objet_appel_offres)
            logger.info("[RAG][GRANITE] numero_reference=%s",result.numero_reference)
            logger.info("[RAG][GRANITE] estimation_financiere=%s",result.estimation_financiere)
            return result

        except ValidationError as exc:
            logger.error("[RAG][GRANITE] JSON invalide selon Pydantic")
            logger.error("[RAG][GRANITE] Validation errors=%s",exc.errors())
            raise

        except json.JSONDecodeError as exc:
            logger.error("[RAG][GRANITE] JSON invalide : %s",exc)
            raise

        except httpx.HTTPError as exc:
            logger.error("[RAG][GRANITE] Erreur communication Ollama : %s",exc)
            raise

    @staticmethod
    def enregistrer_log(db: Session, document: TenderDocument,
        level: str, stage: str, event: str, message: str, details: Dict[str, Any] = None, duration_sec: float = None):
        """
        Persiste un événement RAG en base.
        Cette méthode ne doit jamais interrompre le pipeline si l'écriture du log échoue.
        """
        try:
            log = RAGLog(
                document_id=document.id,
                tender_id=document.tender_id,
                level=level,
                stage=stage,
                event=event,
                message=message,
                details=details,
                duration_sec=duration_sec
            )
            db.add(log)
            db.commit()

        except Exception as exc:
            db.rollback()
            logger.error("[RAG][LOGGING] Impossible de persister le log : %s",exc,exc_info=True)
            
    async def _call_granite_summary(self,structured_data: dict,context: str,doc_type: str) -> TenderRAGSummary:

        prompt = build_granite_summary_prompt(structured_data=structured_data,context=context,doc_type=doc_type)
        schema = TenderRAGSummary.model_json_schema()

        payload = {
            "model": settings.MODEL_RAG_ANALYSIS,
            "prompt": prompt,
            "stream": False,
            "format": schema,
            "options": {"temperature": 0},
            "keep_alive": settings.OLLAMA_KEEP_ALIVE,
        }

        logger.info("[RAG][SUMMARY] Génération du résumé | model=%s",settings.MODEL_RAG_ANALYSIS)

        try:
            async with httpx.AsyncClient(timeout=None) as client:
                response = await client.post(f"{settings.OLLAMA_BASE_URL}/api/generate",json=payload)
                response.raise_for_status()
            data = response.json()
            raw_content = data.get("response", "")
            if not raw_content.strip():
                raise ValueError("Granite a retourné un résumé vide.")
            summary = TenderRAGSummary.model_validate_json(raw_content)
            logger.info("[RAG][SUMMARY] Résumé validé avec succès")
            return summary

        except ValidationError as exc:
            logger.error("[RAG][SUMMARY] JSON invalide selon Pydantic : %s",exc.errors())
            raise

        except httpx.HTTPError as exc:
            logger.error("[RAG][SUMMARY] Erreur Ollama : %s",exc)
            raise

    async def execute_rag_pipeline(self, db: Session, document_id: str):
        start_time = time.time()

        # 1. Récupération du document
        doc = (db.query(TenderDocument).filter(TenderDocument.id == document_id).first())
        
        if not doc:
            logger.warning("[RAG] Document %s introuvable.", document_id)
            return
            
        self.enregistrer_log(
            db=db,
            document=doc,
            level="INFO",
            stage="PIPELINE",
            event="RAG_STARTED",
            message="Pipeline RAG démarré.",
            details={"document_id": str(doc.id),"file_name": doc.file_name,"file_type": doc.file_type}
        )

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
            rag_extract_start = time.time()
            source_path = (doc.classified_file_path or doc.file_path)
            if not source_path or not os.path.exists(source_path):
                raise FileNotFoundError(f"[RAG] Source documentaire introuvable : {source_path}")

            date_ref = (doc.tender.extraction_date or datetime.now(timezone.utc))

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
            administrative_zones = rag_extraction.get("administrative_zones", [])
            detected_types = rag_extraction.get("detected_types") or []

            logger.info(
                "[RAG][TYPES] Document=%s | doc_type=%s | detected_types=%s",
                document_id,
                doc.file_type,
                detected_types
            )

            analysis_types = list(dict.fromkeys([doc.file_type] + detected_types))
            logger.info("[RAG][TYPES] Types utilisés pour l'analyse métier : %s",analysis_types)
            logger.info("[RAG][ZONES] Document=%s | zones=%d",document_id,len(administrative_zones))

            for zone in administrative_zones:
                logger.info(
                    "[RAG][ZONES] page=%s | type=%s | label=%s | bbox=%s",
                    zone.get("page_number"),
                    zone.get("type"),
                    zone.get("label"),
                    zone.get("bbox"),
                )
            doc.administrative_zones = administrative_zones
            db.commit()
            
            if not rag_text.strip():
                raise ValueError("[RAG] L'extracteur RAG n'a extrait aucun texte.")

            rag_extract_duration = time.time() - rag_extract_start

            self.enregistrer_log(
                db=db,
                document=doc,
                level="INFO",
                stage="EXTRACTION",
                event="EXTRACTION_COMPLETED",
                message="Extraction documentaire RAG terminée.",
                details={
                    "characters": len(rag_text),
                    "detected_types": detected_types,
                    "administrative_zones": len(administrative_zones)
                },
                duration_sec=rag_extract_duration
            )

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
            chunk_objects = self.chunker.create_chunks(text=enhanced_text)

            if not chunk_objects:
                raise ValueError("Aucun chunk n'a été généré à partir du texte enrichi.")

            chunks = [chunk["content"] for chunk in chunk_objects]
            logger.info("Document %s : %d chunks générés.", document_id, len(chunk_objects))

            self.enregistrer_log(
                db=db,
                document=doc,
                level="INFO",
                stage="CHUNKING",
                event="CHUNKING_COMPLETED",
                message="Découpage documentaire terminé.",
                details={
                    "chunk_count": len(chunk_objects),
                    "chunk_size": self.chunker.chunk_size,
                    "overlap": self.chunker.overlap
                }
            )

            # INDEXATION : Chunk -> Embedding -> ChromaDB
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
            
            self.enregistrer_log(
                db=db,
                document=doc,
                level="INFO",
                stage="INDEXING",
                event="CHROMA_INDEXING_COMPLETED",
                message="Embeddings générés et chunks indexés dans ChromaDB.",
                details={
                    "chunk_count": len(chunks),
                    "embedding_model": settings.MODEL_EMBEDDINGS,
                    "collection": chroma_manager._sanitize_collection_name(tender_ref)
                },
                duration_sec=indexing_duration
            )

            logger.info(
                "[RAG][INDEXING] Document %s indexé : %d chunks | durée=%.2fs",
                document_id,
                len(chunks),
                indexing_duration
            )

            # RETRIEVAL SEMANTIQUE
            retrieval_start = time.time()
            
            # RETRIEVAL RAG — CONTEXTE ADAPTATIF
            retrieval_start = time.time()

            if len(chunks) <= 12:
                # Petit document : Granite reçoit l'intégralité du document.
                context = "\n\n--- CHUNK DOCUMENTAIRE ---\n\n".join(chunks)
                relevant_chunks = chunks

                logger.info("[RAG][RETRIEVAL] Petit document : ""%d chunks -> contexte complet utilisé.",len(chunks))

            else:

                # Document volumineux :
                # récupération ciblée par catégories métier.
                context = await self.recuperer_contexte_metier(
                    tender_ref=tender_ref,
                    document_id=str(doc.id),
                    detected_types=detected_types,
                    chunks=chunks,
                )

                relevant_chunks = context.split("\n\n--- PASSAGE ---\n\n")
                logger.info("[RAG][RETRIEVAL] Grand document : %d chunks -> retrieval métier utilisé.",len(chunks))

            retrieval_duration = time.time() - retrieval_start
            self.enregistrer_log(
                db=db,
                document=doc,
                level="INFO",
                stage="RETRIEVAL",
                event="RETRIEVAL_COMPLETED",
                message="Recherche sémantique terminée.",
                details={
                    "source_chunks": len(chunks),
                    "retrieved_chunks": len(relevant_chunks),
                    "context_chars": len(context)
                },
                duration_sec=retrieval_duration
            )

            logger.info(
                "[RAG][RETRIEVAL] Tender=%s | chunks source=%d | "
                "passages contexte=%d | context_chars=%d | durée=%.2fs",
                tender_ref,
                len(chunks),
                len(relevant_chunks),
                len(context),
                retrieval_duration
            )
            logger.info("[RAG][RETRIEVAL] Context preview:\n%s",context[:5000])

            # 6. Analyse Métier via Granite 4.1:3B
            rag_entry.status = RAGStatus.ANALYZING
            db.commit()
            generation_start = time.time()
            extracted_json = await self._call_granite_model(context, doc.file_type)
            logger.info("[RAG][GRANITE][OUTPUT] %s",extracted_json.model_dump_json(indent=2))
            # POST-VALIDATION ANTI-HALLUCINATION
            extracted_json = self.nettoyer_resultat_granite(result=extracted_json,context=context)
            extracted_json_dict = extracted_json.model_dump()
            
            # 7. GÉNÉRATION DU VRAI RÉSUMÉ MÉTIER
            summary_start = time.time()
            summary_result = await self._call_granite_summary(
                structured_data=extracted_json_dict,
                context=context,
                doc_type=doc.file_type
            )

            summary_duration = time.time() - summary_start
            summary_dict = summary_result.model_dump()

            logger.info("[RAG][SUMMARY][OUTPUT] %s",summary_result.model_dump_json(indent=2))
            logger.info("[RAG][GRANITE][INPUT] doc_type=%s | context_chars=%d | context_words=%d",doc.file_type, len(context),len(context.split()))
            logger.info("[RAG][GRANITE][INPUT] context_preview=%s",context[:3000].replace("\n", " "))
            #llm_duration = time.time() - llm_start
            generation_duration = time.time() - generation_start
            
            self.enregistrer_log(
                db=db,
                document=doc,
                level="INFO",
                stage="GENERATION",
                event="GRANITE_COMPLETED",
                message="Analyse métier Granite terminée.",
                details={
                    "model": settings.MODEL_RAG_ANALYSIS,
                    "doc_type": doc.file_type,
                    "context_chars": len(context)
                },
                duration_sec=generation_duration
            )

            # 7. Sauvegarde finale et Métriques
            rag_entry.status = RAGStatus.COMPLETED
            rag_entry.rag_analysis = extracted_json_dict
            rag_entry.summary = summary_dict
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
            self.enregistrer_log(
                db=db,
                document=doc,
                level="INFO",
                stage="PIPELINE",
                event="RAG_COMPLETED",
                message="Pipeline RAG terminé avec succès.",
                details={
                    "chunk_count": len(chunks),
                    "document_id": str(doc.id),
                    "file_type": doc.file_type
                },
                duration_sec=rag_entry.total_rag_duration_sec
            )

            logger.info(f"Pipeline RAG (GLM-OCR -> Granite 4.1 -> BGE -> ChromaDB) terminé avec succès pour le document {document_id}")

        except Exception as e:
            logger.error(f"Erreur durant l'exécution du RAG: {str(e)}", exc_info=True)
            doc.rag_processed = False
            rag_entry.status = RAGStatus.FAILED
            rag_entry.error_message = str(e)
            db.commit()
            self.enregistrer_log(
                db=db,
                document=doc,
                level="ERROR",
                stage="PIPELINE",
                event="RAG_FAILED",
                message="Pipeline RAG échoué.",
                details={
                    "error": str(e),
                    "document_id": str(doc.id),
                    "file_type": doc.file_type
                },
                duration_sec=time.time() - start_time
            )

rag_pipeline_service = RAGPipelineService()