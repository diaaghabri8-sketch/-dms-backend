import re
import uuid
from datetime import date, datetime, time, timedelta, timezone

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import STORAGE_DIR
from app.core.deps import get_current_user, require_chef
from app.database import get_db
from app.models.equipement import Equipement
from app.models.equipement_reparation import StatutReparation
from app.models.intervention import Intervention, StatutIntervention, StatutWorkflow, TypeIntervention
from app.models.intervention_equipement import InterventionEquipement
from app.models.intervention_photo import InterventionPhoto
from app.models.notification import TypeNotification
from app.models.technicien import RoleTechnicien, StatutTechnicien, Technicien
from app.schemas.intervention import InterventionCreate, InterventionRead
from app.schemas.intervention_photo import InterventionPhotoRead
from app.services.notifications import notifier, notifier_role
from app.services.parc_sync import synchroniser_statut_parc
from app.services.pdf_workflow import generate_rapport_final_pdf

router = APIRouter(prefix="/interventions", tags=["interventions"], dependencies=[Depends(get_current_user)])

PHOTOS_DIR = STORAGE_DIR / "interventions"

_ID_PATTERN = re.compile(r"^INT(\d+)$")


def _generate_intervention_id(db: Session) -> str:
    """Format `INT001`, `INT002`, ... (même convention que les données de démo existantes) —
    calculé à partir du plus grand suffixe numérique déjà utilisé, en ignorant les identifiants
    legacy qui ne suivent pas ce format (ex: anciens ID de test) plutôt que de planter dessus."""
    max_num = 0
    for (existing_id,) in db.query(Intervention.id).all():
        match = _ID_PATTERN.match(existing_id)
        if match:
            max_num = max(max_num, int(match.group(1)))
    return f"INT{max_num + 1:03d}"


@router.get("", response_model=list[InterventionRead])
def list_interventions(
    db: Session = Depends(get_db),
    date_filtre: date | None = Query(None, alias="date"),
    technicien_id: int | None = Query(None),
    statut: StatutIntervention | None = Query(None),
    statut_workflow: StatutWorkflow | None = Query(None),
) -> list[Intervention]:
    query = db.query(Intervention)
    if date_filtre is not None:
        start = datetime.combine(date_filtre, time.min, tzinfo=timezone.utc)
        end = start + timedelta(days=1)
        query = query.filter(Intervention.date_heure >= start, Intervention.date_heure < end)
    if technicien_id is not None:
        query = query.filter(Intervention.technicien_id == technicien_id)
    if statut is not None:
        query = query.filter(Intervention.statut == statut)
    if statut_workflow is not None:
        query = query.filter(Intervention.statut_workflow == statut_workflow)
    return query.order_by(Intervention.date_heure).all()


@router.get("/{intervention_id}", response_model=InterventionRead)
def get_intervention(intervention_id: str, db: Session = Depends(get_db)) -> Intervention:
    intervention = db.get(Intervention, intervention_id)
    if intervention is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Intervention introuvable")
    return intervention


@router.post("", response_model=InterventionRead, status_code=status.HTTP_201_CREATED)
def create_intervention(
    payload: InterventionCreate,
    db: Session = Depends(get_db),
    _: Technicien = Depends(require_chef),
) -> Intervention:
    if db.get(Technicien, payload.technicien_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Technicien introuvable")

    for item in payload.equipements:
        if item.equipement_id is not None and db.get(Equipement, item.equipement_id) is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, f"Équipement {item.equipement_id} introuvable")

    intervention_fields = payload.model_dump(exclude={"equipements"})
    equipements_data = payload.model_dump()["equipements"]

    # Retry en cas de collision (deux créations concurrentes calculant le même prochain
    # numéro) — improbable sur ce volume d'usage mais gratuit à couvrir proprement.
    for _attempt in range(5):
        intervention = Intervention(id=_generate_intervention_id(db), **intervention_fields)
        db.add(intervention)
        try:
            db.flush()  # obtient l'id généré avant de créer les lignes InterventionEquipement
        except IntegrityError:
            db.rollback()
            continue
        for item in equipements_data:
            db.add(InterventionEquipement(intervention_id=intervention.id, **item))
        notifier(
            db, intervention.technicien_id, TypeNotification.INTERVENTION_ASSIGNEE,
            f"Nouvelle intervention {intervention.id} assignée : {intervention.lieu}",
            intervention_id=intervention.id,
        )
        db.commit()
        db.refresh(intervention)
        return intervention

    raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Impossible de générer un identifiant unique")


