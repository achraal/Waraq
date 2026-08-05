import os, shutil, time, logging, re, copy
from pathlib import Path
from collections import defaultdict
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from backend.app.database.connection import SessionLocal
from pypdf import PdfReader, PdfWriter
from backend.app.database.models import TenderDocument, Tender, ClassificationAuditLog
from backend.app.modules.ai_processor.llm_analyzer import classifier_texte_document, extraire_texte_par_lots, verifier_ou_classifier_par_llm, construire_metriques
from backend.app.modules.ai_processor.learning_service import WaraqLearningEngine
from backend.app.modules.ai_processor.ocr_engine import extraire_texte_integral, extraire_ocr_pdf_page, optimiser_image_pour_analyse, convertir_doc_en_pdf
from backend.app.modules.ai_processor.rules import nettoyer_nom_type, appliquer_types_primitifs
from backend.app.modules.ai_processor.document_splitter import verifier_et_decouper_document, est_une_page_sommaire, filtrer_segments_parasites, contient_structure_tableau, analyser_haut_de_page
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
# SURCHARGE : Sécurité pour les variantes CCTP / CCAG / CPS
# Mots-clés forts qu'on ne veut PAS laisser le LLM rejeter à tort (ex: sur les .docx)
MOTS_CLES_FORTS_CPS = re.compile(r"(^|[\s\-_])(cps|ccftp|ccatp|ccafg|ccafp|cctp|ccaafg|ccag|ccagtp)([\s\-_]|$)", re.IGNORECASE)
MOTS_CLES_AVIS_FR = re.compile(r"avis[\s\-_]*fr|avis\s+en\s+fran[cç]ais", re.IGNORECASE)
MOTS_CLES_AVIS_AR = re.compile(r"avis[\s\-_]*ar|avis\s+en\s+arabe", re.IGNORECASE)
MOTS_CLES_AVIS_GEN = re.compile(r"\bavis\b", re.IGNORECASE)
MOTS_CLES_RC = re.compile(r"(^|[\s\-_])rc([\s\-_]|$)|r[eéèê]glement\s*(de\s*(la\s*)?)?consultation", re.IGNORECASE)
MOTS_CLES_ACTE = re.compile(r"acte[\s\-_]*(d['\s]?)?engagement", re.IGNORECASE)
MOTS_CLES_DECLARATION = re.compile(r"d[eéèê]claration\s*sur\s*l['\s]?honneur", re.IGNORECASE)

