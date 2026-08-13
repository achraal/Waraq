import logging
from pathlib import Path
from typing import Dict, List, Optional
from sqlalchemy.orm import Session
from backend.app.database.models import Tender, TenderDocument

logger = logging.getLogger(__name__)

DOCUMENT_TYPE_ALIASES = {
    "RC": [
        "rc",
        "reglement_consultation",
        "règlement_consultation",
        "reglement de consultation",
        "règlement de consultation",
    ],
    "CPS": [
        "cps",
        "cahier_prescriptions_speciales",
        "cahier des prescriptions spéciales",
    ],
    "BDP": [
        "bdp",
        "bordereau_prix",
        "bordereau des prix",
        "bordereau des prix et descriptif",
        "bordereau prix",
    ],
    "ACTE_ENGAGEMENT": [
        "acte_engagement",
        "acte engagement",
        "acte d'engagement",
        "acte d engagement",
    ],
    "DECLARATION_HONNEUR": [
        "declaration_honneur",
        "déclaration_honneur",
        "declaration sur l'honneur",
        "déclaration sur l'honneur",
    ],
}

class DocumentInventoryService:
    """Recherche et normalisation des pièces d'un appel d'offres."""
    REQUIRED_TYPES = {"RC","CPS","BDP","ACTE_ENGAGEMENT","DECLARATION_HONNEUR"}
    def __init__(self, storage_root: Path):
        self.storage_root = storage_root

    def normalize_document_type(self, filename: str,text: str = "") -> Optional[str]:
        """
        Détermine le type métier d'un document à partir du nom et éventuellement des premières lignes de son contenu.
        """
        value = f"{filename} {text}".lower()
        for canonical, aliases in DOCUMENT_TYPE_ALIASES.items():
            for alias in aliases:
                if alias.lower() in value:
                    return canonical
        return None

    def _candidate_tender_paths(self, tender: Tender) -> List[Path]:
        """
        Construit les chemins potentiels contenant les documents du tender.
        """
        candidates = []
        reference = tender.reference
        for base_name in ["rag_extracted", "extracted", "classified"]:
            base = self.storage_root / base_name
            if not base.exists():
                continue
            for path in base.rglob("*"):
                if path.is_dir() and path.name == reference:
                    candidates.append(path)
        return candidates

    def _scan_directory(self, directory: Path) -> List[Dict]:
        """
        Parcourt récursivement un dossier et retourne les fichiers exploitables en excluant les répertoires techniques _sources.
        """
        documents = []
        if not directory.exists():
            return documents

        for path in directory.rglob("*"):
            if not path.is_file():
                continue
            if "_sources" in path.parts:
                continue
            if path.suffix.lower() not in {".pdf","doc","docx","xls","xlsx","xlsm","png","jpg",".jpeg"}:
                continue
            document_type = self.normalize_document_type(path.name)
            documents.append({
                "file_name": path.name,
                "file_path": str(path),
                "document_type": document_type,
                "source": str(directory),
            })
        return documents

    def collect_files(self, tender: Tender) -> List[Dict]:
        """
        Récupère tous les fichiers physiques correspondant au tender.
        """
        logger.info("Inventory démarré | tender=%s | reference=%s",tender.id,tender.reference)
        files = []

        for directory in self._candidate_tender_paths(tender):
            files.extend(self._scan_directory(directory))

        # Recherche supplémentaire dans les TenderDocument.
        for document in tender.documents:
            if not document.file_path:
                continue
            path = Path(document.file_path)
            if not path.exists():
                continue
            document_type = document.file_type or self.normalize_document_type(document.file_name)
            files.append({
                "file_name": document.file_name,
                "file_path": str(path),
                "document_type": document_type,
                "source": "database",
                "document_id": str(document.id),
            })

        # Suppression des doublons.
        unique = {}
        for item in files:
            unique[item["file_path"]] = item
        result = list(unique.values())
        logger.info("Inventory terminé | tender=%s | files=%s",tender.reference,len(result))
        return result

    def group_by_type(self,files: List[Dict]) -> Dict[str, List[Dict]]:
        """
        Regroupe les fichiers par type métier.
        """

        grouped = {}
        for file in files:
            document_type = file.get("document_type")

            if not document_type:
                continue
            grouped.setdefault(document_type,[]).append(file)
        return grouped