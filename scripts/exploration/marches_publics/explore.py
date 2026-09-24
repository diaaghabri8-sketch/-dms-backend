"""Script d'EXPLORATION uniquement — veille marchés publics tunisiens (marchespublics.gov.tn),
matériel médical. Pas intégré au backend, pas de table, pas de notification : sert seulement à
valider que le scraping est possible et fiable avant d'aller plus loin (voir SUIVI_PROJET.md,
demande de l'utilisateur du 23/09/2026).

Cible : www.marchespublics.gov.tn — PAS TUNEPS.tn (nécessite une connexion, hors périmètre).

Dépendances (installées uniquement dans ce venv d'exploration, jamais ajoutées à
requirements.txt du projet principal — voir la demande explicite de ne rien modifier dans le
projet principal) : requests, beautifulsoup4, lxml.

Bonnes pratiques respectées :
- User-Agent identifiable (nom du projet + contact), jamais un User-Agent de navigateur usurpé.
- Délai (`REQUEST_DELAY_SECONDS`) entre chaque requête HTTP, y compris entre les pages de détail.
- `robots.txt` vérifié avant d'écrire ce script : `User-agent: *` / `Disallow:` (vide) — aucune
  restriction pour aucun user-agent, tout le site est explicitement ouvert au crawl.
- Une seule session HTTP réutilisée (cookies), pas une connexion par requête.
"""

from __future__ import annotations

import sys
import time
from dataclasses import dataclass, field

import requests
from bs4 import BeautifulSoup

# Certains titres d'avis sont uniquement en arabe (voir constat 4 du rapport) — la console
# Windows par défaut (cp1252) ne peut pas les afficher sans ce reconfigure.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

BASE_URL = "https://www.marchespublics.gov.tn"
LISTING_PATH = "/fr/appels-doffres"
USER_AGENT = "Mozilla/5.0 (compatible; DMS-VeilleMarchesPublics/0.1; +contact: diaaghabri8@gmail.com)"
REQUEST_DELAY_SECONDS = 2.0  # entre chaque requête HTTP, liste comme détail


def make_session() -> requests.Session:
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT, "Accept-Language": "fr"})
    # Un premier GET sur la page HTML pose les cookies de session (XSRF-TOKEN, haicop_session,
    # ...) nécessaires ensuite pour l'appel JSON — sans lui, l'appel direct à l'endpoint AJAX
    # fonctionne quand même en pratique (testé), mais on reste prudent : imiter le vrai parcours
    # d'un navigateur plutôt qu'appeler l'API "à froid".
    session.get(f"{BASE_URL}{LISTING_PATH}", timeout=20)
    time.sleep(REQUEST_DELAY_SECONDS)
    return session


@dataclass
class TenderSummary:
    id: str
    title_fr: str
    organization: str
    tender_period_end_date: str | None
    publication_date: str | None
    reserved_sme: bool

    @property
    def detail_url(self) -> str:
        return f"{BASE_URL}{LISTING_PATH}/{self.id}"


def fetch_listing(
    session: requests.Session, *, keywords: str = "", start: int = 0, length: int = 20
) -> tuple[list[TenderSummary], int, int]:
    """Appelle directement l'endpoint JSON server-side de la DataTable (même URL que la page
    HTML, mais en AJAX — voir DETAIL_FINDINGS.md) plutôt que de parser le HTML de la liste, qui
    ne contient elle-même aucune ligne de résultat au chargement initial (tout est chargé par ce
    même appel JS). Retourne (résultats, recordsTotal, recordsFiltered)."""
    # Format `columns[i][data]` attendu par DataTables server-side (protocole standard) —
    # reproduit à l'identique de ce qu'envoie le vrai <script> de la page (voir liste.html
    # capturé pendant l'exploration).
    columns = [
        "id",
        "organization.name_fr",
        "title_fr",
        "tenderPeriod_endDate",
        "publication_date",
        "reservedSME",
    ]
    params: dict[str, str] = {
        "draw": "1",
        "start": str(start),
        "length": str(length),
        "order[0][column]": "4",  # publication_date
        "order[0][dir]": "desc",
    }
    for i, col in enumerate(columns):
        params[f"columns[{i}][data]"] = col
    if keywords:
        params["keywords"] = keywords

    response = session.get(
        f"{BASE_URL}{LISTING_PATH}",
        params=params,
        headers={"X-Requested-With": "XMLHttpRequest", "Accept": "application/json"},
        timeout=20,
    )
    response.raise_for_status()
    payload = response.json()

    results = [
        TenderSummary(
            id=row["id"],
            title_fr=row.get("title_fr") or "",
            organization=(row.get("organization") or {}).get("name_fr") or "",
            tender_period_end_date=row.get("tenderPeriod_endDate"),
            publication_date=row.get("publication_date"),
            reserved_sme=bool((row.get("plan") or {}).get("reservedSME")),
        )
        for row in payload.get("data", [])
    ]
    return results, payload.get("recordsTotal", 0), payload.get("recordsFiltered", 0)


