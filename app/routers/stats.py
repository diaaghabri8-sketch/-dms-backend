from datetime import date, datetime, time, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.database import get_db
from app.models.equipement import Equipement, StatutEquipement
from app.models.intervention import Intervention, StatutIntervention, TypeIntervention
from app.models.technicien import StatutTechnicien, Technicien
from app.schemas.stats import DashboardStats, InterventionsAujourdHui

router = APIRouter(prefix="/stats", tags=["stats"], dependencies=[Depends(get_current_user)])


def _avg_mttr_minutes(db: Session, year: int, month: int) -> float | None:
    avg_duration = (
        db.query(func.avg(Intervention.duree_reelle))
        .filter(
            Intervention.statut == StatutIntervention.TERMINE,
            Intervention.duree_reelle.isnot(None),
            func.extract("year", Intervention.date_heure) == year,
            func.extract("month", Intervention.date_heure) == month,
        )
        .scalar()
    )
    return float(avg_duration) if avg_duration is not None else None


@router.get("/dashboard", response_model=DashboardStats)
def dashboard_stats(db: Session = Depends(get_db)) -> DashboardStats:
    techniciens_total = db.query(func.count(Technicien.id)).scalar() or 0
    techniciens_actifs = (
        db.query(func.count(Technicien.id))
        .filter(Technicien.statut != StatutTechnicien.HORS_LIGNE)
        .scalar()
        or 0
    )

    equipements_total = db.query(func.count(Equipement.id)).scalar() or 0
    equipements_operationnels = (
        db.query(func.count(Equipement.id))
        .filter(Equipement.statut == StatutEquipement.OPERATIONNEL)
        .scalar()
        or 0
    )
    disponibilite_parc = (
        round(equipements_operationnels / equipements_total * 100, 1) if equipements_total else 0.0
    )

    today = date.today()
    day_start = datetime.combine(today, time.min, tzinfo=timezone.utc)
    day_end = day_start + timedelta(days=1)
    interventions_today = db.query(Intervention).filter(
        Intervention.date_heure >= day_start, Intervention.date_heure < day_end
    )
    preventives = interventions_today.filter(Intervention.type == TypeIntervention.PREVENTIF).count()
    curatives = interventions_today.filter(Intervention.type == TypeIntervention.CURATIF).count()

    this_month_mttr = _avg_mttr_minutes(db, today.year, today.month)
    last_month = today.month - 1 or 12
    last_month_year = today.year if today.month > 1 else today.year - 1
    last_month_mttr = _avg_mttr_minutes(db, last_month_year, last_month)

    mttr_heures = round((this_month_mttr or 0) / 60, 1)
    mttr_delta_min = (
        round(this_month_mttr - last_month_mttr, 1)
        if this_month_mttr is not None and last_month_mttr is not None
        else 0.0
    )

    return DashboardStats(
        techniciens_actifs=techniciens_actifs,
        techniciens_total=techniciens_total,
        disponibilite_parc=disponibilite_parc,
        equipements_total=equipements_total,
        equipements_operationnels=equipements_operationnels,
        interventions_aujourd_hui=InterventionsAujourdHui(
            preventives=preventives, curatives=curatives, total=preventives + curatives
        ),
        mttr_heures=mttr_heures,
        mttr_delta_min=mttr_delta_min,
        # Pas d'historique de disponibilité du parc en base (pas de table de snapshot) : delta non calculable.
        disponibilite_delta=0.0,
    )
