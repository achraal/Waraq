import logging
from pathlib import Path
from typing import Dict
from sqlalchemy.orm import Session
from backend.app.database.models import TenderPreparationDocument, PreparationDocumentStatus

logger = logging.getLogger(__name__)

class DocumentValidationService:
    """Validation physique et métier des documents de préparation."""

    def validate_file(self,file_path: str, expected_type: str) -> Dict:
        """
        Vérifie qu'un fichier existe, est lisible et possède une extension compatible avec son type.
        """

        path = Path(file_path)
        if not path.exists():
            return {"valid": False,"message": "Le fichier n'existe pas."}
        if path.stat().st_size == 0:
            return {"valid": False,"message": "Le fichier est vide."}

        allowed = {".pdf",".doc",".docx",".xls",".xlsx",".xlsm",".png",".jpg",".jpeg"}

        if path.suffix.lower() not in allowed:
            return {"valid": False,"message": f"Extension non supportée : {path.suffix}"}

        return {
            "valid": True,
            "message": "Document valide.",
            "size_bytes": path.stat().st_size,
            "extension": path.suffix.lower(),
            "expected_type": expected_type,
        }

    def validate_preparation_document(self,db: Session,preparation_document: TenderPreparationDocument) -> Dict:
        """
        Valide un document enregistré dans la préparation.
        """

        result = self.validate_file(preparation_document.file_path,preparation_document.document_type)
        if result["valid"]:
            preparation_document.status = PreparationDocumentStatus.VALID
        else:
            preparation_document.status = PreparationDocumentStatus.INVALID
        preparation_document.validation_message = result["message"]

        db.add(preparation_document)
        db.commit()
        db.refresh(preparation_document)

        logger.info(
            "Document validé | id=%s | type=%s | valid=%s",
            preparation_document.id,
            preparation_document.document_type,
            result["valid"]
        )

        return result

    def delete_document(self,db: Session,preparation_document: TenderPreparationDocument) -> None:
        """
        Marque une pièce comme supprimée et supprime son fichier physique si celui-ci existe.
        """
        path = Path(preparation_document.file_path)

        if path.exists():
            path.unlink()

        preparation_document.status = PreparationDocumentStatus.DELETED
        db.add(preparation_document)
        db.commit()
        logger.warning("Document supprimé | id=%s | path=%s",preparation_document.id,path)