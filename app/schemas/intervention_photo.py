from datetime import datetime

from pydantic import BaseModel, ConfigDict


class InterventionPhotoRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    intervention_id: str
    chemin_photo: str
    ajoutee_par_id: int
    ajoutee_le: datetime
