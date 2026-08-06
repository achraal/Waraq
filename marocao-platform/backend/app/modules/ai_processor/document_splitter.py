import logging, os, re, unicodedata
from typing import List
from pathlib import Path
from pypdf import PdfReader, PdfWriter
from backend.app.modules.ai_processor.ocr_engine import convertir_doc_en_pdf, extraire_texte_page_pdf_avec_meta

logger = logging.getLogger(__name__)

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

def normaliser_ocr(texte: str) -> str:
    if not texte:
        return ""

    texte = texte.upper()

    # suppression des accents
    texte = unicodedata.normalize("NFD", texte)
    texte = "".join(c for c in texte if unicodedata.category(c) != "Mn")

    # suppression de tout sauf lettres et chiffres
    #texte = re.sub(r"[^A-Z0-9]", "", texte)
    texte = re.sub(r"[\s'’`.,;:!?(){}\[\]_/\\\-]+", "", texte)

    return texte

def est_un_titre(ligne: str) -> bool:
    ligne = ligne.strip().upper()

    if not ligne:
        return False

    # trop longue = probablement un paragraphe
    if len(ligne) > 80:
        return False

    # trop de mots = probablement une phrase
    if len(ligne.split()) > 10:
        return False

    # finit par un point = souvent une phrase
    if ligne.endswith("."):
        return False

    # présence de verbes ou connecteurs
    mots_phrase = [
        "EST", "SONT", "DOIT", "DOIVENT",
        "PEUT", "PEUVENT",
        "SERA", "SERONT", "CONFORMEMENT",
        "CONFORMÉMENT",
    ]

    nb = sum(m in ligne for m in mots_phrase)

    return nb <= 1
    
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
    
    lignes_norm = [normaliser_ocr(l) for l in lignes]
    top_text_norm = normaliser_ocr(top_text)

    # 1. Vérification si c'est explicitement marqué comme modèle / annexe / formulaire
    mots_cles_annexe = ["MODELE", "ANNEXE", "SPECIMEN", "FORMULAIRE", "CANEVAS"]
    est_un_modele = any(keyword in top_text for keyword in mots_cles_annexe)

    # 2. DÉTECTION DU BORDEREAU DES PRIX / DETAIL ESTIMATIF (Modèle interne -> NE COUPE PAS)
    # Gère les cas : "BORDEREAU DES PRIX", "DETAIL ESTIMATIF", "BORDEREAU DES PRIX - DETAIL ESTIMATIF" + VALIDATION TABLEAU

    #pattern_bdp = r"(BORDEREAU\s+(DES\s+)?PRIX|D[EÉè]TAIL\s+ESTIMATIF)"
    if (
        "BORDEREAUDESPRIX" in top_text_norm
        or "DETAILESTIMATIF" in top_text_norm
    ):
        #match_bdp = re.search(pattern_bdp, top_text)
        # VÉRIFICATION DU TABLEAU
        if contient_structure_tableau(page_text):
            return {
                "file_type": "BORDEREAU_PRIX",
                "is_major_break": False,     # NE COUPE PAS
                "is_internal_model": True    # Tracer en BDD / Logs
            }

    #if match_bdp:
        # On prend le reste de la page situé après la mention du titre
        #index_titre = match_bdp.end()
        #reste_page = top_text[index_titre:] + " " + " ".join(lignes[20:])

        # VÉRIFICATION DU TABLEAU
        #if contient_structure_tableau(reste_page):
            #return {
                #"file_type": "BORDEREAU_PRIX",
                #"is_major_break": False,     # NE COUPE PAS
                #"is_internal_model": True    # Tracer en BDD / Logs
            #}
    # -------------------------
    # AVIS D'APPEL D'OFFRES
    # -------------------------
    texte_page = "\n".join(lignes)

    nb_mots = len(page_text.split())
    nb_arabe = len(re.findall(r'[\u0600-\u06FF]', page_text))

    if len(page_text) > 500 and nb_mots > 70:

        top_norm = normaliser_ocr(top_text)

        avis_fr = [
            "AVISDAPPELDOFFRES",
            "AVISDAPPELDOFFRESOUVERT",
            "AVISDAPPELDOFFRESOUVERTINTERNATIONAL",
            "AVISDAPPELDOFFRESSUROFFRESDEPRIX",
        ]

        for mot in avis_fr:
            if mot in top_norm:
                return {
                    "file_type": "AVIS_FRANCAIS",
                    "is_major_break": True,
                    "is_internal_model": False
                }
        avis_ar = [
            "اعلان عن طلب عروض",
            "إعلان عن طلب العروض",
            "اعلان عن طلب عروض مفتوح",
            "إعلان عن طلب العروض مفتوح",
        ]
        top_ar = "\n".join(lignes[:6])

        if nb_arabe > 80:
            for mot in avis_ar:
                if mot in top_ar:
                    return {
                        "file_type": "AVIS_ARABE",
                        "is_major_break": True,
                        "is_internal_model": False
                    }

    # 3. Normalisation CPS / CCAP / CCTP (AVEC DÉTECTION STRICTE DE TITRE)                    
    for alias, canonical in MAPPING_TYPES.items():
        alias_norm = normaliser_ocr(alias)
        #for ligne in lignes_norm[:15]:
        for ligne_originale, ligne_norm in zip(lignes[:15], lignes_norm[:15]):
            if not est_un_titre(ligne_originale):
                continue
            if alias_norm in ligne_norm:
                return {
                    "file_type": canonical,
                    "is_major_break": not est_un_modele,
                    "is_internal_model": est_un_modele
                }

    # 4. Détection Règlement de Consultation (RC)
    #if re.search(r"R[EÉÈ]GLEMENT\s+(DE\s+(LA\s+)?)?CONSULTATION", top_text):
    if "REGLEMENTDELACONSULTATION" in top_text_norm:
        return {
            "file_type": "RC",
            "is_major_break": not est_un_modele,
            "is_internal_model": est_un_modele
        }

    # 5. Détection des autres modèles isolés (Acte d'engagement, Déclaration sur l'honneur, etc.)               
    for model_type, keywords in MODELES_INTERNES.items():
        for ligne in lignes_norm[:15]:
            if not est_un_titre(ligne):
                continue
            for kw in keywords:
                if normaliser_ocr(kw) in ligne:
                    return {
                        "file_type": model_type,
                        "is_major_break": False,
                        "is_internal_model": True
                    }

    return {"file_type": None, "is_major_break": False, "is_internal_model": False}

