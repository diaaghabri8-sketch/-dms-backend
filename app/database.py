from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import settings

# `check_same_thread=False` requis pour SQLite uniquement : une connexion sqlite3 par défaut ne
# peut être réutilisée que par le thread qui l'a ouverte, alors que le pool SQLAlchemy peut la
# faire circuler entre les threads du threadpool d'exécution FastAPI. Sans objet sur Postgres
# (connexions réseau, pas de restriction de thread), voir SUIVI_PROJET.md.
_connect_args = {"check_same_thread": False} if settings.DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True, connect_args=_connect_args)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
