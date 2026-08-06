import time, logging, httpx
from sqlalchemy.orm import Session
from backend.app.database.models import TenderDocument, DocumentRAGAnalysis
from backend.app.modules.rag_engine.embeddings import embedding_service
from backend.app.modules.rag_engine.vector_store import chroma_manager
from backend.app.modules.rag_engine.schemas import TenderRAGAnalysisResult
from backend.app.config import settings

logger = logging.getLogger("waraq.rag.orchestrator")

class RAGPipelineService:

    def chunk_text(self, text: str, chunk_size: int = 800, overlap: int = 150) -> list[str]:
        """Découpe adaptative gérant le texte français et arabe."""
        words = text.split()
        chunks = []
        for i in range(0, len(words), chunk_size - overlap):
            chunk = " ".join(words[i:i + chunk_size])
            if chunk:
                chunks.append(chunk)
        return chunks

    async def execute_rag_pipeline(self, db: Session, document_id: str):
        start_time = time.time()
        doc = db.query(TenderDocument).filter(TenderDocument.id == document_id).first()
        if not doc or not doc.extracted_text:
            logger.warning(f"Document {document_id} introuvable ou texte extrait vide.")
            return

        # 1. Enregistrement / Mise à jour de l'état RAG
        rag_entry = db.query(DocumentRAGAnalysis).filter(DocumentRAGAnalysis.document_id == doc.id).first()
        if not rag_entry:
            rag_entry = DocumentRAGAnalysis(document_id=doc.id)
            db.add(rag_entry)
        
        rag_entry.status = "IN_PROGRESS"
        db.commit()

        try:
            # 2. Chunking & Embeddings
            chunks = self.chunk_text(doc.extracted_text)
            emb_start = time.time()
            embeddings = embedding_service.generate_embeddings(chunks)
            emb_duration = time.time() - emb_start

            # 3. Indexation dans ChromaDB
            collection_name = f"doc_{doc.id}".replace("-", "_")
            metadatas = [{"doc_type": doc.file_type, "chunk_index": i} for i in range(len(chunks))]
            chroma_manager.store_chunks(collection_name, chunks, embeddings, metadatas)

            # 4. Recherche Sémantique ciblée & Extraction LLM Granite 4.1:3B via Ollama
            llm_start = time.time()
            query_prompt = "Objet, dates importantes, pièces administratives et techniques, clauses, critères d'évaluation et pénalités."
            query_emb = embedding_service.generate_embeddings([query_prompt])[0]
            relevant_chunks = chroma_manager.query_similarity(collection_name, query_emb, top_k=6)
            context = "\n---\n".join(relevant_chunks)

            # 5. Appel au modèle Granite 4.1:3B
            extracted_json = await self._call_granite_model(context, doc.file_type)
            llm_duration = time.time() - llm_start

            # 6. Sauvegarde et Isolation des résultats
            rag_entry.status = "COMPLETED"
            rag_entry.rag_analysis = extracted_json
            rag_entry.chroma_collection_name = collection_name
            rag_entry.chunk_count = len(chunks)
            rag_entry.embedding_duration_sec = emb_duration
            rag_entry.llm_extraction_duration_sec = llm_duration
            rag_entry.total_rag_duration_sec = time.time() - start_time
            db.commit()

            logger.info(f"Pipeline RAG terminé avec succès pour le document {document_id}")

        except Exception as e:
            logger.error(f"Erreur durant l'exécution du RAG: {str(e)}", exc_info=True)
            rag_entry.status = "FAILED"
            rag_entry.error_message = str(e)
            db.commit()

    async def _call_granite_model(self, context: str, doc_type: str) -> dict:
        prompt = f"""Tu es un expert juriste et analyste en marchés publics marocains.
Analyse le contexte extrait du document de type '{doc_type}' ci-dessous et extrait les informations clés au format JSON STRICT.

Contexte:
{context}

Format JSON attendu :
{{
  "objet_appel_offres": "...",
  "maitre_douvrage": "...",
  "numero_reference": "...",
  "estimation_financiere": "...",
  "caution_provisoire": "...",
  "delai_execution": "...",
  "dates_importantes": {{
    "date_limite_depot": "...",
    "date_visite_lieux": "...",
    "date_ouverture_plis": "..."
  }},
  "pieces_a_fournir": {{
    "pieces_administratives": ["..."],
    "pieces_techniques": ["..."]
  }},
  "clauses_administratives_clefs": ["..."],
  "clauses_techniques_clefs": ["..."],
  "criteres_evaluation": ["..."],
  "penalites_retard": "...",
  "garanties_exigees": "..."
}}
"""
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                f"{settings.OLLAMA_BASE_URL}/api/generate",
                json={
                    "model": "granite4.1:3b",  # Assurez-vous d'avoir exécuté `ollama run granite4.1:3b`
                    "prompt": prompt,
                    "format": "json",
                    "stream": False
                }
            )
            if response.status_code == 200:
                import json
                return json.loads(response.json().get("response", "{}"))
            return {}

rag_pipeline_service = RAGPipelineService()