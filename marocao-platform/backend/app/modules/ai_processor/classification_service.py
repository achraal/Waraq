import os, shutil, time, logging, re
from pathlib import Path
from collections import defaultdict
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from backend.app.database.connection import SessionLocal
from pypdf import PdfReader, PdfWriter
from backend.app.database.models import TenderDocument, Tender, ClassificationAuditLog
#from backend.app.modules.ai_processor.ocr_engine import extraire_texte_premiere_page, extraire_texte_page_pdf
from backend.app.modules.ai_processor.llm_analyzer import classifier_texte_document, classifier_page_pour_decoupage
from backend.app.modules.ai_processor.learning_service import WaraqLearningEngine
from backend.app.modules.ai_processor.ocr_engine import extraire_texte_integral, extraire_texte_page_pdf, extraire_ocr_pdf_page, optimiser_image_pour_analyse

# Configuration du logger pour ce module
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Optionnel mais ultra efficace : ajoute un Handler pour être sûr que ça sorte dans ton terminal
if not logger.handlers:
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    # Remplacement de %(name)s par un label plus court et propre : [CLASSIFICATION]
    formatter = logging.Formatter('%(asctime)s - [CLASSIFICATION] - %(levelname)s - %(message)s')
    ch.setFormatter(formatter)
    logger.addHandler(ch)

# DOSSIER DE BASE ABSOLU
BASE_STORAGE_DIR = Path(r"C:\Users\achra\Desktop\Intern\Project\marocao-platform\data_storage")
TEMP_DIR = BASE_STORAGE_DIR / "temp_splits"
TEMP_DIR.mkdir(parents=True, exist_ok=True)

def nettoyer_nom_type(type_str: str) -> str:
    """Nettoie et sécurise les libellés de types pour les chemins de fichiers et BDD."""
    if not type_str:
        return "INCONNU"
    # Remplace les caractères invalides par des underscores sans casser les espaces composés (ex: BORDEREAU_PRIX)
    clean = re.sub(r'[\\/*?:"<>|]', '_', str(type_str).strip())
    clean = re.sub(r'\s+', '_', clean)
    return clean.upper()
    
def construire_metadata_standard(
    method: str,
    confidence: int = 5,
    keywords: list = None,
    language: str = "fr",
    text_length: int = 0,
    word_count: int = 0,
    extra_metrics: dict = None
) -> dict:
    base_metadata = {
        "model": extra_metrics.get("model", method) if extra_metrics else method,
        "confidence_score": confidence,
        "extracted_keywords": keywords or [],
        "detected_language": language,
        "text_length_chars": text_length,
        "text_word_count": word_count,
        "is_short_text": word_count < 20,
        "has_uncertainty_keywords": False,
        "ollama_total_duration": extra_metrics.get("ollama_total_duration") if extra_metrics else None,
        "load_duration": extra_metrics.get("load_duration") if extra_metrics else None,
        "prompt_tokens": extra_metrics.get("prompt_tokens") if extra_metrics else None,
        "generated_tokens": extra_metrics.get("generated_tokens") if extra_metrics else None,
        "validation_status": "PENDING",
        "is_correct": None,
        "corrected_type": None
    }
    if extra_metrics:
        for k, v in extra_metrics.items():
            if v is not None or k not in base_metadata:
                base_metadata[k] = v
    return base_metadata

