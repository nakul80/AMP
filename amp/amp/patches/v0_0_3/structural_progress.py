"""Initialise structural stage weights and rebuild cached drawing progress."""
import frappe


def execute():
    for row in frappe.get_all(
        "Drawing BOQ Item",
        filters={"discipline": "Structural"},
        fields=["name", "fabrication_progress_weight", "erection_progress_weight"],
    ):
        if not row.fabrication_progress_weight and not row.erection_progress_weight:
            frappe.db.set_value(
                "Drawing BOQ Item", row.name,
                {"fabrication_progress_weight": 50, "erection_progress_weight": 50},
                update_modified=False,
            )

    from amp.amp.boq import refresh_drawing
    for drawing in frappe.get_all("Project Drawing", pluck="name"):
        refresh_drawing(drawing)
