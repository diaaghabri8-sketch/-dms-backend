"""Endpoint de santé appelé depuis l'extérieur (GitHub Actions, voir .github/workflows/
keep-alive.yml) pour garder le projet Supabase actif — le plan gratuit met la base en pause
après 7 jours sans activité, et un job APScheduler interne ne suffit pas puisque Render (plan
gratuit) met lui-même le service en veille après 15 min sans requête HTTP : le déclencheur doit
donc être externe. Voir SUIVI_PROJET.md.
"""

import logging
import secrets
from datetime import datetime, timezone

from fastapi import APIRouter, Header, HTTPException, status
from sqlalchemy import text

from app.core.config import settings
from app.database import engine

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/db")
def health_db(x_health_token: str | None = Header(default=None, alias="X-Health-Token")) -> dict:
    # `secrets.compare_digest` (pas `==`) — évite une fuite de timing sur un token qui protège
    # un endpoint public, même si l'enjeu réel ici est faible (juste un SELECT 1).
    if not settings.HEALTH_TOKEN or not secrets.compare_digest(x_health_token or "", settings.HEALTH_TOKEN):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token invalide")

    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception:
        logger.exception("Health check /health/db : échec de connexion à la base.")
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Base de données indisponible")

    logger.info("Health check /health/db : OK.")
    return {"status": "ok", "db": "ok", "timestamp": datetime.now(timezone.utc).isoformat()}
