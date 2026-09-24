import uuid

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.core.config import STORAGE_DIR
from app.core.deps import get_current_user, require_admin_or_chef, require_chef
from app.core.security import hash_password
from app.database import get_db
from app.models.intervention import Intervention, StatutIntervention, StatutWorkflow
from app.models.technicien import RoleTechnicien, Technicien
from app.schemas.technicien import (
    TacheActuelle,
    TechnicienCreate,
    TechnicienCreateResponse,
    TechnicienRead,
    TechnicienUpdate,
)
from app.services.account_provisioning import (
    generate_initiales,
    generate_temp_password,
    generate_unique_email,
)
from app.services.equipement_label import equipements_label

PROFILE_PHOTOS_DIR = STORAGE_DIR / "techniciens"

router = APIRouter(prefix="/techniciens", tags=["techniciens"], dependencies=[Depends(get_current_user)])

# Rôles qu'un chef_equipe peut créer/gérer pour un AUTRE compte que le sien — jamais admin ou
# chef_equipe (voir SUIVI_PROJET.md, "gestion des comptes utilisateurs"). L'admin, lui, n'a
# aucune restriction de rôle cible.
_ROLES_GERABLES_PAR_CHEF = {RoleTechnicien.TECHNICIEN}


def _require_target_role_allowed(actor: Technicien, target_role: RoleTechnicien) -> None:
    if actor.role == RoleTechnicien.CHEF_EQUIPE and target_role not in _ROLES_GERABLES_PAR_CHEF:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Un chef d'équipe ne peut créer ou gérer que des comptes technicien",
        )


def _tache_actuelle_map(db: Session, technicien_ids: list[int]) -> dict[int, TacheActuelle]:
    if not technicien_ids:
        return {}
    # "Active" = engagée dans le workflow (appel_recu inclus — dès la création, jusqu'à
    # travail_en_cours) sans être terminée/annulée — pas seulement `statut == en_cours`, qui ne
    # bascule qu'au démarrage effectif du travail et ratait donc tout le diagnostic/devis.
    # `statut != TERMINE` exclut en plus les interventions closes par l'ancien parcours legacy
    # (et le futur parcours simplifié installation/formation) qui restent à `appel_recu` pour
    # toujours sans jamais être "actives".
    en_cours = (
        db.query(Intervention)
        .filter(
            Intervention.technicien_id.in_(technicien_ids),
            Intervention.statut != StatutIntervention.TERMINE,
            Intervention.statut_workflow.notin_([StatutWorkflow.TERMINE, StatutWorkflow.ANNULEE]),
        )
        .order_by(Intervention.date_heure.desc())
        .all()
    )
    result: dict[int, TacheActuelle] = {}
    for intervention in en_cours:
        # Une seule tâche en cours affichée par technicien (la plus récente).
        if intervention.technicien_id in result:
            continue
        result[intervention.technicien_id] = TacheActuelle(
            equipement=equipements_label(intervention.equipements),
            lieu=intervention.lieu,
            debut=intervention.date_heure,
            type=intervention.type,
        )
    return result


def build_technicien_read(technicien: Technicien, db: Session) -> TechnicienRead:
    data = TechnicienRead.model_validate(technicien)
    data.tache_actuelle = _tache_actuelle_map(db, [technicien.id]).get(technicien.id)
    return data


@router.get("", response_model=list[TechnicienRead])
def list_techniciens(db: Session = Depends(get_db)) -> list[TechnicienRead]:
    techniciens = db.query(Technicien).order_by(Technicien.nom).all()
    taches = _tache_actuelle_map(db, [t.id for t in techniciens])
    results = []
    for technicien in techniciens:
        data = TechnicienRead.model_validate(technicien)
        data.tache_actuelle = taches.get(technicien.id)
        results.append(data)
    return results


@router.get("/{technicien_id}", response_model=TechnicienRead)
def get_technicien(technicien_id: int, db: Session = Depends(get_db)) -> TechnicienRead:
    technicien = db.get(Technicien, technicien_id)
    if technicien is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Technicien introuvable")
    return build_technicien_read(technicien, db)


@router.post("", response_model=TechnicienCreateResponse, status_code=status.HTTP_201_CREATED)
def create_technicien(
    payload: TechnicienCreate,
    db: Session = Depends(get_db),
    current_user: Technicien = Depends(require_admin_or_chef),
) -> TechnicienCreateResponse:
    """Email + mot de passe temporaire générés côté serveur (jamais fournis par l'appelant) —
    voir services/account_provisioning.py. Le compte est actif immédiatement (pas de statut
    "en attente" : c'est l'admin/chef qui décide en créant, voir SUIVI_PROJET.md). Aucun email
    n'est envoyé : les identifiants ne sont affichés qu'une fois côté web, à charge de
    l'admin/chef de les transmettre lui-même (voir SUIVI_PROJET.md)."""
    _require_target_role_allowed(current_user, payload.role)

    email = generate_unique_email(db, payload.prenom, payload.nom)
    temp_password = generate_temp_password()
    nom_complet = f"{payload.prenom.strip()} {payload.nom.strip()}".strip()

    technicien = Technicien(
        email=email,
        hashed_password=hash_password(temp_password),
        role=payload.role,
        nom=nom_complet,
        initiales=generate_initiales(payload.prenom, payload.nom),
        specialite=payload.specialite if payload.role == RoleTechnicien.TECHNICIEN else None,
        doit_changer_mdp=True,
        is_active=True,
    )
    db.add(technicien)
    db.commit()
    db.refresh(technicien)

    return TechnicienCreateResponse(technicien=build_technicien_read(technicien, db), temporary_password=temp_password)


