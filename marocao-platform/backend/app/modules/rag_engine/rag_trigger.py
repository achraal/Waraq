import asyncio, logging, threading
from backend.app.database.connection import SessionLocal
from backend.app.database.models import TenderDocument
from backend.app.modules.rag_engine.rag_service import rag_pipeline_service

logger = logging.getLogger("waraq.rag.trigger")

def lancer_rag_tender_async(tender_id: int):
    """
    Déclenche le RAG dans un thread séparé.
    La session DB utilisée par la classification
    n'est jamais réutilisée ici.
    """
    thread = threading.Thread(
        target=_executer_rag_tender_background,
        args=(tender_id,),
        daemon=True,
        name=f"waraq-rag-tender-{tender_id}"
    )
    thread.start()
    logger.info( "[RAG][ASYNC] Tâche RAG lancée en arrière-plan pour Tender ID=%s", tender_id)

def _executer_rag_tender_background(tender_id: int):
    """
    Worker background synchrone qui exécute
    le pipeline RAG asynchrone.
    """

    db = SessionLocal()

    try:
        logger.info("[RAG][ASYNC] Début du traitement du Tender ID=%s", tender_id)
        documents = (
            db.query(TenderDocument)
            .filter(
                TenderDocument.tender_id == tender_id,
                TenderDocument.is_classified == True,
                TenderDocument.file_type.in_(
                    ["CPS", "RC", "BDP"]
                )
            )
            .all()
        )
        if not documents:
            logger.info("[RAG][ASYNC] Aucun document éligible pour Tender ID=%s", tender_id)
            return

        logger.info("[RAG][ASYNC] %s document(s) éligible(s) pour Tender ID=%s", len(documents), tender_id)

        for document in documents:
            logger.info("[RAG][ASYNC] Traitement document ID=%s | type=%s | fichier=%s", document.id, document.file_type, document.file_name)

            try:
                asyncio.run(rag_pipeline_service.execute_rag_pipeline(db=db, document_id=str(document.id)))
                logger.info("[RAG][ASYNC] Document ID=%s terminé", document.id)

            except Exception as document_error:
                logger.error("[RAG][ASYNC] Échec document ID=%s : %s", document.id, document_error, exc_info=True)

        logger.info("[RAG][ASYNC] Traitement complet du Tender ID=%s", tender_id)

    except Exception as e:
        logger.error("[RAG][ASYNC] Erreur globale Tender ID=%s : %s", tender_id, e, exc_info=True)

    finally:
        db.close()
        logger.info("[RAG][ASYNC] Session DB fermée pour Tender ID=%s", tender_id)