from backend.app import database
import os, json
from datetime import datetime
from sqlalchemy.orm import Session
from backend.app.database.models import Tender, TenderDocument
from openpyxl import load_workbook, Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side 
import pandas as pd
import unicodedata

DATA_STORAGE_DIR = r"C:\Users\achra\Desktop\Intern\Project\marocao-platform\data_storage"
EXCEL_PATH = os.path.join(DATA_STORAGE_DIR, "tenders_export.xlsx")

class TenderManager:
    def __init__(self, db_session, data_dir):
        self.db = db_session
        self.data_dir = data_dir

    def is_already_processed(self, ref: str) -> bool:  
        # 1. Vérification BDD (Rien à changer ici, c'est déjà correct)
        exists_in_db = self.db.query(Tender).filter(Tender.reference == ref).first() is not None
        if exists_in_db:
            return True
            
        # 2. Vérification Locale (Corrigée)
        metadata_root = os.path.join(self.data_dir, "metadata")
        
        # On parcourt tous les dossiers de manière récursive
        for root, dirs, files in os.walk(metadata_root):
            for d in dirs:
                # On vérifie si la référence est AU DÉBUT du nom du dossier
                # On utilise .startswith() car c'est plus sûr
                if d.startswith(ref): 
                    return True
        return False

def extract_date_from_path(root_path: str):
    """
    Extrait la date et heure d'extraction à partir de l'arborescence.
    Ex: .../metadata/2026/07/01/04-2026-ENFI_11-07-57
    """
    try:
        # On récupère les parties du chemin
        parts = root_path.split(os.sep)
        # On suppose que les 3 derniers sont AAAA, MM, DD
        day = parts[-2]
        month = parts[-3]
        year = parts[-4]
        
        # Le nom du dossier contient HH-MM-SS
        folder_name = parts[-1]
        time_part = folder_name.split("_")[-1] # Récupère le HH-MM-SS
        
        date_str = f"{year}-{month}-{day} {time_part.replace('-', ':')}"
        return datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
    except:
        return datetime.now() # Fallback si erreur

def get_storage_paths(tender_reference: str):
    """
    Crée une structure propre avec un identifiant de microsecondes (batch de temps)
    pour différencier deux exécutions dans la même seconde.
    Structure : data_storage/TYPE/AAAA/MM/DD/REF_HH-MM-SS_batch_XXXXXX/
    """
    now = datetime.now()
    safe_ref = tender_reference.replace("/", "-").replace(" ", "_").strip()
    folder_name = f"{safe_ref}_{now.strftime('%H-%M-%S')}"
    date_path = now.strftime("%Y/%m/%d")
    
    paths = {
        "archive": os.path.join(DATA_STORAGE_DIR, "archives", date_path, folder_name),
        "extracted": os.path.join(DATA_STORAGE_DIR, "extracted", date_path, folder_name),
        "metadata": os.path.join(DATA_STORAGE_DIR, "metadata", date_path, folder_name)
    }
    
    for path in paths.values():
        os.makedirs(path, exist_ok=True)
        
    return paths

# def sync_local_tenders_to_db(db: Session):
#     metadata_dir = os.path.join(DATA_STORAGE_DIR, "metadata")
#     extracted_parent_dir = os.path.join(DATA_STORAGE_DIR, "extracted")
#     archives_dir = os.path.join(DATA_STORAGE_DIR, "archives")
    
#     if not os.path.exists(metadata_dir):
#         print("-> [Sync] Aucun dossier metadata trouvé.")
#         return {"processed": 0, "inserted": 0}

#     inserted_count = 0
#     processed_count = 0

#     for ref_folder in os.listdir(metadata_dir):
#         ref_path = os.path.join(metadata_dir, ref_folder)
#         if not os.path.isdir(ref_path):
#             continue
            
#         json_file_path = os.path.join(ref_path, "metadata.json")
#         if not os.path.exists(json_file_path):
#             continue
            
#         processed_count += 1
        
#         try:
#             with open(json_file_path, 'r', encoding='utf-8') as f:
#                 meta_data = json.load(f)
            
