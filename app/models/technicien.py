import enum
from datetime import datetime

from sqlalchemy import Boolean, Enum as SQLEnum, Float, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db_types import UTCDateTime
from app.database import Base


class RoleTechnicien(str, enum.Enum):
    ADMIN = "admin"  # Administrateur — gestion du stock (équipements en réparation, pièces détachées) uniquement
    CHEF_EQUIPE = "chef_equipe"
    TECHNICIEN = "technicien"


class StatutTechnicien(str, enum.Enum):
    DISPONIBLE = "disponible"
    EN_INTERVENTION = "en_intervention"
    HORS_LIGNE = "hors_ligne"


class Technicien(Base):
    """Fait aussi office de compte utilisateur (login) — pas de table User séparée."""

    __tablename__ = "techniciens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # ── Authentification ──
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[RoleTechnicien] = mapped_column(
        SQLEnum(RoleTechnicien, values_callable=lambda x: [e.value for e in x], name="role_technicien"),
        default=RoleTechnicien.TECHNICIEN,
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    derniere_connexion: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    # Compte créé par un admin/chef avec mot de passe temporaire généré — jamais mis à jour ici
    # directement, voir services/account_provisioning.py (création + réinitialisation).
    doit_changer_mdp: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # ── Données métier (mockData.js) ──
    nom: Mapped[str] = mapped_column(String(255), nullable=False)
    initiales: Mapped[str] = mapped_column(String(4), nullable=False)
    # Nullable : plus saisis à la création (formulaire réduit à prénom/nom/rôle) — complétés par
    # le titulaire du compte lui-même ensuite (auto-édition de profil, voir techniciens.py).
    specialite: Mapped[str | None] = mapped_column(String(255), nullable=True)
    telephone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    # Photo de profil — upload self-service (voir PATCH /techniciens/me/photo), jamais
    # settable en tant que chaîne brute via le PATCH générique (même principe que
    # Intervention.photo_url).
    photo_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    statut: Mapped[StatutTechnicien] = mapped_column(
        SQLEnum(StatutTechnicien, values_callable=lambda x: [e.value for e in x], name="statut_technicien"),
        default=StatutTechnicien.DISPONIBLE,
        nullable=False,
    )
    heures_ce_mois: Mapped[float] = mapped_column(Float, default=0)
    objectif_heures: Mapped[float] = mapped_column(Float, default=168)
    interventions_ce_mois: Mapped[int] = mapped_column(Integer, default=0)
    note: Mapped[float] = mapped_column(Float, default=0)

    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), server_default=func.now(), onupdate=func.now()
    )

    # ── Relations ──
    # NB: "tache_actuelle" du mock (tâche en cours) n'est pas une colonne : elle sera
    # dérivée à la volée (Intervention où technicien_id=X et statut='en_cours').
    equipements: Mapped[list["Equipement"]] = relationship(back_populates="technicien")
    interventions: Mapped[list["Intervention"]] = relationship(back_populates="technicien")
    plannings: Mapped[list["Planning"]] = relationship(back_populates="technicien")
    formations: Mapped[list["Formation"]] = relationship(back_populates="technicien")
    messages_envoyes: Mapped[list["Message"]] = relationship(back_populates="expediteur")
    conversations: Mapped[list["Conversation"]] = relationship(
        secondary="conversation_participants", back_populates="participants"
    )
