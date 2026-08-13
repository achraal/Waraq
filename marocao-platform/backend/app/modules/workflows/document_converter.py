import logging
import shutil
import subprocess
from pathlib import Path
from backend.app.config import settings

logger = logging.getLogger(__name__)

class DocumentConverter:
    """Convertisseur des formats bureautiques vers PDF."""

    OFFICE_EXTENSIONS = {".doc",".docx",".xls",".xlsx",".xlsm"} 

    def __init__(self, libreoffice_path: str | None = None):
        self.libreoffice_path = (
            libreoffice_path 
            or settings.LIBREOFFICE_PATH
            or shutil.which("libreoffice")
            or shutil.which("soffice")
        )

    def to_pdf(self,input_path: str | Path,output_dir: str | Path) -> Path:
        """
        Convertit un document Office en PDF avec LibreOffice.
        """

        input_path = Path(input_path)
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True,exist_ok=True)

        if input_path.suffix.lower() == ".pdf":
            return input_path

        if not self.libreoffice_path:
            raise RuntimeError("LibreOffice/soffice introuvable.")

        command = [
            self.libreoffice_path,
            "--headless",
            "--convert-to",
            "pdf",
            "--outdir",
            str(output_dir),
            str(input_path),
        ]

        logger.info("Conversion PDF | source=%s",input_path)
        subprocess.run(command,check=True,capture_output=True,text=True)
        output_path = output_dir / f"{input_path.stem}.pdf"

        if not output_path.exists():
            raise RuntimeError(f"PDF non généré : {output_path}")

        logger.info("Conversion terminée | output=%s",output_path)
        return output_path