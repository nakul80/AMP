"""Assign stable references without guessing ambiguous historical allocations."""
from uuid import uuid4
import frappe
from amp.setup import install
from amp.amp.quantities import unique_match


def execute():
    install()
    for drawing in frappe.get_all("Project Drawing", pluck="name"):
        current = frappe.get_all("Drawing BOQ Item", filters={"parent": drawing, "parenttype": "Project Drawing"}, fields=["*"])
        for row in current:
            if not row.boq_line_id and not row.progress_weight:
                frappe.db.set_value("Drawing BOQ Item", row.name, "progress_weight", 1, update_modified=False)
            row.boq_line_id = row.boq_line_id or uuid4().hex
            frappe.db.set_value("Drawing BOQ Item", row.name, "boq_line_id", row.boq_line_id, update_modified=False)
        for revision in frappe.get_all("Drawing Revision", filters={"drawing": drawing}, pluck="name"):
            rows = frappe.get_all("Drawing BOQ Item", filters={"parent": revision, "parenttype": "Drawing Revision"}, fields=["*"])
            for row in rows:
                match = unique_match(current, row.item_code, row.uom, row.discipline or "")
                # Repeated item/discipline/UOM rows cannot be inferred across revisions.
                if not unique_match(rows, row.item_code, row.uom, row.discipline or ""):
                    match = None
                if not row.boq_line_id and not row.progress_weight:
                    frappe.db.set_value("Drawing BOQ Item", row.name, "progress_weight", 1, update_modified=False)
                identity = row.boq_line_id or (match.boq_line_id if match else uuid4().hex)
                frappe.db.set_value("Drawing BOQ Item", row.name, "boq_line_id", identity, update_modified=False)
        for doctype, item_field in (("Daily Progress Item", "boq_item"), ("DPR Material Consumption", "item_code")):
            for row in frappe.get_all(doctype, filters={"drawing": drawing}, fields=["*"]):
                if row.boq_line_id:
                    continue
                match = unique_match(current, row.get(item_field), row.uom)
                if match:
                    frappe.db.set_value(doctype, row.name, "boq_line_id", match.boq_line_id, update_modified=False)
    # The existing explicit DPR -> Stock Entry link is authoritative; remarks are not.
    for dpr in frappe.get_all("Daily Progress Report", filters={"stock_entry": ["is", "set"]}, fields=["name", "stock_entry"]):
        if not frappe.db.exists("Stock Entry", dpr.stock_entry):
            continue
        linked = frappe.get_all("Daily Progress Report", filters={"stock_entry": dpr.stock_entry}, pluck="name")
        if len(linked) != 1:
            continue
        frappe.db.set_value("Stock Entry", dpr.stock_entry, "custom_daily_progress_report", dpr.name, update_modified=False)
        materials = frappe.get_all("DPR Material Consumption", filters={"parent": dpr.name}, fields=["*"])
        for row in frappe.get_all("Stock Entry Detail", filters={"parent": dpr.stock_entry}, fields=["*"]):
            match = unique_match(materials, row.item_code, row.uom)
            if match and match.boq_line_id and not row.custom_amp_boq_line_id:
                frappe.db.set_value("Stock Entry Detail", row.name, dict(custom_amp_drawing=match.drawing,
                    custom_amp_boq_line_id=match.boq_line_id), update_modified=False)
    from amp.amp.boq import refresh_drawing
    for drawing in frappe.get_all("Project Drawing", pluck="name"):
        refresh_drawing(drawing)
    from amp.amp.patches.v0_0_1.sync_workspace import execute as sync_workspace
    sync_workspace()
