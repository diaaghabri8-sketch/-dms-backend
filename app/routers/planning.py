from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, require_chef
from app.database import get_db
from app.models.planning import Planning
from app.models.technicien import Technicien
from app.schemas.planning import PlanningCreate, PlanningRead, PlanningUpdate

router = APIRouter(prefix="/planning", tags=["planning"], dependencies=[Depends(get_current_user)])


@router.get("", response_model=list[PlanningRead])
def list_plannings(db: Session = Depends(get_db)) -> list[Planning]:
    return db.query(Planning).order_by(Planning.date_prochaine).all()


@router.get("/{planning_id}", response_model=PlanningRead)
def get_planning(planning_id: int, db: Session = Depends(get_db)) -> Planning:
    planning = db.get(Planning, planning_id)
    if planning is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Planning introuvable")
    return planning


@router.post("", response_model=PlanningRead, status_code=status.HTTP_201_CREATED)
def create_planning(
    payload: PlanningCreate,
    db: Session = Depends(get_db),
    _: Technicien = Depends(require_chef),
) -> Planning:
    planning = Planning(**payload.model_dump())
    db.add(planning)
    db.commit()
    db.refresh(planning)
    return planning


@router.patch("/{planning_id}", response_model=PlanningRead)
def update_planning(
    planning_id: int,
    payload: PlanningUpdate,
    db: Session = Depends(get_db),
    _: Technicien = Depends(require_chef),
) -> Planning:
    planning = db.get(Planning, planning_id)
    if planning is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Planning introuvable")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(planning, field, value)
    db.commit()
    db.refresh(planning)
    return planning


@router.delete("/{planning_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_planning(
    planning_id: int,
    db: Session = Depends(get_db),
    _: Technicien = Depends(require_chef),
) -> None:
    planning = db.get(Planning, planning_id)
    if planning is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Planning introuvable")
    db.delete(planning)
    db.commit()
