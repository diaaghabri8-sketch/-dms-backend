from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.database import get_db
from app.models.notification import Notification
from app.models.technicien import Technicien
from app.schemas.notification import NotificationRead

router = APIRouter(prefix="/notifications", tags=["notifications"], dependencies=[Depends(get_current_user)])


@router.get("", response_model=list[NotificationRead])
def list_notifications(
    db: Session = Depends(get_db),
    current_user: Technicien = Depends(get_current_user),
    limit: int = Query(20, ge=1, le=200),
    non_lues: bool | None = Query(None),
) -> list[Notification]:
    """Toujours filtré sur le destinataire connecté — aucun paramètre pour cibler un autre
    utilisateur, afin d'exclure toute fuite entre comptes."""
    query = db.query(Notification).filter(Notification.destinataire_id == current_user.id)
    if non_lues is True:
        query = query.filter(Notification.lu_le.is_(None))
    elif non_lues is False:
        query = query.filter(Notification.lu_le.isnot(None))
    return query.order_by(Notification.created_at.desc()).limit(limit).all()


@router.get("/non-lues/count")
def count_non_lues(
    db: Session = Depends(get_db),
    current_user: Technicien = Depends(get_current_user),
) -> dict[str, int]:
    count = (
        db.query(Notification)
        .filter(Notification.destinataire_id == current_user.id, Notification.lu_le.is_(None))
        .count()
    )
    return {"count": count}


@router.patch("/{notification_id}/lu", response_model=NotificationRead)
def marquer_lue(
    notification_id: int,
    db: Session = Depends(get_db),
    current_user: Technicien = Depends(get_current_user),
) -> Notification:
    notification = db.get(Notification, notification_id)
    if notification is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Notification introuvable")
    if notification.destinataire_id != current_user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Cette notification ne vous appartient pas")
    if notification.lu_le is None:
        notification.lu_le = datetime.now(timezone.utc)
        db.commit()
        db.refresh(notification)
    return notification


@router.patch("/lu-tout", response_model=list[NotificationRead])
def marquer_tout_lu(
    db: Session = Depends(get_db),
    current_user: Technicien = Depends(get_current_user),
) -> list[Notification]:
    non_lues = (
        db.query(Notification)
        .filter(Notification.destinataire_id == current_user.id, Notification.lu_le.is_(None))
        .all()
    )
    now = datetime.now(timezone.utc)
    for notification in non_lues:
        notification.lu_le = now
    db.commit()
    return non_lues
