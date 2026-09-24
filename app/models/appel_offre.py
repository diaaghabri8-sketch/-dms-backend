import enum
from datetime import datetime

from sqlalchemy import Enum as SQLEnum, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db_types import UTCDateTime
from app.database import Base


class StatutAppelOffre(str, enum.Enum):
    NOUVEAU = "nouveau"
    VU = "vu"
    A_EVALUER = "a_evaluer"
    HORS_PERIMETRE = "hors_perimetre"


class AppelOffre(Base):
    """Avis de marché public détecté par la veille automatique (marchespublics.gov.tn, jamais
    TUNEPS — voir SUIVI_PROJET.md). Le statut est géré manuellement par l'admin/chef après
    consultation ; la veille elle-même ne fait jamais que créer de nouvelles lignes en `nouveau`,
    jamais mettre à jour une ligne existante (id_externe = clé de déduplication, voir
    services/marches_publics.py)."""

    __tablename__ = "appels_offres"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    id_externe: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    titre: Mapped[str] = mapped_column(String(1000), nullable=False)
    organisme_acheteur: Mapped[str] = mapped_column(String(500), nullable=False)

    date_publication: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    date_limite_offres: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)

    lien_avis: Mapped[str] = mapped_column(String(500), nullable=False)
    lien_pdf: Mapped[str | None] = mapped_column(String(1000), nullable=True)

    # Mots-clés ayant matché (plusieurs possibles pour un même avis, joints par ", ") — pour
    # traçabilité, voir SUIVI_PROJET.md.
    mot_cle_trouve: Mapped[str] = mapped_column(String(255), nullable=False)

    statut: Mapped[StatutAppelOffre] = mapped_column(
        SQLEnum(StatutAppelOffre, values_callable=lambda x: [e.value for e in x], name="statut_appel_offre"),
        default=StatutAppelOffre.NOUVEAU,
        nullable=False,
    )

    date_detection: Mapped[datetime] = mapped_column(UTCDateTime(), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), server_default=func.now(), onupdate=func.now()
    )
