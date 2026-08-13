import logging
from pathlib import Path
from typing import Any, Dict

from backend.app.modules.ai_processor.ocr_engine import extraire_texte_integral

logger = logging.getLogger(__name__)

class WorkflowOCRService:
    """
    Service OCR dédié aux workflows de génération. Réutilise le moteur OCR existant de Waraq afin de traiter :
    - PDF natifs - PDF scannés - DOC / DOCX - XLS / XLSX - images - documents contenant du français et/ou de l'arabe
    Pour les documents scannés, le moteur existant utilise RapidOCR/ONNX Runtime conformément au pipeline OCR de Waraq.
    """

    def __init__(self):
        """
        Initialise le service OCR du module workflows. Aucun moteur n'est instancié ici afin d'éviter de dupliquer les moteurs PaddleOCR/ONNX déjà initialisés dans ai_processor.
        """
        logger.info("[WORKFLOW_OCR] Service OCR initialisé.")

    def extract(self, file_path: str | Path) -> Dict[str, Any]:
        """
        Extrait intégralement le contenu d'un document.

        Args:
            file_path:
                Chemin absolu ou relatif du document à analyser.

        Returns:
            Dictionnaire contenant notamment :
            - text
            - is_scanned
            - inspection_method
            - page_count
            - word_count
            - file_size_mb
            - ocr_duration_sec
            - pages
            - lots

        Raises:
            FileNotFoundError:
                Si le document n'existe pas.
            ValueError:
                Si le chemin fourni est vide ou invalide.
        """

        if not file_path:
            logger.error("[WORKFLOW_OCR] Aucun chemin de fichier fourni.")
            raise ValueError("Le chemin du document est obligatoire.")

        path = Path(file_path)

        if not path.exists():
            logger.error("[WORKFLOW_OCR] Fichier introuvable | file=%s", path)
            raise FileNotFoundError(f"Document introuvable : {path}")

        if not path.is_file():
            logger.error("[WORKFLOW_OCR] Le chemin n'est pas un fichier | file=%s", path)
            raise ValueError(f"Le chemin fourni n'est pas un fichier : {path}")

        logger.info("[WORKFLOW_OCR] OCR workflow démarré | file=%s | extension=%s", path, path.suffix.lower())

        try:
            result = extraire_texte_integral(str(path))

            if not isinstance(result, dict):
                logger.error("[WORKFLOW_OCR] Résultat OCR invalide | file=%s", path)
                raise RuntimeError("Le moteur OCR a retourné un résultat invalide.")

            text = result.get("text", "")
            logger.info(
                "[WORKFLOW_OCR] OCR terminé | "
                "file=%s | "
                "pages=%s | "
                "words=%s | "
                "scanned=%s | "
                "method=%s | "
                "ocr_duration=%s",
                path,
                result.get("page_count"),
                result.get("word_count"),
                result.get("is_scanned"),
                result.get("inspection_method"),
                result.get("ocr_duration_sec"),
            )

            logger.info("[WORKFLOW_OCR] Texte extrait | file=%s | characters=%s", path, len(text))
            return result

        except FileNotFoundError:
            raise

        except Exception as exc:
            logger.exception("[WORKFLOW_OCR] Échec OCR | file=%s | error=%s", path, exc)
            raise RuntimeError(f"Échec de l'extraction OCR du document : {path}") from exc

    def extract_text(self, file_path: str | Path) -> str:
        """
        Retourne uniquement le texte extrait d'un document.
        Cette méthode est utile lorsque le workflow n'a pas besoin des métriques OCR complètes.
        """
        result = self.extract(file_path)
        return result.get("text", "")

    def is_scanned(self, file_path: str | Path) -> bool:
        """
        Détermine si un document est considéré comme scanné
        par le moteur OCR existant.
        """
        result = self.extract(file_path)
        return bool(result.get("is_scanned", False))

    def get_pages(self, file_path: str | Path) -> list[Dict[str, Any]]:
        """
        Retourne le contenu OCR page par page lorsqu'il est disponible.
        Cette méthode est particulièrement utile pour les workflows de signature du RC/CPS et pour l'analyse des documents modèles.
        """
        result = self.extract(file_path)
        pages = result.get("pages", [])
        if not isinstance(pages, list):
            logger.warning("[WORKFLOW_OCR] Structure pages invalide | file=%s",file_path)
            return []

        return pages