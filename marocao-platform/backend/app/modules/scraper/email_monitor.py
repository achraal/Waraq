import imaplib, email
from email.utils import parsedate_to_datetime
from email.header import decode_header, make_header
from sqlalchemy.orm import Session
from backend.app.database.models import EmailNotification
from charset_normalizer import from_bytes
from backend.app.config import settings

username = settings.EMAIL_USER
password = settings.EMAIL_PASSWORD
imap_url = settings.EMAIL_IMAP_SERVER

# def fetch_marche_publics():
#     # Debug avant la connexion
#     if not username or not password:
#         print("ERREUR CRITIQUE: EMAIL_USER ou EMAIL_PASSWORD non définis dans le .env")
#         return []

#     try:
#         # Connexion
#         mail = imaplib.IMAP4_SSL(imap_url)
#         mail.login(username, password)
#         mail.select("inbox")

#         # Recherche
#         status, messages = mail.search(None, 'FROM "noreply-marchespublics@tgr.gov.ma"')
        
#         if status != "OK":
#             return []

#         email_ids = messages[0].split()
#         results = []
        
#         # On itère sur les derniers messages
#         for e_id in email_ids[-5:]:
#             _, msg_data = mail.fetch(e_id, "(RFC822)")
#             for response_part in msg_data:
#                 if isinstance(response_part, tuple):
#                     msg = email.message_from_bytes(response_part[1])
                    
#                     # 1. Obtenir l'objet et le convertir en string proprement
#                     raw_subject = msg.get("Subject", "")
#                     if isinstance(raw_subject, email.header.Header):
#                         # Si c'est un objet Header, on le décode proprement
#                         try:
#                             subject = str(email.header.make_header(decode_header(raw_subject)))
#                         except:
#                             subject = str(raw_subject)
#                     else:
#                         subject = raw_subject

#                     # 2. Nettoyage final sécurisé (on s'assure que c'est une string)
#                     subject = str(subject).replace("PMMP - ", "").strip()
                    
#                     results.append({
#                         "mail_uid": e_id.decode(),
#                         "subject": subject,
#                         "date": msg["Date"]
#                     })
        
#         mail.logout()
#         return results

#     except Exception as e:
#         print(f"Erreur lors de la récupération des emails: {e}")
#         return []

def fetch_marche_publics():
    if not username or not password:
        print("ERREUR CRITIQUE: EMAIL_USER ou EMAIL_PASSWORD non définis")
        return []

    try:
        mail = imaplib.IMAP4_SSL(imap_url)
        mail.login(username, password)
        mail.select("inbox")

        status, messages = mail.search(None, 'FROM "noreply-marchespublics@tgr.gov.ma"')
        if status != "OK": return []

        email_ids = messages[0].split()
        results = []
        
        for e_id in email_ids:
            _, msg_data = mail.fetch(e_id, "(RFC822)")
            for response_part in msg_data:
                if isinstance(response_part, tuple):
                    msg = email.message_from_bytes(response_part[1])
                    
                    # 1. Décodage robuste du Sujet (règle le problème des accents)
                    raw_subject = msg.get("Subject", "")
                    try:
                        # On décode les parties brutes
                        decoded_parts = decode_header(raw_subject)
                        subject_str = ""
                        for part, encoding in decoded_parts:
                            if isinstance(part, bytes):
                                # Utilisation de la détection automatique ultra-robuste
                                result = from_bytes(part).best()
                                subject_str += str(result) if result else part.decode('utf-8', 'replace')
                            else:
                                subject_str += part
                        subject = subject_str
                    except Exception:
                        subject = str(raw_subject)

                    subject = subject.replace("PMMP - ", "").strip()
                    
                    # try:
                    #     # On décode les parties de l'en-tête
                    #     decoded_parts = decode_header(raw_subject)
                    #     subject_str = ""
                    #     for part, encoding in decoded_parts:
                    #         if isinstance(part, bytes):
                    #             # On essaie l'encodage spécifié, sinon on force utf-8 ou latin-1
                    #             enc = encoding if encoding else 'utf-8'
                    #             try:
                    #                 subject_str += part.decode(enc)
                    #             except (UnicodeDecodeError, LookupError):
                    #                 # Secours : forcer le latin-1 (très fréquent pour les accents français/marocains)
                    #                 subject_str += part.decode('latin-1', errors='replace')
                    #         else:
                    #             subject_str += part
                    #     subject = subject_str
                    # except Exception:
                    #     # Dernier recours : garder le texte brut
                    #     subject = str(raw_subject)

                    #subject = subject.replace("PMMP - ", "").strip()
                    
                    # 2. Extraction du corps (pour le champ 'content')
                    content = get_email_body(msg)
                    
                    # 3. Extraction de la date (pour 'received_at')
                    date_str = msg.get("Date")
                    
                    results.append({
                        "mail_uid": e_id.decode(),
                        "subject": subject,
                        "content": content,
                        "date": date_str
                    })
        
        mail.logout()
        return results
    except Exception as e:
        print(f"Erreur lors de la récupération des emails: {e}")
        return []

def get_email_body(msg):
    """Extrait et décode proprement le texte en testant plusieurs encodages."""
    def try_decode(data):
        # Liste des encodages courants pour les systèmes hérités/gouvernementaux
        for encoding in ['utf-8', 'iso-8859-1', 'windows-1252']:
            try:
                return data.decode(encoding)
            except UnicodeDecodeError:
                continue
        # Si aucun ne marche, on force le remplacement des caractères invalides
        return data.decode('utf-8', errors='replace')

    if msg.is_multipart():
        for part in msg.walk():
            # On cherche text/plain, ou à défaut text/html
            if part.get_content_type() in ["text/plain", "text/html"]:
                payload = part.get_payload(decode=True)
                return try_decode(payload)
    else:
        payload = msg.get_payload(decode=True)
        return try_decode(payload)
    
    return ""

def save_emails_to_db(db: Session, emails: list):
    """Insère uniquement les nouveaux emails et retourne le compte."""
    count = 0
    for email_data in emails:
        # Vérification stricte par mail_uid pour éviter tout doublon
        exists = db.query(EmailNotification).filter(
            EmailNotification.mail_uid == email_data["mail_uid"]
        ).first()
        
        if not exists:
            try:
                # Conversion sécurisée de la date
                dt = parsedate_to_datetime(email_data["date"])
            except:
                dt = None
            
            new_email = EmailNotification(
                mail_uid=email_data["mail_uid"],
                subject=email_data["subject"],
                content=email_data["content"],
                received_at=dt,
                is_read=False
            )
            db.add(new_email)
            count += 1
    
    if count > 0:
        db.commit()
        print(f"Synchronisation : {count} nouveau(x) message(s) ajouté(s).")
    else:
        print("Synchronisation : Tout est déjà à jour, aucun nouveau message.")
        
    return count