def determiner_type_par_ia(file_path: str, ext: str, nom_fichier: str, contexte_few_shot: str, doc_id: str, db: Session) -> tuple[str, str, str, dict]:
    valeur_par_defaut = nom_fichier.upper()
    logger.info(f"[IA] Début de l'analyse du document pour classification : {nom_fichier}")
    try:
        chemin_a_analyser = file_path
        if ext in [".jpg", ".jpeg", ".png", ".tiff", ".bmp"]:
            chemin_a_analyser = optimiser_image_pour_analyse(file_path, max_side=2048)
        
        # --- RÉCUPÉRATION ROBUSTE DU TEXTE ET MÉTADONNÉES ---
        res_extraction = extraire_texte_integral(chemin_a_analyser)
        logger.info(
            f"[DEBUG EXTRACTION] "
            f"text={len(res_extraction.get('text',''))} "
            f"scan={res_extraction.get('is_scanned')} "
            f"method={res_extraction.get('inspection_method')}"
        )
        
        if chemin_a_analyser != file_path and os.path.exists(chemin_a_analyser):
            try:
                os.remove(chemin_a_analyser)
            except Exception:
                pass

        is_scanned_detecte = False
        inspection_methode_detectee = "NATIVE"
        # page_count = None
        # word_count = 0
        # file_size_mb = None
        # ocr_duration_sec = 0.0

        if isinstance(res_extraction, dict):
            texte_p1 = res_extraction.get("text", "")
            is_scanned_detecte = res_extraction.get("is_scanned", False)
            inspection_methode_detectee = res_extraction.get("inspection_method", "UNKNOWN")
            page_count = res_extraction.get("page_count")
            word_count = res_extraction.get("word_count")
            file_size_mb = res_extraction.get("file_size_mb")
            ocr_duration_sec = res_extraction.get("ocr_duration_sec")
            
            logger.info(
                "[TRACE determiner_type_par_ia - extraction] "
                f"page_count={page_count} | "
                f"word_count={word_count} | "
                f"file_size_mb={file_size_mb} | "
                f"ocr_duration_sec={ocr_duration_sec}"
            )
        else:
            texte_p1 = str(res_extraction) if res_extraction is not None else ""

        if not texte_p1 or not texte_p1.strip():
            meta_fallback = construire_metriques(
                model="IA_FALLBACK_TEXTE_VIDE",
                confidence=1,
                raison="Le texte extrait de la première page est vide.",
                extra_metrics={"is_scanned": is_scanned_detecte, "inspection_method": inspection_methode_detectee}
            )
            logger.warning(f"[IA] Texte extrait vide pour : {nom_fichier}")
            return valeur_par_defaut, "IA_FALLBACK_TEXTE_VIDE", "Le texte extrait est vide.", meta_fallback

        #logger.info("=" * 80)
        #logger.info(f"SCAN : {is_scanned_detecte}")
        #logger.info(f"METHODE : {inspection_methode_detectee}")
        #logger.info(f"LONGUEUR : {len(texte_p1)}")
        #logger.info(texte_p1[:5000])
        #logger.info("=" * 80)
        #logger.info(f"[IA] Envoi du texte extrait à Qwen pour {nom_fichier}...")
        #res_ia = classifier_texte_document(texte_p1, contexte_few_shot)
        # logger.info(
        #     "[TRACE avant classifier_texte_document] "
        #     f"page_count={page_count} | "
        #     f"word_count={word_count} | "
        #     f"file_size_mb={file_size_mb} | "
        #     f"ocr_duration_sec={ocr_duration_sec}"
        # )
        res_ia = classifier_texte_document(
            texte_p1,
            contexte_few_shot,
            is_scanned=is_scanned_detecte,
            inspection_method=inspection_methode_detectee,
            page_count=page_count,
            word_count=word_count,
            file_size_mb=file_size_mb,
            ocr_duration_sec=ocr_duration_sec,
        )
        
        type_extrait = "INCONNU"
        description_extraite = ""
        metrics_extraites = {}

        if isinstance(res_ia, tuple):
            type_extrait = res_ia[0] if len(res_ia) > 0 else "INCONNU"
            description_extraite = res_ia[1] if len(res_ia) > 1 else ""
            metrics_extraites = res_ia[2] if len(res_ia) > 2 else {}
        elif isinstance(res_ia, str):
            type_extrait = res_ia
            description_extraite = "Classifié par analyse de contenu."

        langue_ia = metrics_extraites.get("detected_language", "fr") if metrics_extraites else "fr"

        # On injecte explicitement is_scanned et inspection_method
        metrics_extraites["is_scanned"] = is_scanned_detecte
        metrics_extraites["inspection_method"] = inspection_methode_detectee

        metrics_complete = construire_metriques(
            model=metrics_extraites.get("model", "QWEN_LLM"),
            confidence=metrics_extraites.get("confidence_score"),
            keywords=metrics_extraites.get("extracted_keywords"),
            language=langue_ia,
            texte=texte_p1,
            raison=description_extraite,
            is_scanned=is_scanned_detecte,
            inspection_method=inspection_methode_detectee,
            page_count=page_count,
            word_count=word_count,
            file_size_mb=file_size_mb,
            ocr_duration_sec=ocr_duration_sec,
            extra_metrics=metrics_extraites
        )
        
        t_clean = nettoyer_nom_type(type_extrait)
        logger.info(f"[DEBUG EXTRACTION] {res_extraction}")
        if t_clean != "INCONNU":
            return t_clean, "CLASSIFICATION_IA_QWEN", description_extraite, metrics_complete

        return valeur_par_defaut, "IA_FALLBACK_INCONNU", description_extraite, metrics_complete

    except Exception as e:
        logger.error(f"[IA] Crash de l'analyse IA pour {nom_fichier}: {str(e)}", exc_info=True)
        meta_crash = construire_metriques(
            model="IA_CRASH_FALLBACK",
            confidence=1,
            raison=f"Erreur lors de l'analyse : {str(e)}"
        )
        return valeur_par_defaut, "IA_CRASH_FALLBACK", f"Erreur lors de l'analyse : {str(e)}", meta_crash

