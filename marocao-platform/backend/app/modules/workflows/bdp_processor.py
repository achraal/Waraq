from typing import Dict, Any, List
import re

class BDPProcessor:
    def __init__(self):
        pass

    def parse_bdp_text(self, text_content: str) -> List[Dict[str, Any]]:
        """
        Extrait les lignes d'un BDP par expression régulière et règles métiers.
        """
        items = []
        # Pattern générique pour capturer N° Prix, Description, Unité, Quantité
        pattern = re.compile(r'(\d+[\.\d+]*)\s+([^\n\d]+)\s+([A-Za-z0-9²/]+)\s+(\d+[\,\.]?\d*)')
        
        lines = text_content.split("\n")
        for line in lines:
            match = pattern.search(line)
            if match:
                num, desc, unit, qty = match.groups()
                items.append({
                    "item_number": num.strip(),
                    "description": desc.strip(),
                    "unit": unit.strip(),
                    "quantity": float(qty.replace(',', '.'))
                })
        return items

    def calculate_totals(self, items: List[Dict[str, Any]], tva_rate: float = 0.20) -> Dict[str, Any]:
        """Calcule les montants HT, TVA et TTC du BDP."""
        total_ht = sum(item.get("total_price_ht", 0.0) for item in items)
        total_tva = total_ht * tva_rate
        total_ttc = total_ht + total_tva

        return {
            "total_ht": round(total_ht, 2),
            "tva_amount": round(total_tva, 2),
            "total_ttc": round(total_ttc, 2),
            "items_count": len(items)
        }