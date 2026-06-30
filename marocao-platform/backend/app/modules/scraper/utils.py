import os
from datetime import datetime

def get_storage_paths(tender_reference: str):
    """
    Crée une structure propre avec un identifiant de microsecondes (batch de temps)
    pour différencier deux exécutions dans la même seconde.
    Structure : data_storage/TYPE/AAAA/MM/DD/REF_HH-MM-SS_batch_XXXXXX/
    """
    now = datetime.now()
    
    # 1. Nettoyage de la référence
    safe_ref = tender_reference.replace("/", "-").replace(" ", "_").strip()
    
    # 2. Utilisation des microsecondes comme identifiant de batch chronologique précis
    # Exemple : batch_452319
    batch_id = f"batch_{now.strftime('%f')}"
    
    # Format final du dossier : REF_14-35-02_batch_452319
    folder_name = f"{safe_ref}_{now.strftime('%H-%M-%S')}_{batch_id}"
    
    base_path = "data_storage"
    paths = {
        "archive": os.path.join(base_path, "archives", now.strftime("%Y/%m/%d"), folder_name),
        "extracted": os.path.join(base_path, "extracted", now.strftime("%Y/%m/%d"), folder_name),
        "metadata": os.path.join(base_path, "metadata", now.strftime("%Y/%m/%d"), folder_name)
    }
    
    # Création effective des répertoires
    for path in paths.values():
        os.makedirs(path, exist_ok=True)
        
    return paths