def determiner_type_par_ia(file_path: str, ext: str, nom_fichier: str, contexte_few_shot: str, doc_id: str, db: Session ) -> tuple[str, str, str, dict]:
    valeur_par_defaut = nom_fichier.upper()
    logger.info(f"[IA] Début de l'analyse du document pour classification : {nom_fichier}")
    try:
        chemin_a_analyser = file_path
        if ext in [".jpg", ".jpeg", ".png", ".tiff", ".bmp"]:
            chemin_a_analyser = optimiser_image_pour_analyse(file_path, max_side=2048)
            
        try:
            texte_p1 = extraire_texte_integral(chemin_a_analyser)
        finally:
            # Nettoyage si un fichier temporaire _opti a été généré
            if chemin_a_analyser != file_path and os.path.exists(chemin_a_analyser):
                try:
                    os.remove(chemin_a_analyser)
                except Exception:
                    pass
                    
        if not texte_p1 or not texte_p1.strip():
            meta_fallback = construire_metadata_standard(method="IA_FALLBACK_TEXTE_VIDE", confidence=1)
            logger.warning(f"[IA] Texte extrait de la première page vide pour : {nom_fichier}")
            log_vide = ClassificationAuditLog(
                document_id=doc_id,
                predicted_type="TEXTE_VIDE",
                classification_reason="Le texte extrait de la première page est vide.",
                model_used="none",
                validation_status="FAILED",
                text_length_chars=0,
                text_word_count=0
            )
            db.add(log_vide)
            return valeur_par_defaut, "IA_FALLBACK_TEXTE_VIDE", "Le texte extrait est vide.", meta_fallback
            
        logger.info(f"[IA] Envoi du texte extrait à Qwen pour {nom_fichier}...")
        res_ia = classifier_texte_document(texte_p1, contexte_few_shot)
        
        type_extrait = "INCONNU"
        description_extraite = ""
        metrics_extraites = {}
        
        if isinstance(res_ia, tuple):
            logger.info(f"[IA] llm_analyzer a renvoyé un tuple : {res_ia}")
            type_extrait = res_ia[0] if len(res_ia) > 0 else "INCONNU"
            description_extraite = res_ia[1] if len(res_ia) > 1 else ""
            metrics_extraites = res_ia[2] if len(res_ia) > 2 else {}
        elif isinstance(res_ia, str):
            type_extrait = res_ia
            description_extraite = "Classifié par analyse de contenu."
        langue_ia = metrics_extraites.get("detected_language", "fr") if metrics_extraites else "fr"
            
        metrics_complete = construire_metadata_standard(
            method="QWEN_LLM",
            language=langue_ia,
            text_length=len(texte_p1),
            word_count=len(texte_p1.split()),
            extra_metrics=metrics_extraites
        )

        t_clean = nettoyer_nom_type(type_extrait)
        # === CRÉATION DU LOG D'AUDIT EN BDD ===
        # Remarque : db est ta session SQLAlchemy courante
        log_audit = ClassificationAuditLog(
            document_id=doc_id,  # L'ID du TenderDocument en cours
            predicted_type=t_clean if t_clean != "INCONNU" else type_extrait,
            classification_reason=description_extraite,
            confidence_score=metrics_extraites.get("confidence_score"),
            detected_language=langue_ia,
            extracted_keywords=metrics_extraites.get("extracted_keywords"),
            model_used=metrics_extraites.get("model", "qwen"),
            execution_duration_sec=metrics_extraites.get("ollama_total_duration"),
            prompt_tokens=metrics_extraites.get("prompt_tokens"),
            generated_tokens=metrics_extraites.get("generated_tokens"),
            text_length_chars=len(texte_p1),
            text_word_count=len(texte_p1.split()),
            has_uncertainty_keywords=metrics_extraites.get("has_uncertainty_keywords", False),
            validation_status="PENDING"
        )
        db.add(log_audit)
        # =======================================
        if t_clean != "INCONNU":
            logger.info(f"[IA] Succès : Qwen a classifié le document en '{t_clean}'")
            return t_clean, "CLASSIFICATION_IA_QWEN", description_extraite, metrics_complete
            
        logger.warning(f"[IA] Qwen a renvoyé 'INCONNU' ou un échec pour {nom_fichier}. Utilisation du nom par défaut.")
        return valeur_par_defaut, "IA_FALLBACK_INCONNU", description_extraite, metrics_complete
    except Exception as e:
        logger.error(f"[IA] Crash de l'analyse IA pour {nom_fichier}: {str(e)}", exc_info=True)
        meta_crash = construire_metadata_standard(method="IA_CRASH_FALLBACK", confidence=1)
        
        # === Logger aussi le crash en BDD ===
        try:
            log_crash = ClassificationAuditLog(
                document_id=doc_id,
                predicted_type="CRASH_ERROR",
                classification_reason=f"Erreur lors de l'analyse : {str(e)}",
                model_used="qwen",
                validation_status="FAILED"
            )
            db.add(log_crash)
        except Exception as log_err:
            logger.error(f"[IA] Impossible d'ajouter le log de crash à la session BDD: {str(log_err)}")
        
        return valeur_par_defaut, "IA_CRASH_FALLBACK", f"Erreur lors de l'analyse : {str(e)}", meta_crash

