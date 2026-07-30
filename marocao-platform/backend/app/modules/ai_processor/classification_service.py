import os, shutil, time, logging, re
from pathlib import Path
from collections import defaultdict
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from backend.app.database.connection import SessionLocal
from pypdf import PdfReader, PdfWriter
from backend.app.database.models import TenderDocument, Tender, ClassificationAuditLog
from backend.app.modules.ai_processor.llm_analyzer import classifier_texte_document, classifier_page_pour_decoupage, extraire_texte_par_lots, verifier_ou_classifier_par_llm
from backend.app.modules.ai_processor.learning_service import WaraqLearningEngine
from backend.app.modules.ai_processor.ocr_engine import extraire_texte_integral, extraire_texte_page_pdf, extraire_ocr_pdf_page, optimiser_image_pour_analyse, convertir_doc_en_pdf
from typing import Optional, List

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
# Types majeurs qui autorisent un découpage physique s'il y a rupture
TYPES_MAJEURS_SPLIT = {"CPS", "RC", "BORDEREAU_PRIX"}

# Mappage des alias vers le type canonique CPS
MAPPING_TYPES = {
    "CCAP": "CPS",
    "CCTP": "CPS",
    "CCATP": "CPS",
    "C.C.A.P": "CPS",
    "C.C.T.P": "CPS",
    "C.C.A.T.P": "CPS",
    "CAHIER DES CLAUSES ADMINISTRATIVES PARTICULIERES": "CPS",
    "CAHIER DES CLAUSES TECHNIQUES PARTICULIERES": "CPS",
    "C.P.S": "CPS",
    "CAHIER DES PRESCRIPTIONS SPECIALES": "CPS"
}

# Modèles et annexes internes (NE PROVOQUENT PAS DE DÉCOUPAGE)
MODELES_INTERNES = {
    "MODELE_ACTE_ENGAGEMENT": ["ACTE D'ENGAGEMENT", "ACTE D ENGAGEMENT", "MODELE D'ACTE"],
    "MODELE_DECLARATION_HONNEUR": ["DECLARATION SUR L'HONNEUR", "DECLARATION SUR L HONNEUR"],
    "MODELE_CV": ["CURRICULUM VITAE", "MODELE DE CV", "CANEVAS DU CV"],
    "MODELE_BORDEREAU_ESTIMATIF": ["DETAIL ESTIMATIF", "BORDEREAU ESTIMATIF"]
}

def est_une_page_sommaire(page_text: str) -> bool:
    """
    Détecte si la page est une Table des matières / Sommaire / Garde d'inventaire.
    """
    if not page_text:
        return False

    text_lower = page_text.lower()

    # 1. Mots-clés explicites de sommaire / table des matières
    mots_cles_sommaire = [
        "sommaire", "table des matieres", "table des matières",
        "dossier d'appel d'offres", "dossier d’appel d’offres",
        "composition du dossier", "liste des pieces", "liste des pièces",
        "tableau recapitulatif", "tableau récapitulatif"
    ]
    
    for mc in mots_cles_sommaire:
        if mc in text_lower[:500]: # Généralement situé en haut de page
            return True

    # 2. Pattern visuel de sommaire (ex: plusieurs lignes avec des numéros de section ou p. X)
    # Ex: "1. Copie de l'avis..." ou "II. REGLEMENT DE CONSULTATION"
    lignes_structurees = re.findall(r'^\s*(?:[I|V|X]+\.|\d+[\.\-\)])\s+[A-ZÀ-Ü]', page_text, re.MULTILINE)
    if len(lignes_structurees) >= 3:
        return True

    return False

