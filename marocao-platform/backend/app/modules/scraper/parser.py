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

    # def get_val(label):
    #     # Utilisation d'une fonction lambda pour cibler le texte exact ou partiel du label
    #     element = recap.find(string=lambda text: text and label in text)
    #     if element:
    #         # Récupération de l'élément frère ou suivant contenant la valeur
    #         next_node = element.find_next()
    #         return next_node.text.strip() if next_node else None
    #     return None

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

# def parse_tender_lots(html_content):
#     soup = BeautifulSoup(html_content, 'html.parser')
#     parts = html_content.split('<div class="separator"></div>')
#     lots = []

#     # On cherche les conteneurs de lots. 
#     # Note : Ajustez 'div.bloc-lot' selon le vrai nom de classe dans votre popup
#     lot_blocks = soup.find_all("div", class_=lambda x: x and "lot" in x.lower())
    
#     for block in lot_blocks:
#         # Fonction utilitaire locale pour nettoyer le texte
#         def get_field(label_text):
#             label = block.find(string=lambda text: text and label_text in text)
#             if label:
#                 # On cherche après le label, souvent dans le prochain élément
#                 val = label.find_next()
#                 return val.text.strip() if val else None
#             return None

#         # Extraction des données du lot
#         lot = {
#             "lot_number": block.find("h3").text.strip() if block.find("h3") else "N/A",
#             "title": get_field("Lot"),
#             "description": get_field("Description"),
#             "estimated_budget": get_field("Estimation"),
#             "provisional_caution": get_field("Caution provisoire"),
#             "qualifications": get_field("Qualifications"),
#             "agrements": get_field("Agréments"),
#             "prospectus_notices": get_field("Prospectus"),
#             "reunion": get_field("Réunion"),
#             "visite_lieux": get_field("Visites des lieux"),
#             "variante": get_field("Variante"),
#             "env_considerations": get_field("Considérations environnementales"),
#             "reserve_pme": get_field("Réservé à")
#         }
#         lots.append(lot)
    
#     return lots


# def parse_tender_lots(html_content):
#     # 1. On découpe par le séparateur fiable
#     parts = html_content.split('<div class="separator"></div>')
#     lots = []
    
#     # 2. On boucle sur les parties (on ignore la dernière si elle est vide)
#     for part in parts:
#         # Création d'une soupe locale pour le lot courant
#         block = BeautifulSoup(part, 'html.parser')
        
#         # On vérifie si ce bloc contient réellement des infos de lot 
#         # (évite les erreurs sur les parties vides)
#         if not block.get_text(strip=True):
#             continue
            
#         # Fonction locale améliorée pour nettoyer le texte
#         def get_field(label_text):
#             label = block.find(string=lambda text: text and label_text in text)
#             if label:
#                 # Chercher le contenu après le label
#                 val = label.find_next()
#                 if val:
#                     text_val = val.get_text(strip=True)
#                     # Nettoyage des caractères parasites '*' et ':'
#                     clean_val = text_val.replace('*', '').replace(':', '').strip()
#                     return clean_val if clean_val else None
#             return None

#         # 3. Extraction des données
#         # On utilise une logique de repli pour le titre et le numéro
#         lot = {
#             "lot_number": get_field("Lot"), 
#             "title": get_field("Gares de") or get_field("Technicentres de") or "N/A",
#             "description": get_field("Description"),
#             "estimated_budget": get_field("Estimation (en Dhs TTC)"),
#             "provisional_caution": get_field("Caution provisoire"),
#             "qualifications": get_field("Qualifications"),
#             "agrements": get_field("Agréments"),
#             "prospectus_notices": get_field("Prospectus"),
#             "reunion": get_field("Réunion"),
#             "visite_lieux": get_field("Visites des lieux"),
#             "variante": get_field("Variante"),
#             "env_considerations": get_field("Considérations environnementales"),
#             "reserve_pme": get_field("Réservé à la TPE et PME installées au Maroc")
#         }
        
#         # On n'ajoute que si on a trouvé au moins une donnée significative
#         if any(v is not None for v in lot.values()):
#             lots.append(lot)
    
#     return lots

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

        # On cherche chaque champ en naviguant dans le bloc
        # On cible les divs "intitule-bloc" et leurs voisins "content-bloc"
        # def extract(label_keyword):
        #     label_tag = block.find("div", class_="intitule-bloc", string=lambda s: s and label_keyword in s)
        #     if label_tag:
        #         val_div = label_tag.find_next_sibling("div", class_="content-bloc")
        #         return val_div.get_text(strip=True) if val_div else None
        #     return None
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
        
        # Pour le titre, on prend le texte dans le d-flex
        # title_div = block.find("div", class_="d-flex")
        # if title_div:
        #     lot["title"] = title_div.get_text(strip=True).replace("Gares de :", "").replace("Technicentres de :", "").strip()

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