"""Génération des PDF justificatifs du workflow intervention (Phase 3).

Quatre documents, générés automatiquement et rattachés à l'intervention via
`InterventionDocument` :
- diagnostic (après PATCH /interventions/{id}/diagnostic)
- devis (après POST /interventions/{id}/devis)
- rapport_final (après que l'intervention passe à `statut_workflow=termine`)
- bon_restitution (à la création de la tâche de restitution, POST
  /equipements-reparation/{id}/restitution — pas à sa validation, le technicien doit l'avoir en
  main en se déplaçant chez le client ; sans aucune date/heure comme le diagnostic, et avec un
  cadre vide pour la signature/cachet du client)

Historique complet des étapes (Phase 6) : `Intervention.date_diagnostic`,
`date_pieces_identifiees`, `date_travail_demarre`, `date_terminee`, combinées à `created_at`
(appel reçu) et `Devis.date_creation`/`date_decision_client` (devis émis/décision client) —
ces horodatages internes ne sont plus affichés dans aucun PDF (retirés du rapport_final,
document remis au client), seulement dans la fiche détail interne côté frontend
(`InterventionDetailPanel.jsx`, `HistoriqueSection`).

Logo DMS (`app/assets/logo-dms.png`, copie backend autonome de l'asset frontend — voir
SUIVI_PROJET.md) : uniquement en en-tête des 3 PDF (`_header`) — la 2e occurrence, plus
petite, initialement ajoutée sous la section diagnostic a été retirée successivement du
rapport_final puis du diagnostic (voir SUIVI_PROJET.md), il n'y en a donc plus nulle part.

Horodatage de génération ("généré le...", sous-titre de `_header`) : absent du PDF
diagnostic (`show_date=False`, document sans aucune date/heure affichée) ; toujours présent
sur devis et rapport_final.
"""

from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from sqlalchemy.orm import Session

from app.core.config import STORAGE_DIR
from app.models.devis import Devis
from app.models.equipement_reparation import EquipementAttenteReparation
from app.models.intervention import Intervention
from app.models.intervention_document import InterventionDocument, TypeDocument
from app.models.piece_necessaire import PieceNecessaire
from app.services.equipement_label import equipements_label

ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets"
LOGO_PATH = ASSETS_DIR / "logo-dms.png"

STYLES = getSampleStyleSheet()
TITLE_STYLE = ParagraphStyle("TitreDMS", parent=STYLES["Title"], fontSize=18, spaceAfter=4)
SUBTITLE_STYLE = ParagraphStyle("SousTitreDMS", parent=STYLES["Normal"], textColor=colors.grey, spaceAfter=16)
SECTION_STYLE = ParagraphStyle("SectionDMS", parent=STYLES["Heading2"], spaceBefore=14, spaceAfter=6)
BODY_STYLE = STYLES["Normal"]

DOCUMENTS_SUBDIR = "documents"

STATUT_DEVIS_LABELS = {
    "brouillon": "Brouillon",
    "envoye": "Envoyé",
    "accepte": "Accepté",
    "refuse": "Refusé",
}


def _document_dir(intervention_id: str) -> Path:
    directory = STORAGE_DIR / "interventions" / intervention_id / DOCUMENTS_SUBDIR
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def _document_url(intervention_id: str, filename: str) -> str:
    return f"/storage/interventions/{intervention_id}/{DOCUMENTS_SUBDIR}/{filename}"


def _resolve_storage_path(url: str) -> Path | None:
    """Reconstruit le chemin disque d'une ressource /storage/... (ex: photo_url)."""
    prefix = "/storage/"
    if not url.startswith(prefix):
        return None
    path = STORAGE_DIR / url[len(prefix) :]
    return path if path.is_file() else None


def _kv_table(rows: list[tuple[str, str]]) -> Table:
    data = [[Paragraph(f"<b>{label}</b>", BODY_STYLE), Paragraph(value or "—", BODY_STYLE)] for label, value in rows]
    table = Table(data, colWidths=[5 * cm, 11 * cm])
    table.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    return table


def _logo_image(width: float, height: float) -> Image | Spacer:
    """Logo DMS, mis à l'échelle en conservant ses proportions (image 585×334, ratio ~1.75) —
    dégrade silencieusement en espace vide si le fichier est absent plutôt que de faire échouer
    toute la génération du PDF pour un élément décoratif."""
    if not LOGO_PATH.is_file():
        return Spacer(width, height)
    logo = Image(str(LOGO_PATH), width=width, height=height, kind="proportional")
    # Image est centré par défaut dans Platypus — le reste du document est aligné à gauche,
    # donc un logo centré détonnerait visuellement en dehors de l'en-tête (où il est en
    # première colonne d'une table, l'alignement par défaut n'y joue aucun rôle).
    logo.hAlign = "LEFT"
    return logo


