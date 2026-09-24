import enum
from datetime import datetime

from sqlalchemy import Enum as SQLEnum, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db_types import UTCDateTime
from app.database import Base


class TypeNotification(str, enum.Enum):
    INTERVENTION_ASSIGNEE = "intervention_assignee"
    DEVIS_ACCEPTE = "devis_accepte"
    DEVIS_REFUSE = "devis_refuse"
    PRET_POUR_DEVIS = "pret_pour_devis"
    INTERVENTION_TERMINEE = "intervention_terminee"
    INTERVENTION_REPORTEE = "intervention_reportee"
    APPEL_OFFRE_DETECTE = "appel_offre_detecte"


class Notification(Base):
    """Notification ciblée à un destinataire précis (cloche) — distinct d'`Evenement`, un fil
    global sans destinataire jamais alimenté automatiquement (voir SUIVI_PROJET.md)."""

    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    destinataire_id: Mapped[int] = mapped_column(ForeignKey("techniciens.id", ondelete="CASCADE"), nullable=False)
    type: Mapped[TypeNotification] = mapped_column(
        SQLEnum(TypeNotification, values_callable=lambda x: [e.value for e in x], name="type_notification"),
        nullable=False,
    )
    message: Mapped[str] = mapped_column(String(500), nullable=False)
    intervention_id: Mapped[str | None] = mapped_column(
        ForeignKey("interventions.id", ondelete="CASCADE"), nullable=True
    )
    # Même convention que Message.lu_le (horodatage plutôt que simple booléen).
    lu_le: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)

    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), server_default=func.now())

    destinataire: Mapped["Technicien"] = relationship()
    intervention: Mapped["Intervention | None"] = relationship()
