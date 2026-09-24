from datetime import datetime

from pydantic import BaseModel, ConfigDict, model_validator

from app.schemas.equipement import EquipementRead


class InterventionEquipementInput(BaseModel):
    """Une entrée d'équipement à la création d'une intervention. Exactement un des 2 champs
    doit être renseigné — lequel dépend du formulaire utilisé côté frontend (Installation,
    Maintenance...), mais ce n'est pas imposé ici par le `type` de l'intervention : la règle
    est volontairement générique plutôt que couplée à un type précis."""

    equipement_id: str | None = None
    description_libre: str | None = None
    # Optionnel : SN déjà connu à la création (ex. formulaire Installation, texte libre —
    # voir SUIVI_PROJET.md). Pour Maintenance (curatif/préventif), reste vide ici et sera
    # renseigné plus tard par le technicien via PATCH .../equipements/{id}/sn.
    sn_saisi_technicien: str | None = None
    # Catégorie libre (moniteur, défibrillateur, respirateur...), pertinente uniquement pour
    # description_libre — sans effet si equipement_id est renseigné (le type vient alors du
    # catalogue, Equipement.type). Optionnelle, pas de validation croisée avec la source.
    type_equipement: str | None = None

    @model_validator(mode="after")
    def _exactement_une_source(self):
        sources = [self.equipement_id, self.description_libre]
        renseignees = [s for s in sources if s not in (None, "")]
        if len(renseignees) != 1:
            raise ValueError("Exactement un parmi equipement_id, description_libre doit être renseigné par équipement")
        return self


class InterventionEquipementRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    intervention_id: str
    equipement_id: str | None = None
    description_libre: str | None = None
    sn_saisi_technicien: str | None = None
    type_equipement: str | None = None
    created_at: datetime
    equipement: EquipementRead | None = None


class SnTechnicienUpdate(BaseModel):
    sn_saisi_technicien: str
