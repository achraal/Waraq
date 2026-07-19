import docx
from pypdf import PdfReader
from paddleocr import PaddleOCR

# Clean initialization of French and Arabic OCR engines (without 'det_lang')
ocr_fr = PaddleOCR(use_angle_cls=True, lang='fr')
ocr_ar = PaddleOCR(use_angle_cls=True, lang='ar')


def extraire_texte_premiere_page(file_path: str, ext: str) -> str:
    """Extrait le texte de la première page ou du début d'un document."""
    try:
        if ext == ".docx":
            doc = docx.Document(file_path)
            return "\n".join([p.text for p in doc.paragraphs[:30]])

        elif ext == ".pdf":
            reader = PdfReader(file_path)
            if not reader.pages:
                return ""
            
            texte = reader.pages[0].extract_text() or ""
            
            # Si le PDF est un scan (pas de texte natif ou peu de texte), fallback sur PaddleOCR
            if len(texte.strip()) < 100:
                lines = []
                
                # Essayez d'abord l'OCR français
                resultat = ocr_fr.ocr(file_path, cls=True)
                if resultat and resultat[0]:
                    lines = [line[1][0] for line in resultat[0][:40]]
                
                # Si le résultat en français est trop faible, essayez l'OCR arabe
                # (Utile pour les documents administratifs marocains majoritairement en arabe)
                if len(lines) < 5:
                    resultat_ar = ocr_ar.ocr(file_path, cls=True)
                    if resultat_ar and resultat_ar[0]:
                        lines = [line[1][0] for line in resultat_ar[0][:40]]
                
                texte = "\n".join(lines)
            return texte
            
    except Exception:
        return ""
    return ""


def extraire_texte_page_pdf(file_path: str, page_num: int, reader: PdfReader) -> str:
    """Extrait le texte d'une page spécifique d'un PDF (Natif)."""
    try:
        texte = reader.pages[page_num].extract_text() or ""
        # Si vous devez ajouter un fallback OCR sur des pages spécifiques à l'avenir,
        # notez que passer le chemin d'un PDF à PaddleOCR traite tout le document par défaut.
        # Pour une page spécifique, il faudra d'abord convertir la page du PDF en image (avec pdf2image par ex.).
        return texte
    except Exception:
        return ""