@router.patch("/{intervention_id}", response_model=InterventionRead)
async def update_intervention(
    intervention_id: str,
    date_heure: datetime | None = Form(None),
    lieu: str | None = Form(None),
    type: TypeIntervention | None = Form(None),
    statut: StatutIntervention | None = Form(None),
    duree_estimee: int | None = Form(None),
    duree_reelle: int | None = Form(None),
    technicien_id: int | None = Form(None),
    nom_contact: str | None = Form(None),
    nom_etablissement: str | None = Form(None),
    photo: UploadFile | None = File(None),
    db: Session = Depends(get_db),
    current_user: Technicien = Depends(get_current_user),
) -> Intervention:
    if current_user.role == RoleTechnicien.ADMIN:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Module réservé au chef d'équipe et aux techniciens")

    intervention = db.get(Intervention, intervention_id)
    if intervention is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Intervention introuvable")

    # Verrou entité close : `statut==TERMINE` couvre à lui seul la clôture du workflow complet
    # (statut_workflow y passe toujours en même temps à TERMINE/ANNULEE) ET celle du parcours
    # simplifié installation/formation/restitution (où statut_workflow reste figé à appel_recu
    # pour toujours par conception) — se fier à statut_workflow seul manquerait ce 2e cas. Aucune
    # exception : ni chef ni technicien ne peut plus rien modifier, y compris `statut` lui-même
    # (empêche de "rouvrir" une intervention déjà close).
    if intervention.statut == StatutIntervention.TERMINE:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Intervention clôturée : plus aucune modification possible.")

    is_chef = current_user.role == RoleTechnicien.CHEF_EQUIPE
    # La liste des équipements liés ne se modifie pas via ce PATCH générique (hors périmètre
    # actuel — un endpoint dédié serait nécessaire pour ajouter/retirer un équipement après
    # coup, non demandé pour l'instant).
    restricted = {
        "date_heure": date_heure,
        "lieu": lieu,
        "type": type,
        "duree_estimee": duree_estimee,
        "technicien_id": technicien_id,
        "nom_contact": nom_contact,
        "nom_etablissement": nom_etablissement,
    }

    if not is_chef:
        if intervention.technicien_id != current_user.id:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN, "Vous ne pouvez modifier que vos propres interventions"
            )
        if any(value is not None for value in restricted.values()):
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                "Un technicien ne peut modifier que le statut, la durée réelle et la photo",
            )
    else:
        if technicien_id is not None and db.get(Technicien, technicien_id) is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Technicien introuvable")
        # Réassignation à un autre technicien — seul le nouveau assigné est notifié (périmètre
        # minimal, décision explicite : pas de notification à l'ancien technicien retiré).
        if technicien_id is not None and technicien_id != intervention.technicien_id:
            notifier(
                db, technicien_id, TypeNotification.INTERVENTION_ASSIGNEE,
                f"Intervention {intervention.id} assignée : {lieu or intervention.lieu}",
                intervention_id=intervention.id,
            )
        for field, value in restricted.items():
            if value is not None:
                setattr(intervention, field, value)

    if duree_reelle is not None:
        intervention.duree_reelle = duree_reelle

    if photo is not None:
        PHOTOS_DIR.mkdir(parents=True, exist_ok=True)
        suffix = "".join(c for c in (photo.filename or "") if c in ".-_" or c.isalnum())[-100:]
        filename = f"{intervention_id}_{uuid.uuid4().hex}_{suffix or 'photo.jpg'}"
        destination = PHOTOS_DIR / filename
        destination.write_bytes(await photo.read())
        intervention.photo_url = f"/storage/interventions/{filename}"

    should_generate_rapport_final = False

    if statut is not None and statut != intervention.statut:
        # Étape 7 du workflow devis (voir SUIVI_PROJET.md) : un technicien ne peut clôturer via
        # ce PATCH générique que si l'intervention n'a jamais engagé le workflow devis (encore
        # à son état par défaut appel_recu) ou si le travail a bien été démarré via
        # /demarrer-travail — impossible de sauter directement de devis_envoye à terminé, par
        # exemple. Le chef d'équipe garde son droit de clôture administrative sans cette
        # contrainte (comportement préexistant, non restreint par cette nouvelle fonctionnalité).
        if (
            statut == StatutIntervention.TERMINE
            and not is_chef
            and intervention.statut_workflow not in (StatutWorkflow.APPEL_RECU, StatutWorkflow.TRAVAIL_EN_COURS)
        ):
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                f"Impossible de terminer : le workflow est au statut '{intervention.statut_workflow.value}', "
                "attendu 'travail_en_cours'",
            )

        intervention.statut = statut
        technicien = intervention.technicien
        if statut == StatutIntervention.EN_COURS:
            technicien.statut = StatutTechnicien.EN_INTERVENTION
        elif statut == StatutIntervention.TERMINE:
            technicien.statut = StatutTechnicien.DISPONIBLE
            technicien.interventions_ce_mois += 1
            if intervention.duree_reelle:
                technicien.heures_ce_mois += intervention.duree_reelle / 60
            if intervention.statut_workflow == StatutWorkflow.TRAVAIL_EN_COURS:
                intervention.statut_workflow = StatutWorkflow.TERMINE
                intervention.date_terminee = datetime.now(timezone.utc)
                synchroniser_statut_parc(db, intervention, StatutReparation.REPARE)
                # Rapport final généré uniquement quand le workflow devis a été réellement
                # suivi jusqu'au bout — une intervention qui ne l'a jamais engagé (voir
                # rétrocompatibilité ci-dessus) n'a ni diagnostic ni devis à résumer.
                should_generate_rapport_final = True
            # Notifie le chef uniquement quand c'est le technicien assigné qui clôture —
            # si c'est le chef lui-même qui clôture (clôture administrative), pas de sens à se
            # notifier de sa propre action.
            if not is_chef:
                notifier_role(
                    db, RoleTechnicien.CHEF_EQUIPE, TypeNotification.INTERVENTION_TERMINEE,
                    f"Intervention {intervention.id} terminée par {technicien.nom}",
                    intervention_id=intervention.id,
                )

    db.commit()
    db.refresh(intervention)

    if should_generate_rapport_final:
        generate_rapport_final_pdf(db, intervention, genere_par_id=current_user.id)

    return intervention


