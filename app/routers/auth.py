from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.core.security import create_access_token, verify_password
from app.database import get_db
from app.models.technicien import Technicien
from app.routers.techniciens import build_technicien_read
from app.schemas.auth import Token
from app.schemas.technicien import TechnicienRead

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=Token)
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
) -> Token:
    """Le champ `username` du formulaire OAuth2 attend l'email du technicien."""
    user = db.query(Technicien).filter(Technicien.email == form_data.username).first()
    if user is None or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email ou mot de passe incorrect",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Compte désactivé")

    user.derniere_connexion = datetime.now(timezone.utc)
    db.commit()

    token = create_access_token(subject=str(user.id), extra_claims={"role": user.role.value})
    return Token(access_token=token)


@router.get("/me", response_model=TechnicienRead)
def read_me(
    current_user: Technicien = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TechnicienRead:
    return build_technicien_read(current_user, db)
