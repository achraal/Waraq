import os, re, shutil, logging, subprocess, tempfile, cv2, fitz
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
import numpy as np
import pandas as pd
from docx import Document
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak)
from rapidocr_onnxruntime import RapidOCR
from backend.app.config import settings

logger = logging.getLogger("waraq.rag.document_extractor")

ZONE_SIGNATURE_KEYWORDS = ["signature","signatures","cachet","cachets","signé","signe","signée","signe par","signé par","signature et cachet","cachet et signature"]

ZONE_VALIDATION_KEYWORDS = ["lu et accepte","lu et accepté","lu et approuve","lu et approuvé","vu et présente","vu et présenté","vu et verifie","vu et vérifie","vise par","visé par","visa","approuve par","approuvé par","approuvé","visa du","visa de"]

ZONE_DATE_KEYWORDS = ["fait a","fait à","le","date"]

ZONE_ADMINISTRATIVE_KEYWORDS = ZONE_SIGNATURE_KEYWORDS + ZONE_VALIDATION_KEYWORDS

# OCR RAPIDOCR

_rapid_ocr_instance = None
def _get_onnx_ocr_engine():
    global _rapid_ocr_instance
    if _rapid_ocr_instance is None:
        try:
            _rapid_ocr_instance = RapidOCR()
            logger.info("[RAG-OCR] RapidOCR / ONNX Runtime initialisé.")
        except Exception as e:
            logger.error("[RAG-OCR] Impossible d'initialiser RapidOCR : %s", e, exc_info=True)
            return None
    return _rapid_ocr_instance

def _ocr_image(engine, image) -> str:
    try:
        result, _ = engine(image)
        lignes = []
        if result:
            for item in result:
                texte = str(item[1]).strip()
                confiance = float(item[2])
                if texte and confiance >= 0.40:
                    lignes.append(texte)
        return "\n".join(lignes).strip()
    except Exception as e:
        logger.error("[RAG-OCR] Erreur OCR image : %s", e)
        return ""

def _ocr_est_de_mauvaise_qualite(texte: str) -> bool:
    if not texte:
        return True
    texte = texte.strip()
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

def extraire_page_complete_fast_ocr(page, page_number: int) -> str:
    """
    OCR COMPLET d'une page. Contrairement à l'ancien OCR d'en-tête,cette fonction analyse toute la page.
    """
    try:
        mat = fitz.Matrix(2.0, 2.0)
        pix = page.get_pixmap(matrix=mat, alpha=False)
        img = np.frombuffer(pix.samples, dtype=np.uint8).reshape((pix.height, pix.width, 3))
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        engine = _get_onnx_ocr_engine()
        if engine is None:
            return ""
        texte = _ocr_image(engine, gray)
        logger.info("[RAG-OCR] Page %s : %s caractères extraits.", page_number, len(texte))
        return texte
    except Exception as e:
        logger.error("[RAG-OCR] Erreur page %s : %s", page_number, e, exc_info=True)
        return ""

DOCUMENT_PATTERNS = {
    "CURRICULUM_VITAE": [
        r"\bcurriculum vitae\b",
        r"\bcv\b",
        r"\bexpérience professionnelle\b",
        r"\bformation\b",
        r"\bparcours professionnel\b",
    ],
    "DECLARATION_HONNEUR": [
        r"d[ée]claration sur l'honneur",
        r"d[ée]claration sur honneur",
        r"d[ée]claration.*honneur",
    ],
    "ACTE_ENGAGEMENT": [
        r"acte d'engagement",
        r"acte d engagement",
        r"marché.*acte d'engagement",
    ],
    "DECLARATION_IDENTITE": [
        r"d[ée]claration d'identit[ée]",
        r"d[ée]claration d'identite",
        r"identification.*soumissionnaire",
        r"identit[ée].*soumissionnaire",
    ],
    "BDP": [
        r"bordereau des prix",
        r"bordereau de prix",
        r"d[ée]tail estimatif",
        r"d[ée]tail des prix",
        r"bordereau.*prix.*unit",
        r"prix unitaire",
        r"prix total",
    ],
    "BPU": [
        r"bordereau des prix unitaires",
        r"prix unitaires",
        r"bpu",
    ],
    "DPGF": [
        r"d[ée]composition du prix global",
        r"d[ée]composition des prix",
        r"dpgf",
        r"d[ée]tail quantitatif",
    ],
    "RC": [
        r"r[èe]glement de consultation",
        r"r[èe]glement.*consultation",
        r"rc",
    ],
    "CPS": [
        r"cahier des prescriptions sp[ée]ciales",
        r"cahier.*prescriptions.*sp[ée]ciales",
        r"\bcps\b",
    ],
    "DECLARATION_FISCALE": [
        r"attestation fiscale",
        r"situation fiscale",
        r"imp[ôo]ts et taxes",
    ],
    "DECLARATION_SOCIALE": [
        r"attestation cnss",
        r"caisse nationale de s[ée]curit[ée] sociale",
        r"cnss",
    ],
}

