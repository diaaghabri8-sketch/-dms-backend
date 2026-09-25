from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.core.config import STORAGE_DIR, settings
from app.core.scheduler import start_scheduler, stop_scheduler
from app.routers import (
    appels_offres,
    auth,
    conversations,
    equipements,
    equipements_reparation,
    evenements,
    formations,
    health,
    interventions,
    intervention_workflow,
    messages,
    notifications,
    planning,
    stats,
    techniciens,
    ws_chat,
)

STORAGE_DIR.mkdir(parents=True, exist_ok=True)


@asynccontextmanager
async def lifespan(_: FastAPI):
    # Veille marchés publics — job quotidien planifié (voir core/scheduler.py). Démarré ici
    # plutôt qu'au chargement du module pour ne pas tourner pendant les imports (ex: alembic,
    # scripts one-off) qui importent app.main indirectement.
    start_scheduler()
    yield
    stop_scheduler()


app = FastAPI(title="DMS Platform API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/storage", StaticFiles(directory=str(STORAGE_DIR)), name="storage")

app.include_router(auth.router)
app.include_router(techniciens.router)
app.include_router(equipements.router)
app.include_router(interventions.router)
app.include_router(intervention_workflow.router)
app.include_router(planning.router)
app.include_router(formations.router)
app.include_router(evenements.router)
app.include_router(conversations.router)
app.include_router(messages.router)
app.include_router(stats.router)
app.include_router(equipements_reparation.router)
app.include_router(notifications.router)
app.include_router(appels_offres.router)
app.include_router(ws_chat.router)
app.include_router(health.router)


@app.get("/health")
def health_check():
    return {"status": "ok"}
