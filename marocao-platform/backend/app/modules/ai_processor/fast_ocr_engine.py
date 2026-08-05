import fitz, logging, cv2, re  
import numpy as np
from typing import Optional
from rapidocr_onnxruntime import RapidOCR

logger = logging.getLogger(__name__)

# Initialisation paresseuse du moteur ONNX
_rapid_ocr_instance = None

def _get_onnx_ocr_engine():
    global _rapid_ocr_instance
    if _rapid_ocr_instance is None:
        try:
            # RapidOCR utilise ONNX Runtime par défaut pour exécuter PaddleOCR en millisecondes sur CPU !
            _rapid_ocr_instance = RapidOCR()
            logger.info("[FAST_OCR_ONNX] Engine ONNX Runtime (CPU) initialisé avec succès.")
        except Exception as e:
            logger.error(f"[FAST_OCR_ONNX] Échec du chargement de RapidOCR/ONNX : {e}")
            return None
    return _rapid_ocr_instance

def extraire_texte_en_tete_fast_ocr(path_pdf: str, page_num: int = 0, ratio_hauteur: float = 0.40) -> str:
    """
    Rend la page sous forme d'image, rogne les X% supérieurs (défaut 30%),
    applique un pré-traitement OpenCV et extrait le texte via ONNX Runtime sur CPU.
    """
    try:
        doc = fitz.open(path_pdf)
        total_pages = len(doc)  

        if page_num >= len(doc):
            return ""
            
        page = doc[page_num]
        # Zoom 2.0 (144 DPI) : Parfait compromis pour l'inférence CPU ONNX
        mat = fitz.Matrix(2.0, 2.0)
        pix = page.get_pixmap(matrix=mat, alpha=False)
        
        # Conversion Pixmap PyMuPDF -> OpenCV (BGR)
        img = np.frombuffer(pix.samples, dtype=np.uint8).reshape((pix.height, pix.width, 3))
        
        # 1. Crop des 40% supérieurs
        hauteur_crop = int(pix.height * ratio_hauteur)
        img_crop = img[0:hauteur_crop, :]
        
        # 2. Pré-traitement OpenCV léger pour maximiser la netteté
        gray = cv2.cvtColor(img_crop, cv2.COLOR_BGR2GRAY)
        #_, thresh = cv2.threshold(gray, 180, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        
        engine = _get_onnx_ocr_engine()
        if not engine:
            return ""
        
        texte_final = _ocr_image(engine, gray)

        # ---------- FALLBACK ----------
        if ocr_est_de_mauvaise_qualite(texte_final):

            logger.info(
                f"[FAST_OCR_ONNX] P.{page_num+1}/{total_pages} "
                "OCR faible -> lecture de toute la page."
            )

            gray_full = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

            texte_complet = _ocr_image(engine, gray_full)

            if len(texte_complet) > len(texte_final):
                texte_final = texte_complet
        
        # 3. Inférence via ONNX Runtime
        #engine = _get_onnx_ocr_engine()
        #if not engine:
            #return ""
            
        # rapidocr_onnxruntime prend directement l'image numpy OpenCV en entrée
        ##result, elapse_list = engine(thresh)
        #result, elapse_list = engine(gray)
        
        #lignes = []
        #if result:
            #for item in result:
                #texte_detecte = item[1]  # Chaîne de texte extraite
                #confiance = item[2]     # Score de confiance
                #if confiance > 0.4:     # Filtrage léger du bruit
                    #lignes.append(texte_detecte)
                
        #texte_final = "\n".join(lignes).strip()
        logger.info(f"[FAST_OCR_ONNX] P.{page_num+1}/{total_pages} - En-tête scannée extraite via ONNX ({len(texte_final)} car.) : {texte_final[:60]}...")
        return texte_final
       
    except Exception as e:
        logger.error(f"[FAST_OCR_ONNX] Erreur d'inférence ONNX sur p.{page_num+1} de '{path_pdf}' : {e}")
        return ""
        
    finally:
        doc.close()
        
def ocr_est_de_mauvaise_qualite(texte: str):

    if not texte:
        return True

    texte = texte.strip()

    # Peu d'information extraite
    if len(texte) < 250:
        return True

    nb_lettres = len(re.findall(r"[A-Za-zÀ-ÿ\u0600-\u06FF]", texte))
    ratio = nb_lettres / max(len(texte), 1)

    if ratio < 0.60:
        return True

    parasites = len(re.findall(r"[+*#=<>\\|~]", texte))

    if parasites >= 2:
        return True

    return False
    
def _ocr_image(engine, image):
    result, _ = engine(image)

    lignes = []

    if result:
        for item in result:
            texte = item[1]
            confiance = item[2]

            if confiance > 0.4:
                lignes.append(texte)

    return "\n".join(lignes).strip()