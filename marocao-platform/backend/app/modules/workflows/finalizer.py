import json
import logging
from datetime import datetime
from pathlib import Path
from uuid import UUID
from sqlalchemy.orm import Session
from backend.app.database.models import GeneratedDocument,GeneratedDocType,PreparationDocumentStatus,PreparationStatus

logger = logging.getLogger(__name__)

class TenderFinalizer:
    """Prépare et persiste les livrables finaux d'un tender."""
    REQUIRED_TYPES = {"RC","CPS","BDP","ACTE_ENGAGEMENT","DECLARATION_HONNEUR"}

    def __init__(self,generated_root: Path,converter):
        self.generated_root = generated_root
        self.converter = converter

    def get_output_directory(self,reference: str) -> Path:
        """
        Construit l'arborescence generated/YYYY/MM/DD/REFERENCE.
        """
        now = datetime.now()
        directory = (
            self.generated_root
            / str(now.year)
            / f"{now.month:02d}"
            / f"{now.day:02d}"
            / reference
        )

        directory.mkdir(parents=True,exist_ok=True)
        return directory

    def check_ready(self,preparation) -> tuple[bool, list[str]]:
        """
        Vérifie que toutes les pièces obligatoires sont prêtes.
        """
        missing = []
        documents = {
            document.document_type: document
            for document in preparation.documents
            if document.status != PreparationDocumentStatus.DELETED
        }

        for required_type in self.REQUIRED_TYPES:
            document = documents.get(required_type)
            if not document:
                missing.append(required_type)
                continue
            if required_type in {"RC","CPS"} and not document.is_signed:
                missing.append(f"{required_type}_SIGNATURE")
            if required_type == "BDP" and not document.is_filled:
                missing.append("BDP_FILLING")
            if required_type in {"ACTE_ENGAGEMENT","DECLARATION_HONNEUR"} and not document.is_filled:
                missing.append(f"{required_type}_FILLING")
        return (len(missing) == 0,missing)

    def finalize(self, db: Session, preparation, user_id: UUID, tender):
        """
        Convertit les livrables en PDF et crée les enregistrements GeneratedDocument.
        """

        ready, missing = self.check_ready(preparation)

        if not ready:
            raise ValueError("Dossier incomplet : " + ", ".join(missing))
        output_dir = self.get_output_directory(tender.reference)
        generated = []
        for document in preparation.documents:
            if document.status == PreparationDocumentStatus.DELETED:
                continue

            source = Path(document.file_path)
            if not source.exists():
                raise FileNotFoundError(str(source))
            pdf_path = self.converter.to_pdf(source, output_dir)
            final_name = f"{document.document_type}.pdf"
            final_path = output_dir / final_name
            if pdf_path != final_path:
                final_path.write_bytes(pdf_path.read_bytes())
            doc_type = self._map_doc_type(document.document_type)

            generated_document = GeneratedDocument(
                user_id=user_id,
                tender_id=tender.id,
                doc_type=doc_type,
                file_name=final_name,
                file_path=str(final_path),
                source_document_id=document.document_id,
                generation_metadata={"source_path": str(source),"preparation_document_id": str(document.id),}
            )
            db.add(generated_document)
            document.status = PreparationDocumentStatus.READY
            generated.append(str(final_path))

        manifest_path = output_dir / "manifest.json"
        manifest_path.write_text(
            json.dumps(
                {
                    "tender_id": str(tender.id),
                    "reference": tender.reference,
                    "generated_documents": generated,
                    "created_at": datetime.now().isoformat(),
                },
                ensure_ascii=False,
                indent=2
            ),
            encoding="utf-8"
        )
        preparation.status = PreparationStatus.FINALIZED
        preparation.can_finalize = True
        db.add(preparation)
        db.commit()
        logger.info("Tender finalisé | reference=%s | files=%s",tender.reference,len(generated))
        return {
            "status": "FINALIZED",
            "reference": tender.reference,
            "output_directory": str(output_dir),
            "files": generated,
        }

    def _map_doc_type(self,document_type: str) -> GeneratedDocType:
        """Convertit un type métier en enum GeneratedDocType."""
        mapping = {
            "ACTE_ENGAGEMENT":GeneratedDocType.ACTE_ENGAGEMENT,
            "DECLARATION_HONNEUR":GeneratedDocType.DECLARATION_HONNEUR,
            "BDP":GeneratedDocType.BDP_COMPLETED,
            "RC":GeneratedDocType.SYNTHESE_CONFORMITE,
            "CPS":GeneratedDocType.SYNTHESE_CONFORMITE,
        }
        return mapping[document_type]