def _header(story: list, title: str, intervention: Intervention, show_date: bool = True) -> None:
    """En-tête commune aux 3 PDF : logo DMS en haut à gauche, aligné avec le titre sur la même
    ligne (table 2 colonnes sans bordure — Platypus n'a pas d'autre façon simple de poser deux
    flowables côte à côte). `show_date=False` (diagnostic uniquement) omet l'horodatage de
    génération du sous-titre — ce document ne doit plus afficher aucune date/heure nulle part."""
    subtitle = f"DMS Digital Medical System — Intervention {intervention.id}"
    if show_date:
        subtitle += f" — généré le {_fmt_dt(_now())}"
    title_block = [
        Paragraph(title, TITLE_STYLE),
        Paragraph(subtitle, SUBTITLE_STYLE),
    ]
    header_table = Table([[_logo_image(4.2 * cm, 2.4 * cm), title_block]], colWidths=[4.6 * cm, 12.4 * cm])
    header_table.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ]
        )
    )
    story.append(header_table)
    story.append(Spacer(1, 0.3 * cm))


def _now():
    from datetime import datetime, timezone

    return datetime.now(timezone.utc)


def _fmt_dt(value) -> str:
    if value is None:
        return "—"
    return value.strftime("%d/%m/%Y %H:%M")


def _fmt_money(value: float) -> str:
    return f"{value:,.2f} TND".replace(",", " ")


def _save_pdf(
    db: Session,
    intervention: Intervention,
    type_document: TypeDocument,
    filename: str,
    story: list,
    genere_par_id: int,
) -> InterventionDocument:
    path = _document_dir(intervention.id) / filename
    doc = SimpleDocTemplate(
        str(path), pagesize=A4, topMargin=2 * cm, bottomMargin=2 * cm, leftMargin=2 * cm, rightMargin=2 * cm
    )
    doc.build(story)

    document = InterventionDocument(
        intervention_id=intervention.id,
        type_document=type_document,
        chemin_pdf=_document_url(intervention.id, filename),
        genere_par_id=genere_par_id,
    )
    db.add(document)
    db.commit()
    db.refresh(document)
    return document


def generate_diagnostic_pdf(db: Session, intervention: Intervention, genere_par_id: int) -> InterventionDocument:
    story: list = []
    _header(story, "Rapport de diagnostic", intervention, show_date=False)

    story.append(
        _kv_table(
            [
                ("Établissement d'origine", intervention.lieu),
                ("Équipement(s)", equipements_label(intervention.equipements)),
                ("Technicien", intervention.technicien.nom),
                (
                    "Lieu de réparation choisi",
                    intervention.lieu_reparation.value.replace("_", " ").capitalize()
                    if intervention.lieu_reparation
                    else "—",
                ),
            ]
        )
    )

    story.append(Paragraph("Panne constatée", SECTION_STYLE))
    story.append(Paragraph(intervention.description_panne or "—", BODY_STYLE))

    filename = f"diagnostic_{intervention.id}.pdf"
    return _save_pdf(db, intervention, TypeDocument.DIAGNOSTIC, filename, story, genere_par_id)


def generate_devis_pdf(db: Session, intervention: Intervention, devis: Devis, genere_par_id: int) -> InterventionDocument:
    story: list = []
    _header(story, f"Devis n°{devis.id}", intervention)

    story.append(
        _kv_table(
            [
                ("Établissement", intervention.lieu),
                ("Équipement(s)", equipements_label(intervention.equipements)),
                ("Date d'émission", _fmt_dt(devis.date_creation)),
            ]
        )
    )

    story.append(Paragraph("Pièces détachées", SECTION_STYLE))
    pieces = db.query(PieceNecessaire).filter(PieceNecessaire.intervention_id == intervention.id).all()
    if pieces:
        # Plus de prix par pièce (texte libre, catalogue non lié) — seul le montant global du
        # devis (saisi par l'admin) apparaît dans le récapitulatif juste en dessous.
        rows = [["Désignation", "Qté"]]
        for p in pieces:
            rows.append([p.description_libre, str(p.quantite_necessaire)])
        pieces_table = Table(rows, colWidths=[12 * cm, 2 * cm])
        pieces_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1B3A6B")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("FONTSIZE", (0, 0), (-1, -1), 9),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#DCE3EB")),
                    ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                    ("TOPPADDING", (0, 0), (-1, -1), 5),
                ]
            )
        )
        story.append(pieces_table)
    else:
        story.append(Paragraph("Aucune pièce détachée nécessaire.", BODY_STYLE))

    story.append(Spacer(1, 0.5 * cm))
    story.append(
        _kv_table(
            [
                ("Montant pièces", _fmt_money(devis.montant_pieces)),
                ("Montant main d'œuvre", _fmt_money(devis.montant_main_oeuvre)),
                ("Montant total", _fmt_money(devis.montant_total)),
            ]
        )
    )

    filename = f"devis_{devis.id}_{intervention.id}.pdf"
    return _save_pdf(db, intervention, TypeDocument.DEVIS, filename, story, genere_par_id)


