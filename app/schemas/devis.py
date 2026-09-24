from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.models.devis import StatutDevis


class DevisCreate(BaseModel):
    # Saisi manuellement par l'admin — plus de calcul automatique depuis les pièces
    # (PieceNecessaire est en texte libre pur, sans prix, voir SUIVI_PROJET.md).
    montant_pieces: float = Field(ge=0)
    montant_main_oeuvre: float = Field(ge=0)


class DevisDecision(BaseModel):
    decision: Literal["accepte", "refuse"]
    notes: str | None = None


class DevisRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    intervention_id: str
    montant_pieces: float
    montant_main_oeuvre: float
    montant_total: float
    statut: StatutDevis
    cree_par_id: int
    date_creation: datetime
    date_decision_client: datetime | None = None
    notes: str | None = None
