"""Création/réinitialisation de compte par un admin/chef — email généré (convention
prenom.nom@{ACCOUNT_EMAIL_DOMAIN}, dédupliqué) et mot de passe temporaire aléatoire. Aucun envoi
automatique (email/SMTP) : les identifiants sont affichés une fois côté web (voir
routers/techniciens.py, TechnicianPanel.jsx) et transmis manuellement par l'admin/chef, voir
SUIVI_PROJET.md. Pas d'auto-inscription publique : ces comptes sont toujours créés par un tiers
habilité, jamais par la personne elle-même.
"""

import re
import secrets
import string
import unicodedata

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.technicien import Technicien

# Alphabet sans caractères ambigus (0/O, 1/l/I) — mot de passe temporaire lu/retapé une seule
# fois par la personne avant qu'elle ne le change (doit_changer_mdp), la lisibilité prime.
_PASSWORD_ALPHABET = "".join(c for c in string.ascii_letters + string.digits if c not in "0O1lI")
_PASSWORD_SYMBOLS = "!@#$%*?"


def _slugify(value: str) -> str:
    """'Émilie De La Croix' -> 'emiliedelacroix' — retire accents/espaces/ponctuation, pour un
    identifiant d'email stable même sur un nom composé."""
    normalized = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]", "", normalized.lower())


def generate_initiales(prenom: str, nom: str) -> str:
    parts = [p for p in (prenom.strip(), nom.strip()) if p]
    initiales = "".join(p[0] for p in parts).upper()
    return (initiales or "??")[:4]


def generate_temp_password(length: int = 12) -> str:
    # Au moins un symbole et un chiffre garantis, le reste tiré de l'alphabet lisible —
    # `secrets` (pas `random`) : ce mot de passe protège un vrai compte, jamais de PRNG non
    # cryptographique ici.
    chars = [secrets.choice(_PASSWORD_ALPHABET) for _ in range(length - 2)]
    chars.append(secrets.choice(string.digits))
    chars.append(secrets.choice(_PASSWORD_SYMBOLS))
    secrets.SystemRandom().shuffle(chars)
    return "".join(chars)


def generate_unique_email(db: Session, prenom: str, nom: str) -> str:
    """prenom.nom@domaine, ou prenom.nom2@domaine / nom3 / ... si déjà pris — jamais un email
    déjà attribué, y compris à un compte désactivé (l'unicité reste globale, contrainte DB)."""
    base_prenom = _slugify(prenom) or "compte"
    base_nom = _slugify(nom)
    domain = settings.ACCOUNT_EMAIL_DOMAIN

    suffix = 1
    while True:
        local = f"{base_prenom}.{base_nom}" if base_nom else base_prenom
        if suffix > 1:
            local = f"{local}{suffix}"
        candidate = f"{local}@{domain}"
        exists = db.query(Technicien.id).filter(Technicien.email == candidate).first() is not None
        if not exists:
            return candidate
        suffix += 1
