import fitz  # PyMuPDF
from typing import List, Dict, Any

class DocumentChunker:
    def __init__(self, chunk_size: int = 1000, overlap: int = 150):
        self.chunk_size = chunk_size
        self.overlap = overlap

    def extract_text_by_page(self, pdf_path: str) -> List[Dict[str, Any]]:
        """Extrait le texte page par page avec métadonnées."""
        doc = fitz.open(pdf_path)
        pages_content = []
        for page_num in range(len(doc)):
            page = doc.load_page(page_num)
            text = page.get_text("text")
            if text.strip():
                pages_content.append({
                    "page_number": page_num + 1,
                    "text": text.strip()
                })
        doc.close()
        return pages_content

    def create_chunks(self, pages_content: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Découpe le texte des pages en chunks avec recouvrement (overlap)."""
        chunks = []
        chunk_id = 0

        for item in pages_content:
            page_num = item["page_number"]
            text = item["text"]
            
            start = 0
            text_length = len(text)

            while start < text_length:
                end = start + self.chunk_size
                chunk_text = text[start:end]
                
                chunks.append({
                    "chunk_id": chunk_id,
                    "page_number": page_num,
                    "content": chunk_text
                })
                
                chunk_id += 1
                start += (self.chunk_size - self.overlap)

        return chunks