# ── Photos internes (traçabilité technicien — jamais incluses dans un PDF) ──


def _require_photo_access(intervention: Intervention, current_user: Technicien) -> None:
    if current_user.role == RoleTechnicien.ADMIN:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Module réservé au chef d'équipe et aux techniciens")
    is_chef = current_user.role == RoleTechnicien.CHEF_EQUIPE
    if not is_chef and intervention.technicien_id != current_user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Vous ne pouvez ajouter des photos qu'à vos propres interventions")


@router.get("/{intervention_id}/photos", response_model=list[InterventionPhotoRead])
def list_intervention_photos(
    intervention_id: str,
    db: Session = Depends(get_db),
) -> list[InterventionPhoto]:
    intervention = db.get(Intervention, intervention_id)
    if intervention is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Intervention introuvable")
    return (
        db.query(InterventionPhoto)
        .filter(InterventionPhoto.intervention_id == intervention_id)
        .order_by(InterventionPhoto.ajoutee_le)
        .all()
    )


@router.post("/{intervention_id}/photos", response_model=list[InterventionPhotoRead], status_code=status.HTTP_201_CREATED)
async def add_intervention_photos(
    intervention_id: str,
    photos: list[UploadFile] = File(...),
    db: Session = Depends(get_db),
    current_user: Technicien = Depends(get_current_user),
) -> list[InterventionPhoto]:
    """Photos d'usage interne uniquement (traçabilité/preuve) — jamais incluses dans un PDF,
    à ne pas confondre avec la photo de couverture unique (`Intervention.photo_url`, PATCH
    générique ci-dessus) qui, elle, apparaît dans le rapport final remis au client."""
    intervention = db.get(Intervention, intervention_id)
    if intervention is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Intervention introuvable")

    _require_photo_access(intervention, current_user)

    # Même verrou que le PATCH générique : plus aucune modification une fois l'intervention
    # clôturée (voir la garde équivalente dans update_intervention ci-dessus).
    if intervention.statut == StatutIntervention.TERMINE:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Intervention clôturée : plus aucune modification possible.")

    directory = PHOTOS_DIR / intervention_id / "photos"
    directory.mkdir(parents=True, exist_ok=True)

    created: list[InterventionPhoto] = []
    for photo in photos:
        suffix = "".join(c for c in (photo.filename or "") if c in ".-_" or c.isalnum())[-100:]
        filename = f"{uuid.uuid4().hex}_{suffix or 'photo.jpg'}"
        destination = directory / filename
        destination.write_bytes(await photo.read())
        record = InterventionPhoto(
            intervention_id=intervention_id,
            chemin_photo=f"/storage/interventions/{intervention_id}/photos/{filename}",
            ajoutee_par_id=current_user.id,
        )
        db.add(record)
        created.append(record)

    db.commit()
    for record in created:
        db.refresh(record)
    return created


@router.delete("/{intervention_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_intervention(
    intervention_id: str,
    db: Session = Depends(get_db),
    _: Technicien = Depends(require_chef),
) -> None:
    intervention = db.get(Intervention, intervention_id)
    if intervention is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Intervention introuvable")
    db.delete(intervention)
    db.commit()
