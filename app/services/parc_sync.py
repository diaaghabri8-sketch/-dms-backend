"""Synchronisation automatique "Parc équipements" depuis le diagnostic d'une intervention
curatif/préventif dont le lieu de réparation est "atelier" — voir SUIVI_PROJET.md pour la
mécanique complète (pourquoi au diagnostic, pas au choix "atelier" ; pourquoi pas de logique
de retour en arrière si le cas "sur place" se présentait après coup)."""

from datetime import date

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.models.equipement_reparation import EquipementAttenteReparation, StatutReparation
from app.models.intervention import Intervention, LieuReparation, TypeIntervention


def sync_equipements_vers_parc(db: Session, intervention: Intervention) -> None:
    if intervention.type not in (TypeIntervention.CURATIF, TypeIntervention.PREVENTIF):
        return
    if intervention.lieu_reparation != LieuReparation.ATELIER:
        return

    for item in intervention.equipements:
        # Seuls les équipements en texte libre (formulaire Maintenance) sont concernés — un
        # équipement du parc DMS déjà suivi (equipement_id) n'est pas un équipement client reçu
        # à l'atelier, ça n'a pas de sens de le faire apparaître ici.
        if not item.description_libre or not item.sn_saisi_technicien:
            continue

        deja_lie = (
            db.query(EquipementAttenteReparation)
            .filter(EquipementAttenteReparation.intervention_equipement_id == item.id)
            .first()
        )
        if deja_lie is not None:
            continue

        # Comparaison normalisée (trim + lowercase des deux côtés) : le SN est saisi en texte
        # libre par le technicien à chaque intervention, une casse ou un espacement différent
        # d'une visite à l'autre ("SN-123" vs " sn-123 ") ne doit pas faire passer un retour
        # d'équipement connu pour un nouvel équipement (créerait une fiche en double, l'une
        # RÉPARÉE et l'autre bloquée à EN_RÉPARATION indéfiniment).
        sn_normalise = item.sn_saisi_technicien.strip().lower()
        sn_existant = (
            db.query(EquipementAttenteReparation)
            .filter(func.lower(func.trim(EquipementAttenteReparation.numero_serie)) == sn_normalise)
            .first()
        )
        if sn_existant is not None:
            # Un équipement avec ce SN est déjà suivi (retour d'un équipement connu) — on ne
            # duplique pas, on laisse la fiche existante telle quelle.
            continue

        db.add(
            EquipementAttenteReparation(
                numero_serie=item.sn_saisi_technicien,
                nom=item.description_libre,
                marque=item.description_libre,
                # Type structuré si le chef/technicien l'a saisi (voir InterventionEquipement.
                # type_equipement) ; sinon on garde l'ancien contournement (copie de la
                # description) pour ne rien casser sur les équipements créés avant ce champ.
                type_equipement=item.type_equipement or item.description_libre,
                etablissement_origine=intervention.nom_etablissement or intervention.lieu,
                date_reception=date.today(),
                statut=StatutReparation.EN_REPARATION,
                description_panne=intervention.description_panne,
                technicien_assigne_id=intervention.technicien_id,
                intervention_equipement_id=item.id,
            )
        )


def _fiches_liees(db: Session, intervention: Intervention) -> list[EquipementAttenteReparation]:
    """Fiches liées à cette intervention par l'un des deux mécanismes possibles : soit la
    maintenance d'origine (intervention_equipement_id, ses propres équipements), soit une
    intervention de restitution créée pour elle (restitution_intervention_id, voir
    POST /equipements-reparation/{id}/restitution) — les deux ne se recoupent jamais (deux
    interventions différentes), d'où le OR plutôt qu'un remplacement du critère existant."""
    equipement_ids = [ie.id for ie in intervention.equipements]
    conditions = [EquipementAttenteReparation.restitution_intervention_id == intervention.id]
    if equipement_ids:
        conditions.append(EquipementAttenteReparation.intervention_equipement_id.in_(equipement_ids))
    return db.query(EquipementAttenteReparation).filter(or_(*conditions)).all()


def synchroniser_statut_parc(db: Session, intervention: Intervention, statut: StatutReparation) -> None:
    """Fait suivre automatiquement le(s) statut(s) des fiches "Parc équipements" liées à cette
    intervention sur les transitions pertinentes du workflow devis, ou sur la validation d'une
    restitution (voir _fiches_liees ci-dessus et SUIVI_PROJET.md pour le mapping complet
    statut_workflow -> statut Parc). Aucune fiche liée (intervention "sur place", type sans
    workflow devis, équipement du parc DMS déjà suivi via equipement_id plutôt que texte
    libre...) -> no-op silencieux, pas une erreur.

    Un devis refusé n'a pas de statut Parc automatique associé (la fiche reste dans son état
    courant, ajustable à la main via le badge cliquable de Parc équipements)."""
    for fiche in _fiches_liees(db, intervention):
        fiche.statut = statut
