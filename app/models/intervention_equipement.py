from datetime import datetime

from sqlalchemy import ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db_types import UTCDateTime
from app.database import Base


class InterventionEquipement(Base):
    """Équipement concerné par une intervention — une intervention peut en avoir plusieurs.

    Une ligne référence exactement UNE des 2 sources possibles (contrainte applicative,
    validée au niveau du schéma Pydantic — pas de CHECK SQL, cohérent avec le reste du
    projet) selon le formulaire utilisé à la création :
    - `equipement_id` : équipement du parc déjà suivi par DMS (`Equipement`).
    - `description_libre` : texte libre saisi par le chef à la création (Maintenance,
      Installation, Formation — aucune référence catalogue). `sn_saisi_technicien` peut être
      connu dès la création (Installation) ou renseigné plus tard par le technicien, sur
      place, avant son diagnostic (types curatif/préventif — voir DiagnosticStep côté
      frontend).

    Une 3e source, `equipement_vente_id` (catalogue vente `EquipementNeufAVendre`), a existé
    et a été retirée — plus aucun formulaire ne l'écrivait, aucune donnée ne l'utilisait (voir
    SUIVI_PROJET.md).
    """

    __tablename__ = "intervention_equipements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    intervention_id: Mapped[str] = mapped_column(ForeignKey("interventions.id", ondelete="CASCADE"), nullable=False)
    equipement_id: Mapped[str | None] = mapped_column(ForeignKey("equipements.id"), nullable=True)
    description_libre: Mapped[str | None] = mapped_column(String(255), nullable=True)
    sn_saisi_technicien: Mapped[str | None] = mapped_column(String(100), nullable=True)
    # Catégorie libre (moniteur, défibrillateur, respirateur...) — même nom de champ que
    # EquipementAttenteReparation.type_equipement pour rester cohérent entre les 2 entités
    # "texte libre". Optionnel : aucune valeur possible sur les lignes existantes (jamais
    # saisi avant l'ajout de ce champ), pas rendu obligatoire à la création non plus.
    type_equipement: Mapped[str | None] = mapped_column(String(150), nullable=True)

    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), server_default=func.now())

    intervention: Mapped["Intervention"] = relationship(back_populates="equipements")
    equipement: Mapped["Equipement | None"] = relationship()