#             ref = meta_data.get("reference")
#             if not ref:
#                 continue

#             # Éviter les doublons : Vérification de la référence
#             exists = db.query(Tender).filter(Tender.reference == ref).first()
#             if exists:
#                 continue

#             # Détection optionnelle du fichier ZIP d'origine
#             zip_filename = f"{ref.replace('/', '_')}.zip"
#             local_zip = os.path.join(archives_dir, zip_filename)
#             local_zip_path = local_zip if os.path.exists(local_zip) else None

#             # Mapping complet des 24 champs de ton dictionnaire de parsing marocain
#             new_tender = Tender(
#                 reference=ref,
#                 title=meta_data.get("objet") or "Sans objet",
#                 buyer=meta_data.get("acheteur") or "Inconnu",
#                 type_annonce=meta_data.get("type_annonce"),
#                 procedure=meta_data.get("procedure"),
#                 categorie=meta_data.get("categorie"),
#                 allotissement=meta_data.get("allotissement"),
#                 lieu_execution=meta_data.get("lieu_execution"),
#                 estimated_budget=meta_data.get("budget"),
#                 reserve_pme=meta_data.get("reserve_pme"),
#                 domaines_activite=meta_data.get("domaines_activite"),
#                 adresse_retrait=meta_data.get("adresse_retrait"),
#                 adresse_depot=meta_data.get("adresse_depot"),
#                 lieu_ouverture=meta_data.get("lieu_ouverture"),
#                 prix_acquisition=meta_data.get("prix_acquisition"),
#                 provisional_caution=meta_data.get("caution"),
#                 qualifications=meta_data.get("qualifications"),
#                 agrements=meta_data.get("agrements"),
#                 variante=meta_data.get("variante"),
#                 deadline=meta_data.get("deadline"),
#                 prospectus_notices=meta_data.get("prospectus_notices"),
#                 reunion=meta_data.get("reunion"),
#                 visite_lieux=meta_data.get("visite_lieux"),
#                 contact_administratif=meta_data.get("contact_administratif"),
#                 local_zip_path=local_zip_path,
#                 metadata_json=meta_data
#             )
            
#             # Lecture de tous les fichiers présents dans le sous-dossier extracted/
#             specific_extracted_dir = os.path.join(extracted_parent_dir, ref)
#             if os.path.exists(specific_extracted_dir):
#                 for filename in os.listdir(specific_extracted_dir):
#                     full_file_path = os.path.join(specific_extracted_dir, filename)
#                     if os.path.isfile(full_file_path):
#                         f_upper = filename.upper()
                        
#                         # Détermination du type de document
#                         if "CPS" in f_upper:
#                             file_type = "CPS"
#                         elif "RC" in f_upper or "REGLEMENT" in f_upper:
#                             file_type = "RC"
#                         elif "AVIS" in f_upper:
#                             file_type = "AVIS"
#                         else:
#                             # Solution de repli : prend l'extension en majuscule ou le nom complet
#                             ext = os.path.splitext(filename)[1].replace(".", "").upper()
#                             file_type = ext if ext else "DOCUMENT"

#                         new_doc = TenderDocument(
#                             file_name=filename,
#                             file_type=file_type,
#                             file_path=full_file_path.replace("\\", "/"),
#                             extracted_text=None
#                         )
#                         new_tender.documents.append(new_doc)

#             db.add(new_tender)
#             inserted_count += 1

#             try:
#                 append_to_excel(meta_data, datetime.now().strftime("%Y-%m-%d %H:%M"))
#             except Exception as e:
#                 print(f"Erreur lors de l'export Excel pour {ref}: {e}")
            
#         except Exception as e:
#             print(f"Erreur de synchronisation pour la référence {ref_folder} : {e}")
#             db.rollback()

#     if inserted_count > 0:
#         db.commit()
#     print(f"-> [Sync BDD] Fini. {inserted_count} offres ajoutées avec succès.")
#     return {"processed": processed_count, "inserted": inserted_count}

def normalize_text(text: str) -> str:
    """Enlève les accents et met en minuscules."""
    nfkd_form = unicodedata.normalize('NFKD', text)
    return "".join([c for c in nfkd_form if not unicodedata.combining(c)]).lower()

