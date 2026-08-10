import logging, chromadb
from pathlib import Path
from chromadb.config import Settings
from backend.app.config import settings

logger = logging.getLogger("waraq.rag.vector_store")

class ChromaDBManager:
    def __init__(self):
        # Répertoire local unique SQLite/HNSW géré de manière optimisée en RAM
        chroma_path = settings.CHROMA_PERSIST_DIR
        chroma_path.mkdir(parents=True, exist_ok=True)

        self.client = chromadb.PersistentClient(
            path=str(chroma_path),
            settings=Settings(anonymized_telemetry=False)
        )

    def _sanitize_collection_name(self, reference: str) -> str:
        """
        Convertit la référence de l'appel d'offres en nom de collection valide pour ChromaDB
        Exemple: 'AO/2026/8942-B' -> 'tender_ao_2026_8942_b'
        """
        clean_ref = "".join(c if c.isalnum() else "_" for c in reference).lower()
        return f"tender_{clean_ref}"

    def get_or_create_collection(self, tender_reference: str):
        """Récupère ou crée une collection unique pour l'Appel d'Offres complet."""
        collection_name = self._sanitize_collection_name(tender_reference)
        return self.client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"}
        )

    def store_document_chunks(
        self, 
        tender_reference: str, 
        document_id: str,
        chunks: list[str], 
        embeddings: list[list[float]], 
        metadatas: list[dict]
    ):
        """
        Stocke ou met à jour les chunks d'un document spécifique au sein 
        de la collection de son Appel d'Offres (Tender).
        """
        if not chunks:
            logger.warning(f"Aucun chunk à stocker pour le document {document_id}.")
            return

        collection = self.get_or_create_collection(tender_reference)
        
        # ID unique de chaque chunk combinant document_id et index
        ids = [f"doc_{document_id}_chunk_{i}" for i in range(len(chunks))]

        collection.upsert(
            documents=chunks,
            embeddings=embeddings,
            metadatas=metadatas,
            ids=ids
        )
        logger.info(
            f"{len(chunks)} chunks stockés/mis à jour dans la collection '{collection.name}' "
            f"(Document ID: {document_id})"
        )

    def query_tender_context(
        self, 
        tender_reference: str, 
        query_embedding: list[float], 
        top_k: int = 6,
        document_id: str = None
    ) -> list[str]:
        """
        Recherche sémantique globale sur TOUT l'appel d'offres.
        Si document_id est précisé, restreint la recherche à ce document spécifique.
        """
        try:
            collection = self.get_or_create_collection(tender_reference)
            
            # Filtre optionnel pour cibler un document précis du dossier
            where_clause = {"document_id": str(document_id)} if document_id else None

            results = collection.query(
                query_embeddings=[query_embedding],
                n_results=top_k,
                where=where_clause
            )
            
            if results and "documents" in results and results["documents"]:
                return results["documents"][0]
            return []
            
        except Exception as e:
            logger.error(f"Erreur lors de la recherche dans '{tender_reference}': {str(e)}")
            return []

    def delete_document_chunks(self, tender_reference: str, document_id: str):
        """Supprime uniquement les chunks d'un document donné en cas de suppression/re-scannage."""
        try:
            collection = self.get_or_create_collection(tender_reference)
            collection.delete(where={"document_id": str(document_id)})
            logger.info(f"Chunks du document {document_id} supprimés de {tender_reference}.")
        except Exception as e:
            logger.warning(f"Impossible de supprimer le document {document_id}: {str(e)}")

chroma_manager = ChromaDBManager()