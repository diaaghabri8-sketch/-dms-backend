from collections.abc import Callable

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.security import decode_access_token
from app.database import get_db
from app.models.technicien import RoleTechnicien, Technicien

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> Technicien:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Identifiants invalides ou expirés",
        headers={"WWW-Authenticate": "Bearer"},
    )

    payload = decode_access_token(token)
    if payload is None:
        raise credentials_exception

    subject = payload.get("sub")
    if subject is None:
        raise credentials_exception

    try:
        technicien_id = int(subject)
    except (TypeError, ValueError):
        raise credentials_exception

    user = db.get(Technicien, technicien_id)
    if user is None or not user.is_active:
        raise credentials_exception

    return user


def require_role(*roles: RoleTechnicien) -> Callable[[Technicien], Technicien]:
    """Dependency factory: 403 si le rôle de l'utilisateur courant n'est pas dans `roles`."""

    def dependency(current_user: Technicien = Depends(get_current_user)) -> Technicien:
        if current_user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Permissions insuffisantes pour cette action",
            )
        return current_user

    return dependency


# Raccourci utilisé par la majorité des routers : chef d'équipe uniquement.
# NB: ADMIN n'est plus un synonyme du chef — c'est un rôle isolé dédié à la gestion du
# stock (équipements en réparation, pièces détachées), voir require_admin ci-dessous.
require_chef = require_role(RoleTechnicien.CHEF_EQUIPE)

# Raccourci pour les modules réservés à l'administrateur (stock).
require_admin = require_role(RoleTechnicien.ADMIN)

# Lecture du stock ouverte au chef d'équipe en plus de l'admin (écriture toujours admin-only) :
# le chef d'équipe doit pouvoir consulter réparations/vente/pièces sans pouvoir les modifier.
require_admin_or_chef = require_role(RoleTechnicien.ADMIN, RoleTechnicien.CHEF_EQUIPE)