def appliquer_types_primitifs(nom_fichier: str, ext: str) -> str | None:
    f_norm = nom_fichier.lower().strip()
    ext_norm = ext.lower().strip()

    # 1. Extensions explicites (Tableurs Excel)
    if ext_norm in [".xlsx", ".xls", ".xlsm"]:
        return "BORDEREAU_PRIX"
        
    # 2. Fichiers SIG / Annexes
    if ext_norm in [".jgw", ".tfw", ".pgw", ".xml", ".dbf", ".prj"]:
        return "AUTRE"

    # --- RECHERCHE PAR MOTS-CLÉS (DÉTECTION N'IMPORTE OÙ DANS LE NOM) ---

    # ACTE D'ENGAGEMENT / ACTE ENGAGEMENT
    # Capture: "acte d'engagement", "acte d engagement", "acte engagement", "acte_engagement", "acte-engagement"
    if re.search(r"acte[\s\-_]*(d['\s]?)?engagement", f_norm):
        return "ACTE_ENGAGEMENT"

    # DECLARATION SUR L'HONNEUR
    if re.search(r"declaration\s*sur\s*l['\s]?honneur", f_norm):
        return "DECLARATION_HONNEUR"
        
    # CPS / CAHIER DES PRESCRIPTIONS SPÉCIALES
    # Capture: cps, ccftp, ccatp, ccafp, cctp ou expressions complètes
    if re.search(r"\b(cps|ccftp|ccatp|ccafp|cctp)\b|cahier\s+des?\s+prescriptions?\s+sp[eé]ciales?", f_norm):
        return "CPS"

    # RC / RÈGLEMENT DE CONSULTATION
    # Capture: "rc", "reglement de la consultation", "reglement de consultation", "reglement consultation"
    if re.search(r"\brc\b|r[eèg]glement\s*(de\s*(la\s*)?)?consultation", f_norm):
        return "RC"

    # BORDEREAU DE PRIX / BDR / BP
    # Capture: "bdr", "bp" (mot isolé), "bordereau"
    if re.search(r"\b(bdr|bp)\b|bordereau", f_norm):
        return "BORDEREAU_PRIX"

    # AVIS EN FRANÇAIS
    # Capture: "avis fr", "avis-fr", "avis en francais", "avis en français"
    if re.search(r"avis[\s\-_]*fr|avis\s+en\s+fran[cç]ais", f_norm):
        return "AVIS_FRANCAIS"

    # AVIS EN ARABE
    # Capture: "avis ar", "avis-ar", "avis en arabe"
    if re.search(r"avis[\s\-_]*ar|avis\s+en\s+arabe", f_norm):
        return "AVIS_ARABE"

    # AVIS GÉNÉRIQUE
    if re.search(r"\bavis\b", f_norm):
        return "AVIS"
    return None

