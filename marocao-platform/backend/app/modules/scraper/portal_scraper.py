from selenium import webdriver
from backend.app.modules.scraper.utils import DATA_STORAGE_DIR
from selenium import webdriver
import time, json, os, shutil, zipfile
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from backend.app.modules.scraper.utils import get_storage_paths
from backend.app.modules.scraper.parser import parse_tender_metadata, save_metadata, parse_tender_lots
from backend.app.database import SessionLocal # Importe ta session DB
from backend.app.modules.scraper.utils import TenderManager

def remove_overlay(driver):
    """Tente de fermer le widget de chat ou tout overlay qui bloque les clics."""
    try:
        # Liste des sélecteurs CSS courants pour les launchers de chat sur ce portail
        selectors = [
            ".WACLauncher__CloseButtonIcon",
            ".WACLauncher__CloseButton",
            "button[aria-label='Close the chat launcher']",
            ".WACLauncherComplex__ContentButton"
        ]
        for selector in selectors:
            elements = driver.find_elements(By.CSS_SELECTOR, selector)
            for el in elements:
                if el.is_displayed():
                    driver.execute_script("arguments[0].click();", el)
                    print("-> [Info] Overlay fermé avec succès.")
                    time.sleep(1)
    except Exception:
        pass # On ignore si ça échoue, ce n'est pas critique

def extract_all_recursive(zip_path, destination_folder):
    """
    zip_path : chemin complet du zip (ex: .../archives/2026/07/08/REF_14-00-00.zip)
    destination_folder : dossier final (ex: .../extracted/2026/07/08/REF_14-00-00/)
    """
    # On s'assure que le dossier cible existe
    os.makedirs(destination_folder, exist_ok=True)
    
    # 1. Extraction du zip courant dans le dossier de la référence
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        zip_ref.extractall(destination_folder)
    
    # 2. Recherche de sous-zips dans ce dossier
    # On utilise os.walk pour parcourir tout ce qui vient d'être extrait
    for root, dirs, files in os.walk(destination_folder):
        for file in files:
            if file.lower().endswith('.zip'):
                sub_zip_path = os.path.join(root, file)
                
                # On crée un dossier au nom du zip pour ne pas mélanger les fichiers
                folder_name = os.path.splitext(file)[0]
                sub_destination = os.path.join(root, folder_name)
                
                # Appel récursif avec le nouveau sous-dossier
                extract_all_recursive(sub_zip_path, sub_destination)
                # --- SUPPRESSION APRÈS EXTRACTION ---
                # try:
                #     os.remove(sub_zip_path)
                #     print(f"-> [Nettoyage] Sous-zip supprimé : {file}")
                # except Exception as e:
                #     print(f"-> [Alerte] Impossible de supprimer {file} : {e}")

def wait_for_download(download_dir, timeout=60):
    seconds = 0
    while seconds < timeout:
        files = os.listdir(download_dir)
        # On ne veut que les fichiers finaux (souvent .zip)
        completed_files = [f for f in files if f.endswith('.zip')]
        
        if completed_files:
            latest_file = max([os.path.join(download_dir, f) for f in completed_files], key=os.path.getctime)
            # Vérifier que le fichier n'est pas en cours d'écriture (taille stable)
            initial_size = os.path.getsize(latest_file)
            time.sleep(2)
            if os.path.getsize(latest_file) == initial_size:
                return os.path.basename(latest_file)
        
        time.sleep(1)
        seconds += 1
    return None

def cleanup_temp_files(download_dir):
    for f in os.listdir(download_dir):
        if f.endswith('.crdownload') or f.endswith('.tmp'):
            try:
                os.remove(os.path.join(download_dir, f))
            except:
                pass

def fill_search_dates(driver, wait, config):
    """Remplit proprement les filtres de date et lance la recherche."""
    date_start = config.get('search', {}).get('date_start')
    date_end = config.get('search', {}).get('date_end')

    if date_start:
        input_start = wait.until(EC.presence_of_element_located((By.ID, "ctl0_CONTENU_PAGE_AdvancedSearch_dateMiseEnLigneCalculeStart")))
        input_start.clear()  # Ta méthode d'origine
        input_start.send_keys(date_start)

    if date_end:
        input_end = driver.find_element(By.ID, "ctl0_CONTENU_PAGE_AdvancedSearch_dateMiseEnLigneCalculeEnd")
        input_end.clear()    # Ta méthode d'origine
        input_end.send_keys(date_end)
        
    #driver.find_element(By.ID, "ctl0_CONTENU_PAGE_AdvancedSearch_lancerRecherche").click()
    search_btn = driver.find_element(By.ID, "ctl0_CONTENU_PAGE_AdvancedSearch_lancerRecherche")
    driver.execute_script("arguments[0].click();", search_btn)  

