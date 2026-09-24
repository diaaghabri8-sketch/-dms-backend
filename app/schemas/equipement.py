from datetime import date, datetime

from pydantic import BaseModel, ConfigDict

from app.models.equipement import NiveauAlerte, StatutEquipement


class EquipementBase(BaseModel):
    nom: str
    type: str
    marque: str
    localisation: str
    statut: StatutEquipement = StatutEquipement.OPERATIONNEL
    niveau_alerte: NiveauAlerte = NiveauAlerte.OK
    derniere_maintenance: date | None = None
    prochaine_maintenance: date | None = None
    description: str | None = None
    technicien_id: int | None = None


class EquipementCreate(EquipementBase):
    id: str


class EquipementUpdate(BaseModel):
    nom: str | None = None
    type: str | None = None
    marque: str | None = None
    localisation: str | None = None
    statut: StatutEquipement | None = None
    niveau_alerte: NiveauAlerte | None = None
    derniere_maintenance: date | None = None
    prochaine_maintenance: date | None = None
    description: str | None = None
    technicien_id: int | None = None


class EquipementRead(EquipementBase):
    model_config = ConfigDict(from_attributes=True)

    id: str
    created_at: datetime
    updated_at: datetime