def verifier_et_decouper_pdf(file_path: str, nom_fichier: str, type_parent: str) -> list:
    """
    Parcourt l'intégralité des pages du PDF pour détecter et extraire les sous-documents 
    imbriqués (ex: Bordereau de Prix de 1 page à la fin d'un CPS de 50 pages).
    """
    try:
        reader = PdfReader(file_path)
        nb_pages = len(reader.pages)
        
        logger.info(f"[DECOUPAGE] Analyse du PDF : '{nom_fichier}' ({nb_pages} page(s) au total)")
        
        # 1. Inutile de chercher un découpage sur un document très court
        if nb_pages <= 3:
            logger.info(f"[DECOUPAGE] Document trop court ({nb_pages} pages). Aucun découpage nécessaire.")
            return []

        # 2. VÉRIFICATION FAST SCAN : Si c'est un scan (< 100 car. natifs sur les 3 premières pages)
        # On évite d'exécuter PaddleOCR 20+ fois
        texte_test = "".join([reader.pages[i].extract_text() or "" for i in range(min(3, nb_pages))])
        if len(texte_test.strip()) < 100:
            logger.warning(f"[DECOUPAGE SAUTÉ] '{nom_fichier}' est un PDF scanné. Découpage OCR ignoré pour préserver les performances.")
            return []

        logger.info(f"[DECOUPAGE] Début du scan page par page...")
        
        pages_types = []
        types_detectes = set()

        # 3. Analyse page par page sur l'ENSEMBLE du document (Texte natif uniquement)
        for idx in range(nb_pages):
            txt_page = extraire_texte_page_pdf(file_path, idx, reader)
            
            # Si une page native est vide, on garde le type parent au lieu de lancer un OCR lourd
            if not txt_page or not txt_page.strip():
                type_page = type_parent
            else:
                type_page = classifier_page_pour_decoupage(txt_page)
            
            # Anti-INCONNU : si la page est indéterminée, elle hérite du type global du document
            if type_page == "INCONNU":
                type_page = type_parent
            
            pages_types.append(type_page)
            types_detectes.add(type_page)

        # 4. Vérification de l'homogénéité du document
        if len(types_detectes) <= 1:
            logger.info(f"[DECOUPAGE] Document 100% homogène ({list(types_detectes)[0]}). Aucun sous-document détecté.")
            return []

        logger.info(f"[DECOUPAGE] Détection de plusieurs types distincts : {list(types_detectes)}. Regroupement des pages...")

        # 5. Regroupement de TOUTES les pages par type (gestion des pages non contiguës)
        pages_par_type = defaultdict(list)
        for p_idx, t_seg in enumerate(pages_types):
            t_clean = t_seg if t_seg != "INCONNU" else type_parent
            pages_par_type[t_clean].append(p_idx)

        # Si toutes les pages ont le même type final, annulation du découpage
        if len(pages_par_type) <= 1:
            logger.info(f"[DECOUPAGE] Annulation du découpage : le document est 100% homogène.")
            return []

        # 6. Extraction physique des fichiers découpés
        logger.info(f"[DECOUPAGE] Génération de {len(pages_par_type)} sous-document(s) unique(s) par type...")
        fichiers_divises = []

        for idx, (type_clean, page_indices) in enumerate(pages_par_type.items()):
            writer = PdfWriter()
            for p_num in page_indices:
                writer.add_page(reader.pages[p_num])

            nom_split = f"split_{idx}_{type_clean}_{nom_fichier}"
            chemin_split = os.path.join(TEMP_DIR, nom_split)

            with open(chemin_split, "wb") as f:
                writer.write(f)

            fichiers_divises.append((type_clean, chemin_split))
            pages_humaines = [p + 1 for p in page_indices]
            logger.info(f"[DECOUPAGE] Sous-document {idx + 1}/{len(pages_par_type)} créé : '{nom_split}' (Type: '{type_clean}', Pages: {pages_humaines})")

        return fichiers_divises

    except Exception as e:
        logger.error(f"[DECOUPAGE] Échec lors de l'analyse ou du découpage de '{nom_fichier}': {e}", exc_info=True)
        return []

        # 5. Regroupement des plages de pages contiguës
        # segments = []
        # dep = 0
        # type_actuel = pages_types[0]

        # for idx in range(1, nb_pages):
            # if pages_types[idx] != type_actuel:
                # segments.append((type_actuel, dep, idx))
                # logger.info(f"[DECOUPAGE] Segment identifié : '{type_actuel}' du début (page {dep + 1}) à la page {idx}")
                # type_actuel = pages_types[idx]
                # dep = idx
                
        # Ajouter le dernier segment
        # segments.append((type_actuel, dep, nb_pages))
        # logger.info(f"[DECOUPAGE] Segment identifié : '{type_actuel}' de la page {dep + 1} à la page {nb_pages}")

        # if len(segments) <= 1:
            # logger.info(f"[DECOUPAGE] Annulation du découpage : tous les blocs se réduisent à une seule entité.")
            # return []

        # 6. Extraction physique des fichiers découpés
        # logger.info(f"[DECOUPAGE] Génération de {len(segments)} sous-document(s) sur le disque...")
        # fichiers_divises = []

        # for idx, (type_seg, p_start, p_end) in enumerate(segments):
            # type_clean = type_seg if type_seg != "INCONNU" else type_parent
            
            # writer = PdfWriter()
            # for p_num in range(p_start, p_end):
                # writer.add_page(reader.pages[p_num])

            # nom_split = f"split_{idx}_{type_clean}_{nom_fichier}"
            # chemin_split = os.path.join(TEMP_DIR, nom_split)

            # with open(chemin_split, "wb") as f:
                # writer.write(f)

            # fichiers_divises.append((type_clean, chemin_split))
            # logger.info(f"[DECOUPAGE] Sous-document {idx + 1}/{len(segments)} créé : '{nom_split}' (Type: '{type_clean}', Pages {p_start + 1} à {p_end})")

        # return fichiers_divises

    # except Exception as e:
        # logger.error(f"[DECOUPAGE] Échec lors de l'analyse ou du découpage de '{nom_fichier}': {e}", exc_info=True)
        # return []

