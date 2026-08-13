import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

class AdminFieldsExtractor:
    """
    Extracteur dynamique des champs administratifs.
    Le document source est considéré comme un modèle arbitraire.
    Aucun ensemble fixe de champs n'est imposé au document.

    L'extracteur :
    - analyse le texte natif ;
    - analyse le texte OCR ;
    - détecte les labels administratifs ;
    - détecte les zones vides ;
    - détecte les lignes à compléter ;
    - conserve le label original du document ;
    - produit une structure exploitable par le frontend ;
    - permet ensuite au générateur de remplir le document.
    """

    # PATTERNS GÉNÉRIQUES
    EMPTY_LINE_PATTERN = re.compile(
        r"^(?P<label>[^:]{2,100})"
        r"\s*[:：]\s*"
        r"(?P<value>[_\.]{2,}|)$",
        re.IGNORECASE,
    )
    UNDERSCORE_PATTERN = re.compile(
        r"(?P<label>[A-Za-zÀ-ÿ\u0600-\u06FF0-9 /().,'-]{2,100})"
        r"\s*[:：]\s*"
        r"(?P<value>_{2,}|\.{3,}|)$"
    )
    LABEL_PATTERN = re.compile(
        r"^(?P<label>"
        r"[A-Za-zÀ-ÿ\u0600-\u06FF0-9 /().,'-]{2,100}"
        r")"
        r"\s*[:：]"
        r"\s*$"
    )

    # Champs très courants utilisés uniquement comme classification sémantique secondaire. Ils ne limitent PAS les champs détectés.
    SEMANTIC_ALIASES = {
        "RAISON_SOCIALE": [
            "raison sociale",
            "dénomination",
            "denomination",
            "nom de la société",
            "nom société",
        ],
        "REPRESENTANT": [
            "représentant",
            "representant",
            "gérant",
            "gerant",
            "dirigeant",
        ],
        "ADRESSE": [
            "adresse",
            "domicile",
            "siège",
            "siege",
        ],
        "IDENTIFICATION": [
            "cin",
            "ice",
            "registre du commerce",
            "rc",
            "patente",
            "identifiant fiscal",
        ],
        "BANQUE": [
            "rib",
            "banque",
            "compte bancaire",
            "compte",
        ],
        "CONTACT": [
            "téléphone",
            "telephone",
            "fax",
            "email",
            "e-mail",
            "courriel",
        ],
    }

    # NORMALISATION

    @staticmethod
    def normalize_text(text: str) -> str:
        """
        Normalise un texte pour faciliter la détection des labels.
        """
        if not text:
            return ""
        text = text.replace("\u00a0", " ")
        text = re.sub(r"[ \t]+", " ", text)
        return text.strip()

    # CLASSIFICATION SÉMANTIQUE

    def classify_field(self, label: str) -> Optional[str]:
        """
        Tente d'associer un label détecté à une catégorie métier.
        Cette classification est optionnelle : le label original reste toujours conservé.
        """
        normalized = self.normalize_text(label).lower()
        for category, aliases in self.SEMANTIC_ALIASES.items():
            for alias in aliases:
                if alias in normalized:
                    return category
        return None

    # DÉTECTION D'UN LABEL

    def _build_field(
        self,
        label: str,
        value: Optional[str] = None,
        line_number: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Construit la structure standard d'un champ détecté.
        """
        clean_label = self.normalize_text(label)

        return {
            "field_id": (
                re.sub(r"[^a-zA-Z0-9]+", "_", clean_label.lower()).strip("_")
                or f"field_{line_number or 0}"
            ),
            "label": clean_label,
            "original_label": clean_label,
            "semantic_type": self.classify_field(clean_label),
            "value": value,
            "required": True,
            "line_number": line_number,
            "source": "document",
        }

    # EXTRACTION DYNAMIQUE

    def extract_from_text(self, text: str) -> List[Dict[str, Any]]:
        """
        Détecte dynamiquement les champs administratifs présents dans le texte du document.
        La méthode ne dépend pas d'une liste fixe de champs. Exemples détectés :
            Nom : ________
            Adresse : ................
            ICE :
            Dénomination :
            N° RC : __________
        Les labels sont conservés tels qu'ils apparaissent dans le document.
        """
        if not text:
            logger.warning("[ADMIN_FIELDS] Texte vide.")
            return []
        lines = text.splitlines()
        fields: List[Dict[str, Any]] = []
        seen_labels = set()
        for line_number, raw_line in enumerate(lines,start=1):

            line = self.normalize_text(raw_line)
            if not line:
                continue
            # Cas :
            # Nom : __________
            # Adresse : .........

            match = self.EMPTY_LINE_PATTERN.match(line)
            if match:

                label = match.group("label").strip()
                value = match.group("value").strip()
                key = label.lower()
                if key not in seen_labels:
                    fields.append(self._build_field(label=label,
                            value=(None if not value or re.fullmatch(r"[_\.]+",value,)
                                else value
                            ),
                            line_number=line_number,
                        )
                    )
                    seen_labels.add(key)
                continue
            # Cas :
            # Nom :
            # Adresse :
            # Dénomination :

            match = self.LABEL_PATTERN.match(line)
            if match:
                label = match.group("label").strip()
                key = label.lower()
                if key not in seen_labels:
                    fields.append(self._build_field(label=label,value=None,line_number=line_number,))
                    seen_labels.add(key)
                continue
            # Cas OCR :
            # Nom _________
            # Adresse .............
            match = self.UNDERSCORE_PATTERN.search(line)

            if match:
                label = match.group("label").strip()
                value = match.group("value").strip()
                key = label.lower()
                if key not in seen_labels:
                    fields.append(self._build_field(label=label,value=None,line_number=line_number,))
                    seen_labels.add(key)
        logger.info("[ADMIN_FIELDS] Champs dynamiques détectés | count=%s",len(fields),)
        for field in fields:
            logger.debug("[ADMIN_FIELDS] Champ | label=%s | type=%s | line=%s",
                field["label"],
                field["semantic_type"],
                field["line_number"],
            )
        return fields

    # EXTRACTION DEPUIS UN FICHIER
    def extract_from_file(self,file_path: str | Path,ocr_service,) -> Dict[str, Any]:
        """
        Extrait dynamiquement les champs d'un document.
        Tous les formats sont délégués au WorkflowOCRService.
        Cela permet de prendre en charge :
        - PDF natif
        - PDF scanné
        - DOC
        - DOCX
        - XLS
        - XLSX
        - XLSM
        - images

        Les documents scannés utilisent donc automatiquement RapidOCR/ONNX via le moteur OCR existant.
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Document introuvable : {path}")
        if ocr_service is None:
            raise ValueError("WorkflowOCRService requis.")
        logger.info("[ADMIN_FIELDS] Analyse du document | file=%s",path,)
        result = ocr_service.extract(str(path))
        text = result.get("text","")
        fields = self.extract_from_text(text)

        response = {
            "file_path": str(path),
            "file_name": path.name,
            "format": path.suffix.lower(),
            "is_scanned": result.get("is_scanned",False,),
            "inspection_method": result.get("inspection_method",),
            "page_count": result.get("page_count",),
            "ocr_duration_sec": result.get("ocr_duration_sec",0,),
            "fields": fields,
            "fields_count": len(fields),
        }

        logger.info(
            "[ADMIN_FIELDS] Analyse terminée | "
            "file=%s | fields=%s | scanned=%s | method=%s",
            path, len(fields),response["is_scanned"],response["inspection_method"],)
        return response

    # PRÉPARATION POUR LE PROFIL
    def resolve_profile_values(self,fields: List[Dict[str, Any]],profile: Any,) -> List[Dict[str, Any]]:
        """
        Tente de pré-remplir les champs détectés à partir du CompanyProfile utilisateur.
        Le mapping sémantique est secondaire : le document reste maître de ses propres champs.
        """

        profile_values = {
            "RAISON_SOCIALE": getattr(profile,"company_name",None,),
            "REPRESENTANT": getattr(profile,"manager_name",None,),
            "ADRESSE": getattr(profile,"address",None,),
            "IDENTIFICATION": getattr(profile,"ice",None,),
            "BANQUE": getattr(profile,"bank_name",None,),
        }

        resolved = []
        for field in fields:
            semantic_type = field.get("semantic_type")
            value = profile_values.get(semantic_type)
            enriched = dict(field)
            if value:
                enriched["suggested_value"] = value
            else:
                enriched["suggested_value"] = None
            resolved.append(enriched)

        logger.info("[ADMIN_FIELDS] Pré-remplissage profil | fields=%s",len(resolved),)
        return resolved