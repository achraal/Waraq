import logging
from io import BytesIO
from pathlib import Path
from typing import Any, Dict, List, Optional
from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen import canvas

logger = logging.getLogger(__name__)

class DocumentSigner:
    """
    Service de signature visuelle des documents RC/CPS.

    IMPORTANT :
    - La pagination existante du document n'est jamais modifiée.
    - Aucune nouvelle pagination n'est ajoutée.
    - Les zones de signature proviennent de `administrative_zones`.
    - Les coordonnées bbox sont celles détectées par le pipeline OCR/RAG.
    - Les zones LU ET ACCEPTE sont traitées séparément.
    """

    # NORMALISATION
    @staticmethod
    def _normalize_text(value: Any) -> str:
        """
        Normalise un texte pour faciliter la détection des libellés malgré les problèmes d'encodage OCR.
        """
        if not value:
            return ""
        text = str(value).lower()

        replacements = {"é": "e","è": "e","ê": "e","ë": "e","à": "a","â": "a","ä": "a","ù": "u","û": "u","ü": "u","ô": "o","ö": "o","î": "i","ï": "i","ç": "c",}

        for old, new in replacements.items():
            text = text.replace(old, new)
        return " ".join(text.split())

    # DETECTION DES ZONES

    def _get_signature_zones(
        self,
        administrative_zones: List[Dict[str, Any]],
        page_number: int,
    ) -> List[Dict[str, Any]]:
        """
        Retourne les zones de signature pertinentes pour une page.
        Seules les zones :
            - SIGNATURE_CACHET
            - correspondant réellement à une zone destinée au concurrent sont retenues.
        Les textes généraux contenant le mot "signature" mais ne représentant pas une zone de signature exploitable sont filtrés.
        """

        zones = []
        for zone in administrative_zones or []:
            if zone.get("page_number") != page_number:
                continue
            zone_type = str(zone.get("type", "")).upper()
            label = self._normalize_text(zone.get("label", ""))
            if zone_type != "SIGNATURE_CACHET":
                continue
            bbox = zone.get("bbox")
            if not self._valid_bbox(bbox):
                continue
            # On évite les faux positifs provenant de textes généraux.

            signature_keywords = ("signature","cachet","concurrent","fournisseur","titulaire","fabricant",)
            if not any(keyword in label for keyword in signature_keywords):
                continue
            zones.append(zone)
        return zones

    def _get_lu_accepte_zones(
        self,
        administrative_zones: List[Dict[str, Any]],
        page_number: int,
    ) -> List[Dict[str, Any]]:
        """
        Retourne les zones contenant explicitement une mention "LU ET ACCEPTE".
        On ne signe pas toutes les zones VISA_APPROBATION : uniquement celles destinées au concurrent/fournisseur.
        """

        zones = []
        for zone in administrative_zones or []:
            if zone.get("page_number") != page_number:
                continue
            zone_type = str(zone.get("type", "")).upper()
            if zone_type != "VISA_APPROBATION":
                continue
            label = self._normalize_text(zone.get("label", ""))
            if "lu et accepte" not in label:
                continue
            bbox = zone.get("bbox")
            if not self._valid_bbox(bbox):
                continue
            zones.append(zone)
        return zones

    @staticmethod
    def _valid_bbox(bbox: Any) -> bool:
        """
        Vérifie qu'une bbox est exploitable.
        Format attendu : [x0, y0, x1, y1]
        """
        if not isinstance(bbox, (list, tuple)):
            return False
        if len(bbox) != 4:
            return False
        try:
            x0, y0, x1, y1 = map(float, bbox)
        except (TypeError, ValueError):
            return False
        return x1 > x0 and y1 > y0

    # CHOIX DE LA MEILLEURE BBOX
    def _select_best_zone(
        self,
        zones: List[Dict[str, Any]],
        page_width: float,
        page_height: float,
    ) -> Optional[Dict[str, Any]]:
        """
        Sélectionne la meilleure bbox parmi plusieurs détections.
        Priorités :
        1. confiance OCR élevée ;
        2. zone explicitement destinée au concurrent ;
        3. zone située vers la partie basse de la page ;
        4. zone raisonnablement dimensionnée.
        La méthode ne modifie jamais les coordonnées détectées.
        """
        if not zones:
            return None
        def score(zone: Dict[str, Any]) -> float:
            bbox = zone["bbox"]
            x0, y0, x1, y1 = map(float, bbox)
            confidence = float(zone.get("confidence") or 0.0)
            label = self._normalize_text(zone.get("label", ""))
            score_value = confidence * 100.0
            # Priorité au concurrent / fournisseur
            if "concurrent" in label:
                score_value += 40
            if "fournisseur" in label:
                score_value += 35
            if "titulaire" in label:
                score_value += 20
            if "fabricant" in label:
                score_value += 15
            # Une zone très haute couvrant une grande partie du texte est souvent un faux positif.
            area = (x1 - x0) * (y1 - y0)
            page_area = page_width * page_height
            if page_area > 0:
                relative_area = area / page_area
                if relative_area > 0.65:
                    score_value -= 80
                elif relative_area > 0.45:
                    score_value -= 30
            # Préférence pour la partie basse.
            center_y = (y0 + y1) / 2
            if page_height > 0:
                relative_y = center_y / page_height
                if relative_y > 0.60:
                    score_value += 20
                elif relative_y > 0.40:
                    score_value += 5
            return score_value
        best_zone = max(zones, key=score)
        logger.debug(
            "Meilleure zone sélectionnée | page=%s | type=%s | label=%s | bbox=%s",
            best_zone.get("page_number"), best_zone.get("type"),best_zone.get("label"), best_zone.get("bbox")
        )
        return best_zone
    # OVERLAY DE SIGNATURE

    def _create_signature_overlay(
        self,
        page_width: float,
        page_height: float,
        bbox: List[float],
        signer_name: str,
        lu_accepte: bool = False,
    ):
        """
        Crée un PDF temporaire contenant la signature dans la bbox fournie.

        Le buffer reste attaché au PdfReader afin d'éviter les erreurs
        de type "Stream has ended unexpectedly" lors du merge.
        """

        x0, y0, x1, y1 = map(float, bbox)

        buffer = BytesIO()

        pdf = canvas.Canvas(
            buffer,
            pagesize=(page_width, page_height)
        )

        box_width = x1 - x0
        box_height = y1 - y0

        text = (
            f"Lu et accepté - {signer_name}"
            if lu_accepte
            else f"Lu et signé - {signer_name}"
        )

        font_size = min(
            9,
            max(
                6,
                box_width / max(len(text), 1) * 0.7
            )
        )

        pdf.setFont("Helvetica", font_size)

        margin_x = min(8, box_width * 0.05)
        margin_y = min(8, box_height * 0.08)

        signature_x = x1 - margin_x
        signature_y = page_height - y1 + margin_y

        pdf.drawRightString(
            signature_x,
            signature_y,
            text
        )

        pdf.save()
        buffer.seek(0)

        reader = PdfReader(buffer)
        overlay_page = reader.pages[0]

        # On conserve le buffer et le reader avec la page.
        overlay_page._signature_buffer = buffer
        overlay_page._signature_reader = reader

        logger.debug(
            "Overlay signature créé | bbox=%s | signer=%s | lu_accepte=%s",
            bbox,
            signer_name,
            lu_accepte,
        )

        return overlay_page

    # SIGNATURE DU PDF
    def sign_pdf(
        self,
        input_path: str | Path,
        output_path: str | Path,
        signer_name: str,
        administrative_zones: Optional[List[Dict[str, Any]]] = None,
    ) -> Path:
        """
        Signe visuellement les zones détectées du PDF.
        Règles :
        - aucune pagination n'est ajoutée ;
        - les pages originales restent inchangées ;
        - les zones SIGNATURE_CACHET sont utilisées ;
        - les zones VISA_APPROBATION ne sont utilisées que si elles
          contiennent "LU ET ACCEPTE" ;
        - en cas de plusieurs bbox sur une même page, la meilleure
          bbox est sélectionnée ;
        - les coordonnées bbox sont utilisées telles quelles.
        Args:
            input_path: PDF original.
            output_path: PDF signé.
            signer_name: Nom du signataire.
            administrative_zones: Zones détectées par OCR/PyMuPDF/RAPIDOCR.
        Returns:
            Chemin du PDF signé.
        """
        input_path = Path(input_path)
        output_path = Path(output_path)
        administrative_zones = administrative_zones or []
        logger.info(
            "Signature PDF démarrée | input=%s | zones=%s",
            input_path,
            len(administrative_zones),
        )
        reader = PdfReader(str(input_path))
        writer = PdfWriter()
        total_pages = len(reader.pages)
        logger.info("PDF chargé | pages=%s | fichier=%s",total_pages,input_path.name)
        signed_pages = 0
        signed_zones = 0
        for page_index, page in enumerate(reader.pages,start=1):
            page_width = float(page.mediabox.width)
            page_height = float(page.mediabox.height)
            # Zones SIGNATURE_CACHET
            signature_zones = self._get_signature_zones(administrative_zones,page_index)
            best_signature_zone = self._select_best_zone(signature_zones,page_width,page_height)
            # Zones LU ET ACCEPTE
            lu_accepte_zones = self._get_lu_accepte_zones(administrative_zones,page_index)
            best_lu_accepte_zone = self._select_best_zone(lu_accepte_zones,page_width,page_height)
            page_was_signed = False
            # Signature normale

            if best_signature_zone:
                overlay = self._create_signature_overlay(
                    page_width=page_width,
                    page_height=page_height,
                    bbox=best_signature_zone["bbox"],
                    signer_name=signer_name,
                    lu_accepte=False,
                )

                page.merge_page(overlay)
                signed_zones += 1
                page_was_signed = True
                logger.info(
                    "Signature ajoutée | page=%s | bbox=%s | label=%s",
                    page_index,best_signature_zone["bbox"],best_signature_zone.get("label"),
                )

            # Signature LU ET ACCEPTE
            if best_lu_accepte_zone:
                overlay = self._create_signature_overlay(
                    page_width=page_width,
                    page_height=page_height,
                    bbox=best_lu_accepte_zone["bbox"],
                    signer_name=signer_name,
                    lu_accepte=True,
                )
                page.merge_page(overlay)
                signed_zones += 1
                page_was_signed = True
                logger.info(
                    "Zone LU ET ACCEPTE signée | page=%s | bbox=%s | label=%s",
                    page_index,best_lu_accepte_zone["bbox"],best_lu_accepte_zone.get("label"),
                )

            if page_was_signed:
                signed_pages += 1

            # IMPORTANT : On conserve la page originale telle quelle.
            # Aucune pagination n'est ajoutée.
            writer.add_page(page)

        output_path.parent.mkdir(parents=True,exist_ok=True)
        with open(output_path, "wb") as file:
            writer.write(file)

        logger.info(
            "Signature PDF terminée | output=%s | pages_signees=%s | zones_signees=%s",
            output_path,signed_pages,signed_zones,
        )
        return output_path