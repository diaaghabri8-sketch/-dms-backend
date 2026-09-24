from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.schemas.technicien import TechnicienBrief


class ConversationBase(BaseModel):
    nom: str | None = None
    is_group: bool = False


class ConversationCreate(ConversationBase):
    participant_ids: list[int]


class ConversationUpdate(BaseModel):
    nom: str | None = None
    is_group: bool | None = None


class ConversationRead(ConversationBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    participants: list[TechnicienBrief]
    created_at: datetime
    updated_at: datetime
