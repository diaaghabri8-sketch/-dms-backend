from datetime import datetime

from pydantic import BaseModel, ConfigDict


class MessageBase(BaseModel):
    contenu: str


class MessageCreate(MessageBase):
    conversation_id: int


class MessageUpdate(BaseModel):
    lu_le: datetime | None = None


class MessageRead(MessageBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    conversation_id: int
    expediteur_id: int
    envoye_le: datetime
    lu_le: datetime | None
    created_at: datetime
