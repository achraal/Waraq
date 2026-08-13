import logging, chromadb
from pathlib import Path
from chromadb.config import Settings
from backend.app.config import settings
import numpy as np
from sklearn.decomposition import PCA

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
        return self.client.get_or_create_collection(name=collection_name, metadata={"hnsw:space": "cosine"})

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

            results = collection.query(query_embeddings=[query_embedding], n_results=top_k, where=where_clause)
            
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

    def visualiser_vecteurs(self, tender_reference: str, document_id: str = None, max_points: int = 500) -> dict:

        collection_name = self._sanitize_collection_name(tender_reference)

        try:
            collection = self.client.get_collection(name=collection_name)
        except Exception as exc:
            logger.error("[CHROMA][VISUALIZATION] Collection introuvable : %s", collection_name)

            raise ValueError(f"Collection ChromaDB introuvable : {collection_name}") from exc

        where = None

        if document_id:
            where = {"document_id": str(document_id)}

        data = collection.get(where=where, include=["embeddings", "documents", "metadatas"], limit=max_points)

        # IMPORTANT : ne pas utiliser `or []`
        embeddings = data.get("embeddings")
        documents = data.get("documents")
        metadatas = data.get("metadatas")
        ids = data.get("ids")

        if embeddings is None:
            embeddings = []
        if documents is None:
            documents = []
        if metadatas is None:
            metadatas = []
        if ids is None:
            ids = []
        if len(embeddings) == 0:
            return {
                "collection": collection_name,
                "tender_reference": tender_reference,
                "document_id": document_id,
                "count": 0,
                "points": []
            }

        matrix = np.asarray(embeddings, dtype=np.float32)
        n_samples, n_dimensions = matrix.shape
        if n_samples == 1:
            coordinates = np.array([[0.0, 0.0]])
            explained_variance = []
        else:
            n_components = min(2, n_samples, n_dimensions)
            pca = PCA(n_components=n_components)
            reduced = pca.fit_transform(matrix)
            if n_components == 1:
                coordinates = np.column_stack([reduced[:, 0], np.zeros(n_samples)])
            else:
                coordinates = reduced
            explained_variance = (pca.explained_variance_ratio_.tolist())
        points = []
        for i, coord in enumerate(coordinates):

            metadata = (
                metadatas[i]
                if i < len(metadatas)
                else {}
            )

            document = (
                documents[i]
                if i < len(documents)
                else ""
            )

            point_id = (
                ids[i]
                if i < len(ids)
                else None
            )

            points.append({
                "id": point_id,
                "x": float(coord[0]),
                "y": float(coord[1]),
                "document_id": metadata.get("document_id"),
                "file_name": metadata.get("file_name"),
                "doc_type": metadata.get("doc_type"),
                "chunk_index": metadata.get("chunk_index"),
                "text_preview": document[:300]
            })

        return {
            "collection": collection_name,
            "tender_reference": tender_reference,
            "document_id": document_id,
            "count": len(points),
            "dimensions_originales": int(matrix.shape[1]),
            "dimensions_visualisation": 2,
            "explained_variance_ratio": explained_variance,
            "points": points
        }

chroma_manager = ChromaDBManager()