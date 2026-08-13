import logging
from typing import List, Dict, Any

logger = logging.getLogger("waraq.rag.chunker")

class DocumentChunker:
    """
    Découpe le texte enrichi produit par GLM-OCR en chunks
    adaptés au retrieval BGE-M3.
    Les chunks conservent :
    - leur identifiant ;
    - leur numéro de page si disponible ;
    - leur contenu ;
    - leur nombre de mots.
    """

    #def __init__(self, chunk_size: int = 800, overlap: int = 150):
    def __init__(self, chunk_size: int = 450, overlap: int = 100):
        self.chunk_size = chunk_size
        self.overlap = overlap
        if overlap >= chunk_size:
            raise ValueError(
                "overlap doit être inférieur à chunk_size"
            )

    def create_chunks(
        self,
        text: str,
        page_number: int = None
    ) -> List[Dict[str, Any]]:
        """
        Découpe un texte en chunks.
        Compatible FR / AR car le découpage se fait
        au niveau des espaces et non des caractères.
        """

        if not text or not text.strip():
            return []

        words = text.split()
        chunks = []
        step = self.chunk_size - self.overlap

        for start in range(0, len(words), step):
            end = start + self.chunk_size
            chunk_words = words[start:end]
            if not chunk_words:
                continue
            chunks.append({
                "chunk_id": len(chunks),
                "page_number": page_number,
                "content": " ".join(chunk_words),
                "word_count": len(chunk_words)
            })
            if end >= len(words):
                break

        logger.info(
            "Chunking terminé : %s chunks générés (%s mots)",
            len(chunks),
            len(words)
        )
        return chunks