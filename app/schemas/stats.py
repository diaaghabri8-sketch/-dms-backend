from pydantic import BaseModel


class InterventionsAujourdHui(BaseModel):
    preventives: int
    curatives: int
    total: int


class DashboardStats(BaseModel):
    techniciens_actifs: int
    techniciens_total: int
    disponibilite_parc: float
    equipements_total: int
    equipements_operationnels: int
    interventions_aujourd_hui: InterventionsAujourdHui
    mttr_heures: float
    mttr_delta_min: float
    disponibilite_delta: float
