from backend.app.modules.scraper.utils import DATA_STORAGE_DIR
from selenium import webdriver
import time, json, os, shutil, zipfile
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from backend.app.modules.scraper.utils import get_storage_paths
from backend.app.modules.scraper.parser import parse_tender_metadata, save_metadata
from backend.app.database import SessionLocal # Importe ta session DB
from backend.app.modules.scraper.utils import TenderManager

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
        
    driver.find_element(By.ID, "ctl0_CONTENU_PAGE_AdvancedSearch_lancerRecherche").click()

def run_scraper():
    # 1. Chargement de la configuration
    with open('backend/app/modules/scraper/config.json', 'r', encoding='utf-8') as f:
        config = json.load(f)
    
    # --- AJOUTER CETTE CONFIGURATION DES OPTIONS DE CHROME ---
    options = webdriver.ChromeOptions()
    
    # Définir le chemin absolu où Chrome doit télécharger les DCE
    # Ici, on crée un dossier temporaire 'downloads' à la racine de ton projet
    download_dir = r"C:\Users\achra\Desktop\Intern\Project\marocao-platform\data_storage"
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
    
    processed = 0
    
    # La boucle principale tourne tant qu'on n'a pas atteint l'objectif personnalisé
    while processed < config['tenders_to_extract']:
        time.sleep(3) # Attente du rafraîchissement ou chargement de la page de liste
        
        # Récupération dynamique des boutons de la page courante
        buttons = driver.find_elements(By.XPATH, "//img[@alt='Accéder à la consultation']")
        tenders_on_page = len(buttons)
        
        if tenders_on_page == 0:
            print("Aucun appel d'offres trouvé sur cette page.")
            break
            
        # On parcourt les offres de la page une par une
        for i in range(tenders_on_page):
            # Condition d'arrêt dès que le quota personnalisé est atteint au milieu d'une page
            if processed >= config['tenders_to_extract']:
                break
                
            try:
                # Reciblage pour éviter StaleElementReference Exception
                buttons = driver.find_elements(By.XPATH, "//img[@alt='Accéder à la consultation']")
                buttons[i].click()
                time.sleep(2)
                
                # ÉTAPE 1 : Cliquer sur le lien pour aller vers la page de Téléchargement du DCE
                dce_link = wait.until(EC.element_to_be_clickable((By.ID, "ctl0_CONTENU_PAGE_linkDownloadDce")))

                meta = parse_tender_metadata(driver.page_source)
                ref = meta.get("reference")
    
                if ref and tender_manager.is_already_processed(ref):
                    print(f"-> [SKIP] La référence {ref} est déjà traitée. On passe.")
                    # Revenir à la liste des résultats sans télécharger
                    driver.get("https://www.marchespublics.gov.ma/index.php?page=entreprise.EntrepriseAdvancedSearch&searchAnnCons") # ou le bouton retour
                    continue
                else : 
                    dce_link.click()
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
                except Exception as e_meta:
                    print(f"-> [Info] Impossible de parser les métadonnées (Panneau masqué ou erreur) : {e_meta}")

                # Traitement et création des dossiers (Toujours hors du grand danger)
                if meta and meta.get('reference'):
                    paths = get_storage_paths(meta['reference'])
                    save_metadata(meta, paths['metadata'])
                    print(f"[{processed + 1}/{config['tenders_to_extract']}] Métadonnées extraites pour la réf : {meta['reference']}")
                else:
                    print(f"[{processed + 1}/{config['tenders_to_extract']}] Attention: Référence non trouvée. Utilisation d'une réf temporaire.")
                    paths = get_storage_paths(f"UNKNOWN_REF_{int(time.time())}")

                # ÉTAPE 3 : Remplir le formulaire de téléchargement (Le script arrivera ICI à 100%)
                wait.until(EC.presence_of_element_located((By.ID, "ctl0_CONTENU_PAGE_EntrepriseFormulaireDemande_nom"))).send_keys(config['user_info']['nom'])
                driver.find_element(By.ID, "ctl0_CONTENU_PAGE_EntrepriseFormulaireDemande_prenom").send_keys(config['user_info']['prenom'])
                driver.find_element(By.ID, "ctl0_CONTENU_PAGE_EntrepriseFormulaireDemande_email").send_keys(config['user_info']['email'])
                
                # Accepter les conditions générales
                checkbox = driver.find_element(By.ID, "ctl0_CONTENU_PAGE_EntrepriseFormulaireDemande_accepterConditions")
                if not checkbox.is_selected():
                    checkbox.click()

                # ÉTAPE 4 : 1ère étape de validation - Clic sur "Valider"
                validate_btn = wait.until(EC.element_to_be_clickable((By.ID, "ctl0_CONTENU_PAGE_validateButton")))
                validate_btn.click()
                print("Formulaire complété, clic sur 'Valider'...")
                time.sleep(3) # Laisse la page exécuter le script de validation et recharger le bouton suivant
                
                # ÉTAPE 4.5 : 2ème étape de validation - Clic sur le bouton de téléchargement effectif
                download_btn = wait.until(EC.element_to_be_clickable((By.ID, "ctl0_CONTENU_PAGE_EntrepriseDownloadDce_completeDownload")))
                
                # Capture de l'état du dossier avant le téléchargement
                files_before = os.listdir(download_dir)
                
                # Déclenchement du téléchargement réel
                driver.execute_script("arguments[0].click();", download_btn)
                print(f"-> Téléchargement du DCE initié.")
                
                # Attente active du fichier (max 20s)
                downloaded_file = None
                for _ in range(20):
                    time.sleep(1)
                    files_after = os.listdir(download_dir)
                    new_files = [f for f in files_after if f not in files_before and not f.endswith('.crdownload')]
                    if new_files:
                        downloaded_file = new_files[0]
                        break

                # Rangement et extraction du livrable
                if downloaded_file and paths:                    
                    src_file = os.path.join(download_dir, downloaded_file)
                    dest_zip = os.path.join(paths['archive'], downloaded_file)
                    
                    shutil.move(src_file, dest_zip)
                    print(f"ZIP archivé dans : {paths['archive']}")
                    
                    if downloaded_file.lower().endswith('.zip'):
                        try:
                            with zipfile.ZipFile(dest_zip, 'r') as zip_ref:
                                zip_ref.extractall(paths['extracted'])
                            print(f"Documents extraits avec succès dans : {paths['extracted']}")
                        except Exception as zip_err:
                            print(f"Impossible d'extraire le ZIP : {zip_err}")
                
                # Pause pour initier le téléchargement du fichier
                time.sleep(2)
                
                # ÉTAPE 5 : Retour à la liste des offres
                # Puisqu'on a fait : Liste -> Page Offre -> Page Téléchargement, 
                # On doit faire un driver.back() pour retourner à la Page Offre, puis un autre pour revenir à la Liste.
                # ÉTAPE 5 : Retour intelligent à la liste des offres via le bouton du site
                # 1. Revenir d'abord à la fiche de consultation
                retour_fiche = wait.until(EC.element_to_be_clickable((By.XPATH, "//a[@title='Retourner à la fiche Détails de la consultation']")))
                retour_fiche.click()
                time.sleep(2)

                # 2. Revenir ensuite à la liste des résultats avec tes critères conservés
                retour_liste = wait.until(EC.element_to_be_clickable((By.ID, "ctl0_CONTENU_PAGE_linkRetourBas2")))
                retour_liste.click()

                
                processed += 1
                
            except Exception as e:
                print(f"Erreur lors du traitement de l'élément à l'index {i}: {e}")
                # En cas d'erreur au milieu du parcours, on tente de revenir à la racine de la recherche
                driver.get("https://www.marchespublics.gov.ma/index.php?page=entreprise.EntrepriseAdvancedSearch&searchAnnCons")
                # Idéalement ré-exécuter la recherche ou s'assurer qu'on est sur la bonne page de liste
                #break
                time.sleep(2)
                fill_search_dates(driver, wait, config)
                continue

        # ÉTAPE 6 : Gestion de la pagination si on a traité les 10 offres de la page et qu'on en veut encore
        # Gestion de la pagination basée sur ton objectif global
        if processed < config['tenders_to_extract']:
            try:
                next_btn = driver.find_element(By.XPATH, "//img[@alt='Aller à la page suivante']")
                next_btn.click()
                print("--- Passage à la page suivante de résultats ---")
            except Exception:
                print("Fin des pages disponibles.")
                break
                
    driver.quit()

if __name__ == "__main__":
    run_scraper()