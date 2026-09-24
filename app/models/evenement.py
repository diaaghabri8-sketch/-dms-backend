import enum
from datetime import datetime

from sqlalchemy import Enum as SQLEnum, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db_types import UTCDateTime
from app.database import Base


class TypeEvenement(str, enum.Enum):
    ALERTE = "alerte"
    RAPPORT = "rapport"
    PLANIF = "planif"
    OK = "ok"
    STOCK = "stock"


class Evenement(Base):
    """Fil d'activité récente (source: activite_recente[] dans mockData.js)."""

    __tablename__ = "evenements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    date_heure: Mapped[datetime] = mapped_column(UTCDateTime(), server_default=func.now(), nullable=False)
    message: Mapped[str] = mapped_column(String(500), nullable=False)
    type: Mapped[TypeEvenement] = mapped_column(
        SQLEnum(TypeEvenement, values_callable=lambda x: [e.value for e in x], name="type_evenement"),
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), server_default=func.now())
