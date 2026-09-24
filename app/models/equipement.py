import enum
from datetime import date, datetime

from sqlalchemy import Date, Enum as SQLEnum, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db_types import UTCDateTime
from app.database import Base


class StatutEquipement(str, enum.Enum):
    OPERATIONNEL = "operationnel"
    EN_MAINTENANCE = "en_maintenance"
    EN_PANNE = "en_panne"
    MAINTENANCE_RETARD = "maintenance_retard"


class NiveauAlerte(str, enum.Enum):
    OK = "ok"
    WARNING = "warning"
    CRITIQUE = "critique"


class Equipement(Base):
    __tablename__ = "equipements"

    # Format métier "EQ001" conservé tel quel comme clé primaire (comme dans mockData.js)
    id: Mapped[str] = mapped_column(String(20), primary_key=True)

    nom: Mapped[str] = mapped_column(String(255), nullable=False)
    type: Mapped[str] = mapped_column(String(100), nullable=False)
    marque: Mapped[str] = mapped_column(String(150), nullable=False)
    localisation: Mapped[str] = mapped_column(String(255), nullable=False)
    statut: Mapped[StatutEquipement] = mapped_column(
        SQLEnum(StatutEquipement, values_callable=lambda x: [e.value for e in x], name="statut_equipement"),
        default=StatutEquipement.OPERATIONNEL,
        nullable=False,
    )
    niveau_alerte: Mapped[NiveauAlerte] = mapped_column(
        SQLEnum(NiveauAlerte, values_callable=lambda x: [e.value for e in x], name="niveau_alerte"),
        default=NiveauAlerte.OK,
        nullable=False,
    )
    derniere_maintenance: Mapped[date | None] = mapped_column(Date, nullable=True)
    prochaine_maintenance: Mapped[date | None] = mapped_column(Date, nullable=True)
    description: Mapped[str | None] = mapped_column(String(1000), nullable=True)

    technicien_id: Mapped[int | None] = mapped_column(
        ForeignKey("techniciens.id", ondelete="SET NULL"), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), server_default=func.now(), onupdate=func.now()
    )

    technicien: Mapped["Technicien | None"] = relationship(back_populates="equipements")
    # Plus de relation directe vers Intervention (many-to-many désormais, via
    # InterventionEquipement — voir ce modèle). `equipement.interventions` n'était utilisé
    # nulle part dans le code, retiré plutôt que reciblé sans usage réel.
    plannings: Mapped[list["Planning"]] = relationship(back_populates="equipement")
