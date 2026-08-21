import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict
from uuid import UUID
from sqlalchemy.orm import Session
from backend.app.database.models import (Tender, TenderPreparation, TenderPreparationDocument, PreparationStatus, PreparationDocumentStatus)
from .document_inventory import (DocumentInventoryService)
from .document_validation import (DocumentValidationService)
from .admin_docs_generator import (AdminDocGeneratorService)
from .admin_fields_extractor import (AdminFieldsExtractor)
from .bdp_processor import (BDPProcessor)
from .document_signer import (DocumentSigner)
from .document_converter import (DocumentConverter)
from .finalizer import (TenderFinalizer)
from .document_filler import (DocumentFiller)

logger = logging.getLogger(__name__)

class TenderPreparationService:
    """Orchestrateur complet de préparation d'un appel d'offres."""
    def __init__(self, storage_root: Path, templates_dir: Path, ocr_service):
        self.storage_root = storage_root
        self.inventory = DocumentInventoryService(storage_root)
        self.validation = DocumentValidationService()
        self.admin_generator = AdminDocGeneratorService(templates_dir)
        self.admin_fields = AdminFieldsExtractor()
        self.bdp = BDPProcessor()
        self.signer = DocumentSigner()
        self.converter = DocumentConverter()
        self.finalizer = TenderFinalizer(storage_root / "generated", self.converter)
        self.ocr = ocr_service
        
    def _get_generation_dir(self, tender: Tender) -> Path:
        """
        Retourne le dossier de génération du tender.

        Structure :
        generated/YYYY/MM/DD/REFERENCE_HH_MM_SS/
        """

        now = datetime.now()

        folder_name = f"{tender.reference}_{now.strftime('%H_%M_%S')}"

        generation_dir = (
            self.storage_root
            / "generated"
            / now.strftime("%Y")
            / now.strftime("%m")
            / now.strftime("%d")
            / folder_name
        )

        generation_dir.mkdir(parents=True, exist_ok=True)

        return generation_dir

    def _get_tender(self, db: Session, tender_id: UUID) -> Tender:
        """Récupère un appel d'offres ou lève une erreur."""
        tender = db.query(Tender).filter(Tender.id == tender_id).first()
        if not tender:
            raise ValueError("Appel d'offres introuvable.")
        return tender

    def _get_or_create_preparation(self, db: Session, tender: Tender, user_id: UUID) -> TenderPreparation:
        """Récupère ou crée la session de préparation du tender."""
        preparation = db.query(TenderPreparation).filter(TenderPreparation.tender_id == tender.id).first()

        if not preparation:
            preparation = TenderPreparation(tender_id=tender.id, user_id=user_id, status=PreparationStatus.PENDING)
            db.add(preparation)
            db.commit()
            db.refresh(preparation)
        return preparation

    def scan_tender(self, db: Session, tender_id: UUID, user_id: UUID) -> Dict[str, Any]:
        """Analyse tous les documents disponibles et construit l'inventaire de préparation."""
        tender = self._get_tender(db, tender_id)
        preparation = self._get_or_create_preparation(db, tender, user_id)
        preparation.status = PreparationStatus.SCANNING
        db.commit()

        logger.info("Préparation démarrée | tender=%s", tender.reference)
        files = self.inventory.collect_files(tender)

        # On supprime les anciens éléments d'inventaire.
        for document in list(preparation.documents):
            db.delete(document)
        db.commit()

        for file in files:
            document_type = file.get("document_type")
            if not document_type:
                continue
            required = document_type in self.inventory.REQUIRED_TYPES
            preparation_document = TenderPreparationDocument(
                    preparation_id=preparation.id,
                    document_id=file.get("document_id"),
                    document_type=document_type,
                    file_name=file["file_name"],
                    file_path=file["file_path"],
                    status=PreparationDocumentStatus.DETECTED,
                    is_required=required,
                    is_user_provided=True,
                )
            db.add(preparation_document)
        db.commit()

        # Validation physique.
        for document in preparation.documents:
            self.validation.validate_preparation_document(db,document)
        # Création des documents administratifs manquants.
        self._create_missing_admin_documents(db, preparation, tender, user_id)
        self._refresh_status(db, preparation)
        logger.info("Préparation inventoriée | tender=%s", tender.reference)
        return self.get_preparation(db, tender_id)

    def _create_missing_admin_documents(
        self,
        db: Session,
        preparation: TenderPreparation,
        tender: Tender,
        user_id: UUID
    ):
        """
        Génère les documents administratifs Waraq uniquement lorsqu'ils sont absents du dossier.
        """

        existing_types = {
            document.document_type
            for document in preparation.documents
            if document.status
            != PreparationDocumentStatus.DELETED
        }
        generated_dir = self._get_generation_dir(tender)
        if "ACTE_ENGAGEMENT" not in existing_types:
            output = (generated_dir / "ACTE_ENGAGEMENT.docx")
            self.admin_generator.generate_acte_engagement(db, user_id, tender.id, output)

            db.add(
                TenderPreparationDocument(
                    preparation_id=preparation.id,
                    document_type="ACTE_ENGAGEMENT",
                    file_name=output.name,
                    file_path=str(output),
                    status=PreparationDocumentStatus.GENERATED,
                    is_required=True,
                    is_generated=True,
                    is_user_provided=False,
                    is_filled=False,
                )
            )
            logger.info("Acte généré automatiquement | tender=%s",tender.reference)
        if "DECLARATION_HONNEUR" not in existing_types:
            output = (generated_dir / "DECLARATION_HONNEUR.docx")
            self.admin_generator.generate_declaration_honneur(db, user_id, tender.id, output)

            db.add(
                TenderPreparationDocument(
                    preparation_id=preparation.id,
                    document_type="DECLARATION_HONNEUR",
                    file_name=output.name,
                    file_path=str(output),
                    status=PreparationDocumentStatus.GENERATED,
                    is_required=True,
                    is_generated=True,
                    is_user_provided=False,
                    is_filled=False,
                )
            )
            logger.info("Déclaration générée automatiquement | tender=%s",tender.reference)
        db.commit()

    def get_preparation(self, db: Session, tender_id: UUID) -> Dict[str, Any]:
        """
        Retourne l'état métier complet de la préparation.
        """
        tender = self._get_tender(db, tender_id)
        preparation = db.query(TenderPreparation).filter(TenderPreparation.tender_id == tender_id).first()

        if not preparation:
            raise ValueError("Préparation non initialisée.")

        documents = [
            document
            for document in preparation.documents
            if document.status
            != PreparationDocumentStatus.DELETED
        ]

        missing = []
        for required_type in self.inventory.REQUIRED_TYPES:
            if not any(d.document_type == required_type for d in documents):
                missing.append(required_type)

        actions = []
        for document in documents:
            if document.document_type in {"RC","CPS"} and not document.is_signed:
                actions.append(f"SIGN_{document.document_type}")

            if document.document_type == "BORDEREAU_PRIX":
                if not document.is_filled:
                    actions.append("FILL_BDP")

            if document.document_type in {"ACTE_ENGAGEMENT","DECLARATION_HONNEUR"}:
                if not document.is_filled:
                    actions.append(f"FILL_{document.document_type}")

        preparation.total_documents = len(documents)

        preparation.valid_documents = sum(
            1 for document in documents
            if document.status in {
                PreparationDocumentStatus.VALID,
                PreparationDocumentStatus.GENERATED,
                PreparationDocumentStatus.FILLED,
                PreparationDocumentStatus.SIGNED,
                PreparationDocumentStatus.READY,
            }
        )

        preparation.invalid_documents = sum(
            1
            for document in documents
            if document.status
            == PreparationDocumentStatus.INVALID
        )

        preparation.can_finalize = (
            len(missing) == 0
            and len(actions) == 0
            and preparation.invalid_documents == 0
        )

        db.add(preparation)
        db.commit()

        return {
            "tender_id": str(tender.id),
            "tender_reference": tender.reference,
            "status": preparation.status.value,
            "total_documents": preparation.total_documents,
            "valid_documents": preparation.valid_documents,
            "invalid_documents": preparation.invalid_documents,
            "can_finalize": preparation.can_finalize,
            "missing_documents": missing,
            "actions_required": list(set(actions)),
            "documents": [
                {
                    "id": str(document.id),
                    "document_type": document.document_type,
                    "file_name": document.file_name,
                    "file_path": document.file_path,
                    "status": document.status.value,
                    "is_required": document.is_required,
                    "is_generated": document.is_generated,
                    "is_signed": document.is_signed,
                    "is_filled": document.is_filled,
                    "validation_message": (
                        document.validation_message
                    ),
                }
                for document in documents
            ],
        }

    def validate_document(self, db: Session, preparation_document_id: UUID,valid: bool,message: str | None = None):
        """
        Valide ou invalide manuellement une pièce.
        """
        document = (db.query(TenderPreparationDocument).filter(TenderPreparationDocument.id == preparation_document_id).first())

        if not document:
            raise ValueError("Document de préparation introuvable.")

        document.status = (PreparationDocumentStatus.VALID if valid else PreparationDocumentStatus.INVALID)
        document.validation_message = message
        db.add(document)
        db.commit()
        logger.info("Validation manuelle | document=%s | valid=%s",preparation_document_id,valid)
        return document

    def delete_document(self,db: Session,preparation_document_id: UUID):
        """
        Supprime une pièce du workflow de préparation.
        """
        document = (db.query(TenderPreparationDocument).filter(TenderPreparationDocument.id == preparation_document_id).first())
        if not document:
            raise ValueError("Document introuvable.")
        self.validation.delete_document(db,document)
        return {"status": "deleted","document_id": str(document.id)}

    def analyze_bdp(self,db: Session,tender_id: UUID):
        """
        Analyse le BDP du tender et retourne les champs que le frontend doit demander à l'utilisateur.
        """
        preparation = (db.query(TenderPreparation).filter(TenderPreparation.tender_id == tender_id).first())
        if not preparation:
            raise ValueError("Préparation inexistante.")

        document = next((item for item in preparation.documents if item.document_type == "BORDEREAU_PRIX" and item.status != PreparationDocumentStatus.DELETED),None)
        if not document:
            raise ValueError("BDP introuvable.")

        structure = (self.bdp.extract_structure(document.file_path,self.ocr))
        document.metadata_json = structure
        db.add(document)
        db.commit()
        return {
            "status": "ready_for_input",
            "document_id": str(document.id),
            "items": structure["items"],
            "items_count": structure["items_count"],
        }

    def fill_bdp(self,db: Session,preparation_document_id: UUID,values: list[dict]):
        """
        Enregistre les prix BDP saisis par l'utilisateur.
        """
        document = (db.query(TenderPreparationDocument).filter(TenderPreparationDocument.id == preparation_document_id).first())
        if not document:
            raise ValueError("Document BDP introuvable.")

        metadata = (document.metadata_json or {})
        items = metadata.get("items",[])
        result = self.bdp.fill_items(items,values)
        metadata.update(result)
        document.metadata_json = metadata
        document.is_filled = True
        document.status = PreparationDocumentStatus.FILLED
        db.add(document)
        db.commit()
        return {"status": "filled","document_id": str(document.id),**result}

    def extract_admin_fields(self,db: Session,preparation_document_id: UUID):
        """
        Extrait les champs à remplir d'un document administratif.
        """
        document = (db.query(TenderPreparationDocument).filter(TenderPreparationDocument.id == preparation_document_id).first())
        if not document:
            raise ValueError("Document administratif introuvable.")
        fields = (self.admin_fields.extract_from_file(document.file_path,self.ocr))
        document.metadata_json = {"fields": fields}
        db.add(document)
        db.commit()
        return {"status": "ready_for_input","document_id": str(document.id),"fields": fields}

    def fill_admin_document(self, db: Session, preparation_document_id: UUID, values: Dict[str, Any]):
        """Remplit un document administratif avec les valeurs fournies."""
        document = db.query(TenderPreparationDocument).filter(TenderPreparationDocument.id == preparation_document_id).first()

        if not document:
            raise ValueError("Document administratif introuvable.")
            
        preparation = document.preparation
        tender = self._get_tender(db, preparation.tender_id)

        # CORRECTION : Appel avec "tender" uniquement
        generation_dir = self._get_generation_dir(tender)    
            
        source = Path(document.file_path)

        # CORRECTION : On garde uniquement cet output, on supprime l'autre
        output = generation_dir / f"{source.stem}_filled{source.suffix}"
        
        if source.suffix.lower() == ".docx":
            filler = DocumentFiller()
            filler.fill_docx(source, output, values)
        elif source.suffix.lower() in {".xlsx", ".xlsm"}:
            filler = DocumentFiller()
            filler.fill_xlsx(source, output, values)
        else:
            raise ValueError("Le remplissage automatique de ce format nécessite une conversion préalable.")

        document.file_path = str(output)
        document.file_name = output.name
        document.is_filled = True
        document.status = PreparationDocumentStatus.FILLED
        document.metadata_json = {"fields": values}
        db.add(document)
        db.commit()
        logger.info("Document administratif rempli | id=%s", preparation_document_id)
        return {"status": "filled", "document_id": str(document.id), "file_path": str(output)}

    def sign_documents(self, db: Session, tender_id: UUID, signer_name: str):
        """Signe graphiquement les RC et CPS et ajoute la pagination."""
        # CORRECTION : Récupération du tender indispensable ici
        tender = self._get_tender(db, tender_id)
        preparation = db.query(TenderPreparation).filter(TenderPreparation.tender_id == tender_id).first()

        if not preparation:
            raise ValueError("Préparation inexistante.")

        signed = []
        for document in preparation.documents:
            if document.document_type not in {"RC", "CPS"}:
                continue
            if document.status == PreparationDocumentStatus.DELETED:
                continue
            
            source = Path(document.file_path)
            
            # CORRECTION : Appel avec "tender" uniquement
            generation_dir = self._get_generation_dir(tender)

            if source.suffix.lower() != ".pdf":
                pdf_path = self.converter.to_pdf(source, generation_dir)
                source = pdf_path

            output = generation_dir / f"{source.stem}_signed.pdf"
            self.signer.sign_pdf(source, output, signer_name)
            
            document.file_path = str(output)
            document.file_name = output.name
            document.is_signed = True
            document.status = PreparationDocumentStatus.SIGNED
            db.add(document)
            signed.append(str(output))
            
        db.commit()
        logger.info("Documents signés | tender=%s | count=%s", tender_id, len(signed))
        return {"status": "signed", "files": signed}

    def finalize(self,db: Session,tender_id: UUID,user_id: UUID):
        """
        Effectue la validation finale et génère les livrables PDF.
        """
        tender = self._get_tender(db,tender_id)
        preparation = (db.query(TenderPreparation).filter(TenderPreparation.tender_id == tender_id).first())
        if not preparation:
            raise ValueError("Préparation inexistante.")
        result = self.finalizer.finalize(db=db,preparation=preparation,user_id=user_id,tender=tender)
        return result

    def _refresh_status(self,db: Session,preparation: TenderPreparation):
        """
        Met à jour le statut global de préparation.
        """
        active_documents = [
            document for document in preparation.documents 
            if document.status != PreparationDocumentStatus.DELETED
        ]
        
        has_invalid = any(document.status == PreparationDocumentStatus.INVALID for document in active_documents)
        if has_invalid:
            preparation.status = (PreparationStatus.REVIEW)
        else:
            preparation.status = (PreparationStatus.READY)

        db.add(preparation)
        db.commit()