def filtrer_segments_parasites(raw_segments: List[dict], min_pages: int = 2) -> List[dict]:
    """
    Conserve le découpage libre (aucun ordre imposé entre RC, CPS, etc.),
    mais empêche la réouverture d'un type déjà traité et filtre les micro-ruptures.
    """
    if not raw_segments:
        return []

    types_deja_vus = set()
    cleaned_segments = []

    for seg in raw_segments:
        current_type = seg.get("type")
        start_p = seg["start"]
        end_p = seg["end"]
        longueur = end_p - start_p + 1

        if not cleaned_segments:
            cleaned_segments.append(seg)
            types_deja_vus.add(current_type)
            continue

        last_seg = cleaned_segments[-1]
        last_type = last_seg["type"]

        # CAS 1 : C'est le même type que le segment précédent -> On fusionne
        if current_type == last_type:
            last_seg["end"] = end_p
            continue

        # CAS 2 : Le type a DÉJÀ été fermé plus tôt dans le fichier -> Faux positif / Citation !
        # Exemple : RC -> CPS -> RC (Le 2ème RC est rejeté et absorbé par le CPS)
        if current_type in types_deja_vus:
            print(f"[FILTRE DECOUPE] Rebond ignoré p.{start_p}-{end_p} ({current_type} déjà fermé). Fusionné dans {last_type}.")
            last_seg["end"] = end_p
            continue

        # CAS 3 : Changement vers un NOUVEAU type, mais le segment est trop court (ex: 1 page isolée)
        if longueur < min_pages and current_type not in ["AVIS_ARABE", "AVIS_FRANCAIS", "AVIS"]:
            print(f"[FILTRE DECOUPE] Rupture trop courte ({longueur} p.) vers {current_type} p.{start_p}. Fusionné dans {last_type}.")
            last_seg["end"] = end_p
            continue

        # CAS 4 : Nouveau type valide -> On valide le segment
        cleaned_segments.append(seg)
        types_deja_vus.add(current_type)

    return cleaned_segments

def contient_structure_tableau(texte_apres_titre: str) -> bool:
    """
    Vérifie si le texte sous le titre comporte les caractéristiques d'un tableau financier / BDP.
    """
    texte_clean = texte_apres_titre.upper()

    # Signaux 1 : Mots-clés de colonnes typiques d'un BDP / Détail Estimatif
    colonnes_bdp = [
        "P.U", "PRIX UNITAIRE", "P.T", "PRIX TOTAL", 
        "MONTANT", "QUANTITE", "QTÉ", "UNITÉ", "DESIGNATION", 
        "TVA", "TOTAL HT", "TOTAL TTC"
    ]
    matches_colonnes = sum(1 for col in colonnes_bdp if col in texte_clean)

    # Signaux 2 : Structure de numérotation de prix/lignes (ex: "1.01", "1 |", "2 -", etc.)
    lignes = texte_clean.split("\n")
    lignes_structurees = 0
    pattern_ligne_tableau = r"^(\d+[\.\-\)]|\d+\s*\|)"  # Ex: "1.", "1-", "1 |" au début d'une ligne
    
    for l in lignes:
        if re.match(pattern_ligne_tableau, l.strip()):
            lignes_structurees += 1

    # Condition : Au moins 2 en-têtes de colonnes BDP OU (1 en-tête + lignes structurées)
    return matches_colonnes >= 2 or (matches_colonnes >= 1 and lignes_structurees >= 2)