def generate_rapport_final_pdf(db: Session, intervention: Intervention, genere_par_id: int) -> InterventionDocument:
    story: list = []
    _header(story, "Rapport final d'intervention", intervention)

    story.append(
        _kv_table(
            [
                ("Établissement", intervention.lieu),
                ("Équipement(s)", equipements_label(intervention.equipements)),
                ("Technicien", intervention.technicien.nom),
                (
                    "Lieu de réparation",
                    intervention.lieu_reparation.value.replace("_", " ").capitalize()
                    if intervention.lieu_reparation
                    else "—",
                ),
                ("Durée réelle", f"{intervention.duree_reelle} min" if intervention.duree_reelle else "—"),
            ]
        )
    )

    story.append(Paragraph("Panne diagnostiquée", SECTION_STYLE))
    story.append(Paragraph(intervention.description_panne or "—", BODY_STYLE))

    devis = db.query(Devis).filter(Devis.intervention_id == intervention.id).first()

    story.append(Paragraph("Pièces utilisées", SECTION_STYLE))
    pieces = db.query(PieceNecessaire).filter(PieceNecessaire.intervention_id == intervention.id).all()
    if pieces:
        noms = ", ".join(f"{p.description_libre} (x{p.quantite_necessaire})" for p in pieces)
        story.append(Paragraph(noms, BODY_STYLE))
    else:
        story.append(Paragraph("Aucune pièce détachée utilisée.", BODY_STYLE))

    story.append(Paragraph("Devis", SECTION_STYLE))
    if devis is not None:
        story.append(
            _kv_table(
                [
                    ("Numéro", str(devis.id)),
                    ("Montant total", _fmt_money(devis.montant_total)),
                    ("Statut", STATUT_DEVIS_LABELS.get(devis.statut.value, devis.statut.value.capitalize())),
                ]
            )
        )
    else:
        story.append(Paragraph("Aucun devis n'a été émis pour cette intervention.", BODY_STYLE))

    if intervention.photo_url:
        photo_path = _resolve_storage_path(intervention.photo_url)
        if photo_path is not None:
            story.append(Paragraph("Photo de l'intervention", SECTION_STYLE))
            story.append(Image(str(photo_path), width=10 * cm, height=7.5 * cm, kind="proportional"))

    filename = f"rapport_final_{intervention.id}.pdf"
    return _save_pdf(db, intervention, TypeDocument.RAPPORT_FINAL, filename, story, genere_par_id)


def _cadre_signature() -> Table:
    """Cadre vide pour la signature et le cachet du client, à remplir à la main sur le document
    imprimé — aligné à droite en fin de document, seul flowable de ce type dans ce module (les 3
    autres PDF n'ont pas besoin de validation manuelle)."""
    cadre = Table(
        [[Paragraph("Signature et cachet du client", BODY_STYLE)], [Spacer(1, 2.5 * cm)]],
        colWidths=[7 * cm],
    )
    cadre.setStyle(
        TableStyle(
            [
                ("BOX", (0, 0), (-1, -1), 0.75, colors.HexColor("#1B3A6B")),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )
    cadre.hAlign = "RIGHT"
    return cadre


def generate_bon_restitution_pdf(
    db: Session, intervention: Intervention, fiche: EquipementAttenteReparation, genere_par_id: int
) -> InterventionDocument:
    """Généré à la création de la tâche de restitution (pas à sa validation) — le technicien
    doit l'avoir en main en se déplaçant chez le client. Sans aucune date/heure (`show_date=
    False`, même mécanisme que le diagnostic) : contrairement aux autres PDF, ce document est
    destiné à être signé physiquement, une date imprimée dessus n'aurait pas de sens tant que la
    signature elle-même n'est pas datée à la main."""
    story: list = []
    _header(story, "Bon de restitution", intervention, show_date=False)

    origine = fiche.intervention_equipement.intervention if fiche.intervention_equipement is not None else None

    story.append(
        _kv_table(
            [
                ("Établissement", fiche.etablissement_origine),
                ("Contact", origine.nom_contact if origine is not None else None),
                ("Équipement", f"{fiche.nom} ({fiche.marque}) — {fiche.type_equipement}"),
                ("Numéro de série", fiche.numero_serie),
                ("Technicien chargé de la restitution", intervention.technicien.nom),
            ]
        )
    )

    story.append(Paragraph("Panne traitée", SECTION_STYLE))
    story.append(Paragraph(fiche.description_panne or "—", BODY_STYLE))

    story.append(Spacer(1, 2 * cm))
    story.append(_cadre_signature())

    filename = f"bon_restitution_{intervention.id}.pdf"
    return _save_pdf(db, intervention, TypeDocument.BON_RESTITUTION, filename, story, genere_par_id)
