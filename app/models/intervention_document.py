import enum
from datetime import datetime

from sqlalchemy import Enum as SQLEnum, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db_types import UTCDateTime
from app.database import Base


class TypeDocument(str, enum.Enum):
    DIAGNOSTIC = "diagnostic"
    DEVIS = "devis"
    RAPPORT_FINAL = "rapport_final"
    BON_RESTITUTION = "bon_restitution"


class InterventionDocument(Base):
    """PDF justificatif rattaché à une intervention à une étape clé du workflow (diagnostic,
    devis, rapport final, bon de restitution) — voir app/services/pdf_workflow.py pour la
    génération de chacun."""

    __tablename__ = "intervention_documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    intervention_id: Mapped[str] = mapped_column(ForeignKey("interventions.id", ondelete="CASCADE"), nullable=False)
    type_document: Mapped[TypeDocument] = mapped_column(
        SQLEnum(TypeDocument, values_callable=lambda x: [e.value for e in x], name="type_document"),
        nullable=False,
    )
    chemin_pdf: Mapped[str] = mapped_column(String(500), nullable=False)
    genere_le: Mapped[datetime] = mapped_column(UTCDateTime(), server_default=func.now())
    genere_par_id: Mapped[int] = mapped_column(ForeignKey("techniciens.id"), nullable=False)

    intervention: Mapped["Intervention"] = relationship(back_populates="documents")
    genere_par: Mapped["Technicien"] = relationship()
