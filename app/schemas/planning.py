from datetime import date, datetime

from pydantic import BaseModel, ConfigDict

from app.models.intervention import TypeIntervention
from app.models.planning import FrequencePlanning, StatutPlanning


class PlanningBase(BaseModel):
    equipement_id: str
    technicien_id: int | None = None
    type_intervention: TypeIntervention = TypeIntervention.PREVENTIF
    frequence: FrequencePlanning
    date_derniere: date | None = None
    date_prochaine: date
    statut: StatutPlanning = StatutPlanning.A_VENIR
    intervention_id: str | None = None


class PlanningCreate(PlanningBase):
    pass


class PlanningUpdate(BaseModel):
    equipement_id: str | None = None
    technicien_id: int | None = None
    type_intervention: TypeIntervention | None = None
    frequence: FrequencePlanning | None = None
    date_derniere: date | None = None
    date_prochaine: date | None = None
    statut: StatutPlanning | None = None
    intervention_id: str | None = None


class PlanningRead(PlanningBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime
