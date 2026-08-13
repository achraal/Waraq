import os, time
# Désactive l'optimisation oneDNN/MKLDNN qui fait crasher PIR sous Windows
os.environ["FLAGS_use_onednn"] = "0"
os.environ["FLAGS_enable_pir_api"] = "0"
import docx, os, logging, openpyxl, tempfile, sys, subprocess, fitz
from pypdf import PdfReader
from paddleocr import PaddleOCR
from pdf2image import convert_from_path
import numpy as np
import pandas as pd
from PIL import Image
#from datetime import time
from typing import Optional, List
from backend.app.modules.ai_processor.fast_ocr_engine import extraire_texte_en_tete_fast_ocr

# Force l'affichage immédiat des logs dans la console sans buffering
sys.stdout.reconfigure(line_buffering=True)
# Configuration explicite du logger pour afficher les INFO
logging.basicConfig(level=logging.INFO, format="%(asctime)s - [%(levelname)s] - %(message)s")
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
""" Clean initialization of French and Arabic OCR engines (without 'det_lang')
Initialisation unique des moteurs PaddleOCR
Utiliser det_limit_side_len au lieu de max_side_limit
Initialisation explicite sur CPU (use_gpu=False est crucial)"""
ocr_fr = PaddleOCR(
    use_angle_cls=False, 
    lang='fr',
    enable_mkldnn=False,
    device='cpu',  # <-- On utilise 'device' au lieu de 'use_gpu'
    det_limit_side_len=736
)
ocr_ar = PaddleOCR(
    use_angle_cls=False, 
    lang='ar',
    enable_mkldnn=False,
    device='cpu',  # <-- On utilise 'device' au lieu de 'use_gpu'
    det_limit_side_len=736
)

LIBREOFFICE_PATH = r"C:\Program Files\LibreOffice\program\soffice.exe"

def convertir_doc_en_pdf(chemin_doc: str) -> str | None:
    """
    Convertit uniquement un ancien fichier .doc en .pdf temporaire via LibreOffice CLI.
    """
    if not os.path.exists(LIBREOFFICE_PATH):
        logger.error(f"[CONVERSION] Executable LibreOffice introuvable à : {LIBREOFFICE_PATH}")
        return None

    try:
        dossier_source = os.path.dirname(chemin_doc)
        nom_base = os.path.splitext(os.path.basename(chemin_doc))[0]
        chemin_pdf_attendu = os.path.join(dossier_source, f"{nom_base}.pdf")

        cmd = [
            LIBREOFFICE_PATH,
            "--headless",
            "--convert-to", "pdf",
            chemin_doc,
            "--outdir", dossier_source
        ]

        logger.info(f"[CONVERSION] Conversion de '{os.path.basename(chemin_doc)}' (.doc) en PDF...")
        resultat = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=30)

        if resultat.returncode == 0 and os.path.exists(chemin_pdf_attendu):
            logger.info(f"[CONVERSION] Succès -> {chemin_pdf_attendu}")
            return chemin_pdf_attendu
        else:
            logger.error(f"[CONVERSION] Échec LibreOffice : {resultat.stderr}")
            return None

    except Exception as e:
        logger.error(f"[CONVERSION] Erreur lors de la conversion du .doc {chemin_doc} : {e}")
        return None

def nom_fichier_court(chemin: str) -> str:
    return os.path.basename(chemin)
  
def optimiser_image_pour_analyse(chemin_image: str, max_side: int = 2048) -> str:
    """
    Redimensionne les images géantes pour accélérer l'analyse et réduire la mémoire.
    Retourne le chemin de l'image optimisée (ou l'originale si aucun redimensionnement n'est nécessaire).
    """
    try:
        with Image.open(chemin_image) as img:
            largeur, hauteur = img.size
            if max(largeur, hauteur) > max_side:
                logger.info(f"[IMAGE] Redimensionnement de {nom_fichier_court(chemin_image)} ({largeur}x{hauteur} -> max {max_side}px)...")
                
                # Conserver le mode couleur adapté (RGB pour JPEG)
                if img.mode in ("RGBA", "P"):
                    img = img.convert("RGB")
                    
                img.thumbnail((max_side, max_side), Image.Resampling.LANCZOS)
                
                base, ext = os.path.splitext(chemin_image)
                chemin_opti = f"{base}_opti{ext}"
                img.save(chemin_opti, quality=85)
                return chemin_opti
    except Exception as e:
        logger.warning(f"[IMAGE] Impossible d'optimiser l'image {chemin_image}: {e}")
    
    return chemin_image
    