def run_scraper():
    # 1. Chargement de la configuration
    with open('backend/app/modules/scraper/config.json', 'r', encoding='utf-8') as f:
        config = json.load(f)
    
    # --- AJOUTER CETTE CONFIGURATION DES OPTIONS DE CHROME ---
    options = webdriver.ChromeOptions()
    
    # Définir le chemin absolu où Chrome doit télécharger les DCE
    # Ici, on crée un dossier temporaire 'downloads' à la racine de ton projet
    download_dir = r"C:\Users\achra\Desktop\Intern\Project\marocao-platform\temp_downloads"
    if not os.path.exists(download_dir):
        os.makedirs(download_dir)

    prefs = {
        "download.default_directory": download_dir,       # Dossier par défaut
        "download.prompt_for_download": False,            # Désactive la boîte de dialogue "Enregistrer sous"
        "download.directory_upgrade": True,
        "safebrowsing.enabled": True                      # Évite les blocages de sécurité sur les fichiers .zip/.rar
    }
    options.add_experimental_option("prefs", prefs)
    
    # On passe les options au driver
    driver = webdriver.Chrome(options=options)
    driver.maximize_window()
    wait = WebDriverWait(driver, 15)
    
    driver.get("https://www.marchespublics.gov.ma/index.php?page=entreprise.EntrepriseAdvancedSearch&searchAnnCons")

    db = SessionLocal() # Ouvre la session
    tender_manager = TenderManager(db, DATA_STORAGE_DIR) # Initialise le gestionnaire

    # Remplissage des filtres de date (Uniquement si renseignées dans la config)
    fill_search_dates(driver, wait, config)
    
    #processed = 0
    
    # # La boucle principale tourne tant qu'on n'a pas atteint l'objectif personnalisé
    # while processed < config['tenders_to_extract']:
    #     time.sleep(3) # Attente du rafraîchissement ou chargement de la page de liste
        
    #     # Récupération dynamique des boutons de la page courante
    #     buttons = driver.find_elements(By.XPATH, "//img[@alt='Accéder à la consultation']")
    #     tenders_on_page = len(buttons)
        
    #     if tenders_on_page == 0:
    #         print("Aucun appel d'offres trouvé sur cette page.")
    #         break
            
    #     # On parcourt les offres de la page une par une
    #     for i in range(tenders_on_page):
    #         # Condition d'arrêt dès que le quota personnalisé est atteint au milieu d'une page
    #         if processed >= config['tenders_to_extract']:
    #             break
                
    #         try:
    #             # Reciblage pour éviter StaleElementReference Exception
    #             buttons = driver.find_elements(By.XPATH, "//img[@alt='Accéder à la consultation']")
    #             buttons[i].click()
    #             time.sleep(2)

    #             # --- BLOC D'EXTRACTION CONDITIONNEL ET SÉCURISÉ ---
    #             lots_data = [] 

    #             # On cherche sans attendre indéfiniment
    #             detail_btns = driver.find_elements(By.XPATH, "//a[contains(@href, 'PopUpDetailLots')]")

    #             if detail_btns:
    #                 print("-> [Info] Bouton 'Détail des lots' trouvé, extraction en cours...")
    #                 try:
    #                     main_win = driver.current_window_handle
                        
    #                     # Clic via JavaScript
    #                     driver.execute_script("arguments[0].click();", detail_btns[0])
    #                     time.sleep(2)
                        
    #                     # Bascule popup
    #                     all_windows = driver.window_handles
    #                     if len(all_windows) > 1:
    #                         new_window = [w for w in all_windows if w != main_win][0]
    #                         driver.switch_to.window(new_window)
                            
    #                         # Parsing
    #                         lots_data = parse_tender_lots(driver.page_source)
                            
    #                         # Fermeture
    #                         driver.execute_script("window.close();")
    #                         driver.switch_to.window(main_win)
    #                         print(f"-> [Info] Extraction terminée : {len(lots_data) if lots_data else 0} lots.")
    #                 except Exception as e:
    #                     print(f"-> [Alerte] Erreur lors de l'extraction des lots : {e}")
    #                     if len(driver.window_handles) > 1:
    #                         driver.switch_to.window(driver.window_handles[0])
    #             else:
    #                 print("-> [Info] Aucun bouton 'Détail des lots' pour cette offre. On continue.")

                
    #             # ÉTAPE 1 : Cliquer sur le lien pour aller vers la page de Téléchargement du DCE
    #             dce_link = wait.until(EC.element_to_be_clickable((By.ID, "ctl0_CONTENU_PAGE_linkDownloadDce")))

    #             meta = parse_tender_metadata(driver.page_source)
    #             ref = meta.get("reference")
    
    #             if ref and tender_manager.is_already_processed(ref):
    #                 print(f"-> [SKIP] La référence {ref} est déjà traitée. On passe.")
    #                 # Revenir à la liste des résultats sans télécharger
    #                 driver.get("https://www.marchespublics.gov.ma/index.php?page=entreprise.EntrepriseAdvancedSearch&searchAnnCons") # ou le bouton retour
    #                 continue
    #             else : 
    #                 dce_link.click()
    #                 time.sleep(2)
                                
    #             # ÉTAPE 2 : Déployer le panneau des métadonnées s'il est masqué, puis extraire
    #             meta = None
    #             paths = None
                
    #             # BLOC ISOLÉ : Quoi qu'il se passe ici, on ne saute PAS au grand 'except' du bas
    #             try:
    #                 # On cherche le lien toggle juste avant le div recap-consultation
    #                 toggle_elements = driver.find_elements(By.CSS_SELECTOR, "a.title-toggle")
    #                 if toggle_elements:
    #                     toggle_elements[0].click()
    #                     time.sleep(1) # Laisse l'animation s'ouvrir
                    
    #                 # Extraction HTML et parsing
    #                 html = driver.page_source
    #                 meta = parse_tender_metadata(html)
    #                 if meta:
    #                     meta['lots'] = lots_data
    #             except Exception as e_meta:
    #                 print(f"-> [Info] Impossible de parser les métadonnées (Panneau masqué ou erreur) : {e_meta}")

    #             # Traitement et création des dossiers (Toujours hors du grand danger)
    #             if meta and meta.get('reference'):
    #                 paths = get_storage_paths(meta['reference'])
    #                 save_metadata(meta, paths['metadata'])
    #                 print(f"[{processed + 1}/{config['tenders_to_extract']}] Métadonnées extraites pour la réf : {meta['reference']}")
    #             else:
    #                 print(f"[{processed + 1}/{config['tenders_to_extract']}] Attention: Référence non trouvée. Utilisation d'une réf temporaire.")
    #                 paths = get_storage_paths(f"UNKNOWN_REF_{int(time.time())}")

    #             # ÉTAPE 3 : Remplir le formulaire de téléchargement (Le script arrivera ICI à 100%)
    #             wait.until(EC.presence_of_element_located((By.ID, "ctl0_CONTENU_PAGE_EntrepriseFormulaireDemande_nom"))).send_keys(config['user_info']['nom'])
    #             driver.find_element(By.ID, "ctl0_CONTENU_PAGE_EntrepriseFormulaireDemande_prenom").send_keys(config['user_info']['prenom'])
    #             driver.find_element(By.ID, "ctl0_CONTENU_PAGE_EntrepriseFormulaireDemande_email").send_keys(config['user_info']['email'])
                
    #             # Accepter les conditions générales
    #             checkbox = driver.find_element(By.ID, "ctl0_CONTENU_PAGE_EntrepriseFormulaireDemande_accepterConditions")
    #             if not checkbox.is_selected():
    #                 checkbox.click()

    #             # ÉTAPE 4 : 1ère étape de validation - Clic sur "Valider"
    #             validate_btn = wait.until(EC.element_to_be_clickable((By.ID, "ctl0_CONTENU_PAGE_validateButton")))
    #             validate_btn.click()
    #             print("Formulaire complété, clic sur 'Valider'...")
    #             time.sleep(3) # Laisse la page exécuter le script de validation et recharger le bouton suivant
                
    #             # ÉTAPE 4.5 : 2ème étape de validation - Clic sur le bouton de téléchargement effectif
                
    #             download_btn = wait.until(EC.element_to_be_clickable((By.ID, "ctl0_CONTENU_PAGE_EntrepriseDownloadDce_completeDownload")))
                
    #             # Capture de l'état du dossier avant le téléchargement
    #             files_before = os.listdir(download_dir)
                
    #             # 1. Nettoyage préventif : on vire les résidus des sessions précédentes
    #             cleanup_temp_files(download_dir)
    #             # Déclenchement du téléchargement réel
    #             driver.execute_script("arguments[0].click();", download_btn)
    #             print(f"-> Téléchargement du DCE initié.")

    #             # 3. Attente robuste : le script reste bloqué ici tant que le fichier n'est pas prêt
    #             downloaded_filename = wait_for_download(download_dir, timeout=60)

    #             if downloaded_filename:
    #                 # 4. Déplacement sécurisé
    #                 src_file = os.path.join(download_dir, downloaded_filename)
    #                 dest_zip = os.path.join(paths['archive'], downloaded_filename)
                    
    #                 # On utilise shutil.move pour déplacer le fichier final vers l'archive
    #                 shutil.move(src_file, dest_zip)
    #                 print(f"ZIP archivé dans : {paths['archive']}")
    #                 # 5. Extraction
    #                 if downloaded_filename.lower().endswith('.zip'):
    #                     try:
    #                         # On extrait tout dans le dossier 'extracted' spécifique à cette réf
    #                         extract_all_recursive(dest_zip, paths['extracted'])
    #                         print(f"Documents extraits récursivement dans : {paths['extracted']}")
    #                     except Exception as zip_err:
    #                         print(f"Erreur lors de l'extraction récursive : {zip_err}")
    #                     #     with zipfile.ZipFile(dest_zip, 'r') as zip_ref:
    #                     #         zip_ref.extractall(paths['extracted'])
    #                     #     print(f"Documents extraits avec succès dans : {paths['extracted']}")
    #                     # except Exception as zip_err:
    #                     #     print(f"Impossible d'extraire le ZIP : {zip_err}")
    #                 else:
    #                     print("-> [Alerte] Le téléchargement a échoué ou a dépassé le temps imparti.")
                
    #             # Attente active du fichier (max 20s)
    #             # downloaded_file = None
    #             # for _ in range(20):
    #             #     time.sleep(1)
    #             #     files_after = os.listdir(download_dir)
    #             #     new_files = [f for f in files_after if f not in files_before and not f.endswith('.crdownload')]
    #             #     if new_files:
    #             #         downloaded_file = new_files[0]
    #             #         break

    #             # Rangement et extraction du livrable
    #             # if downloaded_file and paths:                    
    #             #     src_file = os.path.join(download_dir, downloaded_file)
    #             #     dest_zip = os.path.join(paths['archive'], downloaded_file)
                    
    #             #     shutil.move(src_file, dest_zip)
    #             #     print(f"ZIP archivé dans : {paths['archive']}")
                    
    #             #     if downloaded_file.lower().endswith('.zip'):
    #             #         try:
    #             #             with zipfile.ZipFile(dest_zip, 'r') as zip_ref:
    #             #                 zip_ref.extractall(paths['extracted'])
    #             #             print(f"Documents extraits avec succès dans : {paths['extracted']}")
    #             #         except Exception as zip_err:
    #             #             print(f"Impossible d'extraire le ZIP : {zip_err}")
                
    #             # Pause pour initier le téléchargement du fichier
    #             time.sleep(2)
                
    #             # ÉTAPE 5 : Retour à la liste des offres
    #             # Puisqu'on a fait : Liste -> Page Offre -> Page Téléchargement, 
    #             # On doit faire un driver.back() pour retourner à la Page Offre, puis un autre pour revenir à la Liste.
    #             # ÉTAPE 5 : Retour intelligent à la liste des offres via le bouton du site
    #             # 1. Revenir d'abord à la fiche de consultation
    #             retour_fiche = wait.until(EC.element_to_be_clickable((By.XPATH, "//a[@title='Retourner à la fiche Détails de la consultation']")))
    #             retour_fiche.click()
    #             time.sleep(2)

    #             # 2. Revenir ensuite à la liste des résultats avec tes critères conservés
    #             retour_liste = wait.until(EC.element_to_be_clickable((By.ID, "ctl0_CONTENU_PAGE_linkRetourBas2")))
    #             retour_liste.click()

                
    #             processed += 1
                
    #         except Exception as e:
    #             print(f"Erreur lors du traitement de l'élément à l'index {i}: {e}")
    #             # En cas d'erreur au milieu du parcours, on tente de revenir à la racine de la recherche
    #             driver.get("https://www.marchespublics.gov.ma/index.php?page=entreprise.EntrepriseAdvancedSearch&searchAnnCons")
    #             # Idéalement ré-exécuter la recherche ou s'assurer qu'on est sur la bonne page de liste
    #             #break
    #             time.sleep(2)
    #             fill_search_dates(driver, wait, config)
    #             continue

    #     # ÉTAPE 6 : Gestion de la pagination si on a traité les 10 offres de la page et qu'on en veut encore
    #     # Gestion de la pagination basée sur ton objectif global
    #     if processed < config['tenders_to_extract']:
    #         try:
    #             next_btn = driver.find_element(By.XPATH, "//img[@alt='Aller à la page suivante']")
    #             next_btn.click()
    #             print("--- Passage à la page suivante de résultats ---")
    #         except Exception:
    #             print("Fin des pages disponibles.")
    #             break
                
    # driver.quit()

    processed = 0
    current_page_index = 0 # On suit quel bouton traiter sur la page courante
    
    # La boucle principale tourne tant qu'on n'a pas atteint l'objectif
    while processed < config['tenders_to_extract']:
        time.sleep(3) 
        
        # 1. Récupération dynamique de la liste des boutons
        buttons = driver.find_elements(By.XPATH, "//img[@alt='Accéder à la consultation']")

        # 2. SI L'INDEX DÉPASSE LA TAILLE DE LA LISTE : Passage à la page suivante
        if current_page_index >= len(buttons):
            print(f"-> [Info] Page actuelle terminée ({len(buttons)} offres). Tentative de passage à la suivante...")
            try:
                next_btn = driver.find_element(By.XPATH, "//img[@alt='Aller à la page suivante']")
                next_btn.click()
                current_page_index = 0 # Reset de l'index pour la nouvelle page
                time.sleep(5) # Temps de chargement plus long pour la nouvelle page
                continue 
            except:
                print("-> [Info] Plus de page suivante, fin du scraping.")
                break
        
        # 2. Si aucun bouton, on tente la pagination
        if not buttons:
            try:
                next_btn = driver.find_element(By.XPATH, "//img[@alt='Aller à la page suivante']")
                next_btn.click()
                print("--- Passage à la page suivante de résultats ---")
                current_page_index = 0 # On remet l'index à 0 pour la nouvelle page
                time.sleep(4)
                continue # On repart au début du while pour scraper la nouvelle page
            except:
                print("Fin des résultats disponibles.")
                break
        
        # 3. On traite TOUJOURS le premier bouton de la liste actuelle
        # Cela évite l'IndexError car on ne dépend plus d'un index 'i' fixe
        try:
            # Re-scrapper la liste pour s'assurer qu'elle est à jour
            buttons = driver.find_elements(By.XPATH, "//img[@alt='Accéder à la consultation']")

            #buttons[current_page_index].click() # On cible le bon bouton
            remove_overlay(driver) # Nettoyer avant
            driver.execute_script("arguments[0].click();", buttons[current_page_index]) 
            time.sleep(2)

            meta = parse_tender_metadata(driver.page_source)
            ref = meta.get("reference")

            # --- BLOC D'EXTRACTION (Ton code reste inchangé ici) ---
            lots_data = [] 
            detail_btns = driver.find_elements(By.XPATH, "//a[contains(@href, 'PopUpDetailLots')]")

            # if detail_btns:
            #     print("-> [Info] Bouton 'Détail des lots' trouvé, extraction en cours...")
            #     try:
            #         main_win = driver.current_window_handle
            #         driver.execute_script("arguments[0].click();", detail_btns[0])
            #         time.sleep(2)
            #         all_windows = driver.window_handles
            #         if len(all_windows) > 1:
            #             new_window = [w for w in all_windows if w != main_win][0]
            #             driver.switch_to.window(new_window)
            #             lots_data = parse_tender_lots(driver.page_source)
            #             driver.execute_script("window.close();")
            #             driver.switch_to.window(main_win)
            #             print(f"-> [Info] Extraction terminée : {len(lots_data) if lots_data else 0} lots.")
            #     except Exception as e:
            #         print(f"-> [Alerte] Erreur lors de l'extraction des lots : {e}")
            #         if len(driver.window_handles) > 1:
            #             driver.switch_to.window(driver.window_handles[0])
            # else:
            #     print("-> [Info] Aucun bouton 'Détail des lots' pour cette offre.")
            
            # ÉTAPE 1 : Cliquer sur le lien pour aller vers la page de Téléchargement du DCE
            dce_link = wait.until(EC.element_to_be_clickable((By.ID, "ctl0_CONTENU_PAGE_linkDownloadDce")))

            # meta = parse_tender_metadata(driver.page_source)
            # ref = meta.get("reference")
    
            if ref and tender_manager.is_already_processed(ref):
                print(f"-> [SKIP] La référence {ref} est déjà traitée. On passe.")
                driver.find_element(By.ID, "ctl0_CONTENU_PAGE_linkRetourBas2").click()
                #processed += 1 # IMPORTANT : On compte cette offre comme traitée
                time.sleep(2)
                current_page_index += 1 # On passe au suivant sur la même page
                # Revenir à la liste des résultats sans télécharger
                #driver.get("https://www.marchespublics.gov.ma/index.php?page=entreprise.EntrepriseAdvancedSearch&searchAnnCons") # ou le bouton retour
                continue
            else :
                if detail_btns:
                    print("-> [Info] Bouton 'Détail des lots' trouvé, extraction en cours...")
                    try:
                        main_win = driver.current_window_handle
                        driver.execute_script("arguments[0].click();", detail_btns[0])
                        time.sleep(2)
                        all_windows = driver.window_handles
                        if len(all_windows) > 1:
                            new_window = [w for w in all_windows if w != main_win][0]
                            driver.switch_to.window(new_window)
                            lots_data = parse_tender_lots(driver.page_source)
                            driver.execute_script("window.close();")
                            driver.switch_to.window(main_win)
                            print(f"-> [Info] Extraction terminée : {len(lots_data) if lots_data else 0} lots.")
                    except Exception as e:
                        print(f"-> [Alerte] Erreur lors de l'extraction des lots : {e}")
                        if len(driver.window_handles) > 1:
                            driver.switch_to.window(driver.window_handles[0])
                else:
                    print("-> [Info] Aucun bouton 'Détail des lots' pour cette offre.") 
                    print(f"-> [Action] Traitement complet de {ref}...")
                #dce_link.click()
                driver.execute_script("arguments[0].click();", dce_link)
                time.sleep(2)
                                
            # ÉTAPE 2 : Déployer le panneau des métadonnées s'il est masqué, puis extraire
            meta = None
            paths = None
                
            # BLOC ISOLÉ : Quoi qu'il se passe ici, on ne saute PAS au grand 'except' du bas
            try:
                # On cherche le lien toggle juste avant le div recap-consultation
                toggle_elements = driver.find_elements(By.CSS_SELECTOR, "a.title-toggle")
                if toggle_elements:
                    toggle_elements[0].click()
                    time.sleep(1) # Laisse l'animation s'ouvrir
                    
                # Extraction HTML et parsing
                html = driver.page_source
                meta = parse_tender_metadata(html)
                if meta:
                    meta['lots'] = lots_data
            except Exception as e_meta:
                print(f"-> [Info] Impossible de parser les métadonnées (Panneau masqué ou erreur) : {e_meta}")

            # Traitement et création des dossiers (Toujours hors du grand danger)
            if meta and meta.get('reference'):
                paths = get_storage_paths(meta['reference'])
                save_metadata(meta, paths['metadata'])
                print(f"[{processed + 1}/{config['tenders_to_extract']}] Métadonnées extraites pour la réf : {meta['reference']}")
            else:
                print(f"[{processed + 1}/{config['tenders_to_extract']}] Attention: Référence non trouvée.Utilisation d'une réf temporaire.")
                paths = get_storage_paths(f"UNKNOWN_REF_{int(time.time())}")

            # ÉTAPE 3 : Remplir le formulaire de téléchargement (Le script arrivera ICI à 100%)
            wait.until(EC.presence_of_element_located((By.ID,"ctl0_CONTENU_PAGE_EntrepriseFormulaireDemande_nom"))).send_keys(config['user_info']['nom'])
            driver.find_element(By.ID, "ctl0_CONTENU_PAGE_EntrepriseFormulaireDemande_prenom").send_keys(config['user_info']['prenom'])
            driver.find_element(By.ID, "ctl0_CONTENU_PAGE_EntrepriseFormulaireDemande_email").send_keys(config['user_info']['email'])
                
            # Accepter les conditions générales
            checkbox = driver.find_element(By.ID,"ctl0_CONTENU_PAGE_EntrepriseFormulaireDemande_accepterConditions")
            if not checkbox.is_selected():
                checkbox.click()

            # ÉTAPE 4 : 1ère étape de validation - Clic sur "Valider"
            validate_btn = wait.until(EC.element_to_be_clickable((By.ID, "ctl0_CONTENU_PAGE_validateButton")))
            validate_btn.click()
            print("Formulaire complété, clic sur 'Valider'...")
            time.sleep(3) # Laisse la page exécuter le script de validation et recharger le bouton suivant
                
            # ÉTAPE 4.5 : 2ème étape de validation - Clic sur le bouton de téléchargement effectif
                
            download_btn = wait.until(EC.element_to_be_clickable((By.ID,"ctl0_CONTENU_PAGE_EntrepriseDownloadDce_completeDownload")))
                
            # Capture de l'état du dossier avant le téléchargement
            files_before = os.listdir(download_dir)
                
            # 1. Nettoyage préventif : on vire les résidus des sessions précédentes
            cleanup_temp_files(download_dir)
            # Déclenchement du téléchargement réel
            driver.execute_script("arguments[0].click();", download_btn)
            print(f"-> Téléchargement du DCE initié.")

            # 3. Attente robuste : le script reste bloqué ici tant que le fichier n'est pas prêt
            downloaded_filename = wait_for_download(download_dir, timeout=60)

            if downloaded_filename:
                # 4. Déplacement sécurisé
                src_file = os.path.join(download_dir, downloaded_filename)
                dest_zip = os.path.join(paths['archive'], downloaded_filename)
                    
                # On utilise shutil.move pour déplacer le fichier final vers l'archive
                shutil.move(src_file, dest_zip)
                print(f"ZIP archivé dans : {paths['archive']}")
                # 5. Extraction
                if downloaded_filename.lower().endswith('.zip'):
                    try:
                        # On extrait tout dans le dossier 'extracted' spécifique à cette réf
                        extract_all_recursive(dest_zip, paths['extracted'])
                        print(f"Documents extraits récursivement dans : {paths['extracted']}")
                    except Exception as zip_err:
                        print(f"Erreur lors de l'extraction récursive : {zip_err}")
                else:
                    print("-> [Alerte] Le téléchargement a échoué ou a dépassé le temps imparti.")
                
                
            # Pause pour initier le téléchargement du fichier
            time.sleep(2)
                
            # 1. Revenir d'abord à la fiche de consultation
            retour_fiche = wait.until(EC.element_to_be_clickable((By.XPATH, "//a[@title='Retourner à la fiche Détails de la consultation']")))
            retour_fiche.click()
            time.sleep(2)

            # 2. Revenir ensuite à la liste des résultats avec tes critères conservés
            retour_liste = wait.until(EC.element_to_be_clickable((By.ID, "ctl0_CONTENU_PAGE_linkRetourBas2")))
            retour_liste.click()    
            
            processed += 1
            current_page_index += 1
            print(f"-> [Succès] Offre {processed} traitée.")

        except Exception as e:
            print(f"Erreur lors du traitement d'une offre : {e}")
            # En cas d'erreur, retour à la racine de la recherche
            driver.get("https://www.marchespublics.gov.ma/index.php?page=entreprise.EntrepriseAdvancedSearch&searchAnnCons")
            current_page_index = 0
            time.sleep(2)
            fill_search_dates(driver, wait, config)
            continue
            
    driver.quit()

if __name__ == "__main__":
    run_scraper()