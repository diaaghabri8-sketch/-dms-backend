import enum
from datetime import date, datetime

from sqlalchemy import Date, Enum as SQLEnum, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db_types import UTCDateTime
from app.database import Base


class StatutFormation(str, enum.Enum):
    VALIDE = "valide"
    EXPIREE = "expiree"
    A_RENOUVELER = "a_renouveler"


class Formation(Base):
    """Certification / qualification obtenue par un technicien (distinct du type d'intervention 'Formation')."""

    __tablename__ = "formations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    technicien_id: Mapped[int] = mapped_column(ForeignKey("techniciens.id"), nullable=False)

    intitule: Mapped[str] = mapped_column(String(255), nullable=False)
    organisme: Mapped[str | None] = mapped_column(String(255), nullable=True)
    equipement_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    date_obtention: Mapped[date] = mapped_column(Date, nullable=False)
    date_expiration: Mapped[date | None] = mapped_column(Date, nullable=True)
    statut: Mapped[StatutFormation] = mapped_column(
        SQLEnum(StatutFormation, values_callable=lambda x: [e.value for e in x], name="statut_formation"),
        default=StatutFormation.VALIDE,
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), server_default=func.now(), onupdate=func.now()
    )

    technicien: Mapped["Technicien"] = relationship(back_populates="formations")
