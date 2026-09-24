from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.database import get_db
from app.models.conversation import Conversation
from app.models.technicien import Technicien
from app.schemas.conversation import ConversationCreate, ConversationRead, ConversationUpdate

router = APIRouter(prefix="/conversations", tags=["conversations"], dependencies=[Depends(get_current_user)])


def _get_participant_conversation(conversation_id: int, current_user: Technicien, db: Session) -> Conversation:
    conversation = db.get(Conversation, conversation_id)
    if conversation is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Conversation introuvable")
    if current_user not in conversation.participants:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Vous ne participez pas à cette conversation")
    return conversation


@router.get("", response_model=list[ConversationRead])
def list_conversations(
    db: Session = Depends(get_db),
    current_user: Technicien = Depends(get_current_user),
) -> list[Conversation]:
    return (
        db.query(Conversation)
        .filter(Conversation.participants.any(Technicien.id == current_user.id))
        .order_by(Conversation.updated_at.desc())
        .all()
    )


@router.get("/{conversation_id}", response_model=ConversationRead)
def get_conversation(
    conversation_id: int,
    db: Session = Depends(get_db),
    current_user: Technicien = Depends(get_current_user),
) -> Conversation:
    return _get_participant_conversation(conversation_id, current_user, db)


@router.post("", response_model=ConversationRead, status_code=status.HTTP_201_CREATED)
def create_conversation(
    payload: ConversationCreate,
    db: Session = Depends(get_db),
    current_user: Technicien = Depends(get_current_user),
) -> Conversation:
    participant_ids = set(payload.participant_ids) | {current_user.id}
    participants = db.query(Technicien).filter(Technicien.id.in_(participant_ids)).all()
    if len(participants) != len(participant_ids):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Un ou plusieurs participants sont introuvables")

    conversation = Conversation(nom=payload.nom, is_group=payload.is_group, participants=participants)
    db.add(conversation)
    db.commit()
    db.refresh(conversation)
    return conversation


@router.patch("/{conversation_id}", response_model=ConversationRead)
def update_conversation(
    conversation_id: int,
    payload: ConversationUpdate,
    db: Session = Depends(get_db),
    current_user: Technicien = Depends(get_current_user),
) -> Conversation:
    conversation = _get_participant_conversation(conversation_id, current_user, db)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(conversation, field, value)
    db.commit()
    db.refresh(conversation)
    return conversation


@router.delete("/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_conversation(
    conversation_id: int,
    db: Session = Depends(get_db),
    current_user: Technicien = Depends(get_current_user),
) -> None:
    conversation = _get_participant_conversation(conversation_id, current_user, db)
    db.delete(conversation)
    db.commit()
