from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.deps import require_admin_or_chef
from app.database import get_db
from app.models.equipement_reparation import EquipementAttenteReparation, StatutReparation
from app.models.intervention import Intervention, TypeIntervention
from app.models.intervention_equipement import InterventionEquipement
from app.models.notification import TypeNotification
from app.models.technicien import Technicien
from app.routers.interventions import _generate_intervention_id
from app.schemas.equipement_reparation import (
    EquipementARendreRead,
    EquipementAttenteReparationCreate,
    EquipementAttenteReparationRead,
    EquipementAttenteReparationUpdate,
    EquipementRenduRead,
    RestitutionCreate,
)
from app.schemas.intervention import InterventionRead
from app.services.notifications import notifier
from app.services.pdf_workflow import generate_bon_restitution_pdf

router = APIRouter(
    prefix="/equipements-reparation", tags=["equipements-reparation"], dependencies=[Depends(require_admin_or_chef)]
)


@router.get("", response_model=list[EquipementAttenteReparationRead])
def list_equipements_reparation(
    db: Session = Depends(get_db),
    statut: StatutReparation | None = Query(None),
) -> list[EquipementAttenteReparation]:
    query = db.query(EquipementAttenteReparation)
    if statut is not None:
        query = query.filter(EquipementAttenteReparation.statut == statut)
    return query.order_by(EquipementAttenteReparation.date_reception.desc()).all()


# Déclaré avant /{equipement_id} — même règle de routage que /equipements/historique (voir
# SUIVI_PROJET.md) : un chemin littéral doit précéder un chemin paramétré sous le même préfixe.
@router.get("/a-rendre", response_model=list[EquipementARendreRead])
def list_equipements_a_rendre(db: Session = Depends(get_db)) -> list[EquipementARendreRead]:
    """Fiches réparées sans restitution déjà en cours — écran admin/chef 'Équipements à
    rendre'. Enrichi avec les infos de la maintenance d'origine (établissement déjà sur la
    fiche ; contact et technicien retrouvés via intervention_equipement -> intervention, absents
    si cette intervention d'origine a été supprimée entre-temps — l'écran reste utilisable, sans
    technicien pré-sélectionné dans ce cas)."""
    fiches = (
        db.query(EquipementAttenteReparation)
        .filter(
            EquipementAttenteReparation.statut == StatutReparation.REPARE,
            EquipementAttenteReparation.restitution_intervention_id.is_(None),
        )
        .order_by(EquipementAttenteReparation.updated_at.desc())
        .all()
    )
    resultats = []
    for fiche in fiches:
        origine = fiche.intervention_equipement.intervention if fiche.intervention_equipement is not None else None
        resultats.append(
            EquipementARendreRead(
                id=fiche.id,
                numero_serie=fiche.numero_serie,
                nom=fiche.nom,
                marque=fiche.marque,
                type_equipement=fiche.type_equipement,
                etablissement_origine=fiche.etablissement_origine,
                description_panne=fiche.description_panne,
                date_reception=fiche.date_reception,
                nom_contact=origine.nom_contact if origine is not None else None,
                technicien_origine_id=origine.technicien_id if origine is not None else None,
                technicien_origine_nom=origine.technicien.nom if origine is not None else None,
            )
        )
    return resultats


# Déclaré avant /{equipement_id}, même règle que /a-rendre ci-dessus.
@router.get("/rendus", response_model=list[EquipementRenduRead])
def list_equipements_rendus(db: Session = Depends(get_db)) -> list[EquipementRenduRead]:
    """Fiches effectivement rendues via le workflow de restitution (statut retourne_client ET
    restitution_intervention_id renseigné — exclut une éventuelle bascule manuelle par le badge
    sans passer par ce workflow, qui n'a ni technicien de restitution ni PDF à afficher ici).
    Onglet 'Rendus' de l'écran 'Équipements à rendre'."""
    fiches = (
        db.query(EquipementAttenteReparation)
        .filter(
            EquipementAttenteReparation.statut == StatutReparation.RETOURNE_CLIENT,
            EquipementAttenteReparation.restitution_intervention_id.isnot(None),
        )
        .order_by(EquipementAttenteReparation.updated_at.desc())
        .all()
    )
    return [
        EquipementRenduRead(
            id=fiche.id,
            numero_serie=fiche.numero_serie,
            nom=fiche.nom,
            marque=fiche.marque,
            type_equipement=fiche.type_equipement,
            etablissement_origine=fiche.etablissement_origine,
            restitution_intervention_id=fiche.restitution_intervention_id,
            technicien_restitution_id=fiche.restitution_intervention.technicien_id,
            technicien_restitution_nom=fiche.restitution_intervention.technicien.nom,
        )
        for fiche in fiches
    ]


