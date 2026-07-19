import os, shutil, time, logging, re
from pathlib import Path
from datetime import datetime
from sqlalchemy.orm import Session
from pypdf import PdfReader, PdfWriter
from backend.app.database.models import TenderDocument, Tender
from backend.app.modules.ai_processor.ocr_engine import extraire_texte_premiere_page, extraire_texte_page_pdf
from backend.app.modules.ai_processor.llm_analyzer import classifier_texte_document, classifier_page_pour_decoupage
from backend.app.modules.ai_processor.learning_service import WaraqLearningEngine

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

def determiner_type_par_ia(file_path: str, ext: str, nom_fichier: str, contexte_few_shot: str) -> tuple[str, str, str, dict]:
    valeur_par_defaut = nom_fichier.upper()
    logger.info(f"[IA] Début de l'analyse du document pour classification : {nom_fichier}")
    try:
        texte_p1 = extraire_texte_premiere_page(file_path, ext)
        if not texte_p1 or not texte_p1.strip():
            logger.warning(f"[IA] Texte extrait de la première page vide pour : {nom_fichier}")
            return valeur_par_defaut, "IA_FALLBACK_TEXTE_VIDE", "Le texte extrait est vide.", {}
            
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

        if type_extrait and str(type_extrait).strip().upper() != "INCONNU":
            nettoye = str(type_extrait).strip().replace(":", " ").replace("/", " ").split()[0]
            logger.info(f"[IA] Succès : Qwen a classifié le document en '{nettoye}'")
            return nettoye.upper(), "CLASSIFICATION_IA_QWEN", description_extraite, metrics_extraites
            
        logger.warning(f"[IA] Qwen a renvoyé 'INCONNU' ou un échec pour {nom_fichier}. Utilisation du nom par défaut.")
        return valeur_par_defaut, "IA_FALLBACK_INCONNU", description_extraite, metrics_extraites
    except Exception as e:
        logger.error(f"[IA] Crash de l'analyse IA pour {nom_fichier}: {str(e)}", exc_info=True)
        return valeur_par_defaut, "IA_CRASH_FALLBACK", f"Erreur lors de l'analyse : {str(e)}", {}

def appliquer_types_primitifs(nom_fichier: str, ext: str) -> str | None:
    f_norm = nom_fichier.lower().strip()
    if ext in [".xlsx", ".xls"]:
        return "BORDEREAU_PRIX"
    elif f_norm.startswith("avis fr"): return "AVIS_FRANCAIS"
    elif f_norm.startswith("avis ar"): return "AVIS_ARABE"
    elif f_norm.startswith("avis"): return "AVIS"
    elif f_norm.startswith("cps"): return "CPS"
    elif f_norm.startswith("rc") or f_norm.startswith("reglement"): return "RC"
    elif f_norm.startswith("acte d'engagement"): return "ACTE_ENGAGEMENT"
    elif f_norm.startswith("declaration sur l'honneur"): return "DECLARATION_HONNEUR"
    elif f_norm.startswith("bdr") or f_norm.startswith("bordereau"): return "BORDEREAU_PRIX"
    return None

def verifier_et_decouper_pdf(file_path: str, nom_fichier: str) -> list:
    valeur_par_defaut = nom_fichier.upper()
    try:
        reader = PdfReader(file_path)
        nb_pages = len(reader.pages)
        
        if nb_pages <= 20:
            return []
            
        logger.info(f"[DECOUPAGE] PDF volumineux détecté ({nb_pages} pages) pour {nom_fichier}. Analyse des segments...")
        segments = []
        page_debut = 0
        type_courant = None
        
        for i in range(0, nb_pages, 3):
            txt_page = extraire_texte_page_pdf(file_path, i, reader)
            type_page = classifier_page_pour_decoupage(txt_page)

            if type_courant is None and type_page != "INCONNU":
                type_courant = type_page
            elif type_page != type_courant and type_page in ["RC", "CPS", "BORDEREAU_PRIX"]:
                if type_courant:
                    logger.info(f"[DECOUPAGE] Changement détecté à la page {i}: Fin de {type_courant}, début potentiel de {type_page}")
                    segments.append((type_courant, page_debut, i))
                type_courant = type_page
                page_debut = i
                
        type_final_segment = type_courant if type_courant else valeur_par_defaut
        segments.append((type_final_segment, page_debut, nb_pages))
        
        if len(segments) <= 1:
            logger.info(f"[DECOUPAGE] Le PDF {nom_fichier} seems homogène. Pas de découpage nécessaire.")
            return []
            
        logger.info(f"[DECOUPAGE] Extraction de {len(segments)} sous-documents pour {nom_fichier}...")
        fichiers_divises = []
        base_dir = os.path.dirname(file_path)
        
        for idx, (type_seg, dep, fin) in enumerate(segments):
            writer = PdfWriter()
            for p_num in range(dep, fin):
                writer.add_page(reader.pages[p_num])
                
            type_seg_clean = str(type_seg).strip().replace(":", "_").replace("/", "_").split()[0].upper()
            nom_split = f"split_{idx}_{type_seg_clean}_{os.path.basename(file_path)}"
            chemin_split = os.path.join(base_dir, nom_split)
            with open(chemin_split, "wb") as f:
                writer.write(f)
            fichiers_divises.append((str(type_seg), chemin_split))
            logger.info(f"[DECOUPAGE] Segment {idx} extrait : {nom_split} (Pages {dep} à {fin})")
            
        return fichiers_divises
    except Exception as e:
        logger.error(f"[DECOUPAGE] Erreur lors de l'analyse/découpage de {nom_fichier}: {e}", exc_info=True)
        return []

