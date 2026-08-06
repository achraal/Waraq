from docx import Document
from sqlalchemy.orm import Session
from backend.app.database.models import User, CompanyProfile, Tender, DocumentRAGAnalysis

class AdminDocGeneratorService:

    def generate_acte_engagement(self, db: Session, user_id: str, tender_id: str) -> str:
        user = db.query(User).filter(User.id == user_id).first()
        profile = user.company_profile
        tender = db.query(Tender).filter(Tender.id == tender_id).first()

        # Chemin du modèle fallback Waraq
        template_path = "backend/data_storage/templates/acte_engagement_waraq_template.docx"
        doc = Document(template_path)

        # Mapping des variables dynamiques en fonction du profil juridique
        replacements = {
            "{{RAISON_SOCIALE}}": getattr(profile, "company_name", profile.manager_name),
            "{{NOM_GERANT}}": profile.manager_name,
            "{{ADRESSE}}": profile.address,
            "{{ICE}}": profile.ice or "N/A",
            "{{RC_NUM}}": getattr(profile, "rc_number", profile.cin_number),
            "{{RIB}}": profile.rib,
            "{{BANQUE}}": profile.bank_name,
            "{{OBJET_AO}}": tender.title,
            "{{REF_AO}}": tender.reference,
            "{{BUYER}}": tender.buyer
        }

        # Remplacement direct dans le document .docx
        for p in doc.paragraphs:
            for key, val in replacements.items():
                if key in p.text:
                    p.text = p.text.replace(key, str(val))

        output_path = f"backend/data_storage/generated/{user_id}_{tender.reference}_acte_engagement.docx"
        doc.save(output_path)
        return output_path