def get_file_type(filename: str) -> str:
    # On convertit tout en minuscules pour ne plus se soucier des majuscules
    f_norm = normalize_text(filename)
    # f_lower = filename.lower()
    
    # 1. Traitement des cas spécifiques (du plus précis au plus général)
    if f_norm.startswith("avis fr"): return "AVIS_FRANCAIS"
    if f_norm.startswith("avis ar"): return "AVIS_ARABE"
    if f_norm.startswith("avis"): return "AVIS"
    if f_norm.startswith("cps"): return "CPS"
    if f_norm.startswith("rc") or f_norm.startswith("reglement"): return "RC"
    if f_norm.startswith("acte d'engagement"): return "ACTE_ENGAGEMENT"
    if f_norm.startswith("declaration sur l'honneur"): return "DECLARATION_HONNEUR"
    if f_norm.startswith("bdr") or f_norm.startswith("bordereau"): return "BORDEREAU_PRIX"
    
    # 2. Valeur par défaut : si rien ne correspond, on retourne le nom du fichier
    # Exemple: "Plan_architecte.pdf" -> retournera "PLAN_ARCHITECTE.PDF"
    return filename.upper()

def sync_local_tenders_to_db(db: Session):
    """
    Synchronise les métadonnées et documents stockés localement vers la base de données.
    Parcourt récursivement les dossiers pour trouver metadata.json.
    """
    metadata_root = os.path.join(DATA_STORAGE_DIR, "metadata")
    extracted_root = os.path.join(DATA_STORAGE_DIR, "extracted")
    archives_dir = os.path.join(DATA_STORAGE_DIR, "archives")
    
    if not os.path.exists(metadata_root):
        print("-> [Sync] Aucun dossier metadata trouvé.")
        return {"processed": 0, "inserted": 0}

    # --- OPTIMISATION : Indexation des chemins d'archives ---
    # On stocke { "nom_dossier": "chemin_complet" } 
    # Cela évite de parcourir l'arborescence à chaque fois
    archives_map = {}
    if os.path.exists(archives_dir):
        for root_arch, _, files_arch in os.walk(archives_dir):
            for file in files_arch:
                if file.endswith(".zip"):
                    # On garde la structure : le nom du dossier sert de clé pour la recherche
                    archives_map[os.path.basename(root_arch)] = os.path.join(root_arch, file).replace("\\", "/")

    inserted_count = 0
    processed_count = 0

    # 1. Utilisation de os.walk pour traverser tous les sous-dossiers (AAAA/MM/DD/...)
    for root, dirs, files in os.walk(metadata_root):
        if "metadata.json" in files:
            processed_count += 1
            json_file_path = os.path.join(root, "metadata.json")
            extraction_dt = extract_date_from_path(root)
            
            try:
                with open(json_file_path, 'r', encoding='utf-8') as f:
                    meta_data = json.load(f)
                
                ref = meta_data.get("reference")
                if not ref:
                    continue

                # 2. Vérification stricte des doublons en base de données
                exists = db.query(Tender).filter(Tender.reference == ref).first()
                if exists:
                    continue

                # Détection optionnelle du fichier ZIP d'origine
                # zip_filename = f"{ref.replace('/', '_')}.zip" 
                # local_zip = os.path.join(archives_dir, zip_filename)
                # 1. Chercher le fichier ZIP dynamiquement en parcourant les sous-dossiers
                # 1. Préparation de la référence sécurisée pour comparaison
                ref_to_find = ref.replace("/", "-").replace(" ", "_")

                local_zip_path = None

                # On parcourt récursivement toute l'arborescence de 'archives'
                # for root_arch, dirs_arch, files_arch in os.walk(archives_dir):
                #     # On vérifie si le nom du dossier actuel contient notre référence sécurisée
                #     # root_arch est par ex: .../archives/2026/07/01/04-2026-ENFI_11-07-57
                #     if ref_to_find in os.path.basename(root_arch):
                #         # On cherche un fichier .zip dans ce dossier
                #         for file in files_arch:
                #             if file.endswith(".zip"):
                #                 local_zip_path = os.path.join(root_arch, file).replace("\\", "/")
                #                 break # ZIP trouvé 
                #     if local_zip_path:
                #         break # On arrête la recherche globale

                # --- RECHERCHE OPTIMISÉE (gardant votre logique sémantique) ---
                # On parcourt nos dossiers indexés au lieu de refaire un os.walk()
                for folder_name, zip_full_path in archives_map.items():
                    if ref_to_find in folder_name:
                        local_zip_path = zip_full_path
                        break 
                # -------------------------------------------------------------

                # 3. Création de l'objet Tender
                new_tender = Tender(
                    reference=ref,
                    title=meta_data.get("objet") or "Sans objet",
                    buyer=meta_data.get("acheteur") or "Inconnu",
                    type_annonce=meta_data.get("type_annonce"),
                    procedure=meta_data.get("procedure"),
                    categorie=meta_data.get("categorie"),
                    allotissement=meta_data.get("allotissement"),
                    lieu_execution=meta_data.get("lieu_execution"),
                    estimated_budget=meta_data.get("budget"),
                    reserve_pme=meta_data.get("reserve_pme"),
                    domaines_activite=meta_data.get("domaines_activite"),
                    adresse_retrait=meta_data.get("adresse_retrait"),
                    adresse_depot=meta_data.get("adresse_depot"),
                    lieu_ouverture=meta_data.get("lieu_ouverture"),
                    prix_acquisition=meta_data.get("prix_acquisition"),
                    provisional_caution=meta_data.get("caution"),
                    qualifications=meta_data.get("qualifications"),
                    agrements=meta_data.get("agrements"),
                    variante=meta_data.get("variante"),
                    deadline=meta_data.get("deadline"),
                    prospectus_notices=meta_data.get("prospectus_notices"),
                    reunion=meta_data.get("reunion"),
                    visite_lieux=meta_data.get("visite_lieux"),
                    contact_administratif=meta_data.get("contact_administratif"),
                    local_zip_path=local_zip_path,
                    extraction_date=extraction_dt,
                    metadata_json=meta_data,
                )
                
                # 4. Association des documents extraits
                # Le dossier correspondant dans 'extracted' a le même nom que le dossier contenant metadata.json
                folder_name = os.path.basename(root)
                date_path = os.path.relpath(root, metadata_root) # ex: 2026/06/30/REF_...
                date_dir = os.path.dirname(date_path)
                specific_extracted_dir = os.path.join(extracted_root, date_dir, folder_name)

                # if os.path.exists(specific_extracted_dir):
                #     for filename in os.listdir(specific_extracted_dir):
                #         full_file_path = os.path.join(specific_extracted_dir, filename)
                #         if os.path.isfile(full_file_path):
                #             f_upper = filename.upper()
                #             # Logique de typage
                #             if "CPS" in f_upper: file_type = "CPS"
                #             elif "RC" in f_upper or "REGLEMENT" in f_upper: file_type = "RC"
                #             elif "AVIS" in f_upper: file_type = "AVIS"
                #             else: file_type = os.path.splitext(filename)[1].replace(".", "").upper() or "DOCUMENT"

                #             new_doc = TenderDocument(
                #                 file_name=filename,
                #                 file_type=file_type,
                #                 file_path=full_file_path.replace("\\", "/"),
                #             )
                #             new_tender.documents.append(new_doc)
                if os.path.exists(specific_extracted_dir):
                    for filename in os.listdir(specific_extracted_dir):
                        full_file_path = os.path.join(specific_extracted_dir, filename)
                        if os.path.isfile(full_file_path):
                            # f_upper = filename.upper()
                            file_type = get_file_type(filename)
                            
                            # # Typage dynamique : on cherche si un mot-clé du mapping est dans le nom
                            # file_type = None
                            # for key, val in TYPE_MAPPING.items():
                            #     if key in f_upper:
                            #         file_type = val
                            #         break
                            
                            # # Si aucun mot-clé trouvé, on prend l'extension
                            # if not file_type:
                            #     file_type = os.path.splitext(filename)[1].replace(".", "").upper() or "DOCUMENT"

                            new_doc = TenderDocument(
                                file_name=filename,
                                file_type=file_type,
                                file_path=full_file_path.replace("\\", "/"),
                            )
                            new_tender.documents.append(new_doc)

                db.add(new_tender)
                
                inserted_count += 1
                
            except Exception as e:
                print(f"Erreur lors du traitement de {root} : {e}")
                db.rollback()

    if inserted_count > 0:
        db.commit()
        
    print(f"-> [Sync BDD] Fini. {inserted_count} offres ajoutées.")
    return {"processed": processed_count, "inserted": inserted_count}