def normaliser_texte_detection(text: str) -> str:
    text = text.lower()
    text = text.replace("’", "'").replace("`", "'")
    text = re.sub(r"\s+", " ", text)
    return text

def detecter_types_documents(text: str) -> List[str]:
    text_norm = normaliser_texte_detection(text)
    types_detectes = []
    for document_type, patterns in DOCUMENT_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, text_norm, re.IGNORECASE):
                types_detectes.append(document_type)
                break
    return types_detectes

def _extraire_pdf(file_path: str) -> Dict[str, Any]:
    pages = []
    doc = fitz.open(file_path)
    try:
        for page_index in range(len(doc)):
            page = doc.load_page(page_index)
            page_number = page_index + 1

            # 1. EXTRACTION TEXTE NATIVE
            texte = page.get_text("text",sort=True).strip()
            extraction_method = "PYMUPDF"

            # 2. SI PAGE SCANNEE -> OCR COMPLET
            if not texte or _ocr_est_de_mauvaise_qualite(texte):
                logger.info("[RAG] Page %s : texte natif absent/faible -> OCR COMPLET.", page_number)
                texte_ocr = extraire_page_complete_fast_ocr(page, page_number)
                if len(texte_ocr) > len(texte):
                    texte = texte_ocr
                    extraction_method = "RAPIDOCR_ONNX_FULL_PAGE"
            pages.append(
                {
                    "page_number": page_number,
                    "text": texte,
                    "method": extraction_method,
                }
            )
    finally:
        doc.close()
    texte_complet = "\n\n".join(
        (
            f"===== PAGE {p['page_number']} =====\n"
            f"{p['text']}"
        )
        for p in pages
        if p["text"].strip()
    )
    return {
        "text": texte_complet,
        "pages": pages,
        "page_count": len(pages),
    }

def _extraire_docx(file_path: str) -> Dict[str, Any]:
    document = Document(file_path)
    lignes = []
    # Paragraphes
    for paragraph in document.paragraphs:
        text = paragraph.text.strip()
        if text:
            lignes.append(text)
    # Tableaux
    for table_index, table in enumerate(document.tables, start=1):
        lignes.append(f"\n===== TABLEAU {table_index} =====")
        for row in table.rows:
            cells = [cell.text.strip() for cell in row.cells]
            lignes.append(" | ".join(cells))
    texte = "\n".join(lignes)
    return {
        "text": texte,
        "pages": [],
        "page_count": None,
    }

def _convertir_avec_libreoffice(file_path: str) -> Optional[str]:
    output_dir = tempfile.mkdtemp(prefix="waraq_rag_convert_")
    try:
        result = subprocess.run(
            [settings.LIBREOFFICE_PATH, "--headless", "--convert-to", "pdf", "--outdir", output_dir, file_path,],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=120,
        )
        if result.returncode != 0:
            logger.error("[RAG] LibreOffice conversion failed: %s", result.stderr)
            return None
        expected = (Path(output_dir) / f"{Path(file_path).stem}.pdf")
        if expected.exists():
            return str(expected)
        return None

    except Exception as e:
        logger.error("[RAG] Erreur LibreOffice : %s", e, exc_info=True)
        return None