# def determiner_type_par_ia(file_path: str, ext: str, nom_fichier: str, contexte_few_shot: str, doc_id: str, db: Session ) -> tuple[str, str, str, dict]:
#     valeur_par_defaut = nom_fichier.upper()
#     logger.info(f"[IA] Début de l'analyse du document pour classification : {nom_fichier}")
#     try:
#         chemin_a_analyser = file_path
#         if ext in [".jpg", ".jpeg", ".png", ".tiff", ".bmp"]:
#             chemin_a_analyser = optimiser_image_pour_analyse(file_path, max_side=2048)
#         try:
#             texte_p1 = extraire_texte_integral(chemin_a_analyser)
#         finally:
#             # Nettoyage si un fichier temporaire _opti a été généré
#             if chemin_a_analyser != file_path and os.path.exists(chemin_a_analyser):
#                 try:
#                     os.remove(chemin_a_analyser)
#                 except Exception:
#                     pass
                    
#         if isinstance(texte_p1, dict):
#             # Si c'est un dictionnaire (ex: extrait d'un Excel), on fusionne les valeurs textuelles
#             texte_p1 = " ".join([str(val) for val in texte_p1.values() if val])
#         elif not isinstance(texte_p1, str):
#             texte_p1 = str(texte_p1) if texte_p1 is not None else ""
                    
#         if not texte_p1 or not texte_p1.strip():
#             meta_fallback = construire_metriques(
#                 model="IA_FALLBACK_TEXTE_VIDE",
#                 confidence=1,
#                 raison="Le texte extrait de la première page est vide."
#             )
#             logger.warning(f"[IA] Texte extrait de la première page vide pour : {nom_fichier}")
#             return valeur_par_defaut, "IA_FALLBACK_TEXTE_VIDE", "Le texte extrait est vide.", meta_fallback
            
#         logger.info(f"[IA] Envoi du texte extrait à Qwen pour {nom_fichier}...")
#         res_ia = classifier_texte_document(texte_p1, contexte_few_shot)
#         type_extrait = "INCONNU"
#         description_extraite = ""
#         metrics_extraites = {}
        
#         if isinstance(res_ia, tuple):
#             logger.info(f"[IA] llm_analyzer a renvoyé un tuple : {res_ia}")
#             type_extrait = res_ia[0] if len(res_ia) > 0 else "INCONNU"
#             description_extraite = res_ia[1] if len(res_ia) > 1 else ""
#             metrics_extraites = res_ia[2] if len(res_ia) > 2 else {}
#         elif isinstance(res_ia, str):
#             type_extrait = res_ia
#             description_extraite = "Classifié par analyse de contenu."
#         langue_ia = metrics_extraites.get("detected_language", "fr") if metrics_extraites else "fr"
            
#         metrics_complete = construire_metriques(
#             model=metrics_extraites.get("model", "QWEN_LLM"),
#             confidence=metrics_extraites.get("confidence_score"),
#             keywords=metrics_extraites.get("extracted_keywords"),
#             language=langue_ia,
#             texte=texte_p1,
#             raison=description_extraite,
#             extra_metrics=metrics_extraites
#         )
#         t_clean = nettoyer_nom_type(type_extrait)
#         # === CRÉATION DU LOG D'AUDIT EN BDD ===
#         #log_audit = ClassificationAuditLog(
#            # document_id=doc_id,  # L'ID du TenderDocument en cours
#            # predicted_type=t_clean if t_clean != "INCONNU" else type_extrait,
#            # classification_reason=description_extraite,
#            # confidence_score=metrics_extraites.get("confidence_score"),
#            # detected_language=langue_ia,
#            # extracted_keywords=metrics_extraites.get("extracted_keywords"),
#            # model_used=metrics_extraites.get("model", "qwen"),
#            # execution_duration_sec=metrics_extraites.get("ollama_total_duration"),
#            # prompt_tokens=metrics_extraites.get("prompt_tokens"),
#            # generated_tokens=metrics_extraites.get("generated_tokens"),
#            # text_length_chars=len(texte_p1),
#            # text_word_count=len(texte_p1.split()),
#            # has_uncertainty_keywords=metrics_extraites.get("has_uncertainty_keywords", False),
#            # validation_status="PENDING"
#         #)
#         #db.add(log_audit)
#         if t_clean != "INCONNU":
#             logger.info(f"[IA] Succès : Qwen a classifié le document en '{t_clean}'")
#             return t_clean, "CLASSIFICATION_IA_QWEN", description_extraite, metrics_complete
            
