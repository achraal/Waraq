import re

def nettoyer_nom_type(type_str: str) -> str:
    """Nettoie et sécurise les libellés de types pour les chemins de fichiers et BDD."""
    if not type_str:
        return "INCONNU"
    # Remplace les caractères invalides par des underscores sans casser les espaces composés (ex: BORDEREAU_PRIX)
    clean = re.sub(r'[\\/*?:"<>|]', '_', str(type_str).strip())
    clean = re.sub(r'\s+', '_', clean)
    return clean.upper()
	
def appliquer_types_primitifs(nom_fichier: str, ext: str) -> str | None:
    f_norm = nom_fichier.lower().strip()
    ext_norm = ext.lower().strip()

    # 1. Extensions explicites (Tableurs Excel)
    if ext_norm in [".xlsx", ".xls", ".xlsm"]:
        return "BORDEREAU_PRIX"
       
    # Captures: "bordereau des prix", "bpe", "bp", "bpg"
    REGEX_BORDEREAU = r"(^|[\s\-_])(bordereau[\s\-_]*(des?|de)?[\s\-_]*prix|bpe|bpg)([\s\-_]|$)"
    # Captures: "sous detail des prix", "sous-détail du prix", "s/detail prix", "sousdetail_prix"
    REGEX_SOUS_DETAIL = r"s(ous|/)[\s\-_]*d[eé]tail[\s\-_]*(des?|du)?[\s\-_]*prix"

    if re.search(REGEX_BORDEREAU, f_norm) or re.search(REGEX_SOUS_DETAIL, f_norm):
        return "BORDEREAU_PRIX"       
    # 2. Fichiers SIG / Annexes
    if ext_norm in [".jgw", ".tfw", ".pgw", ".xml", ".dbf", ".prj"]:
        return "AUTRE"
    # ACTE D'ENGAGEMENT / ACTE ENGAGEMENT - Capture: "acte d'engagement", "acte d engagement", "acte engagement", "acte_engagement", "acte-engagement"
    if re.search(r"acte[\s\-_]*(d['\s]?)?engagement", f_norm):
        return "ACTE_ENGAGEMENT"
    # DECLARATION SUR L'HONNEUR
    if re.search(r"declaration\s*sur\s*l['\s]?honneur", f_norm):
        return "DECLARATION_HONNEUR"        
    # CPS / CAHIER DES PRESCRIPTIONS SPÉCIALES - Capture: cps, ccftp, ccatp, ccafp, cctp ou expressions complètes  
    if re.search(r"(^|[\s\-_])(cps|ccftp|ccatp|ccafp|cctp|ccafg|ccaafg|ccag|ccagtp)([\s\-_]|$)|cahier\s+des?\s+prescriptions?\s+sp[eé]ciales?", f_norm):
        return "CPS"
    # RC / RÈGLEMENT DE CONSULTATION - Capture: "rc", "reglement de la consultation", "reglement de consultation", "reglement consultation"
    if re.search(r"(^|[\s\-_])rc([\s\-_]|$)|r[eèg]glement\s*(de\s*(la\s*)?)?consultation", f_norm):
        return "RC"
    # BORDEREAU DE PRIX / BDR / BP - Capture: "bdr", "bp" (mot isolé), "bordereau"
    if re.search(r"\b(bdr|bp)\b|bordereau", f_norm):
        return "BORDEREAU_PRIX"
    # AVIS EN FRANÇAIS - Capture: "avis fr", "avis-fr", "avis en francais", "avis en français"
    if re.search(r"avis[\s\-_]*fr|avis\s+en\s+fran[cç]ais", f_norm):
        return "AVIS_FRANCAIS"
    # AVIS EN ARABE - Capture: "avis ar", "avis-ar", "avis en arabe"
    if re.search(r"avis[\s\-_]*ar|avis\s+en\s+arabe", f_norm):
        return "AVIS_ARABE"
    # AVIS GÉNÉRIQUE
    if re.search(r"\bavis\b", f_norm):
        return "AVIS"
    return None