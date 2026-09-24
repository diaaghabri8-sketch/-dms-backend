from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, require_admin, require_admin_or_chef
from app.database import get_db
from app.models.devis import Devis, StatutDevis
from app.models.equipement_reparation import StatutReparation
from app.models.intervention import Intervention, StatutIntervention, StatutWorkflow, TypeIntervention
from app.models.intervention_document import InterventionDocument
from app.models.intervention_equipement import InterventionEquipement
from app.models.notification import TypeNotification
from app.models.piece_necessaire import PieceNecessaire
from app.models.technicien import RoleTechnicien, StatutTechnicien, Technicien
from app.schemas.devis import DevisCreate, DevisDecision, DevisRead
from app.schemas.intervention import DiagnosticUpdate, InterventionRead, LieuReparationUpdate, ReportIntervention
from app.schemas.intervention_document import InterventionDocumentRead
from app.schemas.intervention_equipement import SnTechnicienUpdate
from app.schemas.piece_necessaire import PieceNecessaireRead, PiecesNecessairesCreate
from app.services.notifications import notifier, notifier_role
from app.services.notify import notifier_technicien_devis_envoye
from app.services.parc_sync import sync_equipements_vers_parc, synchroniser_statut_parc
from app.services.pdf_workflow import generate_devis_pdf, generate_diagnostic_pdf

router = APIRouter(tags=["workflow-intervention"], dependencies=[Depends(get_current_user)])


def _get_intervention_or_404(intervention_id: str, db: Session) -> Intervention:
    intervention = db.get(Intervention, intervention_id)
    if intervention is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Intervention introuvable")
    return intervention


def _require_technicien_assigne(intervention: Intervention, current_user: Technicien) -> None:
    if intervention.technicien_id != current_user.id:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Seul le technicien assigné à cette intervention peut effectuer cette action",
        )


def _require_statut_workflow(intervention: Intervention, *attendus: StatutWorkflow) -> None:
    if intervention.statut_workflow not in attendus:
        attendu_str = " ou ".join(s.value for s in attendus)
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"Étape impossible : le workflow est au statut '{intervention.statut_workflow.value}', "
            f"attendu '{attendu_str}'",
        )


# ── 1. Lieu de réparation (technicien assigné) ──


@router.patch("/interventions/{intervention_id}/lieu-reparation", response_model=InterventionRead)
def set_lieu_reparation(
    intervention_id: str,
    payload: LieuReparationUpdate,
    db: Session = Depends(get_db),
    current_user: Technicien = Depends(get_current_user),
) -> Intervention:
    intervention = _get_intervention_or_404(intervention_id, db)
    _require_technicien_assigne(intervention, current_user)
    _require_statut_workflow(intervention, StatutWorkflow.APPEL_RECU)

    intervention.lieu_reparation = payload.lieu_reparation
    intervention.statut_workflow = StatutWorkflow.DIAGNOSTIC_EN_COURS
    db.commit()
    db.refresh(intervention)
    return intervention


# ── 2. Diagnostic (technicien assigné) ──


@router.patch("/interventions/{intervention_id}/diagnostic", response_model=InterventionRead)
def set_diagnostic(
    intervention_id: str,
    payload: DiagnosticUpdate,
    db: Session = Depends(get_db),
    current_user: Technicien = Depends(get_current_user),
) -> Intervention:
    intervention = _get_intervention_or_404(intervention_id, db)
    _require_technicien_assigne(intervention, current_user)
    _require_statut_workflow(intervention, StatutWorkflow.DIAGNOSTIC_EN_COURS)

    intervention.description_panne = payload.description_panne
    intervention.statut_workflow = StatutWorkflow.DIAGNOSTIC_TERMINE
    intervention.date_diagnostic = datetime.now(timezone.utc)

    # Fait apparaître automatiquement dans "Parc équipements" les équipements texte libre
    # d'une intervention curatif/préventif "atelier" — le SN, requis pour créer la fiche,
    # n'est connu qu'à partir de maintenant (voir app/services/parc_sync.py).
    sync_equipements_vers_parc(db, intervention)

    db.commit()
    db.refresh(intervention)

    generate_diagnostic_pdf(db, intervention, genere_par_id=current_user.id)

    return intervention


