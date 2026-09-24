from fastapi import APIRouter, WebSocket, WebSocketDisconnect, status

from app.core.security import decode_access_token
from app.core.ws_manager import manager
from app.database import SessionLocal
from app.models.conversation import Conversation
from app.models.message import Message
from app.models.technicien import Technicien
from app.schemas.message import MessageRead

router = APIRouter(tags=["websocket"])


@router.websocket("/ws/chat/{conversation_id}")
async def ws_chat(websocket: WebSocket, conversation_id: int, token: str) -> None:
    """Authentification via ?token=<JWT> (les WebSockets navigateur ne supportent pas les headers custom)."""
    payload = decode_access_token(token)
    subject = payload.get("sub") if payload else None
    if subject is None:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    db = SessionLocal()
    try:
        try:
            user = db.get(Technicien, int(subject))
        except (TypeError, ValueError):
            user = None

        conversation = db.get(Conversation, conversation_id)
        if (
            user is None
            or not user.is_active
            or conversation is None
            or user not in conversation.participants
        ):
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return

        await manager.connect(conversation_id, websocket)
        try:
            while True:
                data = await websocket.receive_json()
                contenu = str((data or {}).get("contenu", "")).strip()
                if not contenu:
                    continue

                message = Message(conversation_id=conversation_id, expediteur_id=user.id, contenu=contenu)
                db.add(message)
                db.commit()
                db.refresh(message)

                out = MessageRead.model_validate(message).model_dump(mode="json")
                await manager.broadcast(conversation_id, out)
        except WebSocketDisconnect:
            manager.disconnect(conversation_id, websocket)
    finally:
        db.close()
