from datetime import date, datetime

from pydantic import BaseModel, ConfigDict

from app.models.equipement_reparation import StatutReparation


class EquipementAttenteReparationBase(BaseModel):
    numero_serie: str
    nom: str
    marque: str
    type_equipement: str
    etablissement_origine: str
    date_reception: date
    statut: StatutReparation = StatutReparation.EN_ATTENTE_DIAGNOSTIC
    description_panne: str | None = None
    technicien_assigne_id: int | None = None
    date_retour_prevue: date | None = None
    intervention_equipement_id: int | None = None


class EquipementAttenteReparationCreate(EquipementAttenteReparationBase):
    pass


class EquipementAttenteReparationUpdate(BaseModel):
    numero_serie: str | None = None
    nom: str | None = None
    marque: str | None = None
    type_equipement: str | None = None
    etablissement_origine: str | None = None
    date_reception: date | None = None
    statut: StatutReparation | None = None
    description_panne: str | None = None
    technicien_assigne_id: int | None = None
    date_retour_prevue: date | None = None
    intervention_equipement_id: int | None = None


class EquipementAttenteReparationRead(EquipementAttenteReparationBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    restitution_intervention_id: str | None = None
    created_at: datetime
    updated_at: datetime


class EquipementARendreRead(BaseModel):
    """Fiche 'repare' sans restitution en cours, enrichie des infos de la maintenance d'origine
    (établissement/contact/technicien) — alimente l'écran admin/chef 'Équipements à rendre'.
    Construite à la main dans le router (pas from_attributes) : agrège des champs venant de
    plusieurs tables via la chaîne EquipementAttenteReparation -> InterventionEquipement ->
    Intervention, qui peut être partiellement rompue (intervention d'origine supprimée)."""

    id: int
    numero_serie: str
    nom: str
    marque: str
    type_equipement: str
    etablissement_origine: str
    description_panne: str | None = None
    date_reception: date
    nom_contact: str | None = None
    technicien_origine_id: int | None = None
    technicien_origine_nom: str | None = None


class RestitutionCreate(BaseModel):
    technicien_id: int


class EquipementRenduRead(BaseModel):
    """Fiche 'retourne_client' issue du workflow de restitution (restitution_intervention_id
    renseigné — les fiches basculées à la main via le badge sans passer par ce workflow n'ont
    pas de technicien/PDF à afficher ici, donc hors périmètre de cet onglet), enrichie du
    technicien qui a effectué la restitution — alimente l'onglet 'Rendus' de l'écran admin/chef
    'Équipements à rendre'. Le PDF n'est pas embarqué ici : le frontend réutilise
    GET /interventions/{id}/documents comme ailleurs dans l'app, via restitution_intervention_id."""

    id: int
    numero_serie: str
    nom: str
    marque: str
    type_equipement: str
    etablissement_origine: str
    restitution_intervention_id: str
    technicien_restitution_id: int
    technicien_restitution_nom: str