def analyser_haut_de_page(page_text: str) -> dict:
    """
    Examine le début d'une page pour repérer le type de document ou les annexes/modèles internes.
    """
    if not page_text or not page_text.strip():
        return {"file_type": None, "is_major_break": False, "is_internal_model": False}

    # On passe à 20 lignes pour ne pas rater les titres légèrement décalés vers le bas
    lignes = [l.strip().upper() for l in page_text.split("\n") if l.strip()][:15]
    top_text = " ".join(lignes)

    # 1. Vérification si c'est explicitement marqué comme modèle / annexe / formulaire
    mots_cles_annexe = ["MODELE", "ANNEXE", "SPECIMEN", "FORMULAIRE", "CANEVAS"]
    est_un_modele = any(keyword in top_text for keyword in mots_cles_annexe)

    # 2. DÉTECTION DU BORDEREAU DES PRIX / DETAIL ESTIMATIF (Modèle interne -> NE COUPE PAS)
    # Gère les cas : "BORDEREAU DES PRIX", "DETAIL ESTIMATIF", "BORDEREAU DES PRIX - DETAIL ESTIMATIF" + VALIDATION TABLEAU

    pattern_bdp = r"(BORDEREAU\s+(DES\s+)?PRIX|D[EÉè]TAIL\s+ESTIMATIF)"
    match_bdp = re.search(pattern_bdp, top_text)

    if match_bdp:
        # On prend le reste de la page situé après la mention du titre
        index_titre = match_bdp.end()
        reste_page = top_text[index_titre:] + " " + " ".join(lignes[20:])

        # VÉRIFICATION DU TABLEAU
        if contient_structure_tableau(reste_page):
            return {
                "file_type": "BORDEREAU_PRIX",
                "is_major_break": False,     # NE COUPE PAS
                "is_internal_model": True    # Tracer en BDD / Logs
            }

    # 3. Normalisation CPS / CCAP / CCTP
    for alias, canonical in MAPPING_TYPES.items():
        if alias in top_text:
            return {
                "file_type": canonical,
                "is_major_break": not est_un_modele,
                "is_internal_model": est_un_modele
            }

    # 4. Détection Règlement de Consultation (RC)
    if re.search(r"R[EÉÈ]GLEMENT\s+(DE\s+(LA\s+)?)?CONSULTATION", top_text):
        return {
            "file_type": "RC",
            "is_major_break": not est_un_modele,
            "is_internal_model": est_un_modele
        }

    # 5. Détection des autres modèles isolés (Acte d'engagement, Déclaration sur l'honneur, etc.)
    for model_type, keywords in MODELES_INTERNES.items():
        if any(kw in top_text for kw in keywords):
            return {
                "file_type": model_type,
                "is_major_break": False,  # Ne coupe pas
                "is_internal_model": True
            }

    return {"file_type": None, "is_major_break": False, "is_internal_model": False}

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
       
    # Captures: "bordereau des prix", "bpe", "bp", "bpg"
    REGEX_BORDEREAU = r"(^|[\s\-_])(bordereau[\s\-_]*(des?|de)?[\s\-_]*prix|bpe|bpg)([\s\-_]|$)"
    
    # Captures: "sous detail des prix", "sous-détail du prix", "s/detail prix", "sousdetail_prix"
    REGEX_SOUS_DETAIL = r"s(ous|/)[\s\-_]*d[eé]tail[\s\-_]*(des?|du)?[\s\-_]*prix"

    if re.search(REGEX_BORDEREAU, f_norm) or re.search(REGEX_SOUS_DETAIL, f_norm):
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
        
    if re.search(r"(^|[\s\-_])(cps|ccftp|ccatp|ccafp|cctp|ccafg|ccaafg|ccag|ccagtp)([\s\-_]|$)|cahier\s+des?\s+prescriptions?\s+sp[eé]ciales?", f_norm):
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
    
