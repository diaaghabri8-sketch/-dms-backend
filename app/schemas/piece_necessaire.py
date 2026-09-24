from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class PieceNecessaireItem(BaseModel):
    description_libre: str = Field(min_length=1)
    quantite_necessaire: int = Field(default=1, ge=1)
    # Optionnel : à quel équipement de l'intervention cette pièce se rapporte, quand
    # l'intervention en concerne plusieurs (voir InterventionEquipement). Validé dans
    # l'endpoint (doit appartenir à la même intervention), pas au niveau du schéma.
    intervention_equipement_id: int | None = None


class PiecesNecessairesCreate(BaseModel):
    # Liste vide acceptée : un technicien peut n'avoir besoin d'aucune pièce (réparation
    # main d'œuvre seule) — l'appel avec `pieces: []` fait quand même avancer le workflow
    # vers devis_en_preparation, sans créer de ligne PieceNecessaire.
    pieces: list[PieceNecessaireItem] = Field(default_factory=list)


class PieceNecessaireRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    intervention_id: str
    intervention_equipement_id: int | None = None
    description_libre: str
    quantite_necessaire: int
    ajoute_par_id: int
    date_ajout: datetime