def executer_classification_post_scraping(db: Session):
    """Parcourt la base de données en regroupant le traitement par Appel d'Offres (Tender) 
    qui possède des documents non classifiés.
    """
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
        .subquery()
    )
    
    # Récupération des Tenders correspondants (sans DISTINCT global sur l'objet Tender)
    tenders_a_traiter = (
        db.query(Tender)
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
            date_ref = tender.extraction_date or datetime.utcnow()
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
                    maintenant = datetime.utcnow()
                    
                    # 1. Étape Primitives
                    type_document = appliquer_types_primitifs(nom_fichier, ext)
                    if type_document:
                        raison_classification = "REGLES_PRIMITIVES"
                        description_classification = f"Classifié automatiquement selon les règles de nommage primitives pour l'extension ou le préfixe."
                        metrics_ia = {}
                        logger.info(f"      -> Classifié par règles primitives : '{type_document}'")
                    else:
                        # 2. Étape Fallback IA
                        logger.info("      -> Aucune règle primitive validée. Passage à la détection de contenu...")
                        if ext in [".pdf", ".docx"]:
                            type_document, raison_classification, description_classification, metrics_ia = determiner_type_par_ia(chemin_original, ext, nom_fichier, contexte_few_shot)
                        else:
                            type_document = nom_fichier.upper()
                            raison_classification = "EXTENSION_NON_GEREE_NOM_MAJUSCULE"
                            description_classification = f"Extension '{ext}' non supportée par le moteur OCR/IA."
                            metrics_ia = {}
                            logger.info(f"      -> Extension '{ext}' non gérée par OCR. Nom mis en majuscule par défaut.")

                    t_clean = str(type_document).strip().replace(":", " ").replace("/", " ").split()[0].upper()

                    # 3. Étape Découpage PDF
                    fichiers_finaux = verifier_et_decouper_pdf(chemin_original, nom_fichier) if ext == ".pdf" else []     
                    est_un_split = len(fichiers_finaux) > 1

                    if not fichiers_finaux:
                        fichiers_finaux = [(t_clean, chemin_original)]

                    # 4. Déplacement physique, mise à jour BDD et Nettoyage
                    for idx, (t_final, path_source) in enumerate(fichiers_finaux):
                        t_final_clean = str(t_final).strip().replace(":", " ").replace("/", " ").split()[0].upper()
                        
                        dossier_cible = BASE_STORAGE_DIR / "classified" / identifiant_dossier / t_final_clean
                        os.makedirs(dossier_cible, exist_ok=True)
                        
                        nom_final_fichier = nom_fichier if not est_un_split else f"{t_final_clean}_{idx}_{nom_fichier}"
                        chemin_destination = os.path.join(dossier_cible, nom_final_fichier)
                        
                        shutil.copy2(path_source, chemin_destination)
                        logger.info(f"      [Fichier] Copie effectuée vers -> {chemin_destination}")

                        if est_un_split and os.path.exists(path_source):
                            try:
                                os.remove(path_source)
                                logger.info(f"      [Nettoyage] Segment temporaire supprimé de extracted : {path_source}")
                            except Exception as e:
                                logger.warning(f"      [Nettoyage] Impossible de supprimer {path_source}: {e}")

                        # Calcul de la durée pour ce document précis
                        temps_reponse_doc = time.time() - doc_start_time

                        if idx == 0:
                            doc.file_type = t_final_clean
                            doc.is_classified = True
                            doc.classification_reason = raison_classification
                            doc.classification_description = description_classification
                            doc.classified_at = maintenant
                            doc.classified_file_path = chemin_destination 
                            doc.response_time = temps_reponse_doc
                            doc.analysis_metadata = metrics_ia
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
                                analysis_metadata=metrics_ia
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