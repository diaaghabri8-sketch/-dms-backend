"""Notifications ciblées par destinataire (cloche) — voir SUIVI_PROJET.md pour le choix d'un
modèle dédié `Notification` plutôt qu'une évolution d'`Evenement` (fil global sans destinataire,
jamais alimenté automatiquement) ou de la messagerie (déjà utilisée pour "devis envoyé", gardée
telle quelle car cet événement-là appelle souvent une discussion, contrairement aux événements
à sens unique couverts ici).
"""

from sqlalchemy.orm import Session

from app.models.notification import Notification, TypeNotification
from app.models.technicien import RoleTechnicien, Technicien


def notifier(
    db: Session,
    destinataire_id: int,
    type: TypeNotification,
    message: str,
    intervention_id: str | None = None,
) -> Notification:
    notification = Notification(
        destinataire_id=destinataire_id,
        type=type,
        message=message,
        intervention_id=intervention_id,
    )
    db.add(notification)
    return notification


def notifier_role(
    db: Session,
    role: RoleTechnicien,
    type: TypeNotification,
    message: str,
    intervention_id: str | None = None,
) -> list[Notification]:
    """Diffuse à tous les comptes actifs d'un rôle donné — aucune relation hiérarchique
    technicien→chef n'existe dans le modèle actuel (rôle plat), donc "notifier le chef" ou
    "notifier l'admin" signifie notifier tous les comptes de ce rôle."""
    destinataires = (
        db.query(Technicien.id).filter(Technicien.role == role, Technicien.is_active.is_(True)).all()
    )
    return [
        notifier(db, destinataire_id, type, message, intervention_id)
        for (destinataire_id,) in destinataires
    ]
