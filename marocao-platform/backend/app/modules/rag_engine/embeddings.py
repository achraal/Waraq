import logging
from sentence_transformers import SentenceTransformer

logger = logging.getLogger("waraq.rag.embeddings")

class EmbeddingService:
    def __init__(self):
        self.model_name = "BAAI/bge-m3"
        self._model = None

    @property
    def model(self):
        # Lazy loading pour ne pas encombrer la RAM au démarrage
        if self._model is None:
            logger.info(f"Chargement du modèle d'embeddings {self.model_name}...")
            self._model = SentenceTransformer(self.model_name)
        return self._model

    def generate_embeddings(self, texts: list[str]) -> list[list[float]]:
        embeddings = self.model.encode(texts, convert_to_numpy=True, normalize_embeddings=True)
        return embeddings.tolist()

embedding_service = EmbeddingService()