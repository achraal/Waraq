import logging, chromadb, asyncio
from pathlib import Path
from chromadb.config import Settings
from backend.app.config import settings
import numpy as np
from sklearn.decomposition import PCA
from concurrent.futures import ThreadPoolExecutor
from sklearn.manifold import TSNE
from sklearn.preprocessing import StandardScaler

logger = logging.getLogger("waraq.rag.vector_store")

# Pool de threads pour éviter de bloquer l'Event Loop lors de réductions lourdes
executor = ThreadPoolExecutor(max_workers=4)

def _compute_3d_reduction(matrix: np.ndarray, method: str = "tsne") -> np.ndarray:
    """Réduit la matrice d'embeddings en 3D avec normalisation [-5, 5]."""
    n_samples, n_dimensions = matrix.shape

    if n_samples == 1:
        return np.array([[0.0, 0.0, 0.0]])

    # Nettoyage et centrage
    matrix_scaled = StandardScaler().fit_transform(matrix)

    # Réduction 3D selon la méthode demandée
    if method == "tsne" and n_samples >= 4:
        perplexity = min(30, max(5, n_samples // 3))
        reducer = TSNE(
            n_components=3,
            perplexity=perplexity,
            init="pca",
            learning_rate="auto",
            random_state=42
        )
        reduced = reducer.fit_transform(matrix_scaled)
    else:
        # Repli sur PCA 3D si très peu de points ou méthode PCA demandée
        n_comp = min(3, n_samples, n_dimensions)
        pca = PCA(n_components=n_comp, random_state=42)
        reduced = pca.fit_transform(matrix_scaled)
        
        # Complète avec des 0 si moins de 3 dimensions obtenues
        if reduced.shape[1] < 3:
            padding = np.zeros((n_samples, 3 - reduced.shape[1]))
            reduced = np.hstack([reduced, padding])

    # Normalisation dans une boîte [-5, 5] pour Three.js
    max_val = np.max(np.abs(reduced))
    if max_val > 0:
        reduced = (reduced / max_val) * 5.0

    return reduced

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

    async def visualiser_vecteurs_async(
        self, 
        tender_reference: str, 
        document_id: str = None, 
        max_points: int = 500,
        method: str = "tsne"
    ) -> dict:
        """Génération asynchrone non-bloquante de la représentation 3D."""
        collection_name = self._sanitize_collection_name(tender_reference)

        try:
            collection = self.client.get_collection(name=collection_name)
        except Exception as exc:
            logger.error("[CHROMA][VISUALIZATION] Collection introuvable : %s", collection_name)
            raise ValueError(f"Collection ChromaDB introuvable : {collection_name}") from exc

        where = {"document_id": str(document_id)} if document_id else None
        data = collection.get(where=where, include=["embeddings", "documents", "metadatas"], limit=max_points)

        
        documents = data.get("documents") or []
        metadatas = data.get("metadatas") or []
        ids = data.get("ids") or []
        embeddings = data.get("embeddings")

        if embeddings is None or len(embeddings) == 0:
            return {
                "collection": collection_name,
                "tender_reference": tender_reference,
                "document_id": document_id,
                "count": 0,
                "dimensions_originales": 0,
                "dimensions_visualisation": 3,
                "method_used": method,
                "points": []
            }

        matrix = np.asarray(embeddings, dtype=np.float32)

        # Exécution du calcul mathématique dans un thread séparé pour libérer l'Event Loop FastAPI
        loop = asyncio.get_running_loop()
        coordinates = await loop.run_in_executor(
            executor, 
            _compute_3d_reduction, 
            matrix, 
            method
        )

        points = []
        for i, coord in enumerate(coordinates):
            meta = metadatas[i] if i < len(metadatas) else {}
            doc = documents[i] if i < len(documents) else ""
            point_id = ids[i] if i < len(ids) else None

            points.append({
                "id": point_id,
                "x": float(coord[0]),
                "y": float(coord[1]),
                "z": float(coord[2]),
                "coordinates": [float(coord[0]), float(coord[1]), float(coord[2])],
                "document_id": meta.get("document_id"),
                "file_name": meta.get("file_name"),
                "doc_type": meta.get("doc_type"),
                "chunk_index": meta.get("chunk_index"),
                "text_preview": doc[:300],
                "document": doc
            })

        return {
            "collection": collection_name,
            "tender_reference": tender_reference,
            "document_id": document_id,
            "count": len(points),
            "dimensions_originales": int(matrix.shape[1]),
            "dimensions_visualisation": 3,
            "method_used": method,
            "points": points
        }

chroma_manager = ChromaDBManager()