from bs4 import BeautifulSoup
import json
import os

def parse_tender_metadata(html_content):
    """Extrait les informations clés d'une page de consultation."""
    soup = BeautifulSoup(html_content, 'html.parser')
    recap = soup.find("div", {"id": "recap-consultation"})
    
    if not recap:
        return None

    def get_val(label):
        # 1. Trouve le texte du label
        element = recap.find(string=lambda text: text and label in text)
        if element:
            # 2. On remonte au parent (le container de la ligne)
            parent = element.find_parent(['td', 'tr', 'div'])
            if parent:
                # 3. On cherche spécifiquement le span qui porte la classe "content-bloc"
                # C'est là que le site met la vraie valeur !
                val_span = parent.find("span", class_="content-bloc")
                if val_span:
                    return val_span.text.strip()
            
            # Secours : si pas de classe "content-bloc", on prend le premier texte non vide suivant
            next_node = element.find_next()
            while next_node:
                text_val = next_node.text.strip()
                if text_val and text_val != label and text_val not in ["*", ":", "* :"]:
                    return text_val.lstrip('*').lstrip(':').strip()
                next_node = next_node.find_next()
        return None

    data = {
        "reference": get_val("Référence"),
        "objet": get_val("Objet"),
        "acheteur": get_val("Acheteur public"),
        "type_annonce": get_val("Type d'annonce"),
        "procedure": get_val("Procédure"),
        "categorie": get_val("Catégorie principale"),
        "allotissement": get_val("Allotissement"),
        "lieu_execution": get_val("Lieu d'exécution"),
        "budget": get_val("Estimation (en Dhs TTC)"),
        "reserve_pme": get_val("Réservé à la TPE et PME installées au Maroc"),
        "domaines_activite": get_val("Domaines d'activité"),
        "adresse_retrait": get_val("Adresse de retrait"),
        "adresse_depot": get_val("Adresse de dépôt"),
        "lieu_ouverture": get_val("Lieu d'ouverture"),
        "prix_acquisition": get_val("Prix d'acquisition"),
        "caution": get_val("Caution provisoire"),
        "qualifications": get_val("Qualifications"),
        "agrements": get_val("Agréments"),
        "variante": get_val("Variante"),
        "deadline": get_val("Date et heure limite de remise des plis"),
        "prospectus_notices": get_val("Prospectus, notices"),
        "reunion": get_val("Réunion"),
        "visite_lieux": get_val("Visites des lieux"),
        "contact_administratif": get_val("Contact Administratif"),
    }
    return data

def parse_tender_lots(html_content):
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # On identifie les blocs de lots principaux
    # Le HTML montre que chaque lot commence par un intitule-bloc "Lot"
    # On va extraire tout le bloc de texte pour chaque partie
    parts = html_content.split('<div class="separator"></div>')
    lots = []

    for part in parts:
        block = BeautifulSoup(part, 'html.parser')
        text = block.get_text(separator='|', strip=True)
        
        # On crée un dictionnaire pour stocker les résultats du lot
        lot = {
            "lot_number": None, "title": None, "description": None, 
            "estimated_budget": None, "provisional_caution": None, 
            "qualifications": None, "agrements": None, "prospectus_notices": None, 
            "reunion": None, "visite_lieux": None, "variante": None, 
            "env_considerations": None, "reserve_pme": None
        }

        def extract(label_keyword):
            # 1. Cherche le label (le nœud de texte)
            label_tag = block.find(string=lambda s: s and label_keyword in s)
            if not label_tag:
                return None
            
            # 2. On cherche le prochain bloc qui contient la donnée.
            # Au lieu de remonter au parent, on cherche directement le prochain 
            # élément avec la classe 'content-bloc' qui suit le label trouvé.
            content = label_tag.find_next(class_="content-bloc")
            
            # 3. Vérification de sécurité : si le content trouvé est vide ou None, on retourne None
            if content:
                return content.get_text(strip=True)
            return None

        # # Remplissage
        # lot["lot_number"] = block.find("span", class_="blue").text.strip() if block.find("span", class_="blue") else None
        # 1. Nettoyage du Lot Number
        blue_span = block.find("span", class_="blue")
        if blue_span:
            # Récupère le texte, enlève "Lot", enlève ":", enlève les espaces
            lot["lot_number"] = blue_span.get_text(strip=True).replace("Lot", "").replace(":", "").strip()

        # 2. Nettoyage du Titre
        title_div = block.find("div", class_="d-flex")
        if title_div:
            # On clone le div pour ne pas modifier l'original, 
            # puis on supprime les éléments parasites comme les tooltips/logos
            temp_div = BeautifulSoup(str(title_div), 'html.parser')
            for parasite in temp_div.find_all(class_="info-bulle"):
                parasite.decompose() # Supprime définitivement le logo et son texte

        # On récupère le texte restant
            lot["title"] = temp_div.get_text(strip=True).strip()

        lot["description"] = extract("Description")
        lot["estimated_budget"] = extract("Estimation")
        lot["provisional_caution"] = extract("Caution provisoire")
        lot["qualifications"] = extract("Qualifications")
        lot["agrements"] = extract("Agréments")
        lot["prospectus_notices"] = extract("Prospectus")
        lot["reunion"] = extract("Réunion")
        lot["visite_lieux"] = extract("Visites des lieux")
        lot["variante"] = extract("Variante")
        lot["env_considerations"] = extract("Considérations environnementales")
        lot["reserve_pme"] = extract("Réservé à la TPE")

        if lot["lot_number"]:
            lots.append(lot)
            
    return lots

def save_metadata(data, save_path):
    """Sauvegarde les métadonnées en JSON."""
    file_path = os.path.join(save_path, 'metadata.json')
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)