def _extraire_excel(file_path: str) -> Dict[str, Any]:
    extension = ( Path(file_path).suffix.lower() )
    engine = None
    if extension == ".xls":
        engine = "xlrd"
    elif extension in [".xlsx",".xlsm",]:
        engine = "openpyxl"
    sheets = pd.read_excel(file_path, sheet_name=None, header=None, engine=engine, dtype=object,)
    lignes = []
    feuilles = []
    for sheet_name, dataframe in sheets.items():
        lignes.append(f"\n===== FEUILLE : {sheet_name} =====")
        rows = []
        for _, row in dataframe.iterrows():
            values = []
            for value in row.tolist():
                if pd.isna(value):
                    value = ""
                else:
                    value = str(value).strip()
                values.append(value)

            # Evite les lignes totalement vides
            if any(values):
                ligne = " | ".join(values)
                lignes.append(ligne)
                rows.append(values)
        feuilles.append({"name": sheet_name, "rows": rows})
    return {
        "text": "\n".join(lignes),
        "pages": [],
        "page_count": None,
        "sheets": feuilles,
    }

def _extraire_image(file_path: str) -> Dict[str, Any]:
    image = cv2.imread(file_path)
    if image is None:
        return {
            "text": "",
            "pages": [],
            "page_count": 1,
        }
    engine = _get_onnx_ocr_engine()
    if engine is None:
        return {
            "text": "",
            "pages": [],
            "page_count": 1,
        }
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    texte = _ocr_image(engine, gray)
    return {
        "text": texte,
        "pages": [
            {
                "page_number": 1,
                "text": texte,
                "method": "RAPIDOCR_ONNX_FULL_IMAGE",
            }
        ],
        "page_count": 1,
    }

def extraire_document_complet_pour_rag(file_path: str) -> Dict[str, Any]:
    """
    Extracteur indépendant du Learning Service.
    Il extrait TOUT le contenu exploitable du document.
    """
    if not file_path:
        return {
            "text": "",
            "pages": [],
            "detected_types": [],
            "source_type": None,
        }
    path = Path(file_path)
    if not path.exists():
        logger.error("[RAG] Fichier introuvable : %s", file_path)
        return {
            "text": "",
            "pages": [],
            "detected_types": [],
            "source_type": None,
        }
    extension = path.suffix.lower()
    logger.info("[RAG-EXTRACT] Début extraction complète : %s", path.name)
    try:
        if extension == ".pdf":
            result = _extraire_pdf(file_path)
            source_type = "PDF"
        elif extension == ".docx":
            result = _extraire_docx(file_path)
            source_type = "DOCX"
        elif extension == ".doc":
            converted_pdf = _convertir_avec_libreoffice(file_path)
            if converted_pdf:
                result = _extraire_pdf(converted_pdf)
                source_type = "DOC_VIA_LIBREOFFICE"
            else:
                logger.error("[RAG] Impossible de convertir le DOC : %s", file_path)
                result = {
                    "text": "",
                    "pages": [],
                    "page_count": None,
                }
                source_type = "DOC"
        elif extension in [".xls", ".xlsx", ".xlsm"]:
            result = _extraire_excel(file_path)
            source_type = "EXCEL"
        elif extension in [".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp"]:
            result = _extraire_image(file_path)
            source_type = "IMAGE"
        else:
            logger.warning("[RAG] Extension non supportée : %s", extension)
            result = {
                "text": "",
                "pages": [],
                "page_count": None,
            }
            source_type = extension
        texte = result.get("text","")
        detected_types = detecter_types_documents(texte)
        result["detected_types"] = detected_types
        result["source_type"] = source_type
        result["source_file"] = str(file_path)

        logger.info("[RAG-EXTRACT] Extraction terminée : %s caractères | types détectés=%s",len(texte),detected_types)
        return result
    except Exception as e:
        logger.error("[RAG-EXTRACT] Erreur extraction %s : %s",file_path,e,exc_info=True)
        return {
            "text": "",
            "pages": [],
            "detected_types": [],
            "source_type": source_type
            if "source_type" in locals() else None,
        }