def verifier_et_decouper_document(
    file_path: str, 
    nom_fichier: str, 
    type_document_global: str,
    TYPES_MAJEURS_SPLIT: set = None
) -> tuple[list, bool, str]:
    """
    Découpe universelle avec traçabilité complète des numéros de pages.
    Retourne : (fichiers_divises, est_un_split, description_enrichie)
    """
    if TYPES_MAJEURS_SPLIT is None:
        TYPES_MAJEURS_SPLIT = {"CPS", "RC", "ACTE_ENGAGEMENT", "DECLARATION_HONNEUR", "AVIS"}

    ext = os.path.splitext(file_path)[1].lower()
    pdf_path_a_traiter = file_path
    est_word_converti = False

    try:
        # 1. Conversion temporaire Word -> PDF si nécessaire
        if ext in [".docx", ".doc"]:
            logger.info(f"[DECOUPAGE] Détection Word : '{nom_fichier}'. Conversion temporaire en PDF...")
            pdf_path_a_traiter = convertir_doc_en_pdf(file_path)
            if not pdf_path_a_traiter or not os.path.exists(pdf_path_a_traiter):
                logger.error(f"[DECOUPAGE ABANDONNÉ] Conversion impossible pour '{nom_fichier}'.")
                return [], False, ""
            est_word_converti = True

        # 2. Ouverture PyPDF
        reader = PdfReader(pdf_path_a_traiter)
        total_pages = len(reader.pages)
        logger.info(f"[DECOUPAGE] Analyse du document : '{nom_fichier}' ({total_pages} page(s))")

        if total_pages <= 3:
            logger.info(f"[DECOUPAGE] Document court ({total_pages} p.). Conservé intact.")
            return [(type_document_global, file_path)], False, f"Document court ({total_pages} pages)."

        # Test document scanné
        texte_test = "".join([reader.pages[i].extract_text() or "" for i in range(min(3, total_pages))])
        if len(texte_test.strip()) < 100:
            logger.warning(f"[DECOUPAGE SAUTÉ] '{nom_fichier}' semble être un scan.")
            return [(type_document_global, file_path)], False, f"Document scanné ({total_pages} pages)."

        modeles_detectes = []
        splits_proposes = []

        type_courant = type_document_global
        page_debut_segment = 1

        # 3. Parcours page par page
        for page_idx in range(total_pages):
            num_page = page_idx + 1
            page_text = reader.pages[page_idx].extract_text() or ""
            header_info = analyser_haut_de_page(page_text)
            file_type_detecte = header_info.get("file_type")

            # Capture des modèles internes (BDP, Annexes, etc.)
            if header_info.get("is_internal_model") and file_type_detecte:
                info_mod = f"{file_type_detecte} (p.{num_page})"
                modeles_detectes.append(info_mod)
                logger.info(f"[DECOUPAGE LOG] Modèle interne repéré à la p.{num_page} : {file_type_detecte}")
                
            est_sommaire = est_une_page_sommaire(page_text)
            if est_sommaire:
                logger.info(f"[DECOUPAGE LOG] Page {num_page} identifiée comme SOMMAIRE/TABLE DES MATIÈRES. Rupture ignorée sur cette page.")

            # Capture des ruptures majeures pour découpage (Seulement si >= 20 pages)
            if total_pages >= 20 and not est_sommaire and header_info.get("is_major_break") and file_type_detecte in TYPES_MAJEURS_SPLIT:
                if type_courant and file_type_detecte != type_courant:
                    logger.info(f"[DECOUPAGE LOG] Rupture majeure p.{num_page} : Changement {type_courant} -> {file_type_detecte}")
                    splits_proposes.append({
                        "type": type_courant,
                        "start": page_debut_segment,
                        "end": page_idx  # La page précédente termine le segment
                    })
                    page_debut_segment = num_page
                    type_courant = file_type_detecte

        # Clôture du dernier segment
        splits_proposes.append({
            "type": type_courant,
            "start": page_debut_segment,
            "end": total_pages
        })
        
        splits_proposes = filtrer_segments_parasites(splits_proposes, min_pages=2)
        types_uniques = set(s["type"] for s in splits_proposes)

        # ----------------------------------------------------------------------
        # CAS A : Découpage physique (Plusieurs sections majeures détectées)
        # ----------------------------------------------------------------------
        if total_pages >= 20 and len(types_uniques) > 1 and len(splits_proposes) > 1:
            fichiers_divises = []
            nom_base = os.path.splitext(nom_fichier)[0]
            details_segments = []

            for idx, seg in enumerate(splits_proposes):
                writer = PdfWriter()
                for p_num in range(seg["start"] - 1, seg["end"]):
                    writer.add_page(reader.pages[p_num])

                type_clean = seg["type"]
                nom_split = f"split_{idx}_{type_clean}_{nom_base}.pdf"
                chemin_split = os.path.join(TEMP_DIR, nom_split)

                with open(chemin_split, "wb") as f:
                    writer.write(f)

                fichiers_divises.append((type_clean, chemin_split))
                
                # Formatage précis des pages pour la BDD et les logs
                seg_info = f"{type_clean} (p.{seg['start']}-{seg['end']})"
                details_segments.append(seg_info)
                logger.info(f"[DECOUPAGE CRÉÉ] Segment {idx+1}/{len(splits_proposes)} : {seg_info}")

            desc_enrichie = f"Découpé en {len(fichiers_divises)} parties : " + ", ".join(details_segments)
            if modeles_detectes:
                desc_enrichie += f" | Annexes/Modèles inclus : {', '.join(modeles_detectes)}"

            return fichiers_divises, True, desc_enrichie

        # ----------------------------------------------------------------------
        # CAS B : Document conservé en un seul fichier (Pas de découpage)
        # ----------------------------------------------------------------------
        else:
            desc_enrichie = f"Document unique ({total_pages} pages)."
            if modeles_detectes:
                desc_enrichie += f" Modèles/Annexes détectés : {', '.join(modeles_detectes)}."
            
            logger.info(f"[DECOUPAGE INFO] Aucun split appliqué. {desc_enrichie}")
            return [(type_document_global, file_path)], False, desc_enrichie

    except Exception as e:
        logger.error(f"[DECOUPAGE] Échec lors du découpage de '{nom_fichier}': {e}", exc_info=True)
        return [(type_document_global, file_path)], False, ""

    finally:
        if est_word_converti and pdf_path_a_traiter and os.path.exists(pdf_path_a_traiter):
            try:
                os.remove(pdf_path_a_traiter)
            except Exception:
                pass