# def verifier_et_decouper_pdf(file_path: str, nom_fichier: str, type_parent: str) -> list:
#     """
#     Parcourt l'intégralité des pages du PDF pour détecter et extraire les sous-documents 
#     imbriqués (ex: Bordereau de Prix de 1 page à la fin d'un CPS de 50 pages).
#     """
#     try:
#         reader = PdfReader(file_path)
#         nb_pages = len(reader.pages)
        
#         logger.info(f"[DECOUPAGE] Analyse du PDF : '{nom_fichier}' ({nb_pages} page(s) au total)")
        
#         # Inutile de chercher un découpage sur un document très court
#         if nb_pages <= 3:
#             logger.info(f"[DECOUPAGE] Document trop court ({nb_pages} pages). Aucun découpage nécessaire.")
#             return []

#         logger.info(f"[DECOUPAGE] Début du scan page par page...")
        
#         pages_types = []
#         types_detectes = set()

#         # 1. Analyse page par page sur l'ENSEMBLE du document
#         for idx in range(nb_pages):
#             txt_page = extraire_texte_page_pdf(file_path, idx, reader)
            
#             # Fallback OCR si la page est scannée ou vide
#             if not txt_page or not txt_page.strip():
#                 logger.debug(f"[DECOUPAGE] Page {idx + 1}/{nb_pages} vide/scannée -> Passage à l'OCR")
#                 txt_page = extraire_ocr_pdf_page(file_path, idx)

#             type_page = classifier_page_pour_decoupage(txt_page)
            
#             # Anti-INCONNU : si la page est indéterminée, elle hérite du type global du document
#             if type_page == "INCONNU":
#                 type_page = type_parent
#                 type_page_clean = nettoyer_nom_type(type_page)
#                 logger.debug(f"[DECOUPAGE] Page {idx + 1}/{nb_pages} : Type ambigu -> Héritage du type parent '{type_parent}'")
#             else:
#                 logger.info(f"[DECOUPAGE] Page {idx + 1}/{nb_pages} : Type détecté -> '{type_page}'")
            
#             pages_types.append(type_page)
#             types_detectes.add(type_page)

#         # 2. Vérification de l'homogénéité du document
#         if len(types_detectes) <= 1:
#             logger.info(f"[DECOUPAGE] Document 100% homogène ({list(types_detectes)[0]}). Aucun sous-document détecté.")
#             return []

#         logger.info(f"[DECOUPAGE] Détection de plusieurs types distincts : {list(types_detectes)}. Regroupement des pages...")

#         # 3. Regroupement des plages de pages contiguës
#         segments = []
#         dep = 0
#         type_actuel = pages_types[0]

