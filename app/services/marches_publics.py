"""Veille automatique des marchés publics tunisiens liés au matériel médical —
marchespublics.gov.tn UNIQUEMENT (jamais TUNEPS.tn, qui nécessite une connexion, hors périmètre
de cette fonctionnalité, voir SUIVI_PROJET.md).

Logique reprise et validée par un prototype d'exploration isolé (`scripts/exploration/
marches_publics/`, voir SUIVI_PROJET.md) avant intégration ici : la page de liste ne contient
aucun résultat en HTML statique — les données viennent d'un appel AJAX server-side DataTables
sur la MÊME URL, qui renvoie du JSON directement exploitable. `keywords` filtre déjà côté
serveur (confirmé pendant l'exploration : 95835 résultats au total, 15 pour "respirateur").

Bonnes pratiques respectées (mêmes qu'en exploration) : User-Agent identifiable, délai entre
chaque requête HTTP (`settings.APPELS_OFFRES_DELAI_SECONDES`), une seule session HTTP par scan.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.appel_offre import AppelOffre
from app.models.technicien import RoleTechnicien
from app.schemas.appel_offre import ScanResult
from app.services.notifications import notifier_role
from app.models.notification import TypeNotification

logger = logging.getLogger(__name__)

BASE_URL = "https://www.marchespublics.gov.tn"
LISTING_PATH = "/fr/appels-doffres"
USER_AGENT = "Mozilla/5.0 (compatible; DMS-VeilleMarchesPublics/1.0; +contact: diaaghabri8@gmail.com)"
MAX_RESULTS_PER_KEYWORD = 100  # garde-fou — un terme trop générique ne doit pas tout aspirer
PAGE_SIZE = 20


def _make_session() -> requests.Session:
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT, "Accept-Language": "fr"})
    session.get(f"{BASE_URL}{LISTING_PATH}", timeout=20)
    time.sleep(settings.APPELS_OFFRES_DELAI_SECONDES)
    return session


def _fetch_listing_page(session: requests.Session, keyword: str, start: int) -> tuple[list[dict], int]:
    columns = ["id", "organization.name_fr", "title_fr", "tenderPeriod_endDate", "publication_date"]
    params: dict[str, str] = {
        "draw": "1",
        "start": str(start),
        "length": str(PAGE_SIZE),
        "order[0][column]": "4",
        "order[0][dir]": "desc",
        "keywords": keyword,
    }
    for i, col in enumerate(columns):
        params[f"columns[{i}][data]"] = col

    response = session.get(
        f"{BASE_URL}{LISTING_PATH}",
        params=params,
        headers={"X-Requested-With": "XMLHttpRequest", "Accept": "application/json"},
        timeout=20,
    )
    response.raise_for_status()
    payload = response.json()
    return payload.get("data", []), payload.get("recordsFiltered", 0)


def _fetch_lien_pdf(session: requests.Session, id_externe: str) -> str | None:
    response = session.get(f"{BASE_URL}{LISTING_PATH}/{id_externe}", timeout=20)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "lxml")
    pdf_link = soup.find("a", href=lambda h: h and h.endswith(".pdf"))
    return pdf_link["href"] if pdf_link else None


_TUNIS_TZ = ZoneInfo("Africa/Tunis")


def _parse_date(value: str | None) -> datetime | None:
    """Le site renvoie des dates naïves en heure locale tunisienne (`Africa/Tunis`, UTC+1 fixe,
    pas de changement d'heure d'été depuis 2009) — jamais en UTC. Les interpréter comme UTC
    directement introduirait le même bug de décalage d'une heure déjà rencontré et corrigé une
    fois sur ce projet (voir `UTCDateTime`/`db_types.py` et SUIVI_PROJET.md) : on attache donc
    explicitement le fuseau tunisien avant de convertir en UTC, seul format que `UTCDateTime`
    accepte en écriture."""
    if not value:
        return None
    try:
        naive = datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return None
    return naive.replace(tzinfo=_TUNIS_TZ).astimezone(timezone.utc)


def run_scan(db: Session) -> ScanResult:
    """Une exécution complète de la veille — un mot-clé à la fois, dédoublonnage sur
    `id_externe` (contre la base ET contre les avis déjà créés plus tôt dans ce même run, pour
    le cas où deux mots-clés matchent le même avis), notification admin+chef pour chaque
    nouvel avis réellement enregistré. Jamais de mise à jour d'un avis existant — un avis ne
    change plus une fois détecté, seul son `statut` est modifiable, à la main, via l'écran web."""
    mots_cles = settings.appels_offres_mots_cles_list
    session = _make_session()

    existing_ids = {row.id_externe for row in db.query(AppelOffre.id_externe).all()}
    created_this_run: dict[str, AppelOffre] = {}

    avis_examines = 0
    doublons_ignores = 0
    avis_expires_ignores = 0
    now = datetime.now(timezone.utc)

    for keyword in mots_cles:
        start = 0
        while start < MAX_RESULTS_PER_KEYWORD:
            rows, records_filtered = _fetch_listing_page(session, keyword, start)
            time.sleep(settings.APPELS_OFFRES_DELAI_SECONDES)
            if not rows:
                break

            for row in rows:
                avis_examines += 1
                id_externe = row["id"]
                date_limite = _parse_date(row.get("tenderPeriod_endDate"))

                if date_limite is not None and date_limite < now:
                    avis_expires_ignores += 1
                    continue

                if id_externe in created_this_run:
                    # Même avis déjà créé plus tôt dans ce run par un autre mot-clé — on
                    # complète juste la traçabilité, pas une nouvelle ligne.
                    existing = created_this_run[id_externe]
                    if keyword not in existing.mot_cle_trouve.split(", "):
                        existing.mot_cle_trouve = f"{existing.mot_cle_trouve}, {keyword}"
                    doublons_ignores += 1
                    continue

                if id_externe in existing_ids:
                    doublons_ignores += 1
                    continue

                lien_pdf = _fetch_lien_pdf(session, id_externe)
                time.sleep(settings.APPELS_OFFRES_DELAI_SECONDES)

                appel = AppelOffre(
                    id_externe=id_externe,
                    titre=row.get("title_fr") or "(sans titre)",
                    organisme_acheteur=(row.get("organization") or {}).get("name_fr") or "",
                    date_publication=_parse_date(row.get("publication_date")),
                    date_limite_offres=date_limite,
                    lien_avis=f"{BASE_URL}{LISTING_PATH}/{id_externe}",
                    lien_pdf=lien_pdf,
                    mot_cle_trouve=keyword,
                )
                db.add(appel)
                created_this_run[id_externe] = appel
                existing_ids.add(id_externe)

            start += PAGE_SIZE
            if start >= records_filtered:
                break

    db.flush()  # obtenir les id/titre finaux avant de construire les messages de notification

    for appel in created_this_run.values():
        message = f"Nouvel appel d'offres détecté : {appel.titre[:150]} ({appel.mot_cle_trouve})"
        notifier_role(db, RoleTechnicien.ADMIN, TypeNotification.APPEL_OFFRE_DETECTE, message)
        notifier_role(db, RoleTechnicien.CHEF_EQUIPE, TypeNotification.APPEL_OFFRE_DETECTE, message)

    db.commit()

    result = ScanResult(
        mots_cles_scannes=mots_cles,
        avis_examines=avis_examines,
        nouveaux_enregistres=len(created_this_run),
        doublons_ignores=doublons_ignores,
        avis_expires_ignores=avis_expires_ignores,
    )
    logger.info(
        "Veille marchés publics : %d avis examinés, %d nouveaux, %d doublons, %d expirés.",
        result.avis_examines,
        result.nouveaux_enregistres,
        result.doublons_ignores,
        result.avis_expires_ignores,
    )
    return result