@router.post("/{technicien_id}/reset-password", response_model=TechnicienCreateResponse)
def reset_password(
    technicien_id: int,
    db: Session = Depends(get_db),
    current_user: Technicien = Depends(require_admin_or_chef),
) -> TechnicienCreateResponse:
    """Même logique que la création : nouveau mot de passe temporaire, `doit_changer_mdp` remis
    à True — jamais le mot de passe précédent (hash non réversible). Affiché une fois côté web,
    à transmettre par l'admin/chef lui-même (aucun envoi automatique)."""
    technicien = db.get(Technicien, technicien_id)
    if technicien is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Technicien introuvable")
    _require_target_role_allowed(current_user, technicien.role)

    temp_password = generate_temp_password()
    technicien.hashed_password = hash_password(temp_password)
    technicien.doit_changer_mdp = True
    db.commit()
    db.refresh(technicien)

    return TechnicienCreateResponse(technicien=build_technicien_read(technicien, db), temporary_password=temp_password)


@router.patch("/{technicien_id}", response_model=TechnicienRead)
def update_technicien(
    technicien_id: int,
    payload: TechnicienUpdate,
    db: Session = Depends(get_db),
    current_user: Technicien = Depends(get_current_user),
) -> TechnicienRead:
    technicien = db.get(Technicien, technicien_id)
    if technicien is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Technicien introuvable")

    updates = payload.model_dump(exclude_unset=True)
    is_self_edit = current_user.id == technicien_id
    is_privileged = current_user.role in (RoleTechnicien.ADMIN, RoleTechnicien.CHEF_EQUIPE)

    if is_self_edit and not is_privileged:
        # Auto-édition de son propre profil (tout rôle confondu, pas seulement technicien —
        # voir SUIVI_PROJET.md) : nom/spécialité/téléphone/statut. `photo_url` n'est jamais
        # settable ici (upload-only, voir PATCH /techniciens/me/photo juste en dessous).
        allowed_fields = {"statut", "telephone", "nom", "specialite"}
        if not set(updates).issubset(allowed_fields):
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                "Vous ne pouvez modifier que votre nom, spécialité, téléphone et statut",
            )
    elif not is_self_edit:
        if not is_privileged:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Vous ne pouvez modifier que votre propre profil")
        # Gestion d'un AUTRE compte par un admin/chef — un chef ne peut toucher qu'un compte
        # technicien (ni créer/promouvoir un admin ou chef_equipe), voir _require_target_role_allowed.
        _require_target_role_allowed(current_user, technicien.role)
        if "role" in updates:
            _require_target_role_allowed(current_user, updates["role"])
    # Sinon (self-edit par un admin/chef) : accès complet à ses propres champs gérables, comme
    # avant — aucune restriction de champ supplémentaire nécessaire ici.

    for field, value in updates.items():
        setattr(technicien, field, value)

    db.commit()
    db.refresh(technicien)
    return build_technicien_read(technicien, db)


@router.patch("/me/photo", response_model=TechnicienRead)
async def update_my_photo(
    photo: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: Technicien = Depends(get_current_user),
) -> TechnicienRead:
    """Photo de profil — self-service strict (jamais pour un autre compte, même par le chef) :
    voir SUIVI_PROJET.md pour le choix de scope."""
    PROFILE_PHOTOS_DIR.mkdir(parents=True, exist_ok=True)
    suffix = "".join(c for c in (photo.filename or "") if c in ".-_" or c.isalnum())[-100:]
    filename = f"{current_user.id}_{uuid.uuid4().hex}_{suffix or 'photo.jpg'}"
    destination = PROFILE_PHOTOS_DIR / filename
    destination.write_bytes(await photo.read())
    current_user.photo_url = f"/storage/techniciens/{filename}"

    db.commit()
    db.refresh(current_user)
    return build_technicien_read(current_user, db)


@router.delete("/{technicien_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_technicien(
    technicien_id: int,
    db: Session = Depends(get_db),
    _: Technicien = Depends(require_chef),
) -> None:
    technicien = db.get(Technicien, technicien_id)
    if technicien is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Technicien introuvable")
    db.delete(technicien)
    db.commit()
