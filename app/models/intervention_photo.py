from datetime import datetime

from sqlalchemy import ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db_types import UTCDateTime
from app.database import Base


class InterventionPhoto(Base):
    """Photo ajoutée par le technicien à tout moment du workflow — usage INTERNE uniquement
    (traçabilité, preuve en cas de litige) : ne doit JAMAIS être incluse dans un PDF généré
    (diagnostic/devis/rapport_final/bon_restitution, voir app/services/pdf_workflow.py, qui
    n'importe volontairement pas ce modèle). Distinct de `Intervention.photo_url` (photo de
    couverture unique, elle-même incluse dans le rapport final remis au client — mécanisme
    préexistant, non concerné par ce module)."""

    __tablename__ = "intervention_photos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    intervention_id: Mapped[str] = mapped_column(ForeignKey("interventions.id", ondelete="CASCADE"), nullable=False)
    chemin_photo: Mapped[str] = mapped_column(String(500), nullable=False)
    ajoutee_par_id: Mapped[int] = mapped_column(ForeignKey("techniciens.id"), nullable=False)
    ajoutee_le: Mapped[datetime] = mapped_column(UTCDateTime(), server_default=func.now())

    intervention: Mapped["Intervention"] = relationship(back_populates="photos")
    ajoutee_par: Mapped["Technicien"] = relationship()