@dataclass
class TenderDetail:
    id: str
    objet: str = ""
    descriptif: str = ""
    etat: str = ""
    date_publication: str = ""
    procedure_passation: str = ""
    type_lots: str = ""
    nombre_lots: str = ""
    mode_financement: str = ""
    type_commande: str = ""
    lieu_cahier_charges: str = ""  # "TUNEPS" dans les 2 échantillons testés — voir constat
    date_limite_offres: str = ""
    pdf_avis_url: str | None = None
    lots: list[dict[str, str]] = field(default_factory=list)


def _field_after(soup: BeautifulSoup, label: str) -> str:
    """Trouve le texte qui suit un <strong>/<h5> contenant exactement ce libellé — motif répété
    partout sur la page détail (voir detail1.html/detail2.html capturés pendant l'exploration)."""
    for tag in soup.find_all(["strong", "h5"]):
        if label in tag.get_text(strip=True):
            # Le texte utile est soit dans le prochain frère direct (<span>), soit dans le texte
            # restant du même bloc parent après la balise du libellé.
            sibling = tag.find_next_sibling()
            if sibling and sibling.name == "span":
                return sibling.get_text(strip=True)
            parent_text = tag.parent.get_text(" ", strip=True)
            return parent_text.replace(tag.get_text(strip=True), "", 1).strip()
    return ""


def fetch_detail(session: requests.Session, tender_id: str) -> TenderDetail:
    response = session.get(f"{BASE_URL}{LISTING_PATH}/{tender_id}", timeout=20)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "lxml")

    detail = TenderDetail(id=tender_id)
    detail.objet = _field_after(soup, "Objet")
    detail.descriptif = _field_after(soup, "Descriptif")
    detail.etat = _field_after(soup, "Etat")
    detail.date_publication = _field_after(soup, "Date de publication")
    detail.procedure_passation = _field_after(soup, "Procédure de passation")
    detail.type_lots = _field_after(soup, "Type de lots")
    detail.nombre_lots = _field_after(soup, "Nombre de lots")
    detail.mode_financement = _field_after(soup, "Mode de financement")
    detail.type_commande = _field_after(soup, "Type de commande")
    detail.lieu_cahier_charges = _field_after(soup, "Lieu de retrait ou téléchargement")
    detail.date_limite_offres = _field_after(soup, "Date limite de réception des offres")

    pdf_link = soup.find("a", href=lambda h: h and h.endswith(".pdf"))
    detail.pdf_avis_url = pdf_link["href"] if pdf_link else None

    for card in soup.select(".offre-card"):
        title = card.select_one(".title")
        lot = {
            "titre": title.get_text(" ", strip=True) if title else "",
            "texte": card.get_text(" ", strip=True),
        }
        detail.lots.append(lot)

    return detail


def main() -> None:
    session = make_session()

    print("=" * 70)
    print("1) LISTE — dernières annonces (sans filtre mot-clé)")
    print("=" * 70)
    results, total, filtered = fetch_listing(session, length=5)
    print(f"recordsTotal (toute la base, historique inclus) = {total}")
    for t in results:
        print(f"  {t.id} | {t.publication_date} | {t.organization[:40]:40} | {t.title_fr[:70]}")
    time.sleep(REQUEST_DELAY_SECONDS)

    print()
    print("=" * 70)
    print("2) LISTE — filtrée par mot-clé 'respirateur' (test du filtre serveur)")
    print("=" * 70)
    results_kw, total_kw, filtered_kw = fetch_listing(session, keywords="respirateur", length=10)
    print(f"recordsFiltered = {filtered_kw} (sur {total_kw} au total) pour keywords='respirateur'")
    for t in results_kw:
        print(f"  {t.id} | {t.publication_date} | fin: {t.tender_period_end_date} | {t.title_fr[:70]}")
    time.sleep(REQUEST_DELAY_SECONDS)

    print()
    print("=" * 70)
    print("3) DÉTAIL — 2 avis (le plus récent de la liste générale + un avis 'respirateur')")
    print("=" * 70)
    sample_ids = [results[0].id] if results else []
    sample_ids += [t.id for t in results_kw[:2]]

    for tender_id in sample_ids:
        detail = fetch_detail(session, tender_id)
        print(f"\n--- {tender_id} ---")
        print(f"  Objet               : {detail.objet}")
        print(f"  État                : {detail.etat}")
        print(f"  Procédure           : {detail.procedure_passation}")
        print(f"  Type de commande    : {detail.type_commande}")
        print(f"  Nb lots             : {detail.nombre_lots}")
        print(f"  Cahier des charges  : {detail.lieu_cahier_charges}")
        print(f"  Date limite offres  : {detail.date_limite_offres}")
        print(f"  PDF avis officiel   : {detail.pdf_avis_url}")
        print(f"  Lots ({len(detail.lots)}):")
        for lot in detail.lots:
            print(f"    - {lot['titre']}")
        time.sleep(REQUEST_DELAY_SECONDS)


if __name__ == "__main__":
    main()
