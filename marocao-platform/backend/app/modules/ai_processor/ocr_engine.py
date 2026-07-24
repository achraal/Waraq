import os

# Désactive l'optimisation oneDNN/MKLDNN qui fait crasher PIR sous Windows
os.environ["FLAGS_use_onednn"] = "0"
os.environ["FLAGS_enable_pir_api"] = "0"

import docx, os, logging, openpyxl, tempfile, sys, subprocess
from pypdf import PdfReader
from paddleocr import PaddleOCR
from pdf2image import convert_from_path
import numpy as np
from PIL import Image

# Force l'affichage immédiat des logs dans la console sans buffering
sys.stdout.reconfigure(line_buffering=True)

# Configuration explicite du logger pour afficher les INFO
logging.basicConfig(level=logging.INFO, format="%(asctime)s - [%(levelname)s] - %(message)s")
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
# Clean initialization of French and Arabic OCR engines (without 'det_lang')
# Initialisation unique des moteurs PaddleOCR
# Utiliser det_limit_side_len au lieu de max_side_limit


# Initialisation explicite sur CPU (use_gpu=False est crucial)
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

#def _analyser_image_ram(img_np: np.ndarray) -> str:
    #"""Analyse l'image d'abord en FR, puis en AR si aucun texte FR significatif n'est trouvé."""
    #lines = []
    
    # 1. Tentative en Français
    #res = ocr_fr.ocr(img_np)
    #if res and res[0]:
        #lines = [line[1][0] for line in res[0]]
    
    # 2. Si le résultat contient moins de 3 lignes, c'est probablement un doc en Arabe
    #if len(lines) < 3:
        #res_ar = ocr_ar.ocr(img_np)
        #if res_ar and res_ar[0]:
            #lines = [line[1][0] for line in res_ar[0]]

    #return "\n".join(lines)
    
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