def extraire_pages_modeles_pdf(
    source_pdf: str,
    output_dir: str,
    types_a_extraire: Optional[List[str]] = None,
    contexte_pages: int = 1,
) -> List[Dict[str, Any]]:
    """
    Recherche les modèles dans un PDF page par page.
    Exemple :
    - CV, declaration sur l'honneur, acte d'engagement, declaration d'identité, BDP
    """
    os.makedirs(output_dir, exist_ok=True)
    doc = fitz.open(source_pdf)
    resultats = []
    try:
        pages_detectees = {}
        for page_index in range(len(doc)):
            page = doc.load_page(page_index)
            texte = page.get_text("text",sort=True).strip()
            # PDF scanné
            if not texte:
                texte = extraire_page_complete_fast_ocr(page,page_index + 1)
            types_page = detecter_types_documents(texte)
            for type_document in types_page:
                if (types_a_extraire and type_document not in types_a_extraire):
                    continue
                pages_detectees.setdefault(type_document,set())
                debut = max(0,page_index - contexte_pages)
                fin = min(len(doc),page_index + contexte_pages + 1)
                for p in range(debut,fin):
                    pages_detectees[type_document].add(p)

        # CREATION PDF PAR TYPE
        for type_document, pages in pages_detectees.items():
            if not pages:
                continue
            output_pdf = Path(output_dir)/ f"{type_document}.pdf"
            nouveau_pdf = fitz.open()
            for page_index in sorted(pages):
                nouveau_pdf.insert_pdf(doc, from_page=page_index, to_page=page_index)
            nouveau_pdf.save(str(output_pdf))
            nouveau_pdf.close()
            resultats.append(
                {
                    "type": type_document,
                    "path": str(output_pdf),
                    "pages": [p + 1 for p in sorted(pages)],
                }
            )
            logger.info("[RAG-EXTRACT] Modèle extrait : %s -> %s",type_document,output_pdf)
    finally:
        doc.close()
    return resultats
    
def extraire_bdp_excel_vers_pdf(file_path: str, output_pdf: str) -> Optional[str]:
    """
    Transforme toutes les feuilles Excel identifiées comme BDP
    en PDF exploitable par le workflow de génération.
    """
    extension = Path(file_path).suffix.lower()
    engine = None
    if extension == ".xls":
        engine = "xlrd"
    elif extension in [".xlsx", ".xlsm"]:
        engine = "openpyxl"
    try:
        sheets = pd.read_excel(file_path, sheet_name=None, header=None, engine=engine, dtype=object)
    except Exception as e:
        logger.error("[RAG-BDP] Impossible de lire Excel : %s",e,exc_info=True)
        return None

    styles = getSampleStyleSheet()
    normal_style = ParagraphStyle("BDPNormal",parent=styles["Normal"], fontSize=7, leading=9,)
    title_style = ParagraphStyle("BDPTitle",parent=styles["Title"], alignment=TA_CENTER, fontSize=14, leading=17,)
    doc = SimpleDocTemplate(output_pdf, pagesize=landscape(A4), rightMargin=20, leftMargin=20, topMargin=20,bottomMargin=20,)
    story = []
    story.append(Paragraph("BORDEREAU DES PRIX / DÉTAIL ESTIMATIF",title_style))
    story.append(Spacer(1, 15))
    feuille_bdp_trouvee = False

    for sheet_name, dataframe in sheets.items():
        # Convertir en texte pour détecter le BDP
        contenu_feuille = " ".join(str(v) for v in dataframe.astype(str).values.flatten())
        types = detecter_types_documents(contenu_feuille)
        est_bdp = ("BDP" in types or "BPU" in types or "DPGF" in types)
        if not est_bdp:
            continue
        feuille_bdp_trouvee = True
        story.append(Paragraph(f"Feuille : {sheet_name}",styles["Heading2"]))
        data = []

        for _, row in dataframe.iterrows():
            values = []
            for value in row.tolist():
                if pd.isna(value):
                    value = ""
                value = str(value).strip()
                values.append(Paragraph(value.replace("&","&amp;"),normal_style))
            if any(str(x.text).strip() for x in values):
                data.append(values)
        if data:
            table = Table(data,repeatRows=1)
            table.setStyle(TableStyle([
                        ("GRID",(0, 0),(-1, -1), 0.4, colors.grey,),
                        ("VALIGN",(0, 0),(-1, -1), "TOP",),
                        ("FONTNAME",(0, 0),(-1, 0),"Helvetica-Bold",),
                        ("BACKGROUND",(0, 0),(-1, 0),colors.lightgrey,),
                    ]))
            story.append(table)
            story.append(PageBreak())
    if not feuille_bdp_trouvee:
        logger.warning("[RAG-BDP] Aucun BDP détecté dans %s", file_path)
        return None
    doc.build(story)
    logger.info("[RAG-BDP] PDF généré : %s", output_pdf)
    return output_pdf
    
