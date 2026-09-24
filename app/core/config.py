from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent  # dms-backend/app
STORAGE_DIR = BASE_DIR / "storage"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # SQLite en développement local par défaut (rapide, pas de dépendance réseau) — en
    # production (Render), DATABASE_URL est définie dans l'environnement et pointe vers
    # Postgres/Supabase, voir SUIVI_PROJET.md.
    DATABASE_URL: str = "sqlite:///./dev_demo.db"
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    ACCOUNT_EMAIL_DOMAIN: str = "dms.tn"

    # Origines autorisées en CORS, séparées par des virgules — jamais en dur dans le code pour
    # que Render puisse pointer vers l'URL Vercel définitive sans toucher au code, voir
    # SUIVI_PROJET.md.
    CORS_ORIGINS: str = "http://localhost:5173"

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    # Veille marchés publics (voir services/marches_publics.py) — mots-clés séparés par des
    # virgules, modifiable sans toucher au code. Liste de départ donnée par l'utilisateur.
    APPELS_OFFRES_MOTS_CLES: str = (
        "respirateur,pousse-seringue,échographe,défibrillateur,moniteur,oxygénothérapie"
    )
    APPELS_OFFRES_DELAI_SECONDES: float = 2.0
    APPELS_OFFRES_SCAN_HEURE: int = 6  # heure locale du job planifié quotidien (0-23)

    @property
    def appels_offres_mots_cles_list(self) -> list[str]:
        return [m.strip() for m in self.APPELS_OFFRES_MOTS_CLES.split(",") if m.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