def extraire_texte_integral(file_path: str) -> str:
    """Extracteur universel qui lit TOUT le contenu d'un fichier peu importe son extension."""
    if not os.path.exists(file_path):
        return ""

    ext = os.path.splitext(file_path)[1].lower()

    try:
        # 1. PDF (Texte intégral de TOUTES les pages)
        if ext == ".pdf":
            reader = PdfReader(file_path)
            textes = []
            for idx, page in enumerate(reader.pages):
                txt = page.extract_text() or ""
                if txt.strip():
                    textes.append(f"--- PAGE {idx + 1} ---\n{txt}")
            
            texte_complet = "\n\n".join(textes)
            # Fallback OCR si le PDF est un scan complet (texte vide)
            # Si le texte extrait par PyPDF est trop pauvre (< 100 caractères pour 69 pages),
            # c'est un scan -> Forcer le fallback OCR intégral !
            if len(texte_complet.strip()) < 100:
                logger.info(f"[PDF SCAN DÉTECTÉ] Texte natif insuffisant ({len(texte_complet)} car.). Lancement de PaddleOCR...")
                return extraire_ocr_pdf_integral(file_path)
            
            logger.info(f"[PDF TEXTE DÉTECTÉ] Extraction native réussie ({len(texte_complet)} car.).")
            return texte_complet

        # 2. Word (DOCX / DOC)
        #elif ext in [".docx", ".doc"]:
        elif ext == ".docx":
            doc = docx.Document(file_path)
            return "\n".join([p.text for p in doc.paragraphs if p.text.strip()])
            
        elif ext == ".doc":
            pdf_temp = convertir_doc_en_pdf(file_path)
            if pdf_temp:
                try:
                    # On réutilise directement l'extraction PDF qui fonctionne déjà dans ton code
                    return extraire_texte_integral(pdf_temp)
                finally:
                    if os.path.exists(pdf_temp):
                        try:
                            os.remove(pdf_temp)
                        except Exception:
                            pass
            return ""        

        # 3. Excel (XLSX / XLS)
        elif ext in [".xlsx", ".xls"]:
            wb = openpyxl.load_workbook(file_path, data_only=True)
            textes = []
            for sheet in wb.worksheets:
                for row in sheet.iter_rows(values_only=True):
                    row_txt = " ".join([str(cell) for cell in row if cell is not None])
                    if row_txt.strip():
                        textes.append(row_txt)
            return "\n".join(textes)

        # 4. Images (JPG, PNG, TIFF, etc.)
        elif ext in [".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".tif"]:
            return extraire_ocr_image(file_path)

        # 5. Fichiers CAO/DAO (DWG, DXF) ou archives
        elif ext in [".dwg", ".dxf", ".zip", ".rar"]:
            return f"FICHIER_TECHNIQUE_DAO_{ext.replace('.', '').upper()}"

        # Fallback Texte brut
        else:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                return f.read()

    except Exception as e:
        logger.error(f"Erreur d'extraction intégrale sur {file_path}: {e}")
        return ""

def extraire_texte_page_pdf(file_path: str, page_num: int, reader: PdfReader) -> str:
    """Extrait le texte d'une page spécifique d'un PDF."""
    try:
        return reader.pages[page_num].extract_text() or ""
    except Exception:
        return ""
         
        
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
   
"""
Necessite une GPU lit tous les pages
"""
   
# def extraire_ocr_pdf_integral(file_path: str) -> str:
    # """OCR ultra-rapide optimisé pour les gros documents PDF."""
    # try:
        # reader = PdfReader(file_path)
        # total_pages = len(reader.pages)
        # print(f"[OCR INTEGRAL] Traitement de {total_pages} page(s) pour {os.path.basename(file_path)}...", flush=True)
        # textes = []

        # Conversion multithreadée à 150 DPI
        # images = convert_from_path(
            # file_path, 
            # dpi=130, 
            # thread_count=4
        # )

        # for i, img in enumerate(images):
            # print(f"-> [OCR] Page {i + 1}/{total_pages} en cours...", flush=True)
            
            # Passage direct sous forme de matrice numpy
            # img_np = np.array(img)
            
            # Traitement unique combiné FR / AR
            # txt = _analyser_image_ram(img_np)
            
            # if txt.strip():
                # textes.append(f"--- PAGE {i + 1} ---\n{txt}")

        # print(f"[OCR INTEGRAL] Terminé avec succès pour {os.path.basename(file_path)} !", flush=True)
        # return "\n\n".join(textes)

    # except Exception as e:
        # print(f"[ERREUR OCR INTEGRAL] Sur {file_path}: {e}", flush=True)
        # return ""

"""
CPU 5 pages
"""

# def extraire_ocr_pdf_integral(file_path: str, max_pages_debut: int = 3, max_pages_fin: int = 2) -> str:
    # """
    # OCR optimisé CPU : extrait uniquement les pages stratégiques (début et fin)
    # pour classifier rapidement le document sans charger la totalité du PDF. 
    # """
    # import time
    # start_time = time.time()
    # filename = os.path.basename(file_path)

    # try:
        # reader = PdfReader(file_path)
        # total_pages = len(reader.pages)
        # textes = []

        # Sélection des pages clés
        # if total_pages <= (max_pages_debut + max_pages_fin):
            # pages_a_traiter = list(range(total_pages))
        # else:
            # pages_a_traiter = list(range(max_pages_debut)) + list(range(total_pages - max_pages_fin, total_pages))

        # logger.info(
            # f"[OCR STRATÉGIQUE START] '{filename}' ({total_pages} pages au total). "
            # f"Analyse ciblée sur {len(pages_a_traiter)} page(s) : {[p + 1 for p in pages_a_traiter]}"
        # )

        # for idx, page_idx in enumerate(pages_a_traiter, 1):
            # page_start = time.time()
            # 1. Log d'annonce AVANT l'OCR de la page
            # logger.info(f"[OCR IN PROGRESS] Traitement de la page {page_idx + 1}/{total_pages} ({idx}/{len(pages_a_traiter)})...")
            # Conversion page par page pour ne pas charger la RAM
            # images = convert_from_path(file_path, first_page=page_idx + 1, last_page=page_idx + 1, dpi=130)

            # if images:
                # img_np = np.array(images[0])
                # txt = _analyser_image_ram(img_np)
                
                # if txt and txt.strip():
                    # textes.append(f"--- PAGE {page_idx + 1} ---\n{txt}")
                    # logger.info(
                        # f"[OCR PAGE {page_idx + 1}/{total_pages}] ({idx}/{len(pages_a_traiter)}) "
                        # f"- Extrait {len(txt)} caractères en {time.time() - page_start:.2f}s"
                    # )
                # else:
                    # logger.warning(
                        # f"[OCR PAGE {page_idx + 1}/{total_pages}] Aucun texte extrait par PaddleOCR "
                        # f"({time.time() - page_start:.2f}s)"
                    # )

        # texte_final = "\n\n".join(textes)
        # duree_totale = time.time() - start_time
        
        # logger.info(
            # f"[OCR STRATÉGIQUE END] '{filename}' - {len(texte_final)} caractères récupérés "
            # f"sur {len(pages_a_traiter)} page(s) traitée(s) en {duree_totale:.2f}s"
        # )

        # return texte_final

    # except Exception as e:
        # logger.error(f"[ERREUR OCR STRATÉGIQUE] Échec lors du traitement de '{filename}' : {e}", exc_info=True)
        # return ""
        
def extraire_ocr_pdf_integral(file_path: str) -> str:
    """
    Stratégie Hybride Optimisée CPU :
    1. Tente l'extraction native du texte via PyPDF (< 0.5s).
    2. Si le texte est suffisant (>= 100 car.), le renvoie directement pour analyse LLM.
    3. Si le PDF est un scan (< 100 car.) :
       - Tente de déduire le type via le nom du fichier / règles heuristiques.
       - Sinon, abandonne l'OCR lourd et renvoie le marqueur 'A_CLASSIFIER_MANUELLEMENT'.
    """
    filename = os.path.basename(file_path)
    
    try:
        # Step 1 : Tentative d'extraction native ultra-rapide
        reader = PdfReader(file_path)
        texte_native = []
        
        for idx, page in enumerate(reader.pages):
            txt = page.extract_text() or ""
            if txt.strip():
                texte_native.append(f"--- PAGE {idx + 1} ---\n{txt.strip()}")
        
        contenu_complet = "\n\n".join(texte_native)
        
        # Step 2 : Si le texte natif est exploitable, on valide
        if len(contenu_complet.strip()) >= 100:
            logger.info(f"[NATIVE READ SUCCESS] '{filename}' - {len(contenu_complet)} caractères extraits instantanément.")
            return contenu_complet
            
        # Step 3 : Traitement du Scan (Texte insuffisant < 100 car.)
        logger.warning(f"[SCAN DÉTECTÉ] '{filename}' a moins de 100 car. natifs. Évitement de l'OCR lourd.")
        
        # 3a. Heuristique sur le nom du fichier (Exemple : cps, rc, bordereau, etc.)
        filename_lower = filename.lower()
        if any(keyword in filename_lower for keyword in ["cps", "c.p.s", "cahier_des_charges"]):
            logger.info(f"[HEURISTIQUE MATCH] Nom de fichier identifié comme CPS : '{filename}'")
            return "TYPE_HEURISTIQUE: CPS - Cahier des Prescriptions Spéciales"
            
        if any(keyword in filename_lower for keyword in ["rc", "r.c", "reglement"]):
            logger.info(f"[HEURISTIQUE MATCH] Nom de fichier identifié comme RC : '{filename}'")
            return "TYPE_HEURISTIQUE: RC - Règlement de Consultation"
            
        if any(keyword in filename_lower for keyword in ["bdr", "bordereau", "prix"]):
            logger.info(f"[HEURISTIQUE MATCH] Nom de fichier identifié comme BORDEREAU_PRIX : '{filename}'")
            return "TYPE_HEURISTIQUE: BORDEREAU_PRIX"

        # 3b. Aucun indice fiable -> Redirection vers la file d'attente humaine
        logger.info(f"[ESCALADE HUMAINE] Aucun indice probant sur le scan '{filename}'. Marqué pour classification manuelle.")
        return "STATUS: A_CLASSIFIER_MANUELLEMENT"

    except Exception as e:
        logger.error(f"[ERREUR EXTRACTION] Échec sur '{filename}' : {e}", exc_info=True)
        return "STATUS: A_CLASSIFIER_MANUELLEMENT"

#def extraire_ocr_image(file_path: str) -> str:
    #"""Applique PaddleOCR sur un fichier image."""
    #return _executer_paddle_ocr(file_path)
    
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