#         for idx in range(1, nb_pages):
#             if pages_types[idx] != type_actuel:
#                 segments.append((type_actuel, dep, idx))
#                 logger.info(f"[DECOUPAGE] Segment identifié : '{type_actuel}' du début (page {dep + 1}) à la page {idx}")
#                 type_actuel = pages_types[idx]
#                 dep = idx
                
#         # Ajouter le dernier segment
#         segments.append((type_actuel, dep, nb_pages))
#         logger.info(f"[DECOUPAGE] Segment identifié : '{type_actuel}' de la page {dep + 1} à la page {nb_pages}")

#         # Si le regroupement n'a donné qu'un seul bloc, pas besoin de fichier split
#         if len(segments) <= 1:
#             logger.info(f"[DECOUPAGE] Annulation du découpage : tous les blocs se réduisent à une seule entité.")
#             return []

#         # 4. Extraction physique des fichiers découpés
#         logger.info(f"[DECOUPAGE] Génération de {len(segments)} sous-document(s) sur le disque...")
#         fichiers_divises = []
#         base_dir = os.path.dirname(file_path)

#         for idx, (type_seg, p_start, p_end) in enumerate(segments):
#             # Sécurité supplémentaire contre le mot-clé INCONNU
#             type_clean = type_seg if type_seg != "INCONNU" else type_parent
            
#             writer = PdfWriter()
#             for p_num in range(p_start, p_end):
#                 writer.add_page(reader.pages[p_num])

#             nom_split = f"split_{idx}_{type_clean}_{nom_fichier}"
#             #chemin_split = os.path.join(base_dir, nom_split)
#             chemin_split = os.path.join(TEMP_DIR, nom_split)

#             with open(chemin_split, "wb") as f:
#                 writer.write(f)

#             fichiers_divises.append((type_clean, chemin_split))
#             logger.info(f"[DECOUPAGE] Sous-document {idx + 1}/{len(segments)} créé : '{nom_split}' (Type: '{type_clean}', Pages {p_start + 1} à {p_end})")

#         return fichiers_divises

#     except Exception as e:
#         logger.error(f"[DECOUPAGE] Échec lors de l'analyse ou du découpage de '{nom_fichier}': {e}", exc_info=True)
#         return []