@router.patch(
    "/interventions/{intervention_id}/equipements/{intervention_equipement_id}/sn",
    response_model=InterventionRead,
)
def set_sn_technicien(
    intervention_id: str,
    intervention_equipement_id: int,
    payload: SnTechnicienUpdate,
    db: Session = Depends(get_db),
    current_user: Technicien = Depends(get_current_user),
) -> Intervention:
    """Saisie du numéro de série par le technicien, sur place — pour les équipements entrés en
    texte libre à la création (type curatif/préventif, formulaire "Maintenance", sans référence
    catalogue). Pas de nouvelle étape de workflow dédiée (décision produit) : reste au même
    statut que le diagnostic (`diagnostic_en_cours`), le technicien renseigne le(s) SN juste
    avant/avec sa saisie de la panne constatée, sur le même écran."""
    intervention = _get_intervention_or_404(intervention_id, db)
    _require_technicien_assigne(intervention, current_user)
    _require_statut_workflow(intervention, StatutWorkflow.DIAGNOSTIC_EN_COURS)

    intervention_equipement = db.get(InterventionEquipement, intervention_equipement_id)
    if intervention_equipement is None or intervention_equipement.intervention_id != intervention_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Équipement introuvable pour cette intervention")

    intervention_equipement.sn_saisi_technicien = payload.sn_saisi_technicien
    db.commit()
    db.refresh(intervention)
    return intervention


# ── 3. Pièces nécessaires (technicien assigné pour écrire, lecture ouverte à tout authentifié) ──


@router.get("/interventions/{intervention_id}/pieces-necessaires", response_model=list[PieceNecessaireRead])
def list_pieces_necessaires(
    intervention_id: str,
    db: Session = Depends(get_db),
) -> list[PieceNecessaire]:
    _get_intervention_or_404(intervention_id, db)
    return (
        db.query(PieceNecessaire)
        .filter(PieceNecessaire.intervention_id == intervention_id)
        .order_by(PieceNecessaire.date_ajout)
        .all()
    )


@router.post(
    "/interventions/{intervention_id}/pieces-necessaires",
    response_model=list[PieceNecessaireRead],
    status_code=status.HTTP_201_CREATED,
)
def add_pieces_necessaires(
    intervention_id: str,
    payload: PiecesNecessairesCreate,
    db: Session = Depends(get_db),
    current_user: Technicien = Depends(get_current_user),
) -> list[PieceNecessaire]:
    intervention = _get_intervention_or_404(intervention_id, db)
    _require_technicien_assigne(intervention, current_user)
    _require_statut_workflow(intervention, StatutWorkflow.DIAGNOSTIC_TERMINE, StatutWorkflow.DEVIS_EN_PREPARATION)

    # Validation groupée avant tout insert (tout ou rien si l'équipement précisé n'appartient
    # pas à cette intervention) — plus de vérification catalogue, la pièce est en texte libre.
    for item in payload.pieces:
        if item.intervention_equipement_id is not None:
            intervention_equipement = db.get(InterventionEquipement, item.intervention_equipement_id)
            if intervention_equipement is None or intervention_equipement.intervention_id != intervention_id:
                raise HTTPException(
                    status.HTTP_404_NOT_FOUND,
                    f"Équipement d'intervention {item.intervention_equipement_id} introuvable pour cette intervention",
                )

    created: list[PieceNecessaire] = []
    for item in payload.pieces:
        piece_necessaire = PieceNecessaire(
            intervention_id=intervention_id,
            intervention_equipement_id=item.intervention_equipement_id,
            description_libre=item.description_libre,
            quantite_necessaire=item.quantite_necessaire,
            ajoute_par_id=current_user.id,
        )
        db.add(piece_necessaire)
        created.append(piece_necessaire)

    intervention.statut_workflow = StatutWorkflow.DEVIS_EN_PREPARATION
    intervention.date_pieces_identifiees = datetime.now(timezone.utc)
    # Diagnostic + pièces traités : prêt pour devis — seul l'admin peut créer un devis
    # (`require_admin` sur create_devis ci-dessous), c'est donc lui le destinataire pertinent.
    notifier_role(
        db, RoleTechnicien.ADMIN, TypeNotification.PRET_POUR_DEVIS,
        f"Intervention {intervention.id} prête pour devis",
        intervention_id=intervention.id,
    )
    db.commit()
    for piece_necessaire in created:
        db.refresh(piece_necessaire)
    return created


