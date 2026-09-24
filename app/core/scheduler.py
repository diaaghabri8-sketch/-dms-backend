"""Planification de la veille marchés publics — un job quotidien (APScheduler, cohérent avec le
reste du stack Python, voir SUIVI_PROJET.md). Démarré/arrêté depuis le lifespan de `main.py`.
"""

import logging

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from app.core.config import settings
from app.database import SessionLocal
from app.services.marches_publics import run_scan

logger = logging.getLogger(__name__)

scheduler = BackgroundScheduler()


def _run_scan_job() -> None:
    """Wrapper pour le job planifié — ouvre sa propre session DB (pas de `Depends(get_db)` hors
    d'une requête HTTP) et journalise une erreur complète plutôt que de laisser le scheduler
    avaler silencieusement une exception."""
    db = SessionLocal()
    try:
        run_scan(db)
    except Exception:
        logger.exception("Échec du job planifié de veille marchés publics.")
    finally:
        db.close()


def start_scheduler() -> None:
    if scheduler.running:
        return
    scheduler.add_job(
        _run_scan_job,
        trigger=CronTrigger(hour=settings.APPELS_OFFRES_SCAN_HEURE, minute=0),
        id="veille_marches_publics",
        replace_existing=True,
    )
    scheduler.start()
    logger.info("Scheduler démarré — veille marchés publics planifiée à %dh00.", settings.APPELS_OFFRES_SCAN_HEURE)


def stop_scheduler() -> None:
    if scheduler.running:
        scheduler.shutdown(wait=False)
