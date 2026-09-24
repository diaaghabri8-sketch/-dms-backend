import enum
from datetime import date, datetime

from sqlalchemy import Date, Enum as SQLEnum, ForeignKey, Integer, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db_types import UTCDateTime
from app.database import Base
from app.models.intervention import TypeIntervention


class FrequencePlanning(str, enum.Enum):
    MENSUELLE = "mensuelle"
    TRIMESTRIELLE = "trimestrielle"
    SEMESTRIELLE = "semestrielle"
    ANNUELLE = "annuelle"


class StatutPlanning(str, enum.Enum):
    A_JOUR = "a_jour"
    A_VENIR = "a_venir"
    RETARD = "retard"


class Planning(Base):
    """Calendrier de maintenance récurrente d'un équipement (distinct des interventions ponctuelles)."""

    __tablename__ = "plannings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    equipement_id: Mapped[str] = mapped_column(ForeignKey("equipements.id"), nullable=False)
    technicien_id: Mapped[int | None] = mapped_column(ForeignKey("techniciens.id"), nullable=True)

    type_intervention: Mapped[TypeIntervention] = mapped_column(
        SQLEnum(TypeIntervention, values_callable=lambda x: [e.value for e in x], name="type_intervention"),
        default=TypeIntervention.PREVENTIF,
        nullable=False,
    )
    frequence: Mapped[FrequencePlanning] = mapped_column(
        SQLEnum(FrequencePlanning, values_callable=lambda x: [e.value for e in x], name="frequence_planning"),
        nullable=False,
    )
    date_derniere: Mapped[date | None] = mapped_column(Date, nullable=True)
    date_prochaine: Mapped[date] = mapped_column(Date, nullable=False)
    statut: Mapped[StatutPlanning] = mapped_column(
        SQLEnum(StatutPlanning, values_callable=lambda x: [e.value for e in x], name="statut_planning"),
        default=StatutPlanning.A_VENIR,
        nullable=False,
    )

    # Intervention concrète générée pour la prochaine échéance de ce planning
    intervention_id: Mapped[str | None] = mapped_column(ForeignKey("interventions.id"), nullable=True)

    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), server_default=func.now(), onupdate=func.now()
    )

    equipement: Mapped["Equipement"] = relationship(back_populates="plannings")
    technicien: Mapped["Technicien | None"] = relationship(back_populates="plannings")
    intervention: Mapped["Intervention | None"] = relationship(back_populates="planning")