# def verifier_et_decouper_pdf(file_path: str, nom_fichier: str, type_parent: str) -> list:
#     """
#     Parcourt l'intégralité des pages du PDF pour détecter et extraire les sous-documents 
#     imbriqués (ex: Bordereau de Prix de 1 page à la fin d'un CPS de 50 pages).
#     """
#     try:
#         reader = PdfReader(file_path)
#         nb_pages = len(reader.pages)
        
#         logger.info(f"[DECOUPAGE] Analyse du PDF : '{nom_fichier}' ({nb_pages} page(s) au total)")
        
#         # 1. Inutile de chercher un découpage sur un document très court
#         if nb_pages <= 3:
#             logger.info(f"[DECOUPAGE] Document trop court ({nb_pages} pages). Aucun découpage nécessaire.")
#             return []

#         # 2. VÉRIFICATION FAST SCAN : Si c'est un scan (< 100 car. natifs sur les 3 premières pages)
#         # On évite d'exécuter PaddleOCR 20+ fois
#         texte_test = "".join([reader.pages[i].extract_text() or "" for i in range(min(3, nb_pages))])
#         if len(texte_test.strip()) < 100:
#             logger.warning(f"[DECOUPAGE SAUTÉ] '{nom_fichier}' est un PDF scanné. Découpage OCR ignoré pour préserver les performances.")
#             return []

#         logger.info(f"[DECOUPAGE] Début du scan page par page...")
        
#         pages_types = []
#         types_detectes = set()

#         # 3. Analyse page par page sur l'ENSEMBLE du document (Texte natif uniquement)
#         for idx in range(nb_pages):
#             txt_page = extraire_texte_page_pdf(file_path, idx, reader)
            
#             # Si une page native est vide, on garde le type parent au lieu de lancer un OCR lourd
#             if not txt_page or not txt_page.strip():
#                 type_page = type_parent
#             else:
#                 type_page = classifier_page_pour_decoupage(txt_page)
            
#             # Anti-INCONNU : si la page est indéterminée, elle hérite du type global du document
#             if type_page == "INCONNU":
#                 type_page = type_parent
            
#             pages_types.append(type_page)
#             types_detectes.add(type_page)

#         # 4. Vérification de l'homogénéité du document
#         if len(types_detectes) <= 1:
#             logger.info(f"[DECOUPAGE] Document 100% homogène ({list(types_detectes)[0]}). Aucun sous-document détecté.")
#             return []

#         logger.info(f"[DECOUPAGE] Détection de plusieurs types distincts : {list(types_detectes)}. Regroupement des pages...")

#         # 5. Regroupement de TOUTES les pages par type (gestion des pages non contiguës)
#         pages_par_type = defaultdict(list)
#         for p_idx, t_seg in enumerate(pages_types):
#             t_clean = t_seg if t_seg != "INCONNU" else type_parent
#             pages_par_type[t_clean].append(p_idx)

#         # Si toutes les pages ont le même type final, annulation du découpage
#         if len(pages_par_type) <= 1:
#             logger.info(f"[DECOUPAGE] Annulation du découpage : le document est 100% homogène.")
#             return []

#         # 6. Extraction physique des fichiers découpés
#         logger.info(f"[DECOUPAGE] Génération de {len(pages_par_type)} sous-document(s) unique(s) par type...")
#         fichiers_divises = []

#         for idx, (type_clean, page_indices) in enumerate(pages_par_type.items()):
#             writer = PdfWriter()
#             for p_num in page_indices:
#                 writer.add_page(reader.pages[p_num])

#             nom_split = f"split_{idx}_{type_clean}_{nom_fichier}"
#             chemin_split = os.path.join(TEMP_DIR, nom_split)

#             with open(chemin_split, "wb") as f:
#                 writer.write(f)

#             fichiers_divises.append((type_clean, chemin_split))
#             pages_humaines = [p + 1 for p in page_indices]
#             logger.info(f"[DECOUPAGE] Sous-document {idx + 1}/{len(pages_par_type)} créé : '{nom_split}' (Type: '{type_clean}', Pages: {pages_humaines})")

#         return fichiers_divises

#     except Exception as e:
#         logger.error(f"[DECOUPAGE] Échec lors de l'analyse ou du découpage de '{nom_fichier}': {e}", exc_info=True)
#         return []

