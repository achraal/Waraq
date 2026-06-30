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
        # Utilisation d'une fonction lambda pour cibler le texte exact ou partiel du label
        element = recap.find(string=lambda text: text and label in text)
        if element:
            # Récupération de l'élément frère ou suivant contenant la valeur
            next_node = element.find_next()
            return next_node.text.strip() if next_node else None
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
        "budget": get_val("Estimation"),
        "reserve_pme": get_val("Réservé à la TPE et PME"),
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

def save_metadata(data, save_path):
    """Sauvegarde les métadonnées en JSON."""
    file_path = os.path.join(save_path, 'metadata.json')
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)