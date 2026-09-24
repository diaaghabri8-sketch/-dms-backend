import enum
from datetime import datetime

from sqlalchemy import Enum as SQLEnum, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db_types import UTCDateTime
from app.database import Base


class TypeIntervention(str, enum.Enum):
    CURATIF = "curatif"
    PREVENTIF = "preventif"
    INSTALLATION = "installation"
    FORMATION = "formation"
    # Remise au client d'un équipement réparé (Parc équipements, statut "repare") — parcours
    # simplifié Valider/Reporter comme installation/formation, jamais le workflow diagnostic/
    # devis. Voir app/services/parc_sync.py et SUIVI_PROJET.md.
    RESTITUTION = "restitution"


class StatutIntervention(str, enum.Enum):
    PLANIFIE = "planifie"
    EN_COURS = "en_cours"
    TERMINE = "termine"


class LieuReparation(str, enum.Enum):
    SUR_PLACE = "sur_place"
    ATELIER = "atelier"


class StatutWorkflow(str, enum.Enum):
    """État du workflow métier appel→diagnostic→devis→réparation — distinct de `statut`
    (planifie/en_cours/termine, vue calendrier/disponibilité) : voir SUIVI_PROJET.md pour le
    raisonnement. `appel_recu` est la valeur par défaut de toute intervention, qu'elle utilise
    ou non ce workflow ensuite — c'est un état neutre, pas une action requise."""

    APPEL_RECU = "appel_recu"
    DIAGNOSTIC_EN_COURS = "diagnostic_en_cours"
    DIAGNOSTIC_TERMINE = "diagnostic_termine"
    DEVIS_EN_PREPARATION = "devis_en_preparation"
    DEVIS_ENVOYE = "devis_envoye"
    DEVIS_ACCEPTE = "devis_accepte"
    DEVIS_REFUSE = "devis_refuse"
    TRAVAIL_EN_COURS = "travail_en_cours"
    TERMINE = "termine"
    ANNULEE = "annulee"


class Intervention(Base):
    __tablename__ = "interventions"

    # Format métier "INT001" conservé tel quel comme clé primaire (comme dans mockData.js)
    id: Mapped[str] = mapped_column(String(20), primary_key=True)

    date_heure: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    lieu: Mapped[str] = mapped_column(String(255), nullable=False)
    type: Mapped[TypeIntervention] = mapped_column(
        SQLEnum(TypeIntervention, values_callable=lambda x: [e.value for e in x], name="type_intervention"),
        nullable=False,
    )
    statut: Mapped[StatutIntervention] = mapped_column(
        SQLEnum(StatutIntervention, values_callable=lambda x: [e.value for e in x], name="statut_intervention"),
        default=StatutIntervention.PLANIFIE,
        nullable=False,
    )
    duree_estimee: Mapped[int | None] = mapped_column(Integer, nullable=True)
    duree_reelle: Mapped[int | None] = mapped_column(Integer, nullable=True)
    photo_url: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # ── Workflow appel → diagnostic → devis → réparation (voir StatutWorkflow ci-dessus) ──
    lieu_reparation: Mapped[LieuReparation | None] = mapped_column(
        SQLEnum(LieuReparation, values_callable=lambda x: [e.value for e in x], name="lieu_reparation"),
        nullable=True,
    )
    description_panne: Mapped[str | None] = mapped_column(Text, nullable=True)
    statut_workflow: Mapped[StatutWorkflow] = mapped_column(
        SQLEnum(StatutWorkflow, values_callable=lambda x: [e.value for e in x], name="statut_workflow"),
        default=StatutWorkflow.APPEL_RECU,
        nullable=False,
    )
    # Horodatage de chaque étape franchie, pour l'historique complet (fiche détail chef/admin
    # et rapport final PDF) — "appel reçu" utilise created_at (déjà présent), "devis créé" et
    # "décision client" utilisent Devis.date_creation/date_decision_client (déjà présents) :
    # seules les 4 étapes suivantes n'avaient encore aucune date tracée avant cette Phase 6.
    date_diagnostic: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    date_pieces_identifiees: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    date_travail_demarre: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    date_terminee: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)

    technicien_id: Mapped[int] = mapped_column(ForeignKey("techniciens.id"), nullable=False)

    # ── Contact sur place — formulaires "Installation"/"Maintenance" (voir SUIVI_PROJET.md) ──
    # nom_etablissement n'est peuplé en pratique que pour le type installation, mais reste
    # générique/optionnel plutôt que réservé à un type précis (pas de contrainte artificielle).
    nom_contact: Mapped[str | None] = mapped_column(String(255), nullable=True)
    nom_etablissement: Mapped[str | None] = mapped_column(String(255), nullable=True)

    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), server_default=func.now(), onupdate=func.now()
    )

    technicien: Mapped["Technicien"] = relationship(back_populates="interventions")
    # Reverse d'un Planning éventuel qui a généré cette intervention (FK côté Planning)
    planning: Mapped["Planning | None"] = relationship(back_populates="intervention", uselist=False)
    equipements: Mapped[list["InterventionEquipement"]] = relationship(
        back_populates="intervention", cascade="all, delete-orphan"
    )
    pieces_necessaires: Mapped[list["PieceNecessaire"]] = relationship(
        back_populates="intervention", cascade="all, delete-orphan"
    )
    devis: Mapped[list["Devis"]] = relationship(back_populates="intervention", cascade="all, delete-orphan")
    documents: Mapped[list["InterventionDocument"]] = relationship(
        back_populates="intervention", cascade="all, delete-orphan"
    )
    # Photos internes (traçabilité technicien) — distinct de `photo_url` ci-dessus et de
    # `documents` (PDF) : jamais incluses dans un PDF, voir InterventionPhoto.
    photos: Mapped[list["InterventionPhoto"]] = relationship(
        back_populates="intervention", cascade="all, delete-orphan"
    )
