import logging, httpx 
from backend.app.config import settings

logger = logging.getLogger("waraq.rag.embeddings")

class OllamaEmbeddingService:
    async def generate_embeddings(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []

        payload = {
            "model": settings.MODEL_EMBEDDINGS,  
            "input": texts,
            "keep_alive": settings.OLLAMA_KEEP_ALIVE  # 0 pour libérer la RAM immédiatement
        }

        async with httpx.AsyncClient(timeout=None) as client:
            response = await client.post(
                f"{settings.OLLAMA_BASE_URL}/api/embed",
                json=payload
            )
            if response.status_code == 200:
                return response.json().get("embeddings", [])
            
            logger.error(f"Erreur lors de la génération d'embeddings (Status {response.status_code})")
            return []

embedding_service = OllamaEmbeddingService()