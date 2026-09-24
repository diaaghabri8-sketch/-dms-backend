"""Notifications automatiques envoyées via la messagerie existante (Conversation/Message +
WebSocket déjà en place) — voir SUIVI_PROJET.md pour le choix de ce mécanisme plutôt
qu'`Evenement` : ce dernier est un fil d'activité global sans notion de destinataire (aucun
champ liant un événement à un utilisateur précis) et n'a jamais été alimenté automatiquement
nulle part dans le code — toujours créé à la main par le chef via `POST /evenements`. La
messagerie, elle, a déjà tout ce qu'il faut pour cibler précisément un utilisateur : une
conversation entre participants, livrée en temps réel via le WebSocket existant.
"""

from sqlalchemy.orm import Session

from app.core.ws_manager import manager
from app.models.conversation import Conversation
from app.models.intervention import Intervention
from app.models.message import Message
from app.models.technicien import Technicien
from app.schemas.message import MessageRead


async def notifier_technicien_devis_envoye(db: Session, intervention: Intervention, expediteur_id: int) -> None:
    """Message automatique au technicien assigné à l'intervention, à la création d'un devis —
    il attend cette décision client pour savoir s'il peut démarrer son travail. Réutilise une
    conversation 1:1 existante avec l'expéditeur (l'admin qui a créé le devis) si elle existe,
    sinon en crée une, exactement comme le ferait POST /conversations puis POST /messages."""
    technicien_id = intervention.technicien_id
    if technicien_id == expediteur_id:
        # Cas marginal (l'admin est aussi l'assigné de l'intervention, possible depuis que
        # technicien_id peut référencer n'importe quel rôle) — pas de message à soi-même.
        return

    conversation = (
        db.query(Conversation)
        .filter(Conversation.is_group.is_(False))
        .filter(Conversation.participants.any(Technicien.id == technicien_id))
        .filter(Conversation.participants.any(Technicien.id == expediteur_id))
        .first()
    )
    if conversation is None:
        technicien = db.get(Technicien, technicien_id)
        expediteur = db.get(Technicien, expediteur_id)
        conversation = Conversation(is_group=False, participants=[expediteur, technicien])
        db.add(conversation)
        db.flush()  # obtenir conversation.id avant de créer le message

    message = Message(
        conversation_id=conversation.id,
        expediteur_id=expediteur_id,
        contenu=f"Le devis de l'intervention {intervention.id} a été envoyé au client.",
    )
    db.add(message)
    db.commit()
    db.refresh(message)

    data = MessageRead.model_validate(message)
    await manager.broadcast(conversation.id, data.model_dump(mode="json"))
