import enum
from datetime import datetime

from sqlalchemy import Enum as SQLEnum, Float, ForeignKey, Integer, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db_types import UTCDateTime
from app.database import Base


class StatutDevis(str, enum.Enum):
    BROUILLON = "brouillon"
    ENVOYE = "envoye"
    ACCEPTE = "accepte"
    REFUSE = "refuse"


class Devis(Base):
    """Devis (pièces + main d'œuvre) présenté au client — créé par un administrateur à partir
    des PieceNecessaire identifiées par le technicien (étape 5 du workflow)."""

    __tablename__ = "devis"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    intervention_id: Mapped[str] = mapped_column(ForeignKey("interventions.id", ondelete="CASCADE"), nullable=False)
    montant_pieces: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    montant_main_oeuvre: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    montant_total: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    statut: Mapped[StatutDevis] = mapped_column(
        SQLEnum(StatutDevis, values_callable=lambda x: [e.value for e in x], name="statut_devis"),
        default=StatutDevis.BROUILLON,
        nullable=False,
    )
    cree_par_id: Mapped[int] = mapped_column(ForeignKey("techniciens.id"), nullable=False)
    date_creation: Mapped[datetime] = mapped_column(UTCDateTime(), server_default=func.now())
    date_decision_client: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    intervention: Mapped["Intervention"] = relationship(back_populates="devis")
    cree_par: Mapped["Technicien"] = relationship()