def compter_pages_doc(file_path: str) -> int | None:
    pdf_temp = convertir_doc_en_pdf(file_path)
    if not pdf_temp:
        return None

    try:
        pdf = fitz.open(pdf_temp)
        pages = len(pdf)

        logger.info(
            f"[PAGE COUNT DOC] {os.path.basename(file_path)} -> {pages} pages"
        )
        return pages
    finally:
        pdf.close()
        if os.path.exists(pdf_temp):
            os.remove(pdf_temp)

def extraire_texte_integral(file_path: str) -> dict:
    """Extracteur universel qui lit TOUT le contenu d'un fichier et remonte les métas d'inspection."""
    if not os.path.exists(file_path):
        return {"text": "", "is_scanned": False, "inspection_method": "FILE_NOT_FOUND"}

    ext = os.path.splitext(file_path)[1].lower()
    page_count = None
    word_count = 0
    file_size_mb = round(os.path.getsize(file_path) / (1024 * 1024), 2)
    ocr_duration_total = 0.0

    logger.info(f"[METRICS INIT] {os.path.basename(file_path)} | " f"ext={ext} | file_size_mb={file_size_mb}")

    try:
        # 1. PDF (Parcours page par page avec métadonnées)
        if ext == ".pdf":
            doc = fitz.open(file_path)
            est_scanne_force, methode_forcee = analyser_si_scanne(doc)

            methods_utilisees = set()
            nb_pages_ocr = 0
            total_pages = len(doc)
            page_count = total_pages            
            ocr_duration_total = 0.0
            
            textes = []
            lots = []
            lot_pages = []
            lot_scan = False
            lot_method = "NATIVE_TEXT_PYMUPDF"          
            pages = []            

            if est_scanne_force:
                methods_utilisees.add(methode_forcee)

            for idx in range(len(doc)):
                start = time.perf_counter()
                res_page = extraire_texte_page_pdf_avec_meta(
                    doc, 
                    page_num=idx, 
                    path_pdf=file_path, 
                    force_scanned=est_scanne_force
                )
                methode = res_page.get("inspection_method", "")

                if methode.startswith("FAST_OCR"):
                    ocr_duration_total += time.perf_counter() - start
                txt = res_page.get("text", "")
                
                pages.append({
                    "page_num": idx + 1,
                    "text": txt,
                    "is_scanned": res_page.get("is_scanned", False),
                    "inspection_method": res_page.get(
                        "inspection_method",
                        "NATIVE_TEXT_PYMUPDF"
                    )
                })
                
                if txt.strip():
                    textes.append(f"--- PAGE {idx + 1} ---\n{txt}")
                    
                    lot_pages.append(f"--- PAGE {idx + 1} ---\n{txt}")

                    if res_page.get("is_scanned", False):
                        lot_scan = True
                        lot_method = res_page.get(
                            "inspection_method",
                            "FAST_OCR_ONNX_HEADER"
                        )

                    if len(lot_pages) == 10 or idx == total_pages - 1:
                        lots.append({
                            "lot_index": len(lots) + 1,
                            "page_debut": idx - len(lot_pages) + 2,
                            "page_fin": idx + 1,
                            "texte": "\n".join(lot_pages),
                            "is_scanned": lot_scan,
                            "inspection_method": lot_method
                        })

                        lot_pages = []
                        lot_scan = False
                        lot_method = "NATIVE_TEXT_PYMUPDF"
               
                methode = res_page.get("inspection_method", "UNKNOWN")
                methods_utilisees.add(methode)

                if methode.startswith("FAST_OCR"):
                    nb_pages_ocr += 1

            doc.close()
            texte_complet = "\n\n".join(textes)
            word_count = len(texte_complet.split())

            if est_scanne_force or "FAST_OCR_ONNX_FULL_PAGE" in methods_utilisees:
                inspection_method_finale = "FAST_OCR_ONNX_FULL_PAGE"
            elif "FAST_OCR_ONNX_HEADER" in methods_utilisees:
                inspection_method_finale = "FAST_OCR_ONNX_HEADER"
            else:
                inspection_method_finale = "NATIVE_TEXT_PYMUPDF"
                
            ratio_ocr = nb_pages_ocr / total_pages if total_pages else 0

            if est_scanne_force:
                is_scanned_global = True
                inspection_method_finale = "FAST_OCR_ONNX_FULL_PAGE"

            elif ratio_ocr == 0:
                is_scanned_global = False
                inspection_method_finale = "NATIVE_TEXT_PYMUPDF"

            elif ratio_ocr < 0.30:
                is_scanned_global = False
                inspection_method_finale = "MIXED_TEXT_OCR"

            else:
                is_scanned_global = True
                inspection_method_finale = "FAST_OCR_ONNX_FULL_PAGE"

            logger.info(f"[EXTRACTION PDF] Méthode: {inspection_method_finale} | Scan: {is_scanned_global} | Longueur: {len(texte_complet)} car.")
            return {
                "text": texte_complet,
                "is_scanned": is_scanned_global,
                "inspection_method": inspection_method_finale,
                "page_count": page_count,
                "word_count": word_count,
                "file_size_mb": file_size_mb,
                "ocr_duration_sec": round(ocr_duration_total, 2),
                "lots": lots,
                "pages": pages,
            }

        # 2. Word (DOCX / DOC)
        elif ext == ".docx":
            doc = docx.Document(file_path)
            texte = "\n".join([p.text for p in doc.paragraphs if p.text.strip()])
            word_count = len(texte.split())
            page_count = compter_pages_doc(file_path)

            logger.info(
                f"[METRICS DOCX] "
                f"pages={page_count} | "
                f"words={word_count} | "
                f"size={file_size_mb} MB | "
                f"ocr=0.0 s"
            )
            return {
                "text": texte,
                "is_scanned": False,
                "inspection_method": "NATIVE_WORD_DOCX",
                "page_count": page_count,
                "word_count": word_count,
                "file_size_mb": file_size_mb,
                "ocr_duration_sec": 0.0
            }
        elif ext == ".doc":
            pdf_temp = convertir_doc_en_pdf(file_path)

            if not pdf_temp:
                return {
                    "text": "",
                    "is_scanned": False,
                    "inspection_method": "CONVERSION_FAILED",
                    "page_count": None,
                    "word_count": 0,
                    "file_size_mb": file_size_mb,
                    "ocr_duration_sec": 0.0
                }
            try:
                result = extraire_texte_integral(pdf_temp)
                # on garde la taille du .doc original
                result["file_size_mb"] = file_size_mb
                logger.info(
                    f"[METRICS DOC] "
                    f"pages={result.get('page_count')} | "
                    f"words={result.get('word_count')} | "
                    f"size={result.get('file_size_mb')} MB | "
                    f"ocr={result.get('ocr_duration_sec')} s"
                )
                return result
            finally:
                if os.path.exists(pdf_temp):
                    os.remove(pdf_temp)

        # 3. Excel (XLSX / XLS)
        elif ext == ".xlsx":
            wb = openpyxl.load_workbook(file_path, data_only=True)
            textes = []

            for sheet in wb.worksheets:
                for row in sheet.iter_rows(values_only=True):
                    
                    row_txt = " ".join([str(cell) for cell in row if cell is not None])
                    if row_txt.strip():
                        textes.append(row_txt)
            texte = "\n".join(textes)
            word_count = len(texte.split())
            logger.info(
                f"[METRICS XLSX] "
                f"pages={page_count} | "
                f"words={word_count} | "
                f"size={file_size_mb} MB"
            )
            return {
                "text": "\n".join(textes),
                "is_scanned": False,
                "inspection_method": "NATIVE_EXCEL_XLSX",
                "page_count": page_count,
                "word_count": word_count,
                "file_size_mb": file_size_mb,
                "ocr_duration_sec": round(ocr_duration_total, 2)
            }
            
        elif ext == ".xls":
            df_dict = pd.read_excel(file_path, sheet_name=None, engine="xlrd")
            textes = []
            for sheet_name, df in df_dict.items():
                if not df.empty:
                    
                    textes.append(df.to_string(index=False))
            texte = "\n".join(textes)
            word_count = len(texte.split())
            logger.info(
                f"[METRICS XLS] "
                f"pages={page_count} | "
                f"words={word_count} | "
                f"size={file_size_mb} MB"
            )
            return {
                "text": "\n".join(textes),
                "is_scanned": False,
                "inspection_method": "NATIVE_EXCEL_XLS",
                "page_count": page_count,
                "word_count": word_count,
                "file_size_mb": file_size_mb,
                "ocr_duration_sec": round(ocr_duration_total, 2)
            }

        # 4. Images (JPG, PNG, TIFF, etc.)
        elif ext in [".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".tif"]:
            start = time.perf_counter()
            texte = extraire_ocr_image(file_path)
            ocr_duration_total = time.perf_counter() - start
            word_count = len(texte.split())
            page_count = 1

            logger.info(
                f"[METRICS IMAGE] "
                f"pages={page_count} | "
                f"words={word_count} | "
                f"size={file_size_mb} MB | "
                f"ocr={round(ocr_duration_total,2)} s"
            )
            return {
                "text": texte,
                "is_scanned": True,
                "inspection_method": "FAST_OCR_ONNX_IMAGE",
                "page_count": page_count,
                "word_count": word_count,
                "file_size_mb": file_size_mb,
                "ocr_duration_sec": round(ocr_duration_total, 2)
            }

        # 5. Fichiers CAO/DAO (DWG, DXF) ou archives
        elif ext in [".dwg", ".dxf", ".zip", ".rar"]:
            return {
                "text": f"FICHIER_TECHNIQUE_DAO_{ext.replace('.', '').upper()}",
                "is_scanned": False,
                "inspection_method": "TECHNICAL_FILE",
                "page_count": page_count,
                "word_count": word_count,
                "file_size_mb": file_size_mb,
                "ocr_duration_sec": round(ocr_duration_total, 2)
            }

        # Fallback Texte brut
        else:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                texte = f.read()
                word_count = len(texte.split())
                logger.info(
                    f"[METRICS RAW] "
                    f"pages={page_count} | "
                    f"words={word_count} | "
                    f"size={file_size_mb} MB"
                )
                return {
                    "text": texte,
                    "is_scanned": False,
                    "inspection_method": "RAW_TEXT",
                    "page_count": page_count,
                    "word_count": word_count,
                    "file_size_mb": file_size_mb,
                    "ocr_duration_sec": round(ocr_duration_total, 2)
                }

    except Exception as e:
        logger.error(f"Erreur d'extraction intégrale sur {file_path}: {e}")
        return {"text": "", "is_scanned": False, "inspection_method": "ERROR", "page_count": None,
            "word_count": 0,
            "file_size_mb": file_size_mb if os.path.exists(file_path) else 0.0,
            "ocr_duration_sec": 0.0}
    
def extraire_texte_page_pdf_avec_meta(doc_or_path, page_num: int = 0, path_pdf: str = None, force_scanned: bool = False) -> dict:
    should_close = False
    result = {
        "text": "",
        "is_scanned": True,
        "inspection_method": "FAILED_EXTRACTION"
    }
    
    try:
        if isinstance(doc_or_path, str):
            doc = fitz.open(doc_or_path)
            actual_path = doc_or_path
            should_close = True
        else:
            doc = doc_or_path
            actual_path = path_pdf or getattr(doc, "name", "")

        if page_num < len(doc):
            texte_natif = doc[page_num].get_text("text").strip()
            
            # --- LOG DIAGNOSTIC ---
            #logger.info(f"[DIAG_OCR_PAGE] Page {page_num + 1}/{len(doc)} | Caractères natifs PyMuPDF: {len(texte_natif)} | force_scanned: {force_scanned}")

            if not force_scanned and len(texte_natif) >= 50:
                #logger.info(f"[DIAG_OCR_PAGE] Page {page_num + 1} -> Retenu comme NATIVE_TEXT_PYMUPDF")
                result = {
                    "text": texte_natif,
                    "is_scanned": False,
                    "inspection_method": "NATIVE_TEXT_PYMUPDF"
                }
            else:
                #logger.info(f"[DIAG_OCR_PAGE] Page {page_num + 1} -> Force/Nécessite OCR -> FAST_OCR_ONNX")
                texte_ocr = extraire_texte_en_tete_fast_ocr(actual_path, page_num=page_num, ratio_hauteur=0.40)
                
                if len(texte_ocr.strip()) < 15:
                    texte_ocr = extraire_texte_en_tete_fast_ocr(actual_path, page_num=page_num, ratio_hauteur=1.00)
                    method = "FAST_OCR_ONNX_FULL_PAGE"
                else:
                    method = "FAST_OCR_ONNX_HEADER"
                
                result = {"text": texte_ocr,"is_scanned": True,"inspection_method": method}

    except Exception as e:
        logger.error(f"[OCR PAGE] Erreur P.{page_num+1} sur '{doc_or_path}' : {e}")
    finally:
        if should_close and 'doc' in locals() and doc:
            doc.close()

    return result
           
def extraire_ocr_pdf_page(file_path: str, page_num: int) -> str:
    """Applique PaddleOCR sur une page spécifique d'un PDF scanné."""
    temp_img_path = None
    try:
        # LOG VISIBLE DANS LE TERMINAL POUR CHACUNE DES 69 PAGES
        logger.info(f"[OCR PAGE] Traitement de la page {page_num + 1} pour {os.path.basename(file_path)}...")
        
        images = convert_from_path(file_path, first_page=page_num+1, last_page=page_num+1)
        if not images:
            return ""
        # 1. Création et fermeture immédiate du descripteur de fichier
        tmp_file = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
        temp_img_path = tmp_file.name
        tmp_file.close() # Libère le descripteur pour éviter tout conflit sous Windows
        # 2. Sauvegarde et exécution de l'OCR
        images[0].save(temp_img_path, "PNG")
        return _executer_paddle_ocr(temp_img_path)

    except Exception as e:
        logger.error(f"Erreur OCR Page {page_num} sur {file_path}: {e}")
        return ""
    finally:
        # Garanti de s'exécuter, même en cas de crash
        if temp_img_path and os.path.exists(temp_img_path):
            try:
                # 3. Nettoyage sécurisé
                os.remove(temp_img_path)
            except Exception as clean_err:
                logger.warning(f"Impossible de supprimer l'image temporaire {temp_img_path}: {clean_err}")
    
def extraire_ocr_image(file_path: str) -> str:
    """Applique PaddleOCR sur un fichier image avec optimisation préalable si l'image est géante."""
    # 1. Optimiser l'image si elle est trop grande (ex: T2.jpg)
    chemin_a_analyser = optimiser_image_pour_analyse(file_path, max_side=2048)
    try:
        # 2. Exécuter PaddleOCR sur le chemin (optimisé ou d'origine)
        return _executer_paddle_ocr(chemin_a_analyser)
    finally:
        # 3. Nettoyer l'image temporaire _opti si elle a été créée
        if chemin_a_analyser != file_path and os.path.exists(chemin_a_analyser):
            try:
                os.remove(chemin_a_analyser)
            except Exception as e:
                logger.warning(f"Impossible de supprimer l'image optimisée temporaire {chemin_a_analyser}: {e}")

def _executer_paddle_ocr(image_path: str) -> str:
    """Utilise PaddleOCR (FR puis AR si échec)."""
    lines = []
    res = ocr_fr.ocr(image_path)
    if res and res[0]:
        lines = [line[1][0] for line in res[0]]
    
    if len(lines) < 3:
        res_ar = ocr_ar.ocr(image_path)
        if res_ar and res_ar[0]:
            lines = [line[1][0] for line in res_ar[0]]
            
    return "\n".join(lines)

def analyser_si_scanne(doc_fitz: fitz.Document, min_words_per_page: int = 15) -> tuple[bool, str]:
    """
    Détermine si le PDF est un document scanné même s'il contient du texte résiduel/OCR bas de gamme.
    """
    total_pages = len(doc_fitz)
    pages_avec_images_domina = 0
    total_mots = 0

    for idx, page in enumerate(doc_fitz):
        mots = page.get_text("words")
        total_mots += len(mots)
        
        rect_page = page.rect
        surface_page = rect_page.width * rect_page.height
        
        images = page.get_images()
        surface_images = 0
        for img in images:
            for img_rect in page.get_image_rects(img[0]):
                surface_images += img_rect.width * img_rect.height

        ratio_img = (surface_images / surface_page) if surface_page > 0 else 0
        
        # --- LOG DIAGNOSTIC PAGE PAR PAGE ---
        #logger.info(f"[DIAG_ANALYSER] P.{idx+1} | Mots: {len(mots)} | Surf. Images: {ratio_img*100:.1f}%")

        if surface_page > 0 and ratio_img > 0.70 and len(mots) < 50:
            pages_avec_images_domina += 1

    mots_par_page = total_mots / max(total_pages, 1)
    
    # --- LOG DIAGNOSTIC GLOBAL ---
    logger.info(f"[DIAG_ANALYSER] Total P.: {total_pages} | Mots/P. moyen: {mots_par_page:.1f} | Pages dominées images: {pages_avec_images_domina}/{total_pages}")

    # AJOUT DE LA SÉCURITÉ ABSOLUE : Si 0 mot extrait, c'est un scan ou une image pure !
    if total_mots == 0:
        logger.info("[DIAG_ANALYSER] RÉSULTAT -> 0 MOT TROUVÉ : FORCER SCAN (FAST_OCR_ONNX_FULL_PAGE)")
        return True, "FAST_OCR_ONNX_FULL_PAGE"

    if mots_par_page < min_words_per_page or (pages_avec_images_domina / total_pages) >= 0.5:
        logger.info("[DIAG_ANALYSER] RÉSULTAT -> DÉCEPTIF: FORCER SCAN (FAST_OCR_ONNX_FULL_PAGE)")
        return True, "FAST_OCR_ONNX_FULL_PAGE"
    
    logger.info("[DIAG_ANALYSER] RÉSULTAT -> NON SCAN (NATIVE_TEXT_PYMUPDF)")
    return False, "NATIVE_TEXT_PYMUPDF"