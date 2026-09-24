from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models.technicien import RoleTechnicien, StatutTechnicien
from app.models.intervention import TypeIntervention


class TacheActuelle(BaseModel):
    """Tâche en cours d'un technicien — dérivée à la volée (Intervention en_cours), pas stockée."""

    equipement: str
    lieu: str
    debut: datetime
    type: TypeIntervention


class TechnicienBase(BaseModel):
    nom: str
    initiales: str = Field(max_length=4)
    # Nullable depuis la refonte "gestion des comptes" (2026-09-22) : plus saisis à la création,
    # complétés par le titulaire du compte ensuite (voir techniciens.py, auto-édition de profil).
    specialite: str | None = None
    telephone: str | None = None
    statut: StatutTechnicien = StatutTechnicien.DISPONIBLE
    heures_ce_mois: float = 0
    objectif_heures: float = 168
    interventions_ce_mois: int = 0
    note: float = 0


class TechnicienCreate(BaseModel):
    """Création par un admin/chef uniquement (pas d'auto-inscription) — email et mot de passe
    ne sont jamais fournis par l'appelant, voir services/account_provisioning.py."""

    prenom: str = Field(min_length=1)
    nom: str = Field(min_length=1, description="Nom de famille — combiné avec prenom pour Technicien.nom")
    role: RoleTechnicien = RoleTechnicien.TECHNICIEN
    specialite: str | None = None


class TechnicienUpdate(BaseModel):
    nom: str | None = None
    initiales: str | None = Field(default=None, max_length=4)
    specialite: str | None = None
    telephone: str | None = None
    statut: StatutTechnicien | None = None
    heures_ce_mois: float | None = None
    objectif_heures: float | None = None
    interventions_ce_mois: int | None = None
    note: float | None = None
    role: RoleTechnicien | None = None
    is_active: bool | None = None
    # Pas de champ `password`/`email` ici — changement de mot de passe centralisé sur
    # POST /techniciens/{id}/reset-password (génère un nouveau mot de passe temporaire, affiché
    # une fois côté web), jamais en clair via ce PATCH générique ; l'email est figé après
    # création (convention prenom.nom@domaine).


class TechnicienRead(TechnicienBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    role: RoleTechnicien
    is_active: bool
    doit_changer_mdp: bool
    photo_url: str | None = None
    derniere_connexion: datetime | None
    tache_actuelle: TacheActuelle | None = None
    created_at: datetime
    updated_at: datetime


class TechnicienCreateResponse(BaseModel):
    """Réponse de création/réinitialisation — `temporary_password` n'est renvoyé qu'une fois ici,
    jamais relisible ensuite (seul le hash est stocké). Aucun envoi automatique : c'est à
    l'admin/chef de transmettre ces identifiants lui-même (voir TechnicianPanel.jsx)."""

    technicien: TechnicienRead
    temporary_password: str


class TechnicienBrief(BaseModel):
    """Référence légère utilisée dans les réponses d'autres entités (ex: participants d'une conversation)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    nom: str
    initiales: str
