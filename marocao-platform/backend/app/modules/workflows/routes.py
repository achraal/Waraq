from fastapi import APIRouter, HTTPException, Body
from typing import Dict, Any
from backend.app.modules.workflows.bdp_processor import BDPProcessor
from backend.app.modules.workflows.doc_generator import DocumentGenerator

router = APIRouter(prefix="/workflows", tags=["Workflows"])

# Instanciation des services
bdp_processor = BDPProcessor()
doc_generator = DocumentGenerator()

@router.post("/process-bdp")
async def process_bdp_endpoint(payload: Dict[str, Any] = Body(...)):
    """Traitement et calcul automatique du BDP à partir du texte extrait."""
    text_content = payload.get("text", "")
    if not text_content:
        raise HTTPException(status_code=400, detail="Le texte source est obligatoire.")

    items = bdp_processor.parse_bdp_text(text_content)
    totals = bdp_processor.calculate_totals(items)

    return {
        "status": "completed",
        "items": items,
        "summary": totals
    }

@router.post("/generate-report")
async def generate_report_endpoint(payload: Dict[str, Any] = Body(...)):
    """Génération du rapport de synthèse du dossier."""
    doc_info = payload.get("document_info", {})
    bdp_info = payload.get("bdp_info", {})

    report = doc_generator.generate_summary_report(doc_info, bdp_info)
    return {
        "status": "success",
        "report": report
    }