def append_to_excel_fast(meta_data: dict, sync_date: str, extraction_date: datetime):
    """Ajoute une ligne de manière optimisée avec openpyxl."""
    print(f"-> [Excel] Tentative d'ajout pour la référence : {meta_data.get('reference')}")
    print(f"-> [Excel] Chemin du fichier : {EXCEL_PATH}")
    # Liste des colonnes dans l'ordre pour garantir la cohérence  
    headers = [
        "Date d'importation", "Date d'extraction", "Référence", "Objet", "Acheteur public", 
        "Type d'annonce", "Procédure", "Catégorie principale", "Allotissement", 
        "Lieu d'exécution", "Estimation (en Dhs TTC)", "Réservé à la TPE et PME installées au Maroc", 
        "Domaines d'activité", "Adresse de retrait", "Adresse de dépôt", 
        "Lieu d'ouverture", "Prix d'acquisition", "Caution provisoire", 
        "Qualifications", "Agréments", "Variante", 
        "Date et heure limite de remise des plis", "Prospectus, notices", 
        "Réunion", "Visites des lieux", "Contact Administratif"
    ]

    # Préparation des données dans l'ordre des headers
    row_data = [
        sync_date, extraction_date.strftime("%Y-%m-%d %H:%M:%S"),meta_data.get("reference"), meta_data.get("objet"), meta_data.get("acheteur"),
        meta_data.get("type_annonce"), meta_data.get("procedure"), meta_data.get("categorie"),
        meta_data.get("allotissement"), meta_data.get("lieu_execution"), meta_data.get("budget"),
        meta_data.get("reserve_pme"), meta_data.get("domaines_activite"), meta_data.get("adresse_retrait"),
        meta_data.get("adresse_depot"), meta_data.get("lieu_ouverture"), meta_data.get("prix_acquisition"),
        meta_data.get("caution"), meta_data.get("qualifications"), meta_data.get("agrements"),
        meta_data.get("variante"), meta_data.get("deadline"), meta_data.get("prospectus_notices"),
        meta_data.get("reunion"), meta_data.get("visite_lieux"), meta_data.get("contact_administratif")
    ]

    # Si le fichier n'existe pas, on le crée avec les en-têtes
    if not os.path.exists(EXCEL_PATH):
        wb = Workbook()
        ws = wb.active
        ws.append(headers)
        wb.save(EXCEL_PATH)
    try:
        wb = load_workbook(EXCEL_PATH)
        ws = wb.active
        ws.append(row_data)
        apply_professional_style(ws)
        wb.save(EXCEL_PATH) 
    except PermissionError:
        print("!!! ERREUR : Fermez le fichier Excel pour permettre la mise à jour.")

