"""Libellé d'affichage d'un équipement d'intervention — factorisé ici car utilisé à la fois
par la "tâche actuelle" des techniciens et par les 3 PDF du workflow (voir pdf_workflow.py)."""

from app.models.intervention_equipement import InterventionEquipement


def equipement_label(item: InterventionEquipement) -> str:
    if item.equipement is not None:
        return f"{item.equipement.nom} ({item.equipement.marque})"
    if item.description_libre:
        sn = f" — SN {item.sn_saisi_technicien}" if item.sn_saisi_technicien else " — SN non renseigné"
        return f"{item.description_libre}{sn}"
    return "Équipement non renseigné"


def equipements_label(items: list[InterventionEquipement]) -> str:
    if not items:
        return "Aucun équipement renseigné"
    return ", ".join(equipement_label(item) for item in items)
