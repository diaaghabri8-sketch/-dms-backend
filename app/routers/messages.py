from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.core.ws_manager import manager
from app.database import get_db
from app.models.conversation import Conversation
from app.models.message import Message
from app.models.technicien import RoleTechnicien, Technicien
from app.schemas.message import MessageCreate, MessageRead

router = APIRouter(prefix="/messages", tags=["messages"], dependencies=[Depends(get_current_user)])


def _require_participant(conversation_id: int, current_user: Technicien, db: Session) -> Conversation:
    conversation = db.get(Conversation, conversation_id)
    if conversation is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Conversation introuvable")
    if current_user not in conversation.participants:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Vous ne participez pas à cette conversation")
    return conversation


@router.get("", response_model=list[MessageRead])
def list_messages(
    conversation_id: int = Query(...),
    db: Session = Depends(get_db),
    current_user: Technicien = Depends(get_current_user),
) -> list[Message]:
    _require_participant(conversation_id, current_user, db)
    return (
        db.query(Message)
        .filter(Message.conversation_id == conversation_id)
        .order_by(Message.envoye_le)
        .all()
    )


# Même chemin littéral avant /{message_id} que dans les autres routers du projet (voir
# notifications.py, equipements.py) — pas de conflit ici (aucun autre GET paramétré sur ce
# router), mais on garde la convention pour la lisibilité.
@router.get("/non-lues/count")
def count_non_lues(
    db: Session = Depends(get_db),
    current_user: Technicien = Depends(get_current_user),
) -> dict[str, int]:
    """Nombre de messages non lus, toutes conversations de l'utilisateur confondues — pas
    envoyés par lui-même. Ajouté pour le badge de la messagerie (mobile, voir SUIVI_PROJET.md) :
    aucun endpoint équivalent n'existait déjà (contrairement aux notifications), et calculer ce
    total côté client aurait demandé de récupérer l'historique complet de chaque conversation à
    chaque rafraîchissement — coûteux et hors de propos ici."""
    count = (
        db.query(Message)
        .join(Conversation, Message.conversation_id == Conversation.id)
        .filter(
            Conversation.participants.any(Technicien.id == current_user.id),
            Message.expediteur_id != current_user.id,
            Message.lu_le.is_(None),
        )
        .count()
    )
    return {"count": count}


@router.post("", response_model=MessageRead, status_code=status.HTTP_201_CREATED)
async def create_message(
    payload: MessageCreate,
    db: Session = Depends(get_db),
    current_user: Technicien = Depends(get_current_user),
) -> Message:
    _require_participant(payload.conversation_id, current_user, db)

    message = Message(
        conversation_id=payload.conversation_id,
        expediteur_id=current_user.id,
        contenu=payload.contenu,
    )
    db.add(message)
    db.commit()
    db.refresh(message)

    data = MessageRead.model_validate(message)
    await manager.broadcast(payload.conversation_id, data.model_dump(mode="json"))
    return message


@router.patch("/{message_id}", response_model=MessageRead)
def mark_message_read(
    message_id: int,
    db: Session = Depends(get_db),
    current_user: Technicien = Depends(get_current_user),
) -> Message:
    message = db.get(Message, message_id)
    if message is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Message introuvable")
    _require_participant(message.conversation_id, current_user, db)
    if message.lu_le is None:
        message.lu_le = datetime.now(timezone.utc)
        db.commit()
        db.refresh(message)
    return message


@router.delete("/{message_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_message(
    message_id: int,
    db: Session = Depends(get_db),
    current_user: Technicien = Depends(get_current_user),
) -> None:
    message = db.get(Message, message_id)
    if message is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Message introuvable")
    is_chef = current_user.role == RoleTechnicien.CHEF_EQUIPE
    if message.expediteur_id != current_user.id and not is_chef:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Vous ne pouvez supprimer que vos propres messages")
    db.delete(message)
    db.commit()