def executer_classification_post_scraping(target_tender_id: Optional[int] = None):
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
        #subquery = (
            #db.query(TenderDocument.tender_id)
            #.filter(TenderDocument.is_classified == False)
            #.distinct()
            ##.subquery()
            #.scalar_subquery()
        #)
        
        subquery = db.query(TenderDocument.tender_id).filter(
            TenderDocument.is_classified == False
        )

        if target_tender_id:
            subquery = subquery.filter(TenderDocument.tender_id == target_tender_id)

        subquery = subquery.distinct().scalar_subquery()
        
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
                        # type_document = appliquer_types_primitifs(nom_fichier, ext)
                        # if type_document:
                            # raison_classification = "REGLES_PRIMITIVES"
                            # description_classification = f"Classifié automatiquement selon les règles de nommage primitives pour l'extension ou le préfixe."
                            # langue_detectee = "ar" if type_document == "AVIS_ARABE" else "fr"
                            # metrics_ia = construire_metadata_standard(
                                # method="PRIMITIVE_RULES",
                                # confidence=5,
                                # keywords=[type_document.lower(), ext.replace(".", "")],
                                # language=langue_detectee
                            # )
                            # logger.info(f"      -> Classifié par règles primitives : '{type_document}'")
                            # log_primitive = ClassificationAuditLog(
                                # document_id=doc.id,
                                # predicted_type=type_document,
                                # classification_reason="Règles primitives de nommage.",
                                # model_used="primitive_rules",
                                # validation_status="PENDING"
                            # )
                            # db.add(log_primitive)
                        # else:
                            # 2. Étape Fallback IA
                            # logger.info("      -> Aucune règle primitive validée. Passage à la détection de contenu...")
                            # type_document, raison_classification, description_classification, metrics_ia = determiner_type_par_ia(
                                # chemin_original, ext, nom_fichier, contexte_few_shot, doc.id, db
                            # )
                            
                        # 1. Étape Primitives + Vérification LLM par lots de 10 pages
                        type_primitive = appliquer_types_primitifs(nom_fichier, ext)
                        
                        # Extraction de 100% du texte par lots de 10 pages
                        lots = extraire_texte_par_lots(chemin_original, taille_lot=10) if ext == ".pdf" else []
                        texte_global_condense = "\n".join([lot["texte"][:500] for lot in lots]) if lots else nom_fichier
                        
                        # Vérification LLM (validation du primitif ou classification directe)
                        res_llm = verifier_ou_classifier_par_llm(texte_global_condense, type_primitif_detecte=type_primitive)
                        # Variable booléenne explicitement définie
                        est_primitive_valide = res_llm.get("est_valide", False) and res_llm.get("type_confirme") != "AUTRE"
    
                        # ----------------------------------------------------------------------
                        # SURCHARGE : Sécurité pour les variantes CCTP / CCAG / CPS
                        # ----------------------------------------------------------------------
                        # Mots-clés forts qu'on ne veut PAS laisser le LLM rejeter à tort (ex: sur les .docx)
                        f_norm = nom_fichier.lower().strip()
                        MOTS_CLES_FORTS_CPS = r"(^|[\s\-_])(cps|ccftp|ccatp|ccafg|ccafp|cctp|ccaafg|ccag|ccagtp)([\s\-_]|$)"
                        MOTS_CLES_AVIS_FR = r"avis[\s\-_]*fr|avis\s+en\s+fran[cç]ais"
                        MOTS_CLES_AVIS_AR = r"avis[\s\-_]*ar|avis\s+en\s+arabe"
                        MOTS_CLES_AVIS_GEN = r"\bavis\b"
                        # --- NOUVEAUX MOTS CLÉS AJOUTÉS ---
                        # 1. Regex RC : Boundaries strictes avec séparateurs (espaces, tirets, underscores)
                        MOTS_CLES_RC = r"(^|[\s\-_])rc([\s\-_]|$)|r[eéèê]glement\s*(de\s*(la\s*)?)?consultation"

                        # 2. Regex ACTE : Support des accents sur 'engagement' ou variations de séparation
                        MOTS_CLES_ACTE = r"acte[\s\-_]*(d['\s]?)?engagement"

                        # 3. Regex DECLARATION : Support complet des accents (é, è)
                        MOTS_CLES_DECLARATION = r"d[eéèê]claration\s*sur\s*l['\s]?honneur"

                        type_surcharge = None

                        if not est_primitive_valide:
                            if re.search(MOTS_CLES_FORTS_CPS, f_norm):
                                type_surcharge = "CPS"
                            elif re.search(MOTS_CLES_AVIS_FR, f_norm):
                                type_surcharge = "AVIS_FRANCAIS"
                            elif re.search(MOTS_CLES_AVIS_AR, f_norm):
                                type_surcharge = "AVIS_ARABE"
                            elif re.search(MOTS_CLES_AVIS_GEN, f_norm):
                                type_surcharge = "AVIS"
                            # 3. Règlement de consultation
                            elif re.search(MOTS_CLES_RC, f_norm):
                                type_surcharge = "RC"
                            # 4. Acte d'engagement
                            elif re.search(MOTS_CLES_ACTE, f_norm):
                                type_surcharge = "ACTE_ENGAGEMENT"
                            # 5. Déclaration sur l'honneur
                            elif re.search(MOTS_CLES_DECLARATION, f_norm):
                                type_surcharge = "DECLARATION_HONNEUR"

                        if not est_primitive_valide and type_surcharge:
                            logger.warning(
                                f"⚠️ Le LLM a rejeté la primitive '{type_primitive}' pour '{nom_fichier}' "
                                f"(Justification: {res_llm.get('justification')}). "
                                f"Surcharge appliquée : Maintien du type '{type_surcharge}' basé sur le nom du fichier."
                            )
                            est_primitive_valide = True
                            type_document = type_surcharge
                            raison_classification = f"SURCHARGE_NOM_FICHIER_{type_surcharge}"
                            description_classification = f"Forcé en {type_surcharge} (Règle nom fichier). Refus LLM initial : {res_llm.get('justification', '')}"
                            langue_detecte = "ar" if type_surcharge == "AVIS_ARABE" else res_llm.get("langue", "fr").lower()
                            metrics_ia = construire_metadata_standard(
                                method="PRIMITIVE_RULES_OVERRIDE",
                                confidence=5,
                                keywords=[type_surcharge.lower(), ext.replace(".", "")],
                                language=langue_detecte
                            )
                            logger.info(f"      -> Classifié par Surcharge Nom Fichier : '{type_surcharge}' ({langue_detecte})")
                        
                        elif est_primitive_valide:
                            type_document = res_llm["type_confirme"]
                            raison_classification = "REGLES_PRIMITIVES_VALIDEES_LLM"
                            description_classification = f"Validé par LLM ({res_llm.get('justification', '')})"
                            langue_detecte = res_llm.get("langue", "fr").lower()
                            metrics_ia = construire_metadata_standard(
                                method="PRIMITIVE_RULES_LLM",
                                confidence=5,
                                keywords=[type_document.lower(), ext.replace(".", "")],
                                language=langue_detecte
                            )
                            logger.info(f"      -> Classifié & Validé LLM : '{type_document}' ({langue_detecte})")
                            
                        else:
                            # 2. Étape Fallback IA si la règle primitive est rejetée ou absente
                            logger.info("      -> Primitif non validé ou absent. Détection de contenu IA par lots...")
                            type_document, raison_classification, description_classification, metrics_ia = determiner_type_par_ia(
                                chemin_original, ext, nom_fichier, contexte_few_shot, doc.id, db
                            )
                            modele_utilise = "ia_fallback_llm"

                        #t_clean = str(type_document).strip().replace(":", " ").replace("/", " ").split()[0].upper()
                        t_clean = nettoyer_nom_type(type_document)

                        # 3. Étape Découpage PDF
                        #fichiers_finaux = verifier_et_decouper_pdf(chemin_original, nom_fichier, t_clean) if ext == ".pdf" else []     
                        # AUTORISER PDF, DOCX ET DOC :
                        # ext_autorisees = [".pdf", ".docx", ".doc"]
                        # fichiers_finaux = verifier_et_decouper_document(chemin_original, nom_fichier, t_clean) if ext in ext_autorisees else []    
                        # est_un_split = len(fichiers_finaux) > 1

                        # if not fichiers_finaux:
                            # fichiers_finaux = [(t_clean, chemin_original)]
                            
                        # 3. Étape Découpage PDF / Word
                        ext_autorisees = [".pdf", ".docx", ".doc"]
                        if ext in ext_autorisees:
                            fichiers_finaux, est_un_split, desc_decoupage = verifier_et_decouper_document(
                                chemin_original, nom_fichier, t_clean
                            )
                            if desc_decoupage:
                                description_classification = f"{description_classification} | {desc_decoupage}".strip(" |")
                        else:
                            fichiers_finaux = [(t_clean, chemin_original)]
                            est_un_split = False
                            description_classification = f"Fichier {ext} conservé sans analyse de découpage."

                        # 4. Déplacement physique, mise à jour BDD et Nettoyage
                        for idx, (t_final, path_source) in enumerate(fichiers_finaux):
                            #t_final_clean = str(t_final).strip().replace(":", " ").replace("/", " ").split()[0].upper()
                            t_final_clean = nettoyer_nom_type(t_final)
                            
                            dossier_cible = BASE_STORAGE_DIR / "classified" / identifiant_dossier / t_final_clean
                            os.makedirs(dossier_cible, exist_ok=True)
                            
                            #nom_final_fichier = nom_fichier if not est_un_split else f"{t_final_clean}_{idx}_{nom_fichier}"
                            if not est_un_split:
                                nom_final_fichier = nom_fichier
                            else:
                                # Si c'est un split, le fichier extrait est TOUJOURS un PDF
                                nom_sans_extension = os.path.splitext(nom_fichier)[0]
                                nom_final_fichier = f"{t_final_clean}_{idx}_{nom_sans_extension}.pdf"
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
                            
                                # Extraction des métriques calculées par l'IA
                                confidence = metrics_ia.get("confidence")
                                langue = metrics_ia.get("language")
                                keywords = metadata_segment.get("extracted_keywords", [])
                            
                                # Enregistrement propre du Log Audit selon le mode de classification
                                if est_primitive_valide:
                                    modele_utilise = "primitive_rules_override" if raison_classification == "SURCHARGE_NOM_FICHIER_CPS" else "primitive_rules_llm"
                                    log_principal = ClassificationAuditLog(
                                        document_id=doc.id,
                                        predicted_type=t_final_clean,
                                        classification_reason=f"{raison_classification} | {description_classification}",
                                        #classification_description=description_classification,
                                        confidence_score=confidence,
                                        detected_language=langue,
                                        extracted_keywords=keywords,
                                        execution_duration_sec=temps_reponse_doc,
                                        model_used=modele_utilise,
                                        validation_status="PENDING"
                                    )
                                else:
                                    log_principal = ClassificationAuditLog(
                                        document_id=doc.id,
                                        predicted_type=t_final_clean,
                                        classification_reason=f"{raison_classification} | {description_classification}",
                                        #classification_description=description_classification,
                                        confidence_score=confidence,
                                        detected_language=langue,
                                        extracted_keywords=keywords,
                                        execution_duration_sec=temps_reponse_doc,
                                        # Si metrics_ia contient les compteurs LLM/Ollama, tu peux les extraire directement :
                                        prompt_tokens=metrics_ia.get("prompt_tokens"),
                                        generated_tokens=metrics_ia.get("generated_tokens"),
                                        ollama_total_duration=metrics_ia.get("ollama_total_duration"),
                                        model_used="ia_fallback_llm",
                                        validation_status="PENDING"
                                    )
                                db.add(log_principal)
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
                                db.flush()  # Récupère l'ID généré pour le segment découpé
                                
                                # Création de l'audit log spécifique au sous-segment découpé
                                log_segment = ClassificationAuditLog(
                                    document_id=nouveau_morceau.id,
                                    predicted_type=t_final_clean,
                                    classification_reason="DECOUPAGE_PDF_AUTOMATIQUE",
                                    #classification_description=f"Segment découpé #{idx}. Analyse parente : {description_classification}",
                                    confidence_score=metrics_ia.get("confidence"),
                                    detected_language=metrics_ia.get("language"),
                                    extracted_keywords=metadata_segment.get("extracted_keywords", []),
                                    execution_duration_sec=temps_reponse_doc,
                                    model_used="pdf_splitter_llm",
                                    validation_status="PENDING"
                                )
                                db.add(log_segment)
                                logger.info(f"      [BDD] Nouveau segment ID {nouveau_morceau.id} enregistré avec AuditLog.")
                                #logger.info(f"      [BDD] Nouveau segment enregistré.")
                                
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
       