from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, require_chef
from app.database import get_db
from app.models.formation import Formation
from app.models.technicien import Technicien
from app.schemas.formation import FormationCreate, FormationRead, FormationUpdate

router = APIRouter(prefix="/formations", tags=["formations"], dependencies=[Depends(get_current_user)])


@router.get("", response_model=list[FormationRead])
def list_formations(
    db: Session = Depends(get_db),
    technicien_id: int | None = Query(None),
) -> list[Formation]:
    query = db.query(Formation)
    if technicien_id is not None:
        query = query.filter(Formation.technicien_id == technicien_id)
    return query.order_by(Formation.date_obtention.desc()).all()


@router.get("/{formation_id}", response_model=FormationRead)
def get_formation(formation_id: int, db: Session = Depends(get_db)) -> Formation:
    formation = db.get(Formation, formation_id)
    if formation is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Formation introuvable")
    return formation


@router.post("", response_model=FormationRead, status_code=status.HTTP_201_CREATED)
def create_formation(
    payload: FormationCreate,
    db: Session = Depends(get_db),
    _: Technicien = Depends(require_chef),
) -> Formation:
    if db.get(Technicien, payload.technicien_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Technicien introuvable")
    formation = Formation(**payload.model_dump())
    db.add(formation)
    db.commit()
    db.refresh(formation)
    return formation


@router.patch("/{formation_id}", response_model=FormationRead)
def update_formation(
    formation_id: int,
    payload: FormationUpdate,
    db: Session = Depends(get_db),
    _: Technicien = Depends(require_chef),
) -> Formation:
    formation = db.get(Formation, formation_id)
    if formation is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Formation introuvable")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(formation, field, value)
    db.commit()
    db.refresh(formation)
    return formation


@router.delete("/{formation_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_formation(
    formation_id: int,
    db: Session = Depends(get_db),
    _: Technicien = Depends(require_chef),
) -> None:
    formation = db.get(Formation, formation_id)
    if formation is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Formation introuvable")
    db.delete(formation)
    db.commit()