@router.delete(
    "/interventions/{intervention_id}/pieces-necessaires/{piece_necessaire_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def remove_piece_necessaire(
    intervention_id: str,
    piece_necessaire_id: int,
    db: Session = Depends(get_db),
    current_user: Technicien = Depends(get_current_user),
) -> None:
    intervention = _get_intervention_or_404(intervention_id, db)
    _require_technicien_assigne(intervention, current_user)
    _require_statut_workflow(intervention, StatutWorkflow.DEVIS_EN_PREPARATION)

    piece_necessaire = db.get(PieceNecessaire, piece_necessaire_id)
    if piece_necessaire is None or piece_necessaire.intervention_id != intervention_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Pièce nécessaire introuvable pour cette intervention")

    db.delete(piece_necessaire)
    db.commit()


# ── 4. Devis (admin uniquement pour créer, lecture ouverte à tout authentifié) ──


@router.get("/devis", response_model=list[DevisRead])
def list_all_devis(
    db: Session = Depends(get_db),
    statut: StatutDevis | None = Query(None),
) -> list[Devis]:
    """Liste globale, tous intervention confondues — ex: panneau admin "Devis" qui affiche
    les devis en attente de décision (`?statut=envoye`)."""
    query = db.query(Devis)
    if statut is not None:
        query = query.filter(Devis.statut == statut)
    return query.order_by(Devis.date_creation.desc()).all()


@router.get("/interventions/{intervention_id}/devis", response_model=list[DevisRead])
def list_devis(
    intervention_id: str,
    db: Session = Depends(get_db),
) -> list[Devis]:
    _get_intervention_or_404(intervention_id, db)
    return db.query(Devis).filter(Devis.intervention_id == intervention_id).order_by(Devis.date_creation).all()


@router.post(
    "/interventions/{intervention_id}/devis", response_model=DevisRead, status_code=status.HTTP_201_CREATED
)
async def create_devis(
    intervention_id: str,
    payload: DevisCreate,
    db: Session = Depends(get_db),
    current_user: Technicien = Depends(require_admin),
) -> Devis:
    intervention = _get_intervention_or_404(intervention_id, db)
    _require_statut_workflow(intervention, StatutWorkflow.DEVIS_EN_PREPARATION)

    if db.query(Devis).filter(Devis.intervention_id == intervention_id).first() is not None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Un devis existe déjà pour cette intervention")

    # montant_pieces est désormais saisi par l'admin (payload), plus de calcul automatique
    # depuis le catalogue — PieceNecessaire n'a plus de prix (texte libre pur).
    montant_total = payload.montant_pieces + payload.montant_main_oeuvre

    devis = Devis(
        intervention_id=intervention_id,
        montant_pieces=payload.montant_pieces,
        montant_main_oeuvre=payload.montant_main_oeuvre,
        montant_total=montant_total,
        statut=StatutDevis.ENVOYE,
        cree_par_id=current_user.id,
    )
    db.add(devis)
    intervention.statut_workflow = StatutWorkflow.DEVIS_ENVOYE
    # Synchro Parc équipements : le besoin réel en pièces n'est connu qu'à cet instant (le
    # montant est saisi ici, PieceNecessaire est du texte libre sans prix) — voir
    # synchroniser_statut_parc pour le mapping complet.
    synchroniser_statut_parc(
        db, intervention,
        StatutReparation.EN_ATTENTE_PIECE if payload.montant_pieces > 0 else StatutReparation.EN_REPARATION,
    )
    db.commit()
    db.refresh(devis)

    generate_devis_pdf(db, intervention, devis, genere_par_id=current_user.id)

    # Le technicien assigné attend cette décision pour savoir s'il peut démarrer son travail —
    # notifié via la messagerie existante (voir app/services/notify.py).
    await notifier_technicien_devis_envoye(db, intervention, expediteur_id=current_user.id)

    return devis


# ── 5. Décision client sur le devis (admin ou chef) ──


@router.patch("/devis/{devis_id}/decision", response_model=DevisRead)
def decide_devis(
    devis_id: int,
    payload: DevisDecision,
    db: Session = Depends(get_db),
    current_user: Technicien = Depends(require_admin_or_chef),
) -> Devis:
    devis = db.get(Devis, devis_id)
    if devis is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Devis introuvable")
    if devis.statut != StatutDevis.ENVOYE:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"Décision impossible : le devis est au statut '{devis.statut.value}', attendu 'envoye'",
        )

    intervention = devis.intervention
    _require_statut_workflow(intervention, StatutWorkflow.DEVIS_ENVOYE)

    devis.date_decision_client = datetime.now(timezone.utc)
    if payload.notes is not None:
        devis.notes = payload.notes

    if payload.decision == "accepte":
        devis.statut = StatutDevis.ACCEPTE
        intervention.statut_workflow = StatutWorkflow.DEVIS_ACCEPTE
        synchroniser_statut_parc(db, intervention, StatutReparation.EN_REPARATION)
        notifier(
            db, intervention.technicien_id, TypeNotification.DEVIS_ACCEPTE,
            f"Devis accepté pour l'intervention {intervention.id} — vous pouvez démarrer le travail",
            intervention_id=intervention.id,
        )
    else:
        devis.statut = StatutDevis.REFUSE
        # Refus client : le workflow saute directement à l'état terminal "annulee" (pas de
        # relance de devis prévue dans ce workflow) — l'intervention s'arrête là. Pas de
        # statut Parc automatique associé (aucune réparation n'a lieu) : la fiche reste dans
        # son état courant, ajustable manuellement via le badge si besoin (ex: "retourné
        # client" une fois l'équipement physiquement repris par le client sans réparation).
        intervention.statut_workflow = StatutWorkflow.ANNULEE
        intervention.statut = StatutIntervention.TERMINE
        notifier(
            db, intervention.technicien_id, TypeNotification.DEVIS_REFUSE,
            f"Devis refusé pour l'intervention {intervention.id} — intervention annulée",
            intervention_id=intervention.id,
        )
        intervention.technicien.statut = StatutTechnicien.DISPONIBLE

    db.commit()
    db.refresh(devis)
    return devis


# ── 6. Démarrer le travail (technicien assigné) ──


@router.patch("/interventions/{intervention_id}/demarrer-travail", response_model=InterventionRead)
def demarrer_travail(
    intervention_id: str,
    db: Session = Depends(get_db),
    current_user: Technicien = Depends(get_current_user),
) -> Intervention:
    intervention = _get_intervention_or_404(intervention_id, db)
    _require_technicien_assigne(intervention, current_user)
    _require_statut_workflow(intervention, StatutWorkflow.DEVIS_ACCEPTE)

    intervention.statut_workflow = StatutWorkflow.TRAVAIL_EN_COURS
    intervention.statut = StatutIntervention.EN_COURS
    intervention.date_travail_demarre = datetime.now(timezone.utc)
    intervention.technicien.statut = StatutTechnicien.EN_INTERVENTION
    # Redondant avec la synchro faite à l'acceptation du devis (déjà en_reparation), mais la
    # demande est explicite : chaque transition pertinente resynchronise, pas seulement le
    # résultat final — filet de sécurité si l'état Parc avait dérivé entre-temps.
    synchroniser_statut_parc(db, intervention, StatutReparation.EN_REPARATION)
    db.commit()
    db.refresh(intervention)
    return intervention


