from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.notification import TypeNotification


class NotificationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    type: TypeNotification
    message: str
    intervention_id: str | None
    lu_le: datetime | None
    created_at: datetime
