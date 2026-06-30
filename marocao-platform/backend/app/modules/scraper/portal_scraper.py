import time
import json
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from backend.app.scrapping.utils import get_storage_paths
from backend.app.scrapping.parser import parse_tender_metadata, save_metadata

def run_scraper():
    # 1. Chargement de la configuration
    with open('config.json', 'r', encoding='utf-8') as f:
        config = json.load(f)
    
    driver = webdriver.Chrome()
    driver.maximize_window()
    wait = WebDriverWait(driver, 15)
    
    driver.get("https://www.marchespublics.gov.ma/index.php?page=entreprise.EntrepriseAdvancedSearch&searchAnnCons")
    
    # Remplissage des filtres de date
    wait.until(EC.presence_of_element_located((By.ID, "ctl0_CONTENU_PAGE_AdvancedSearch_dateMiseEnLigneCalculeStart"))).send_keys(config['search']['date_start'])
    driver.find_element(By.ID, "ctl0_CONTENU_PAGE_AdvancedSearch_dateMiseEnLigneCalculeEnd").send_keys(config['search']['date_end'])
    driver.find_element(By.ID, "ctl0_CONTENU_PAGE_AdvancedSearch_lancerRecherche").click()
    
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
                dce_link.click()
                time.sleep(2)
                
                # ÉTAPE 2 : Déployer le panneau des métadonnées s'il est masqué, puis extraire
                try:
                    # On cherche le lien toggle juste avant le div recap-consultation
                    toggle_btn = driver.find_element(By.CSS_SELECTOR, "a.title-toggle")
                    toggle_btn.click()
                    time.sleep(0.5) # Laisser le panneau s'ouvrir au cas où il y a une animation
                except Exception:
                    # Si le bouton toggle n'est pas cliquable ou absent, on tente quand même le parsing
                    pass
                
                # Extraction HTML de la page de téléchargement (qui contient maintenant le recap)
                html = driver.page_source
                meta = parse_tender_metadata(html)
                
                if meta and meta['reference']:
                    # Génération des chemins et sauvegarde des métadonnées
                    paths = get_storage_paths(meta['reference'])
                    save_metadata(meta, paths['metadata'])
                    print(f"[{processed + 1}/{config['tenders_to_extract']}] Métadonnées extraites pour la réf : {meta['reference']}")
                else:
                    print(f"[{processed + 1}/{config['tenders_to_extract']}] Attention: Métadonnées non trouvées sur cette page.")
                    # Si pas de référence, on génère un identifiant temporaire pour ne pas bloquer
                    paths = get_storage_paths(f"UNKNOWN_REF_{int(time.time())}")
                
                # ÉTAPE 3 : Remplir le formulaire de téléchargement
                wait.until(EC.presence_of_element_located((By.ID, "ctl0_CONTENU_PAGE_EntrepriseFormulaireDemande_nom"))).send_keys(config['user_info']['nom'])
                driver.find_element(By.ID, "ctl0_CONTENU_PAGE_EntrepriseFormulaireDemande_prenom").send_keys(config['user_info']['prenom'])
                driver.find_element(By.ID, "ctl0_CONTENU_PAGE_EntrepriseFormulaireDemande_email").send_keys(config['user_info']['email'])
                
                # Accepter les conditions générales
                checkbox = driver.find_element(By.ID, "ctl0_CONTENU_PAGE_EntrepriseFormulaireDemande_accepterConditions")
                if not checkbox.is_selected():
                    checkbox.click()
                
                # ÉTAPE 4 : Lancer le téléchargement effectif du fichier
                download_btn = wait.until(EC.element_to_be_clickable((By.ID, "ctl0_CONTENU_PAGE_EntrepriseDownloadDce_completeDownload")))
                download_btn.click()
                print(f"-> Téléchargement du DCE initié pour {meta.get('reference', 'Inconnue') if meta else 'Inconnue'}.")
                
                # Pause pour initier le téléchargement du fichier
                time.sleep(4)
                
                # ÉTAPE 5 : Retour à la liste des offres
                # Puisqu'on a fait : Liste -> Page Offre -> Page Téléchargement, 
                # On doit faire un driver.back() pour retourner à la Page Offre, puis un autre pour revenir à la Liste.
                driver.back() # Revient à la page de la consultation
                time.sleep(1)
                driver.back() # Revient à la liste principale des résultats
                
                processed += 1
                
            except Exception as e:
                print(f"Erreur lors du traitement de l'élément à l'index {i}: {e}")
                # En cas d'erreur au milieu du parcours, on tente de revenir à la racine de la recherche
                driver.get("https://www.marchespublics.gov.ma/index.php?page=entreprise.EntrepriseAdvancedSearch&searchAnnCons")
                # Idéalement ré-exécuter la recherche ou s'assurer qu'on est sur la bonne page de liste
                break

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