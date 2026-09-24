from datetime import datetime

from sqlalchemy import ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db_types import UTCDateTime
from app.database import Base


class PieceNecessaire(Base):
    """Pièce de rechange identifiée par le technicien comme nécessaire à la réparation
    d'une intervention — sert de base au devis (étape 5 du workflow). Texte libre pur (même
    pattern que les équipements en texte libre) : aucun lien catalogue (le catalogue
    `PieceDetachee` a été supprimé, plus utilisé nulle part — voir SUIVI_PROJET.md)."""

    __tablename__ = "pieces_necessaires"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    intervention_id: Mapped[str] = mapped_column(ForeignKey("interventions.id", ondelete="CASCADE"), nullable=False)
    # Optionnel : précise à quel équipement de l'intervention cette pièce se rapporte, quand
    # l'intervention en concerne plusieurs (voir InterventionEquipement) — reste vide si un
    # seul équipement, ou si non pertinent/non précisé par le technicien.
    intervention_equipement_id: Mapped[int | None] = mapped_column(
        ForeignKey("intervention_equipements.id", ondelete="SET NULL"), nullable=True
    )
    description_libre: Mapped[str] = mapped_column(String(255), nullable=False)
    quantite_necessaire: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    ajoute_par_id: Mapped[int] = mapped_column(ForeignKey("techniciens.id"), nullable=False)
    date_ajout: Mapped[datetime] = mapped_column(UTCDateTime(), server_default=func.now())

    intervention: Mapped["Intervention"] = relationship(back_populates="pieces_necessaires")
    intervention_equipement: Mapped["InterventionEquipement | None"] = relationship()
    ajoute_par: Mapped["Technicien"] = relationship()
