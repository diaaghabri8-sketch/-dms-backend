from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.deps import require_admin_or_chef
from app.database import get_db
from app.models.appel_offre import AppelOffre, StatutAppelOffre
from app.schemas.appel_offre import AppelOffreRead, AppelOffreUpdate, ScanResult
from app.services.marches_publics import run_scan

# Jamais accessible au technicien — veille réservée à l'admin et au chef d'équipe, voir
# SUIVI_PROJET.md.
router = APIRouter(
    prefix="/appels-offres", tags=["appels-offres"], dependencies=[Depends(require_admin_or_chef)]
)


@router.get("", response_model=list[AppelOffreRead])
def list_appels_offres(
    statut: StatutAppelOffre | None = None, db: Session = Depends(get_db)
) -> list[AppelOffreRead]:
    query = db.query(AppelOffre)
    if statut is not None:
        query = query.filter(AppelOffre.statut == statut)
    rows = query.order_by(AppelOffre.date_limite_offres.asc().nullslast()).all()
    return [AppelOffreRead.model_validate(row) for row in rows]


@router.patch("/{appel_offre_id}", response_model=AppelOffreRead)
def update_appel_offre(
    appel_offre_id: int, payload: AppelOffreUpdate, db: Session = Depends(get_db)
) -> AppelOffreRead:
    appel = db.get(AppelOffre, appel_offre_id)
    if appel is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Appel d'offres introuvable")
    appel.statut = payload.statut
    db.commit()
    db.refresh(appel)
    return AppelOffreRead.model_validate(appel)


@router.post("/scan", response_model=ScanResult)
def trigger_scan(db: Session = Depends(get_db)) -> ScanResult:
    """Déclenchement manuel — même fonction que le job planifié quotidien, pour tester sans
    attendre 24h (voir SUIVI_PROJET.md). Appel synchrone : prend quelques secondes à quelques
    dizaines de secondes selon le nombre de mots-clés et de nouveaux avis (délai volontaire
    entre chaque requête vers marchespublics.gov.tn)."""
    return run_scan(db)
