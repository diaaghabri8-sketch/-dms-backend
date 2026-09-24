from datetime import date, datetime

from pydantic import BaseModel, ConfigDict

from app.models.formation import StatutFormation


class FormationBase(BaseModel):
    technicien_id: int
    intitule: str
    organisme: str | None = None
    equipement_type: str | None = None
    date_obtention: date
    date_expiration: date | None = None
    statut: StatutFormation = StatutFormation.VALIDE


class FormationCreate(FormationBase):
    pass


class FormationUpdate(BaseModel):
    technicien_id: int | None = None
    intitule: str | None = None
    organisme: str | None = None
    equipement_type: str | None = None
    date_obtention: date | None = None
    date_expiration: date | None = None
    statut: StatutFormation | None = None


class FormationRead(FormationBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime
