"""Cree ou met a jour les 3 comptes de demo (idempotent)."""

from app.core.security import hash_password
from app.database import SessionLocal
from app.models.technicien import RoleTechnicien, StatutTechnicien, Technicien

DEMO_ACCOUNTS = [
    {
        "email": "chef@dms.tn",
        "role": RoleTechnicien.CHEF_EQUIPE,
        "nom": "Nadia Chef",
        "initiales": "NC",
        "specialite": "Gestion equipe",
        "telephone": "+216 20 000 001",
    },
    {
        "email": "admin@dms.tn",
        "role": RoleTechnicien.ADMIN,
        "nom": "Sami Admin",
        "initiales": "SA",
        "specialite": "Administration stock",
        "telephone": "+216 20 000 002",
    },
    {
        "email": "tech@dms.tn",
        "role": RoleTechnicien.TECHNICIEN,
        "nom": "Karim Technicien",
        "initiales": "KT",
        "specialite": "Maintenance generale",
        "telephone": "+216 20 000 003",
    },
]

PASSWORD = "password123"


def main() -> None:
    db = SessionLocal()
    try:
        for account in DEMO_ACCOUNTS:
            existing = db.query(Technicien).filter(Technicien.email == account["email"]).first()
            if existing:
                existing.hashed_password = hash_password(PASSWORD)
                existing.role = account["role"]
                existing.is_active = True
                print(f"Mis a jour: {account['email']} ({account['role'].value})")
            else:
                db.add(
                    Technicien(
                        email=account["email"],
                        hashed_password=hash_password(PASSWORD),
                        role=account["role"],
                        is_active=True,
                        nom=account["nom"],
                        initiales=account["initiales"],
                        specialite=account["specialite"],
                        telephone=account["telephone"],
                        statut=StatutTechnicien.DISPONIBLE,
                    )
                )
                print(f"Cree: {account['email']} ({account['role'].value})")
        db.commit()
    finally:
        db.close()


if __name__ == "__main__":
    main()
