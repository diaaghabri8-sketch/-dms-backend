from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.intervention import LieuReparation, StatutIntervention, StatutWorkflow, TypeIntervention
from app.schemas.intervention_equipement import InterventionEquipementInput, InterventionEquipementRead


class InterventionBase(BaseModel):
    date_heure: datetime
    lieu: str
    type: TypeIntervention
    statut: StatutIntervention = StatutIntervention.PLANIFIE
    duree_estimee: int | None = None
    duree_reelle: int | None = None
    technicien_id: int
    nom_contact: str | None = None
    nom_etablissement: str | None = None


class InterventionCreate(InterventionBase):
    """Pas de champ `id` : généré automatiquement côté serveur (voir
    `interventions.py::_generate_intervention_id`) — jamais saisi par l'utilisateur.

    `equipements` remplace l'ancien `equipement_id` unique : une intervention concerne
    désormais un ou plusieurs équipements (voir InterventionEquipement)."""

    equipements: list[InterventionEquipementInput] = Field(min_length=1)


class InterventionUpdate(BaseModel):
    date_heure: datetime | None = None
    lieu: str | None = None
    type: TypeIntervention | None = None
    statut: StatutIntervention | None = None
    duree_estimee: int | None = None
    duree_reelle: int | None = None
    technicien_id: int | None = None
    nom_contact: str | None = None
    nom_etablissement: str | None = None


class InterventionRead(InterventionBase):
    model_config = ConfigDict(from_attributes=True)

    id: str
    photo_url: str | None = None
    lieu_reparation: LieuReparation | None = None
    description_panne: str | None = None
    statut_workflow: StatutWorkflow
    date_diagnostic: datetime | None = None
    date_pieces_identifiees: datetime | None = None
    date_travail_demarre: datetime | None = None
    date_terminee: datetime | None = None
    created_at: datetime
    updated_at: datetime
    equipements: list[InterventionEquipementRead] = []


# ── Requêtes du workflow appel → diagnostic → devis → réparation ──


class LieuReparationUpdate(BaseModel):
    lieu_reparation: LieuReparation


class DiagnosticUpdate(BaseModel):
    description_panne: str


# ── Parcours simplifié installation/formation (pas de diagnostic/pièces/devis) ──


class ReportIntervention(BaseModel):
    nouvelle_date_heure: datetime