# def export_all_tenders_to_excel(db: Session):
#     """
#     Exporte TOUTES les offres de la base de données vers le fichier Excel.
#     À utiliser pour initialiser votre fichier Excel.
#     """
#     tenders = db.query(Tender).all()
#     print(f"-> [Excel] Export de {len(tenders)} offres vers Excel...")  
    
#     for tender in tenders:
#         # On utilise le même dictionnaire que dans votre sync
#         # On suppose que vous avez stocké le metadata original dans Tender.metadata_json
#         meta_data = tender.metadata_json 
#         extraction_dt = tender.extraction_date if tender.extraction_date else datetime.now()
        
#         # Appel de votre fonction de mise à jour
#         append_to_excel_fast(meta_data, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), extraction_dt)
    
#     print("-> [Excel] Export terminé.")
def export_all_tenders_to_excel(db: Session):
    """
    Exporte TOUTES les offres de la base de données vers le fichier Excel.
    Remplace le fichier existant pour éviter les doublons.
    """
    print(f"-> [Excel] Export complet de la base vers Excel...")
    
    # 1. Créer un nouveau classeur propre
    wb = Workbook()
    ws = wb.active
    
    # 2. Ajouter les en-têtes
    headers = [
        "Date d'importation", "Date d'extraction", "Référence", "Objet", "Acheteur public", 
        "Type d'annonce", "Procédure", "Catégorie principale", "Allotissement", 
        "Lieu d'exécution", "Estimation (en Dhs TTC)", "Réservé à la TPE et PME installées au Maroc", 
        "Domaines d'activité", "Adresse de retrait", "Adresse de dépôt", 
        "Lieu d'ouverture", "Prix d'acquisition", "Caution provisoire", 
        "Qualifications", "Agréments", "Variante", 
        "Date et heure limite de remise des plis", "Prospectus, notices", 
        "Réunion", "Visites des lieux", "Contact Administratif"
    ]
    ws.append(headers)
    
    # 3. Récupérer toutes les données
    tenders = db.query(Tender).all()
    sync_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    for tender in tenders:
        meta_data = tender.metadata_json or {}
        extraction_dt = tender.extraction_date if tender.extraction_date else datetime.now()
        
        row_data = [
            sync_date, 
            extraction_dt.strftime("%Y-%m-%d %H:%M:%S"),
            meta_data.get("reference"), meta_data.get("objet"), meta_data.get("acheteur"),
            meta_data.get("type_annonce"), meta_data.get("procedure"), meta_data.get("categorie"),
            meta_data.get("allotissement"), meta_data.get("lieu_execution"), meta_data.get("budget"),
            meta_data.get("reserve_pme"), meta_data.get("domaines_activite"), meta_data.get("adresse_retrait"),
            meta_data.get("adresse_depot"), meta_data.get("lieu_ouverture"), meta_data.get("prix_acquisition"),
            meta_data.get("caution"), meta_data.get("qualifications"), meta_data.get("agrements"),
            meta_data.get("variante"), meta_data.get("deadline"), meta_data.get("prospectus_notices"),
            meta_data.get("reunion"), meta_data.get("visite_lieux"), meta_data.get("contact_administratif")
        ]
        ws.append(row_data)
    
    # 4. Appliquer le style et sauvegarder (écrase le fichier précédent)
    apply_professional_style(ws)
    wb.save(EXCEL_PATH)
    print(f"-> [Excel] Export terminé. {len(tenders)} offres exportées.") 