#         logger.warning(f"[IA] Qwen a renvoyé 'INCONNU' ou un échec pour {nom_fichier}. Utilisation du nom par défaut.")
#         return valeur_par_defaut, "IA_FALLBACK_INCONNU", description_extraite, metrics_complete
#     except Exception as e:
#         logger.error(f"[IA] Crash de l'analyse IA pour {nom_fichier}: {str(e)}", exc_info=True)
#         meta_crash = construire_metriques(
#             model="IA_CRASH_FALLBACK",
#             confidence=1,
#             raison=f"Erreur lors de l'analyse : {str(e)}"
#         )
        
#         try:
#             log_crash = ClassificationAuditLog(
#                 document_id=doc_id,
#                 predicted_type="CRASH_ERROR",
#                 classification_reason=f"Erreur lors de l'analyse : {str(e)}",
#                 model_used="qwen",
#                 validation_status="FAILED"
#             )
#             db.add(log_crash)
#         except Exception as log_err:
#             logger.error(f"[IA] Impossible d'ajouter le log de crash à la session BDD: {str(log_err)}")
#         return valeur_par_defaut, "IA_CRASH_FALLBACK", f"Erreur lors de l'analyse : {str(e)}", meta_crash
   
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
                            
                        # 1. Étape Primitives + Vérification LLM par lots de 10 pages
                        type_primitive = appliquer_types_primitifs(nom_fichier, ext)
                        logger.info(f"[PRIMITIF] {nom_fichier} -> {type_primitive}")
                        # Extraction de 100% du texte par lots de 10 pages
                        if ext == ".pdf":
                            extraction = extraire_texte_integral(chemin_original)

                            page_count = extraction.get("page_count")
                            word_count = extraction.get("word_count")
                            file_size_mb = extraction.get("file_size_mb")
                            ocr_duration_sec = extraction.get("ocr_duration_sec")
                            
                            is_scanned_global = extraction["is_scanned"]
                            inspection_method_global = extraction["inspection_method"]
                            
                            #lots = extraire_texte_par_lots(chemin_original, taille_lot=10)
                            lots = extraction["lots"]
                            texte_global_condense = "\n".join(
                                lot["texte"][:1500]
                                for lot in lots
                            )

                        else:
                            extraction = extraire_texte_integral(chemin_original)

                            if isinstance(extraction, dict):
                                texte_global_condense = extraction.get("text", "")
                                is_scanned_global = extraction.get("is_scanned", False)
                                inspection_method_global = extraction.get(
                                    "inspection_method",
                                    "NATIVE_TEXT_PYMUPDF"
                                )
                                page_count=extraction.get("page_count")
                                word_count=extraction.get("word_count")
                                file_size_mb=extraction.get("file_size_mb")
                                ocr_duration_sec=extraction.get("ocr_duration_sec")
                            else:
                                texte_global_condense = str(extraction)

                            if not texte_global_condense.strip():
                                texte_global_condense = nom_fichier

                        #if ext == ".pdf":
                            #is_scanned_global = any(
                                #lot.get("is_scanned", False)
                                #for lot in lots
                            #)

                            #inspection_method_global = (
                                #"FAST_OCR_ONNX_FULL_PAGE"
                                #if is_scanned_global
                                #else "NATIVE_TEXT_PYMUPDF"
                            #)
                        # logger.info(
                        #     "[DIAG AVANT LLM] "
                        #     f"page_count={page_count} | "
                        #     f"word_count={word_count} | "
                        #     f"file_size_mb={file_size_mb} | "
                        #     f"ocr_duration_sec={ocr_duration_sec}"
                        # )
                        # Vérification LLM (validation du primitif ou classification directe)
                        res_llm = verifier_ou_classifier_par_llm(texte_global_condense, type_primitif_detecte=type_primitive, 
                        is_scanned=is_scanned_global, 
                        inspection_method=inspection_method_global, 
                        page_count=page_count, 
                        word_count=word_count, 
                        file_size_mb=file_size_mb,          
                        ocr_duration_sec=ocr_duration_sec
                        )
                        # Variable booléenne explicitement définie
                        est_primitive_valide = res_llm.get("est_valide", False) and res_llm.get("type_confirme") != "AUTRE"
                        f_norm = nom_fichier.lower().strip()
    
                        type_surcharge = None                                
                        if not est_primitive_valide:
                            if MOTS_CLES_FORTS_CPS.search(f_norm):
                                type_surcharge = "CPS"
                            elif MOTS_CLES_AVIS_FR.search(f_norm):
                                type_surcharge = "AVIS_FRANCAIS"
                            elif MOTS_CLES_AVIS_AR.search(f_norm):
                                type_surcharge = "AVIS_ARABE"
                            elif MOTS_CLES_AVIS_GEN.search(f_norm):
                                type_surcharge = "AVIS"
                            elif MOTS_CLES_RC.search(f_norm):
                                type_surcharge = "RC"
                            elif MOTS_CLES_ACTE.search(f_norm):
                                type_surcharge = "ACTE_ENGAGEMENT"
                            elif MOTS_CLES_DECLARATION.search(f_norm):
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
                            logger.info(res_llm["metrics"])
                            metrics_ia = copy.deepcopy(res_llm["metrics"])
                            metrics_ia["detected_language"] = langue_detecte

                            metrics_ia["model"] = "PRIMITIVE_RULES_OVERRIDE"
                            metrics_ia["confidence_score"] = res_llm["metrics"].get("confidence_score", 5)
                            metrics_ia["extracted_keywords"] = [
                                type_document.lower(),
                                ext.replace(".", "")
                            ]
                            logger.info(metrics_ia)
                            logger.info(f"      -> Classifié par Surcharge Nom Fichier : '{type_surcharge}' ({langue_detecte})")
                        elif est_primitive_valide:
                            type_document = res_llm["type_confirme"]
                            raison_classification = "REGLES_PRIMITIVES_VALIDEES_LLM"
                            description_classification = f"Validé par LLM ({res_llm.get('justification', '')})"
                            langue_detecte = res_llm.get("langue", "fr").lower()
                            
                            arabic_chars = len(re.findall(r'[\u0600-\u06FF]', texte_global_condense))
                            latin_chars = len(re.findall(r'[A-Za-zÀ-ÿ]', texte_global_condense))

                            if arabic_chars > latin_chars:
                                langue_detecte = "ar"
                            else:
                                langue_detecte = "fr"
                                
                            logger.info(res_llm["metrics"])
                            metrics_ia = copy.deepcopy(res_llm["metrics"])
                            metrics_ia["detected_language"] = langue_detecte

                            metrics_ia["model"] = "PRIMITIVE_RULES_LLM"
                            metrics_ia["confidence_score"] = res_llm["metrics"].get("confidence_score",    5)
                            metrics_ia["extracted_keywords"] = [
                                type_document.lower(),
                                ext.replace(".", "")
                            ]
                            logger.info(metrics_ia)
                            logger.info(f"      -> Classifié & Validé LLM : '{type_document}' ({langue_detecte})")
                        else:
                            # 2. Étape Fallback IA si la règle primitive est rejetée ou absente
                            logger.info("      -> Primitif non validé ou absent. Détection de contenu IA par lots...")
                            type_document, raison_classification, description_classification, metrics_ia = determiner_type_par_ia(
                                chemin_original, ext, nom_fichier, contexte_few_shot, doc.id, db
                            )
                            modele_utilise = "ia_fallback_llm"
                        t_clean = nettoyer_nom_type(type_document)
                            
                        # 3. Étape Découpage PDF / Word
                        ext_autorisees = [".pdf", ".docx", ".doc"]
                        if ext in ext_autorisees:
                            fichiers_finaux, est_un_split, desc_decoupage = verifier_et_decouper_document(
                                chemin_original, nom_fichier, t_clean,
                                extraction=extraction
                            )
                            if desc_decoupage:
                                description_classification = f"{description_classification} | {desc_decoupage}".strip(" |")
                        else:
                            fichiers_finaux = [(t_clean, chemin_original)]
                            est_un_split = False
                            description_classification = f"Fichier {ext} conservé sans analyse de découpage."
                            
                        if not isinstance(metrics_ia, dict):
                            metrics_ia = construire_metriques(model="UNKNOWN", confidence=0, raison="Métadonnées indisponibles")
                            
                        # 4. Déplacement physique, mise à jour BDD et Nettoyage
                        # 4. Déplacement physique, mise à jour BDD et Nettoyage
                        for idx, (t_final, path_source) in enumerate(fichiers_finaux):
                            t_final_clean = nettoyer_nom_type(t_final)
                            dossier_cible = BASE_STORAGE_DIR / "classified" / identifiant_dossier / t_final_clean
                            os.makedirs(dossier_cible, exist_ok=True)
                            
                            if not est_un_split:
                                nom_final_fichier = nom_fichier
                            else:
                                nom_sans_extension = os.path.splitext(nom_fichier)[0]
                                nom_final_fichier = f"{t_final_clean}_{idx}_{nom_sans_extension}.pdf"
                            
                            chemin_destination = os.path.join(dossier_cible, nom_final_fichier)
                            shutil.copy2(path_source, chemin_destination)
                            logger.info(f"      [Fichier] Copie effectuée vers -> {chemin_destination}")
                                    
                            if est_un_split and os.path.exists(path_source): 
                                if str(path_source).startswith(str(TEMP_DIR)):
                                    try:
                                        os.remove(path_source)
                                        logger.info(f"   [Nettoyage] Fichier temporaire supprimé : {path_source}")
                                    except Exception as e:
                                        logger.error(f"   [Erreur] Nettoyage impossible pour {path_source} : {e}")

                            temps_reponse_doc = time.time() - doc_start_time
                            
                            # -------------------------------------------------------------
                            # FIX : Copie profonde et isolation stricte du dictionnaire JSON
                            # -------------------------------------------------------------
                            # --- LOG DE DIAGNOSTIC AVANT INSERTION AUDIT ---
                            metadata_segment = copy.deepcopy(metrics_ia or {})
                            
                            if est_un_split:
                                keywords = list(metadata_segment.get("extracted_keywords") or [])
                                if "split_pdf" not in keywords:
                                    keywords.append("split_pdf")
                                metadata_segment["extracted_keywords"] = keywords
                                metadata_segment["is_split_segment"] = True
                                metadata_segment["segment_index"] = idx
                                
                            logger.info(f"    [DIAG] Fichier: {nom_fichier} | inspection_method reçu: {metadata_segment.get('inspection_method')} | is_scanned: {metadata_segment.get('is_scanned')}")


                            # Détermination unifiée du modèle pour le Log d'Audit
                            if "SURCHARGE_NOM_FICHIER" in raison_classification:
                                modele_log = "primitive_rules_override"
                            elif est_primitive_valide:
                                modele_log = "primitive_rules_llm"
                            else:
                                modele_log = metadata_segment.get("model", "qwen")
                                
                            logger.info(
                                "[DEBUG BDD] metadata_segment = %s",
                                metadata_segment
                            )

                            if idx == 0:
                                doc.file_type = t_final_clean
                                doc.is_classified = True
                                doc.is_scanned = metadata_segment.get("is_scanned", False)
                                doc.classification_reason = raison_classification
                                doc.classification_description = description_classification
                                doc.classified_at = maintenant
                                doc.classified_file_path = chemin_destination 
                                doc.response_time = temps_reponse_doc
                                doc.page_count = metadata_segment.get("page_count")
                                doc.word_count = metadata_segment.get("word_count")
                                doc.file_size_mb = metadata_segment.get("file_size_mb")
                                doc.ocr_duration_sec = metadata_segment.get("ocr_duration_sec")
                                doc.analysis_metadata = metadata_segment
                                doc.validation_status = metadata_segment.get("validation_status")
                                doc.confidence_score = metadata_segment.get("confidence_score")
                                doc.prompt_tokens = metadata_segment.get("prompt_tokens")
                                doc.generated_tokens = metadata_segment.get("generated_tokens")
                                doc.detected_language = metadata_segment.get("detected_language", "fr")
                                doc.text_length_chars = metadata_segment.get("text_length_chars", 0)
                                doc.text_word_count = metadata_segment.get("text_word_count", 0)
                                doc.inspection_method = metadata_segment.get("inspection_method") or ("RULES_ENGINE" if est_primitive_valide else "QWEN_LLM")
                                doc.model_used = modele_log
                                doc.file_type = t_final_clean
                                logger.info(f"      [BDD] Entrée principale ID {doc.id} mise à jour en {temps_reponse_doc:.2f}s.")

                                # logger.info(
                                #     "[DEBUG DOC] "
                                #     f"page_count={doc.page_count} "
                                #     f"word_count={doc.word_count} "
                                #     f"file_size_mb={doc.file_size_mb} "
                                #     f"ocr_duration_sec={doc.ocr_duration_sec}"
                                # )
                                log_principal = ClassificationAuditLog(
                                    document_id=doc.id,
                                    predicted_type=t_final_clean,
                                    classification_reason=f"{raison_classification} | {description_classification}".strip(" |"),
                                    confidence_score=metadata_segment.get("confidence_score"),
                                    detected_language=metadata_segment.get("detected_language", "fr"),
                                    extracted_keywords=metadata_segment.get("extracted_keywords", []),
                                    execution_duration_sec=temps_reponse_doc,
                                    text_length_chars=metadata_segment.get("text_length_chars", 0),
                                    text_word_count=metadata_segment.get("text_word_count", 0),
                                    has_uncertainty_keywords=metadata_segment.get("has_uncertainty_keywords", False),
                                    is_scanned=metadata_segment.get("is_scanned", False),
                                    inspection_method=metadata_segment.get("inspection_method") or ("RULES_ENGINE" if est_primitive_valide else "QWEN_LLM"),
                                    prompt_tokens=metadata_segment.get("prompt_tokens"),
                                    generated_tokens=metadata_segment.get("generated_tokens"),
                                    ollama_total_duration=metadata_segment.get("ollama_total_duration"),
                                    model_used=modele_log,
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
                                    #is_scanned=metadata_segment.get("is_scanned", False),
                                    classification_reason="DECOUPAGE_PDF_AUTOMATIQUE",
                                    classification_description=f"Segment découpé automatiquement. Analyse parente : {description_classification}",
                                    classified_at=maintenant,
                                    response_time=temps_reponse_doc,
                                    analysis_metadata=metadata_segment,
                                    validation_status="PENDING",
                                    # page_count=metadata_segment.get("page_count"),
                                    # word_count=metadata_segment.get("word_count"),
                                    # file_size_mb=metadata_segment.get("file_size_mb"),
                                    # ocr_duration_sec=metadata_segment.get("ocr_duration_sec"),
                                    #confidence_score=metadata_segment.get("confidence_score"),
                                    #prompt_tokens=metadata_segment.get("prompt_tokens"),
                                    #generated_tokens=metadata_segment.get("generated_tokens"),
                                    #detected_language=metadata_segment.get("detected_language", "fr"),
                                    #text_length_chars=metadata_segment.get("text_length_chars", 0),
                                    #text_word_count=metadata_segment.get("text_word_count", 0),
                                    #inspection_method="PDF_SPLITTER",
                                    #model_used="pdf_splitter_llm"
                                )
                                db.add(nouveau_morceau)
                                db.flush()
                                
                                log_segment = ClassificationAuditLog(
                                    document_id=nouveau_morceau.id,
                                    predicted_type=t_final_clean,
                                    classification_reason="DECOUPAGE_PDF_AUTOMATIQUE",
                                    confidence_score=metadata_segment.get("confidence_score"),
                                    detected_language=metadata_segment.get("detected_language", "fr"),
                                    extracted_keywords=metadata_segment.get("extracted_keywords", []),
                                    execution_duration_sec=temps_reponse_doc,
                                    text_length_chars=metadata_segment.get("text_length_chars", 0),
                                    text_word_count=metadata_segment.get("text_word_count", 0),
                                    is_scanned=metadata_segment.get("is_scanned", False),
                                    inspection_method="PDF_SPLITTER",
                                    model_used="pdf_splitter_llm",
                                    validation_status="PENDING"
                                )
                                db.add(log_segment)
                                logger.info(f"      [BDD] Nouveau segment ID {nouveau_morceau.id} enregistré avec AuditLog.")                  
                        db.commit()
                        # logger.info(
                        #     "[DEBUG DB AFTER COMMIT] "
                        #     f"page_count={doc.page_count} "
                        #     f"word_count={doc.word_count} "
                        #     f"file_size_mb={doc.file_size_mb} "
                        #     f"ocr_duration_sec={doc.ocr_duration_sec}"
                        # )
                        
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
        db.close() # 2. FERMETURE OBLIGATOIRE de la session à la fin du traitement