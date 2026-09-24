from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.intervention_document import TypeDocument


class InterventionDocumentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    intervention_id: str
    type_document: TypeDocument
    chemin_pdf: str
    genere_le: datetime
    genere_par_id: int
