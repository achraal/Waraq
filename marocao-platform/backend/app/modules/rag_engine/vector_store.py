import chromadb
from chromadb.config import Settings
from backend.app.config import settings

class ChromaDBManager:
    def __init__(self):
        # Initialisation du client persistant local pour préserver la RAM
        self.client = chromadb.PersistentClient(
            path=str(settings.DATA_STORAGE_PATH / "chroma_db"),
            settings=Settings(anonymized_telemetry=False)
        )

    def get_or_create_collection(self, collection_name: str):
        return self.client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"}
        )

    def store_chunks(self, collection_name: str, chunks: list[str], embeddings: list[list[float]], metadatas: list[dict]):
        collection = self.get_or_create_collection(collection_name)
        ids = [f"chunk_{i}" for i in range(len(chunks))]
        collection.add(
            documents=chunks,
            embeddings=embeddings,
            metadatas=metadatas,
            ids=ids
        )

    def query_similarity(self, collection_name: str, query_embedding: list[float], top_k: int = 5):
        collection = self.get_or_create_collection(collection_name)
        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k
        )
        return results["documents"][0] if results["documents"] else []

chroma_manager = ChromaDBManager()