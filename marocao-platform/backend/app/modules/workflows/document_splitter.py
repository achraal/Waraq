import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

import fitz  # PyMuPDF

logger = logging.getLogger(__name__)


class DocumentSplitter:
    """
    Service de découpage des documents PDF.

    Le splitter permet de :
    - détecter des frontières logiques entre documents ;
    - découper un PDF en plusieurs fichiers ;
    - conserver les pages originales ;
    - produire un fichier PDF par document détecté ;
    - fonctionner avec des PDF natifs ou scannés ;
    - utiliser éventuellement le texte OCR fourni par WorkflowOCRService.

    Cas d'utilisation principaux :
        - CPS
        - RC
        - BORDEREAU_PRIX
        - documents multi-pièces

    Le service ne modifie jamais le fichier source.
    """

    # ------------------------------------------------------------------
    # TYPES DE DOCUMENTS POUR LESQUELS LE SPLIT EST PERTINENT
    # ------------------------------------------------------------------

    SPLITTABLE_TYPES = {
        "CPS",
        "RC",
        "BORDEREAU_PRIX",
    }

    # ------------------------------------------------------------------
    # MOTIFS DE DÉTECTION
    # ------------------------------------------------------------------

    DOCUMENT_PATTERNS = {
        "RC": [
            r"\br[èe]glement\s+de\s+consultation\b",
            r"\br[èe]glement\s+de\s+la\s+consultation\b",
            r"\brc\b",
        ],
        "CPS": [
            r"\bcahier\s+des\s+prescriptions\s+sp[ée]ciales\b",
            r"\bcahier\s+des\s+prescriptions\b",
            r"\bcps\b",
        ],
        "BORDEREAU_PRIX": [
            r"\bbordereau\s+des\s+prix\b",
            r"\bbordereau\s+des\s+prix\s+et\s+des\s+quantit[ée]s\b",
            r"\bbordereau\s+des\s+prix\s+unitaires\b",
            r"\bbpu\b",
        ],
        "ACTE_ENGAGEMENT": [
            r"\bacte\s+d['’]engagement\b",
        ],
        "DECLARATION_HONNEUR": [
            r"\bd[ée]claration\s+sur\s+l['’]honneur\b",
        ],
    }

    # ------------------------------------------------------------------
    # NORMALISATION
    # ------------------------------------------------------------------

    @staticmethod
    def normalize_text(text: str) -> str:
        """
        Normalise un texte pour faciliter la détection des titres.
        """

        if not text:
            return ""

        text = text.replace("\u00a0", " ")

        replacements = {
            "É": "E",
            "È": "E",
            "Ê": "E",
            "Ë": "E",
            "À": "A",
            "Â": "A",
            "Ä": "A",
            "Ù": "U",
            "Û": "U",
            "Ü": "U",
            "Ô": "O",
            "Ö": "O",
            "Î": "I",
            "Ï": "I",
            "Ç": "C",
            "é": "e",
            "è": "e",
            "ê": "e",
            "ë": "e",
            "à": "a",
            "â": "a",
            "ä": "a",
            "ù": "u",
            "û": "u",
            "ü": "u",
            "ô": "o",
            "ö": "o",
            "î": "i",
            "ï": "i",
            "ç": "c",
        }

        for old, new in replacements.items():
            text = text.replace(old, new)

        text = re.sub(r"[ \t]+", " ", text)
        text = re.sub(r"\n+", "\n", text)

        return text.strip().lower()

    # ------------------------------------------------------------------
    # DÉTECTION DU TYPE
    # ------------------------------------------------------------------

    def detect_document_type(self, text: str) -> Optional[str]:
        """
        Détecte le type logique d'un document à partir de son texte.

        Retourne par exemple :
            RC
            CPS
            BORDEREAU_PRIX
            ACTE_ENGAGEMENT
            DECLARATION_HONNEUR

        Retourne None si aucun type n'est détecté.
        """

        normalized = self.normalize_text(text)

        if not normalized:
            return None

        for document_type, patterns in self.DOCUMENT_PATTERNS.items():

            for pattern in patterns:

                if re.search(pattern, normalized, re.IGNORECASE):
                    return document_type

        return None

    # ------------------------------------------------------------------
    # DÉTECTION D'UNE PAGE
    # ------------------------------------------------------------------

    def detect_page_type(self, text: str) -> Optional[str]:
        """
        Détermine si une page semble être le début d'un nouveau document.

        On privilégie les titres forts afin d'éviter les faux positifs.
        """

        normalized = self.normalize_text(text)

        if not normalized:
            return None

        # Les expressions fortes sont testées en premier.
        strong_patterns = {
            "RC": [
                r"\br[èe]glement\s+de\s+consultation\b",
                r"\br[èe]glement\s+de\s+la\s+consultation\b",
            ],
            "CPS": [
                r"\bcahier\s+des\s+prescriptions\s+sp[ée]ciales\b",
                r"\bcahier\s+des\s+prescriptions\b",
            ],
            "BORDEREAU_PRIX": [
                r"\bbordereau\s+des\s+prix\b",
                r"\bbordereau\s+des\s+prix\s+et\s+des\s+quantit[ée]s\b",
                r"\bbordereau\s+des\s+prix\s+unitaires\b",
            ],
            "ACTE_ENGAGEMENT": [
                r"\bacte\s+d['’]engagement\b",
            ],
            "DECLARATION_HONNEUR": [
                r"\bd[ée]claration\s+sur\s+l['’]honneur\b",
            ],
        }

        for document_type, patterns in strong_patterns.items():

            for pattern in patterns:

                if re.search(pattern, normalized, re.IGNORECASE):
                    return document_type

        return None

    # ------------------------------------------------------------------
    # EXTRACTION DU TEXTE D'UNE PAGE
    # ------------------------------------------------------------------

    @staticmethod
    def extract_page_text(page: fitz.Page) -> str:
        """
        Extrait le texte natif d'une page PDF.
        """

        try:
            return page.get_text("text") or ""
        except Exception as exc:

            logger.warning(
                "[DOCUMENT_SPLITTER] Impossible d'extraire le texte | "
                "page=%s | error=%s",
                page.number + 1,
                exc,
            )

            return ""

    # ------------------------------------------------------------------
    # ANALYSE DU PDF
    # ------------------------------------------------------------------

    def analyze_pdf(
        self,
        file_path: str | Path,
        ocr_service=None,
    ) -> Dict[str, Any]:
        """
        Analyse un PDF afin d'identifier les pages susceptibles
        de constituer des débuts de documents.

        Fonctionne :
        - directement avec le texte natif ;
        - avec OCR lorsque le PDF est scanné.

        Retourne une structure contenant :
            pages
            boundaries
            document_count
        """

        path = Path(file_path)

        if not path.exists():
            raise FileNotFoundError(
                f"Document introuvable : {path}"
            )

        if path.suffix.lower() != ".pdf":
            raise ValueError(
                "DocumentSplitter travaille uniquement sur les PDF."
            )

        logger.info(
            "[DOCUMENT_SPLITTER] Analyse PDF | file=%s",
            path,
        )

        pdf = fitz.open(str(path))

        pages: List[Dict[str, Any]] = []
        boundaries: List[Dict[str, Any]] = []

        try:

            for page_index, page in enumerate(pdf):

                page_number = page_index + 1

                text = self.extract_page_text(page)

                # ------------------------------------------------------
                # Si la page ne contient pas de texte natif :
                # tentative OCR
                # ------------------------------------------------------

                if not text.strip() and ocr_service is not None:

                    try:

                        # Le moteur OCR peut travailler sur le PDF complet.
                        # On ne l'utilise ici que comme fallback.
                        result = ocr_service.extract(str(path))

                        ocr_text = result.get("text", "")

                        if ocr_text:
                            text = ocr_text

                    except Exception as exc:

                        logger.warning(
                            "[DOCUMENT_SPLITTER] OCR impossible | "
                            "page=%s | error=%s",
                            page_number,
                            exc,
                        )

                document_type = self.detect_page_type(text)

                page_info = {
                    "page_number": page_number,
                    "text": text,
                    "document_type": document_type,
                    "is_boundary": document_type is not None,
                }

                pages.append(page_info)

                if document_type:

                    boundaries.append(
                        {
                            "page_number": page_number,
                            "document_type": document_type,
                        }
                    )

        finally:
            pdf.close()

        logger.info(
            "[DOCUMENT_SPLITTER] Analyse terminée | "
            "pages=%s | boundaries=%s",
            len(pages),
            len(boundaries),
        )

        return {
            "file_path": str(path),
            "page_count": len(pages),
            "pages": pages,
            "boundaries": boundaries,
            "boundaries_count": len(boundaries),
        }

    # ------------------------------------------------------------------
    # CALCUL DES SEGMENTS
    # ------------------------------------------------------------------

    def build_segments(
        self,
        analysis: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """
        Transforme les frontières détectées en segments de pages.

        Exemple :

            Page 1 -> RC
            Page 2 -> RC
            Page 3 -> RC
            Page 4 -> CPS
            Page 5 -> CPS
            Page 6 -> BDP

        devient :

            RC   : 1-3
            CPS  : 4-5
            BDP  : 6
        """

        page_count = int(analysis.get("page_count", 0))

        boundaries = analysis.get("boundaries", [])

        if page_count <= 0:
            return []

        if not boundaries:
            return []

        segments: List[Dict[str, Any]] = []

        for index, boundary in enumerate(boundaries):

            start_page = int(boundary["page_number"])

            document_type = boundary["document_type"]

            if index + 1 < len(boundaries):

                next_start = int(
                    boundaries[index + 1]["page_number"]
                )

                end_page = next_start - 1

            else:

                end_page = page_count

            if end_page < start_page:
                continue

            segments.append(
                {
                    "document_type": document_type,
                    "start_page": start_page,
                    "end_page": end_page,
                    "page_count": end_page - start_page + 1,
                }
            )

        logger.info(
            "[DOCUMENT_SPLITTER] Segments construits | count=%s",
            len(segments),
        )

        return segments

    # ------------------------------------------------------------------
    # SPLIT PHYSIQUE
    # ------------------------------------------------------------------

    def split_pdf(
        self,
        file_path: str | Path,
        output_dir: str | Path,
        analysis: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Découpe physiquement le PDF selon les segments détectés.

        Le fichier original n'est jamais modifié.

        Retourne une liste de documents générés.
        """

        input_path = Path(file_path)
        output_path = Path(output_dir)

        if not input_path.exists():
            raise FileNotFoundError(
                f"Document introuvable : {input_path}"
            )

        if input_path.suffix.lower() != ".pdf":
            raise ValueError(
                "Le split nécessite un PDF."
            )

        if analysis is None:
            raise ValueError(
                "L'analyse du document est requise avant le split."
            )

        segments = self.build_segments(analysis)

        if not segments:

            logger.info(
                "[DOCUMENT_SPLITTER] Aucun segment détecté | file=%s",
                input_path,
            )

            return []

        output_path.mkdir(
            parents=True,
            exist_ok=True,
        )

        source_pdf = fitz.open(str(input_path))

        generated_documents: List[Dict[str, Any]] = []

        try:

            for index, segment in enumerate(segments, start=1):

                document_type = segment["document_type"]

                start_page = segment["start_page"]

                end_page = segment["end_page"]

                output_file = (
                    output_path
                    / f"{document_type}_{index}.pdf"
                )

                new_pdf = fitz.open()

                try:

                    new_pdf.insert_pdf(
                        source_pdf,
                        from_page=start_page - 1,
                        to_page=end_page - 1,
                    )

                    new_pdf.save(
                        str(output_file)
                    )

                finally:
                    new_pdf.close()

                generated_documents.append(
                    {
                        "file_path": str(output_file),
                        "file_name": output_file.name,
                        "document_type": document_type,
                        "start_page": start_page,
                        "end_page": end_page,
                        "page_count": segment["page_count"],
                    }
                )

                logger.info(
                    "[DOCUMENT_SPLITTER] Document créé | "
                    "type=%s | pages=%s-%s | output=%s",
                    document_type,
                    start_page,
                    end_page,
                    output_file,
                )

        finally:
            source_pdf.close()

        logger.info(
            "[DOCUMENT_SPLITTER] Split terminé | "
            "documents=%s | source=%s",
            len(generated_documents),
            input_path,
        )

        return generated_documents

    # ------------------------------------------------------------------
    # MÉTHODE COMPLÈTE
    # ------------------------------------------------------------------

    def split(
        self,
        file_path: str | Path,
        output_dir: str | Path,
        ocr_service=None,
    ) -> Dict[str, Any]:
        """
        Pipeline complet :

            PDF
              ↓
        analyse
              ↓
        détection des frontières
              ↓
        construction des segments
              ↓
        split physique
              ↓
        fichiers PDF séparés
        """

        path = Path(file_path)

        logger.info(
            "[DOCUMENT_SPLITTER] Démarrage | file=%s",
            path,
        )

        analysis = self.analyze_pdf(
            file_path=path,
            ocr_service=ocr_service,
        )

        segments = self.build_segments(
            analysis
        )

        # Aucun découpage nécessaire.
        if len(segments) <= 1:

            logger.info(
                "[DOCUMENT_SPLITTER] Aucun découpage multiple nécessaire | "
                "segments=%s",
                len(segments),
            )

            return {
                "status": "no_split",
                "file_path": str(path),
                "page_count": analysis["page_count"],
                "segments": segments,
                "documents": [],
            }

        documents = self.split_pdf(
            file_path=path,
            output_dir=output_dir,
            analysis=analysis,
        )

        return {
            "status": "split",
            "file_path": str(path),
            "page_count": analysis["page_count"],
            "segments": segments,
            "documents": documents,
            "documents_count": len(documents),
        }