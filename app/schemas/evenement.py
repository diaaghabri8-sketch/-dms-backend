from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.evenement import TypeEvenement


class EvenementBase(BaseModel):
    message: str
    type: TypeEvenement


class EvenementCreate(EvenementBase):
    date_heure: datetime | None = None


class EvenementUpdate(BaseModel):
    message: str | None = None
    type: TypeEvenement | None = None


class EvenementRead(EvenementBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    date_heure: datetime
    created_at: datetime