def traiter_extraction_rag(file_path: str, extracted_root: str, tender_relative_path: str) -> Dict[str, Any]:
    """
    Pipeline complet d'extraction documentaire RAG.
    1. Ré-extrait le document source.
    2. Détecte les modèles.
    3. Extrait les modèles en PDF.
    4. Extrait les BDP Excel en PDF.
    5. Retourne le texte intégral pour le RAG.
    """
    extraction = extraire_document_complet_pour_rag(file_path)
    texte_complet = extraction.get("text","")
    detected_types = extraction.get("detected_types",[])
    zones_administratives = []

    extension = Path(file_path).suffix.lower()

    if extension == ".pdf":

        zones_administratives = (
            extraire_zones_administratives_pdf_complet(file_path))

    extraction["administrative_zones"] = zones_administratives
    output_base = (Path(extracted_root)/ tender_relative_path)
    output_base.mkdir(parents=True,exist_ok=True)
    fichiers_extraits = []
    extension = Path(file_path).suffix.lower()

    if extension == ".pdf":
        for type_document in detected_types:
            dossier_type = (output_base/ type_document)
            dossier_type.mkdir(parents=True,exist_ok=True)

        model_files = extraire_pages_modeles_pdf(source_pdf=file_path, output_dir=str(output_base),types_a_extraire=detected_types, contexte_pages=1,)

        # Replacer chaque fichier dans son propre dossier
        for item in model_files:
            type_document = item["type"]
            source = Path(item["path"])
            destination_dir = (output_base/ type_document)
            destination_dir.mkdir(parents=True,exist_ok=True)
            destination = (destination_dir/ f"{type_document}.pdf")
            if source.exists():
                shutil.move(str(source), str(destination))
                item["path"] = str(destination)
                fichiers_extraits.append(item)

    elif extension in [".xls",".xlsx",".xlsm",]:
        contenu = normaliser_texte_detection(texte_complet)
        types_excel = detecter_types_documents(contenu)
        if any(x in types_excel for x in ["BDP","BPU","DPGF",]):
            dossier_bdp = (output_base/ "BDP")
            dossier_bdp.mkdir(parents=True,exist_ok=True)
            output_pdf = (dossier_bdp/ "BDP.pdf")
            pdf_bdp = extraire_bdp_excel_vers_pdf(file_path,str(output_pdf))
            if pdf_bdp:
                fichiers_extraits.append({"type": "BDP","path": pdf_bdp})

    extraction["extracted_files"] = fichiers_extraits
    extraction["extracted_root"] = str(output_base)
    extraction["administrative_zone_count"] = (len(zones_administratives))

    logger.info("[RAG-EXTRACT] Extraction terminée : %s | %s fichiers modèles générés | %s zones administratives détectées", Path(file_path).name, len(fichiers_extraits), len(zones_administratives))
    return extraction  
    
def normaliser_texte_zone(text: str) -> str:
    """
    Normalisation légère utilisée uniquement pour la détection
    des zones administratives.
    """
    if not text:
        return ""
    text = text.lower()
    replacements = {"é": "e","è": "e","ê": "e","ë": "e","à": "a", "â": "a","î": "i","ï": "i","ô": "o","ù": "u","û": "u","ç": "c",}

    for src, dst in replacements.items():
        text = text.replace(src, dst)

    text = re.sub(r"\s+", " ", text)
    return text.strip()    
    
def determiner_type_zone(text: str) -> Optional[str]:
    text_norm = normaliser_texte_zone(text)
    if not text_norm:
        return None
    if any(normaliser_texte_zone(keyword) in text_norm for keyword in ZONE_SIGNATURE_KEYWORDS):
        return "SIGNATURE_CACHET"
    if any(normaliser_texte_zone(keyword) in text_norm for keyword in ZONE_VALIDATION_KEYWORDS):
        return "VISA_APPROBATION"
    if "fait a" in text_norm or "le :" in text_norm or "le:" in text_norm:
        return "DATE_LIEU"
    return None    
    