@router.post(
    "/{equipement_id}/restitution", response_model=InterventionRead, status_code=status.HTTP_201_CREATED
)
def creer_restitution(
    equipement_id: int,
    payload: RestitutionCreate,
    db: Session = Depends(get_db),
    current_user: Technicien = Depends(require_admin_or_chef),
) -> Intervention:
    """Crée la tâche de restitution (intervention type=restitution, parcours simplifié
    Valider/Reporter) pour une fiche réparée, l'assigne au technicien choisi (par défaut celui
    de la maintenance d'origine, voir GET /a-rendre), et génère immédiatement le bon de
    restitution PDF — pas à la validation, le technicien doit l'avoir en main en se déplaçant."""
    fiche = db.get(EquipementAttenteReparation, equipement_id)
    if fiche is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Équipement introuvable")
    if fiche.statut != StatutReparation.REPARE:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Seul un équipement au statut 'réparé' peut être restitué")
    if fiche.restitution_intervention_id is not None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Une restitution est déjà en cours pour cet équipement")
    if db.get(Technicien, payload.technicien_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Technicien introuvable")

    origine = fiche.intervention_equipement.intervention if fiche.intervention_equipement is not None else None
    nom_contact = origine.nom_contact if origine is not None else None

    for _attempt in range(5):
        intervention = Intervention(
            id=_generate_intervention_id(db),
            date_heure=datetime.now(timezone.utc),
            lieu=fiche.etablissement_origine,
            type=TypeIntervention.RESTITUTION,
            technicien_id=payload.technicien_id,
            nom_contact=nom_contact,
            nom_etablissement=fiche.etablissement_origine,
        )
        db.add(intervention)
        try:
            db.flush()
        except IntegrityError:
            db.rollback()
            continue
        db.add(
            InterventionEquipement(
                intervention_id=intervention.id,
                description_libre=fiche.nom,
                sn_saisi_technicien=fiche.numero_serie,
                type_equipement=fiche.type_equipement,
            )
        )
        fiche.restitution_intervention_id = intervention.id
        notifier(
            db, intervention.technicien_id, TypeNotification.INTERVENTION_ASSIGNEE,
            f"Nouvelle restitution {intervention.id} assignée : {intervention.lieu}",
            intervention_id=intervention.id,
        )
        db.commit()
        db.refresh(intervention)

        generate_bon_restitution_pdf(db, intervention, fiche, genere_par_id=current_user.id)

        return intervention

    raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Impossible de générer un identifiant unique")


@router.get("/{equipement_id}", response_model=EquipementAttenteReparationRead)
def get_equipement_reparation(equipement_id: int, db: Session = Depends(get_db)) -> EquipementAttenteReparation:
    equipement = db.get(EquipementAttenteReparation, equipement_id)
    if equipement is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Équipement introuvable")
    return equipement


@router.post("", response_model=EquipementAttenteReparationRead, status_code=status.HTTP_201_CREATED)
def create_equipement_reparation(
    payload: EquipementAttenteReparationCreate,
    db: Session = Depends(get_db),
    _: Technicien = Depends(require_admin_or_chef),
) -> EquipementAttenteReparation:
    if (
        db.query(EquipementAttenteReparation)
        .filter(EquipementAttenteReparation.numero_serie == payload.numero_serie)
        .first()
        is not None
    ):
        raise HTTPException(status.HTTP_409_CONFLICT, "Un équipement avec ce numéro de série existe déjà")
    if payload.technicien_assigne_id is not None and db.get(Technicien, payload.technicien_assigne_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Technicien introuvable")
    if payload.intervention_equipement_id is not None and db.get(InterventionEquipement, payload.intervention_equipement_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Équipement d'intervention introuvable")

    equipement = EquipementAttenteReparation(**payload.model_dump())
    db.add(equipement)
    db.commit()
    db.refresh(equipement)
    return equipement


@router.patch("/{equipement_id}", response_model=EquipementAttenteReparationRead)
def update_equipement_reparation(
    equipement_id: int,
    payload: EquipementAttenteReparationUpdate,
    db: Session = Depends(get_db),
    _: Technicien = Depends(require_admin_or_chef),
) -> EquipementAttenteReparation:
    equipement = db.get(EquipementAttenteReparation, equipement_id)
    if equipement is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Équipement introuvable")

    updates = payload.model_dump(exclude_unset=True)

    # Verrou total une fois rendu au client — y compris `statut` lui-même : l'équipement est
    # physiquement reparti chez le client, aucune raison légitime de rouvrir son statut (revient
    # sur l'exception précédente, retirée sur demande explicite — voir SUIVI_PROJET.md).
    if equipement.statut == StatutReparation.RETOURNE_CLIENT and updates:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "Équipement déjà rendu au client : plus aucune modification possible."
        )

    if "technicien_assigne_id" in updates and updates["technicien_assigne_id"] is not None:
        if db.get(Technicien, updates["technicien_assigne_id"]) is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Technicien introuvable")
    if "intervention_equipement_id" in updates and updates["intervention_equipement_id"] is not None:
        if db.get(InterventionEquipement, updates["intervention_equipement_id"]) is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Équipement d'intervention introuvable")

    for field, value in updates.items():
        setattr(equipement, field, value)
    db.commit()
    db.refresh(equipement)
    return equipement


@router.delete("/{equipement_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_equipement_reparation(
    equipement_id: int,
    db: Session = Depends(get_db),
    _: Technicien = Depends(require_admin_or_chef),
) -> None:
    equipement = db.get(EquipementAttenteReparation, equipement_id)
    if equipement is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Équipement introuvable")
    db.delete(equipement)
    db.commit()
