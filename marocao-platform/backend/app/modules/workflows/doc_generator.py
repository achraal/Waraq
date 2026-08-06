from typing import Dict, Any
import json

class DocumentGenerator:
    def __init__(self):
        pass

    def generate_summary_report(self, document_info: Dict[str, Any], bdp_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Génère une synthèse structurée prête à être convertie ou affichée sur le frontend.
        """
        report = {
            "title": f"Synthèse de l'Appel d'Offres - {document_info.get('filename', 'Inconnu')}",
            "metadata": {
                "category": document_info.get("category", "Non classifié"),
                "pages_processed": document_info.get("total_pages", 0)
            },
            "financial_summary": {
                "total_ht": bdp_data.get("total_ht", 0.0),
                "tva": bdp_data.get("tva_amount", 0.0),
                "total_ttc": bdp_data.get("total_ttc", 0.0)
            },
            "items_extracted": bdp_data.get("items_count", 0)
        }
        return report