def verifier_et_decouper_document(
    file_path: str, 
    nom_fichier: str, 
    type_document_global: str,
    extraction=None,
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
        modeles_detectes = []
        splits_proposes = []
        type_courant = type_document_global
        page_debut_segment = 1
        est_un_scan_detecte = False
        methodes_utilisees = set()

        # 3. Parcours page par page
        for page_idx in range(total_pages):
            num_page = page_idx + 1
           
            if extraction and "pages" in extraction:
                res_ocr = extraction["pages"][page_idx]
            else:
                res_ocr = extraire_texte_page_pdf_avec_meta(
                    pdf_path_a_traiter,
                    page_num=page_idx
                )

            page_text = res_ocr["text"]
            
            if res_ocr["is_scanned"]:
                est_un_scan_detecte = True
            methodes_utilisees.add(res_ocr["inspection_method"])
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
            if (
                total_pages >= 10
                and not est_sommaire
                and header_info.get("is_major_break")
                and file_type_detecte in TYPES_MAJEURS_SPLIT
            ):
                if file_type_detecte != type_courant:
                    # Premier changement dès la page 1
                    if num_page == 1:
                        logger.info(
                            f"[DECOUPAGE] Type global '{type_courant}' remplacé immédiatement par '{file_type_detecte}'."
                        )
                        type_document_global = file_type_detecte
                        type_courant = file_type_detecte
                        page_debut_segment = 1
                        continue
                    logger.info(
                        f"[DECOUPAGE LOG] Rupture majeure p.{num_page} : {type_courant} -> {file_type_detecte}"
                    )
                    splits_proposes.append({
                        "type": type_courant,
                        "start": page_debut_segment,
                        "end": page_idx
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

        # CAS A : Découpage physique (Plusieurs sections majeures détectées)
        if total_pages >= 10 and len(types_uniques) > 1 and len(splits_proposes) > 1:
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
        # CAS B : Document conservé en un seul fichier (Pas de découpage)
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