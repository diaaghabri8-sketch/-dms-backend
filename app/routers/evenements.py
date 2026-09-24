from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, require_chef
from app.database import get_db
from app.models.evenement import Evenement
from app.models.technicien import Technicien
from app.schemas.evenement import EvenementCreate, EvenementRead, EvenementUpdate

router = APIRouter(prefix="/evenements", tags=["evenements"], dependencies=[Depends(get_current_user)])


@router.get("", response_model=list[EvenementRead])
def list_evenements(
    db: Session = Depends(get_db),
    limit: int = Query(10, ge=1, le=200),
) -> list[Evenement]:
    return db.query(Evenement).order_by(Evenement.date_heure.desc()).limit(limit).all()


@router.get("/{evenement_id}", response_model=EvenementRead)
def get_evenement(evenement_id: int, db: Session = Depends(get_db)) -> Evenement:
    evenement = db.get(Evenement, evenement_id)
    if evenement is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Événement introuvable")
    return evenement


@router.post("", response_model=EvenementRead, status_code=status.HTTP_201_CREATED)
def create_evenement(
    payload: EvenementCreate,
    db: Session = Depends(get_db),
    _: Technicien = Depends(require_chef),
) -> Evenement:
    evenement = Evenement(**payload.model_dump(exclude_unset=True))
    db.add(evenement)
    db.commit()
    db.refresh(evenement)
    return evenement


@router.patch("/{evenement_id}", response_model=EvenementRead)
def update_evenement(
    evenement_id: int,
    payload: EvenementUpdate,
    db: Session = Depends(get_db),
    _: Technicien = Depends(require_chef),
) -> Evenement:
    evenement = db.get(Evenement, evenement_id)
    if evenement is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Événement introuvable")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(evenement, field, value)
    db.commit()
    db.refresh(evenement)
    return evenement


@router.delete("/{evenement_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_evenement(
    evenement_id: int,
    db: Session = Depends(get_db),
    _: Technicien = Depends(require_chef),
) -> None:
    evenement = db.get(Evenement, evenement_id)
    if evenement is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Événement introuvable")
    db.delete(evenement)
    db.commit()