# ── 7. Parcours simplifié installation/formation/restitution (voir SUIVI_PROJET.md) ──
# Ces types n'engagent jamais le workflow diagnostic → pièces → devis → travail : `statut`
# (planifie/termine) porte seul l'état de ce parcours, `statut_workflow` reste figé à sa valeur
# par défaut `appel_recu` pour toujours. Ce choix réutilise tel quel le garde-fou déjà existant
# dans TaskWorkflowPanel.jsx (statut==termine && statut_workflow==appel_recu → écran "terminé
# sans passer par le workflow diagnostic/devis"), qui affiche donc correctement ces
# interventions une fois validées, sans changement frontend supplémentaire.


def _require_type_simple(intervention: Intervention) -> None:
    if intervention.type not in (TypeIntervention.INSTALLATION, TypeIntervention.FORMATION, TypeIntervention.RESTITUTION):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Cette action est réservée aux interventions de type installation, formation ou restitution",
        )


@router.patch("/interventions/{intervention_id}/valider", response_model=InterventionRead)
def valider_intervention_simple(
    intervention_id: str,
    db: Session = Depends(get_db),
    current_user: Technicien = Depends(get_current_user),
) -> Intervention:
    intervention = _get_intervention_or_404(intervention_id, db)
    _require_technicien_assigne(intervention, current_user)
    _require_type_simple(intervention)
    if intervention.statut == StatutIntervention.TERMINE:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Intervention déjà terminée")

    intervention.statut = StatutIntervention.TERMINE
    intervention.date_terminee = datetime.now(timezone.utc)
    technicien = intervention.technicien
    technicien.statut = StatutTechnicien.DISPONIBLE
    technicien.interventions_ce_mois += 1
    if intervention.duree_reelle:
        technicien.heures_ce_mois += intervention.duree_reelle / 60

    # Boucle Parc équipements : la restitution vient d'être remise au client (signature
    # obtenue), la fiche liée (via restitution_intervention_id) referme le cycle.
    if intervention.type == TypeIntervention.RESTITUTION:
        synchroniser_statut_parc(db, intervention, StatutReparation.RETOURNE_CLIENT)

    # Toujours déclenché par le technicien assigné (_require_technicien_assigne ci-dessus) —
    # contrairement au PATCH générique, pas de cas "chef clôture lui-même" à exclure ici.
    notifier_role(
        db, RoleTechnicien.CHEF_EQUIPE, TypeNotification.INTERVENTION_TERMINEE,
        f"Intervention {intervention.id} terminée par {technicien.nom}",
        intervention_id=intervention.id,
    )

    db.commit()
    db.refresh(intervention)
    return intervention


@router.patch("/interventions/{intervention_id}/reporter", response_model=InterventionRead)
def reporter_intervention_simple(
    intervention_id: str,
    payload: ReportIntervention,
    db: Session = Depends(get_db),
    current_user: Technicien = Depends(get_current_user),
) -> Intervention:
    intervention = _get_intervention_or_404(intervention_id, db)
    _require_technicien_assigne(intervention, current_user)
    _require_type_simple(intervention)
    if intervention.statut == StatutIntervention.TERMINE:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Intervention déjà terminée, report impossible")

    intervention.date_heure = payload.nouvelle_date_heure
    intervention.statut = StatutIntervention.PLANIFIE

    notifier_role(
        db, RoleTechnicien.CHEF_EQUIPE, TypeNotification.INTERVENTION_REPORTEE,
        f"Intervention {intervention.id} reportée par {current_user.nom}",
        intervention_id=intervention.id,
    )

    db.commit()
    db.refresh(intervention)
    return intervention


# ── 8. Documents générés (lecture ouverte à tout authentifié — chef/admin/technicien) ──


@router.get("/interventions/{intervention_id}/documents", response_model=list[InterventionDocumentRead])
def list_intervention_documents(
    intervention_id: str,
    db: Session = Depends(get_db),
) -> list[InterventionDocument]:
    _get_intervention_or_404(intervention_id, db)
    return (
        db.query(InterventionDocument)
        .filter(InterventionDocument.intervention_id == intervention_id)
        .order_by(InterventionDocument.genere_le)
        .all()
    )