def detecter_rectangles_page(page: fitz.Page) -> List[fitz.Rect]:
    """
    Détecte les rectangles / grandes zones graphiques présents sur une page PDF.
    Utile pour identifier les cases de signature, visa, approbation, etc.
    """
    rectangles = []
    try:
        drawings = page.get_drawings()
        for drawing in drawings:
            rect = drawing.get("rect")
            if not rect:
                continue
            rect = fitz.Rect(rect)
            # Éliminer les petits éléments graphiques
            if rect.width < 80 or rect.height < 30:
                continue
            # Éliminer les énormes rectangles correspondant éventuellement à toute la page
            if rect.width > page.rect.width * 0.98 and rect.height > page.rect.height * 0.98:
                continue
            rectangles.append(rect)
    except Exception as e:
        logger.warning("[RAG][ZONE] Impossible de détecter les rectangles : %s", e)
    return rectangles

def detecter_zones_administratives_pdf(page: fitz.Page,page_number: int) -> List[Dict[str, Any]]:
    """
    Détecte les zones administratives importantes d'une page :
    - signature- cachet- visa- approbation- lu et accepté- fait à / le- zones de validation
    Retourne également la page et les coordonnées.
    """
    zones = []

    # 1. Récupération des blocs texte
    text_dict = page.get_text("dict")
    text_blocks = []
    for block in text_dict.get("blocks", []):
        if block.get("type") != 0:
            continue
        block_text_parts = []
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                txt = span.get("text", "").strip()
                if txt:
                    block_text_parts.append(txt)
        block_text = " ".join(block_text_parts).strip()
        if not block_text:
            continue
        bbox = fitz.Rect(block["bbox"])
        text_blocks.append({"text": block_text,"bbox": bbox})

    # 2. Détection des rectangles
    rectangles = detecter_rectangles_page(page)
    # 3. Recherche des libellés administratifs
    for block in text_blocks:
        zone_type = determiner_type_zone(block["text"])
        if not zone_type:
            continue
        label_rect = block["bbox"]
        # Recherche d'une case contenant le libellé
        meilleure_case = None
        meilleur_score = 0
        for rect in rectangles:
            # Le rectangle doit contenir ou être proche du libellé.
            centre_x = rect.x0 + rect.width / 2
            centre_y = rect.y0 + rect.height / 2
            if rect.contains(label_rect):
                score = 100
            else:
                distance = abs(centre_y - (label_rect.y0 + label_rect.height / 2))
                if distance < 150:
                    score = max(0, 80 - distance / 2)
                else:
                    score = 0
            if score > meilleur_score:
                meilleur_score = score
                meilleure_case = rect

        # Si une case a été trouvée
        if meilleure_case:
            zone_rect = meilleure_case
        else:
            # Fallback : zone autour du texte
            zone_rect = fitz.Rect(max(0, label_rect.x0 - 20),max(0, label_rect.y0 - 20),min(page.rect.width, label_rect.x1 + 200),min(page.rect.height, label_rect.y1 + 150))
        zones.append({
            "page_number": page_number,
            "type": zone_type,
            "label": block["text"],
            "bbox": [round(zone_rect.x0, 2),round(zone_rect.y0, 2),round(zone_rect.x1, 2),round(zone_rect.y1, 2)],
            "source": "PYMUPDF_TEXT_AND_DRAWINGS",
            "is_signature_zone": zone_type == "SIGNATURE_CACHET",
            "is_validation_zone": zone_type == "VISA_APPROBATION",
            "is_date_zone": zone_type == "DATE_LIEU",
        })
    return zones