def executer_classification_post_scraping():
    """Parcourt la base de données en regroupant le traitement par Appel d'Offres (Tender) 
    qui possède des documents non classifiés.
    """
    db = SessionLocal()
    try:
        logger.info("=== DÉMARRAGE DU PIPELINE DE CLASSIFICATION POST-SCRAPING ===")
        global_start_time = time.time()
        total_lignes_traitees = 0

        # OPTION A : Extraction de TOUTES les corrections humaines de la BDD (limite=None)
        logger.info("[OPTION A] Chargement de l'historique complet des corrections utilisateur...")
        contexte_few_shot = WaraqLearningEngine.obtenir_exemples_few_shot(db, limite=None)

        # 1. Récupération des Tenders uniques qui ont au moins un document non classifié
        # 1. Sous-requête pour récupérer les IDs uniques des Tenders qui ont des documents non classifiés
        subquery = (
            db.query(TenderDocument.tender_id)
            .filter(TenderDocument.is_classified == False)
            .distinct()
            #.subquery()
            .scalar_subquery()
        )
        
        # Récupération des Tenders correspondants (sans DISTINCT global sur l'objet Tender)
        tenders_a_traiter = (
            db.query(Tender)
            #.filter(Tender.id.in_(subquery))
            .filter(Tender.id.in_(subquery))
            .all()
        )
        
        total_tenders = len(tenders_a_traiter)
        logger.info(f"{total_tenders} dossier(s) d'appel d'offres trouvé(s) avec des documents en attente.")
        
        # 2. Boucle principale sur chaque Dossier (Tender)
        for index_tender, tender in enumerate(tenders_a_traiter, start=1):
            try:
                # Récupération de tous les documents non classifiés propres à CE tender précis
                docs_du_tender = (
                    db.query(TenderDocument)
                    .filter(TenderDocument.tender_id == tender.id, TenderDocument.is_classified == False)
                    .all()
                )
                total_docs_du_tender = len(docs_du_tender)
                
                # --- CONFIGURATION CHEMINS CHRONOLOGIQUES & NOM DOSSIER ---
                date_ref = tender.extraction_date or datetime.now(timezone.utc)
                annee = date_ref.strftime('%Y')
                mois = date_ref.strftime('%m')
                jour = date_ref.strftime('%d')
                heure_ref = date_ref.strftime('%H-%M-%S')

                ref_propre = tender.reference.strip().replace("/", "-").replace("\\", "-")
                ref_propre = re.sub(r'[?:"<>|*]', '_', ref_propre)

                nom_dossier_offre = f"{ref_propre}_{heure_ref}"
                identifiant_dossier = os.path.join(annee, mois, jour, nom_dossier_offre)
                
                # Log d'entête pour le dossier en cours
                logger.info(f"[{index_tender}/{total_tenders}] Traitement Dossier : {nom_dossier_offre} ({total_docs_du_tender} document(s) à classifier)")
                
                # 3. Boucle secondaire sur les documents de ce tender
                for index_doc, doc in enumerate(docs_du_tender, start=1):
                    try:
                        if not os.path.exists(doc.file_path):
                            logger.error(f"   -> [Doc {index_doc}/{total_docs_du_tender}] Erreur : Fichier introuvable sur le disque : {doc.file_path}")
                            continue

                        doc_start_time = time.time()
                        total_lignes_traitees += 1
                            
                        nom_fichier = doc.file_name
                        chemin_original = doc.file_path
                        _, ext = os.path.splitext(nom_fichier.lower().strip())
                        
                        # Log d'avancement pour le document au sein de son dossier
                        logger.info(f"   -> [Doc {index_doc}/{total_docs_du_tender}] Fichier : {nom_fichier}")
                        
                        description_classification = ""
                        maintenant = datetime.now(timezone.utc)
                        
                        # 1. Étape Primitives
                        type_document = appliquer_types_primitifs(nom_fichier, ext)
                        if type_document:
                            raison_classification = "REGLES_PRIMITIVES"
                            description_classification = f"Classifié automatiquement selon les règles de nommage primitives pour l'extension ou le préfixe."
                            langue_detectee = "ar" if type_document == "AVIS_ARABE" else "fr"
                            metrics_ia = construire_metadata_standard(
                                method="PRIMITIVE_RULES",
                                confidence=5,
                                keywords=[type_document.lower(), ext.replace(".", "")],
                                language=langue_detectee
                            )
                            logger.info(f"      -> Classifié par règles primitives : '{type_document}'")
                            log_primitive = ClassificationAuditLog(
                                document_id=doc.id,
                                predicted_type=type_document,
                                classification_reason="Règles primitives de nommage.",
                                model_used="primitive_rules",
                                validation_status="PENDING"
                            )
                            db.add(log_primitive)
                        else:
                            # 2. Étape Fallback IA
                            logger.info("      -> Aucune règle primitive validée. Passage à la détection de contenu...")
                            type_document, raison_classification, description_classification, metrics_ia = determiner_type_par_ia(
                                chemin_original, ext, nom_fichier, contexte_few_shot, doc.id, db
                            )

                        #t_clean = str(type_document).strip().replace(":", " ").replace("/", " ").split()[0].upper()
                        t_clean = nettoyer_nom_type(type_document)

                        # 3. Étape Découpage PDF
                        fichiers_finaux = verifier_et_decouper_pdf(chemin_original, nom_fichier, t_clean) if ext == ".pdf" else []     
                        est_un_split = len(fichiers_finaux) > 1

                        if not fichiers_finaux:
                            fichiers_finaux = [(t_clean, chemin_original)]

                        # 4. Déplacement physique, mise à jour BDD et Nettoyage
                        for idx, (t_final, path_source) in enumerate(fichiers_finaux):
                            #t_final_clean = str(t_final).strip().replace(":", " ").replace("/", " ").split()[0].upper()
                            t_final_clean = nettoyer_nom_type(t_final)
                            
                            dossier_cible = BASE_STORAGE_DIR / "classified" / identifiant_dossier / t_final_clean
                            os.makedirs(dossier_cible, exist_ok=True)
                            
                            nom_final_fichier = nom_fichier if not est_un_split else f"{t_final_clean}_{idx}_{nom_fichier}"
                            chemin_destination = os.path.join(dossier_cible, nom_final_fichier)
                            
                            shutil.copy2(path_source, chemin_destination)
                            logger.info(f"      [Fichier] Copie effectuée vers -> {chemin_destination}")
                                    
                            if est_un_split and os.path.exists(path_source): 
                                # Seuls les fichiers générés dans TEMP_DIR sont nettoyés
                                if str(path_source).startswith(str(TEMP_DIR)):
                                    try:
                                        os.remove(path_source)
                                        logger.info(f"   [Nettoyage] Fichier temporaire supprimé : {path_source}")
                                    except Exception as e:
                                        logger.error(f"   [Erreur] Nettoyage impossible pour {path_source} : {e}")

                            # Calcul de la durée pour ce document précis
                            temps_reponse_doc = time.time() - doc_start_time
                            
                            # Construction des métadonnées (calculé pour CHAQUE segment, index 0 ou supérieur)
                            
                            metadata_segment = metrics_ia.copy()
                            if est_un_split:
                                # Création d'une nouvelle liste isolée pour éviter de modifier la source
                                current_keywords = list(metadata_segment.get("extracted_keywords", []))
                                if "split_pdf" not in current_keywords:
                                    current_keywords.append("split_pdf")
                                metadata_segment["extracted_keywords"] = current_keywords

                            if idx == 0:
                                doc.file_type = t_final_clean
                                doc.is_classified = True
                                doc.classification_reason = raison_classification
                                doc.classification_description = description_classification
                                doc.classified_at = maintenant
                                doc.classified_file_path = chemin_destination 
                                doc.response_time = temps_reponse_doc
                                doc.analysis_metadata = metadata_segment
                                #doc.analysis_metadata = metrics_ia
                                logger.info(f"      [BDD] Entrée principale ID {doc.id} mise à jour en {temps_reponse_doc:.2f}s.")
                            else:
                                nouveau_morceau = TenderDocument(
                                    tender_id=tender.id,
                                    file_name=nom_final_fichier,
                                    file_type=t_final_clean,
                                    file_path=doc.file_path,  
                                    classified_file_path=chemin_destination,
                                    is_classified=True,
                                    classification_reason="DECOUPAGE_PDF_AUTOMATIQUE",
                                    classification_description=f"Segment découpé automatiquement. Analyse parente : {description_classification}",
                                    classified_at=maintenant,
                                    response_time=temps_reponse_doc,
                                    analysis_metadata=metadata_segment
                                )
                                db.add(nouveau_morceau)
                                logger.info(f"      [BDD] Nouveau segment enregistré.")
                                
                        db.commit()
                        
                    except Exception as doc_error:
                        db.rollback()
                        logger.error(f"   -> Erreur lors du traitement du document ID {doc.id}: {str(doc_error)}")
                        continue
                
                logger.info(f"-> Dossier [{index_tender}/{total_tenders}] ({nom_dossier_offre}) finalisé avec succès.\n")
                
            except Exception as tender_error:
                db.rollback()
                logger.critical(f"Erreur critique sur le dossier Tender ID {tender.id}: {str(tender_error)}", exc_info=True)
                continue

        duree_totale = time.time() - global_start_time
        logger.info(f"\n=== STATISTIQUES DE CLASSIFICATION ===")
        logger.info(f"Nombre total de lignes/documents traités : {total_lignes_traitees}")
        logger.info(f"Temps total d'exécution : {duree_totale:.2f} secondes (~{duree_totale/60:.2f} minutes)")    

        logger.info("=== FIN DU PIPELINE DE CLASSIFICATION ===")
        
    except Exception as global_error:
        logger.critical(f"Erreur globale dans le traitement : {global_error}", exc_info=True)
    finally:
        # 2. FERMETURE OBLIGATOIRE de la session à la fin du traitement
        db.close()