def apply_professional_style(ws):
    """Applique un style professionnel, filtres et bordures."""
    
    # Définition des styles
    header_font = Font(bold=True, color="FFFFFF", name='Arial', size=11)
    header_fill = PatternFill(start_color="2F75B5", end_color="2F75B5", fill_type="solid")
    center_alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    thin_border = Border(left=Side(style='thin'), right=Side(style='thin'), 
                         top=Side(style='thin'), bottom=Side(style='thin'))

    # 1. Appliquer le style au Header (Ligne 1)
    for cell in ws[1]:
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = center_alignment
        cell.border = thin_border

    # 2. Activer le filtre automatique (la petite flèche)
    # On définit la zone du filtre sur toute la première ligne
    ws.auto_filter.ref = ws.dimensions

    # 3. Style des données (Lignes 2+)
    for row in ws.iter_rows(min_row=2):
        for cell in row:
            cell.border = thin_border
            cell.alignment = Alignment(vertical="center", horizontal="left", wrap_text=True)

    # 4. Ajustement automatique de la largeur
    for col in ws.columns:
        max_length = 0
        column = col[0].column_letter
        for cell in col:
            try:
                # On force la conversion en str pour éviter les erreurs
                if cell.value:
                    val_len = len(str(cell.value))
                    if val_len > max_length:
                        max_length = val_len
            except:
                pass
        # Largeur minimale de 15, maximale de 50
        ws.column_dimensions[column].width = max(15, min(max_length + 2, 50))