def ocr_page_complete_avec_positions(page: fitz.Page, zoom: float = 2.0) -> List[Dict[str, Any]]:
    """
    OCR complet d'une page avec conservation des coordonnées des textes détectés.
    Utilisé uniquement pour les documents scannés.
    """
    resultats = []
    try:
        mat = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat,alpha=False)
        img = np.frombuffer(pix.samples,dtype=np.uint8).reshape(pix.height,pix.width,3)
        gray = cv2.cvtColor(img,cv2.COLOR_BGR2GRAY)
        engine = _get_onnx_ocr_engine()
        if engine is None:
            return []
        result, _ = engine(gray)
        if not result:
            return []
        for item in result:
            if len(item) < 3:
                continue
            points = item[0]
            text = str(item[1]).strip()
            confidence = float(item[2])
            if not text:
                continue
            if confidence < 0.40:
                continue
            xs = [float(point[0]) for point in points]
            ys = [float(point[1]) for point in points]
            x0 = min(xs) / zoom
            y0 = min(ys) / zoom
            x1 = max(xs) / zoom
            y1 = max(ys) / zoom

            resultats.append({
                "text": text,
                "confidence": confidence,
                "bbox": [round(x0, 2),round(y0, 2),round(x1, 2),round(y1, 2)]
            })
    except Exception as e:
        logger.error("[RAG][OCR] Erreur OCR page complète : %s",e,exc_info=True)
    return resultats    
    
def detecter_zones_administratives_scan(page: fitz.Page,page_number: int) -> List[Dict[str, Any]]:
    ocr_items = ocr_page_complete_avec_positions(page)

    if not ocr_items:
        return []
    zones = []
    for item in ocr_items:
        text = item["text"]
        zone_type = determiner_type_zone(text)
        if not zone_type:
            continue
        bbox = item["bbox"]

        # Agrandir la zone autour du libellé pour couvrir la case de signature/visa.
        x0, y0, x1, y1 = bbox
        zone_rect = fitz.Rect(max(0, x0 - 30),max(0, y0 - 30),min(page.rect.width, x1 + 250),min(page.rect.height, y1 + 180))
        zones.append({
            "page_number": page_number,
            "type": zone_type,
            "label": text,
            "bbox": [round(zone_rect.x0, 2),round(zone_rect.y0, 2),round(zone_rect.x1, 2),round(zone_rect.y1, 2)],
            "source": "RAPIDOCR_ONNX",
            "confidence": item["confidence"],
            "is_signature_zone": zone_type == "SIGNATURE_CACHET",
            "is_validation_zone": zone_type == "VISA_APPROBATION",
            "is_date_zone": zone_type == "DATE_LIEU",
        })
    return zones
    
def detecter_zones_administratives(page: fitz.Page,page_number: int) -> List[Dict[str, Any]]:
    # Tentative 1 : texte natif
    zones = detecter_zones_administratives_pdf(page=page,page_number=page_number)
    if zones:
        logger.info("[RAG][ZONES] Page %s : %s zone(s) détectée(s) via texte natif.",page_number,len(zones))
        return zones
    # Tentative 2 : document scanné
    zones = detecter_zones_administratives_scan(page=page,page_number=page_number)
    if zones:
        logger.info("[RAG][ZONES] Page %s : %s zone(s) détectée(s) via OCR.",page_number,len(zones))
    return zones
    
def extraire_zones_administratives_pdf_complet(file_path: str) -> List[Dict[str, Any]]:
    """
    Analyse toutes les pages d'un PDF afin de détecter les zones administratives utiles au workflow de génération :
    - signatures - cachets - visas - approbations - acceptations - dates / lieux - zones de validation
    Pour chaque zone, on conserve : page_number - type - label - bbox - source - confiance éventuelle
    """

    zones_detectees = []
    try:
        doc = fitz.open(file_path)
        logger.info("[RAG][ZONES] Analyse administrative : %s pages | %s", len(doc), Path(file_path).name)

        for page_index in range(len(doc)):
            page = doc[page_index]
            page_number = page_index + 1
            zones_page = detecter_zones_administratives(page=page, page_number=page_number)

            if zones_page:
                zones_detectees.extend(zones_page)
                logger.info("[RAG][ZONES] Page %s : %s zone(s)", page_number, len(zones_page))

        doc.close()

    except Exception as e:
        logger.error("[RAG][ZONES] Erreur analyse zones administratives : %s", e, exc_info=True)

    logger.info("[RAG][ZONES] Total détecté : %s zone(s)", len(zones_detectees))

    return zones_detectees