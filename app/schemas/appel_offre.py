from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.appel_offre import StatutAppelOffre


class AppelOffreRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    id_externe: str
    titre: str
    organisme_acheteur: str
    date_publication: datetime | None
    date_limite_offres: datetime | None
    lien_avis: str
    lien_pdf: str | None
    mot_cle_trouve: str
    statut: StatutAppelOffre
    date_detection: datetime
    updated_at: datetime


class AppelOffreUpdate(BaseModel):
    """Seul le statut est modifiable manuellement — tout le reste vient de la veille
    automatique, jamais édité à la main."""

    statut: StatutAppelOffre


class ScanResult(BaseModel):
    """Résumé d'une exécution de la veille (planifiée ou déclenchée manuellement)."""

    mots_cles_scannes: list[str]
    avis_examines: int
    nouveaux_enregistres: int
    doublons_ignores: int
    avis_expires_ignores: int
