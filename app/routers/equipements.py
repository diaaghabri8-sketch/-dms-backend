from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, require_chef
from app.database import get_db
from app.models.equipement import Equipement
from app.models.equipement_reparation import EquipementAttenteReparation
from app.models.intervention import Intervention
from app.models.intervention_equipement import InterventionEquipement
from app.models.technicien import Technicien
from app.schemas.equipement import EquipementCreate, EquipementRead, EquipementUpdate
from app.schemas.intervention import InterventionRead

router = APIRouter(prefix="/equipements", tags=["equipements"], dependencies=[Depends(get_current_user)])

# Liste canonique suggérée en plus des valeurs déjà utilisées (voir GET /types ci-dessous) —
# mêmes libellés que les clés de EQUIP_ICON côté frontend (ui.jsx), pour rester cohérent avec
# les icônes déjà associées. Catégorie libre, pas un enum strict : une saisie hors liste reste
# acceptée partout, ceci ne sert qu'à l'autocomplétion.
TYPES_EQUIPEMENT_SUGGERES = [
    "Moniteur de surveillance",
    "Défibrillateur",
    "Pousse-seringue",
    "Respirateur",
    "Respirateur Anesthésie",
    "Échographe",
]


@router.get("", response_model=list[EquipementRead])
def list_equipements(db: Session = Depends(get_db)) -> list[Equipement]:
    return db.query(Equipement).order_by(Equipement.id).all()


# Doit être déclaré AVANT `/{equipement_id}` : sinon FastAPI/Starlette matche ce chemin
# littéral "historique" contre le paramètre `equipement_id` (str) de la route suivante en
# premier (ordre d'enregistrement des routes), et cet endpoint ne serait jamais atteint.
@router.get("/historique", response_model=list[InterventionRead])
def historique_equipement(
    sn: str = Query(..., min_length=1),
    db: Session = Depends(get_db),
) -> list[Intervention]:
    """Recherche (partielle, insensible à la casse) l'historique complet des interventions
    liées à un numéro de série — sur `InterventionEquipement.sn_saisi_technicien` (texte
    libre, seule source de SN restante depuis la suppression du catalogue vente
    `EquipementNeufAVendre`, voir SUIVI_PROJET.md). Le parc DMS interne (`Equipement`, source
    `equipement_id`) n'a pas de numéro de série et n'est donc jamais concerné par cette
    recherche.

    Ouvert à tout utilisateur authentifié (pas juste admin/chef comme le reste de ce module) :
    réutilisé par la détection automatique "équipement déjà connu" à la saisie du SN
    (DiagnosticStep côté technicien, InstallationForm côté chef) — voir SUIVI_PROJET.md. L'écran
    de recherche manuelle "Historique équipement" reste lui réservé à admin/chef côté frontend
    (menu), cette ouverture ne change que l'accès à l'endpoint lui-même."""
    pattern = f"%{sn}%"
    return (
        db.query(Intervention)
        .join(InterventionEquipement, InterventionEquipement.intervention_id == Intervention.id)
        .filter(InterventionEquipement.sn_saisi_technicien.ilike(pattern))
        .distinct()
        .order_by(Intervention.date_heure.desc())
        .all()
    )


# Même règle de routage que /historique ci-dessus : déclaré avant /{equipement_id}.
@router.get("/types", response_model=list[str])
def types_equipement_utilises(db: Session = Depends(get_db)) -> list[str]:
    """Types déjà utilisés sur les 3 entités qui portent une catégorie d'équipement (parc
    générique, Parc équipements, équipements texte libre d'intervention), unis à une petite
    liste suggérée — alimente l'autocomplétion des formulaires de saisie. Catégorie libre :
    ceci ne fait qu'aider la saisie, aucune valeur n'est imposée."""
    types = set(TYPES_EQUIPEMENT_SUGGERES)
    for (valeur,) in db.query(Equipement.type).distinct():
        if valeur:
            types.add(valeur)
    for (valeur,) in db.query(EquipementAttenteReparation.type_equipement).distinct():
        if valeur:
            types.add(valeur)
    for (valeur,) in db.query(InterventionEquipement.type_equipement).distinct():
        if valeur:
            types.add(valeur)
    return sorted(types)


@router.get("/{equipement_id}", response_model=EquipementRead)
def get_equipement(equipement_id: str, db: Session = Depends(get_db)) -> Equipement:
    equipement = db.get(Equipement, equipement_id)
    if equipement is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Équipement introuvable")
    return equipement


@router.post("", response_model=EquipementRead, status_code=status.HTTP_201_CREATED)
def create_equipement(
    payload: EquipementCreate,
    db: Session = Depends(get_db),
    _: Technicien = Depends(require_chef),
) -> Equipement:
    if db.get(Equipement, payload.id) is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Un équipement avec cet id existe déjà")
    equipement = Equipement(**payload.model_dump())
    db.add(equipement)
    db.commit()
    db.refresh(equipement)
    return equipement


@router.patch("/{equipement_id}", response_model=EquipementRead)
def update_equipement(
    equipement_id: str,
    payload: EquipementUpdate,
    db: Session = Depends(get_db),
    _: Technicien = Depends(require_chef),
) -> Equipement:
    equipement = db.get(Equipement, equipement_id)
    if equipement is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Équipement introuvable")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(equipement, field, value)
    db.commit()
    db.refresh(equipement)
    return equipement


@router.delete("/{equipement_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_equipement(
    equipement_id: str,
    db: Session = Depends(get_db),
    _: Technicien = Depends(require_chef),
) -> None:
    equipement = db.get(Equipement, equipement_id)
    if equipement is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Équipement introuvable")
    db.delete(equipement)
    db.commit()
