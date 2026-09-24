import enum
from datetime import date, datetime

from sqlalchemy import Date, Enum as SQLEnum, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db_types import UTCDateTime
from app.database import Base


class StatutReparation(str, enum.Enum):
    EN_ATTENTE_DIAGNOSTIC = "en_attente_diagnostic"
    EN_REPARATION = "en_reparation"
    EN_ATTENTE_PIECE = "en_attente_piece"
    REPARE = "repare"
    RETOURNE_CLIENT = "retourne_client"


class EquipementAttenteReparation(Base):
    """Équipement d'un établissement client envoyé en réparation — module réservé au rôle administrateur."""

    __tablename__ = "equipements_attente_reparation"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    numero_serie: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    nom: Mapped[str] = mapped_column(String(255), nullable=False)
    marque: Mapped[str] = mapped_column(String(150), nullable=False)
    type_equipement: Mapped[str] = mapped_column(String(150), nullable=False)
    etablissement_origine: Mapped[str] = mapped_column(String(255), nullable=False)
    date_reception: Mapped[date] = mapped_column(Date, nullable=False)
    statut: Mapped[StatutReparation] = mapped_column(
        SQLEnum(StatutReparation, values_callable=lambda x: [e.value for e in x], name="statut_reparation"),
        default=StatutReparation.EN_ATTENTE_DIAGNOSTIC,
        nullable=False,
    )
    description_panne: Mapped[str | None] = mapped_column(Text, nullable=True)

    technicien_assigne_id: Mapped[int | None] = mapped_column(
        ForeignKey("techniciens.id", ondelete="SET NULL"), nullable=True
    )
    date_retour_prevue: Mapped[date | None] = mapped_column(Date, nullable=True)

    # Lien vers l'équipement d'intervention d'origine — renseigné automatiquement quand cette
    # fiche est créée par la synchronisation depuis un diagnostic "atelier" (voir
    # app/services/parc_sync.py et SUIVI_PROJET.md). Pas de cascade : si l'intervention est
    # supprimée, cette fiche reste (équipement physique toujours réel dans l'atelier) — juste
    # le lien qui disparaît.
    intervention_equipement_id: Mapped[int | None] = mapped_column(
        ForeignKey("intervention_equipements.id", ondelete="SET NULL"), nullable=True
    )

    # Intervention de type "restitution" créée pour rendre cet équipement réparé au client (voir
    # app/services/parc_sync.py, endpoint POST /equipements-reparation/{id}/restitution) — pose
    # tant qu'une restitution est en cours (créée mais pas encore validée), exclut la fiche de
    # "Équipements à rendre". Remis à NULL automatiquement si l'intervention est supprimée (la
    # fiche redevient éligible à une nouvelle restitution), même logique que
    # intervention_equipement_id ci-dessus.
    restitution_intervention_id: Mapped[str | None] = mapped_column(
        ForeignKey("interventions.id", ondelete="SET NULL"), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), server_default=func.now(), onupdate=func.now()
    )

    technicien_assigne: Mapped["Technicien | None"] = relationship()
    intervention_equipement: Mapped["InterventionEquipement | None"] = relationship()
    restitution_intervention: Mapped["Intervention | None"] = relationship()
