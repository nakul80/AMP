"""BOQ identity, project boundaries, and quantity conversions."""
from uuid import uuid4
import frappe
from frappe import _
from amp.amp.quantities import number, structural_progress_values, unique_match

GFC = "Good For Construction (GFC)"


def lock_drawing(name):
    # Serialize procurement, revisions, and execution against the same drawing.
    frappe.db.sql("select name from `tabProject Drawing` where name=%s for update", (name,))


def validate_location(project, main_area=None, sub_area=None):
    frappe.get_doc("Project", project).check_permission("read")
    if main_area and frappe.db.get_value("Project Main Area", main_area, "project") != project:
        frappe.throw(_("Main Area does not belong to the selected Project."))
    if sub_area:
        area = frappe.db.get_value("Project Sub Area", sub_area, "main_area")
        if not area or (main_area and area != main_area) or frappe.db.get_value("Project Main Area", area, "project") != project:
            frappe.throw(_("Sub Area does not belong to the selected Project/Main Area."))


def ensure_ids(rows):
    seen = set()
    for row in rows:
        if not row.boq_line_id:
            row.boq_line_id = uuid4().hex
        if row.boq_line_id in seen:
            frappe.throw(_("Duplicate BOQ line reference. Add a new row instead of duplicating its reference."))
        seen.add(row.boq_line_id)
        for field in ("estimated_qty", "wastage_percent", "progress_weight", "fabrication_progress_weight", "erection_progress_weight"):
            if number(row.get(field)) < 0:
                frappe.throw(_("BOQ quantities, wastage and progress weights cannot be negative."))
        if row.discipline == "Structural" and round(number(row.fabrication_progress_weight) + number(row.erection_progress_weight), 6) != 100:
            frappe.throw(_("Fabrication and erection progress weights must total 100% for Structural BOQ lines."))


def resolve_line(drawing, line_id=None, item_code=None, uom=None):
    if line_id:
        matches = [r for r in drawing.boq_items if r.boq_line_id == line_id]
        row = matches[0] if len(matches) == 1 else None
    else:
        row = unique_match(drawing.boq_items, item_code, uom)
    if not row or (item_code and row.item_code != item_code):
        frappe.throw(_("Select a valid, unambiguous BOQ line for drawing {0}.").format(drawing.name))
    return row


def stock_factor(item_code, uom):
    stock_uom = frappe.db.get_value("Item", item_code, "stock_uom")
    if uom == stock_uom:
        return 1.0
    factor = frappe.db.get_value("UOM Conversion Detail", {"parent": item_code, "parenttype": "Item", "uom": uom}, "conversion_factor")
    if not factor or number(factor) <= 0:
        frappe.throw(_("No stock UOM conversion for item {0}, UOM {1}.").format(item_code, uom))
    return number(factor)


def drawing_totals(drawing, for_update=False):
    """Rebuild execution from submitted DPRs; never increment a mutable counter."""
    totals = {}
    locking = " for update" if for_update else ""
    rows = frappe.db.sql("""select i.boq_line_id, i.boq_item as item_code, i.uom,
        i.today_executed_qty as qty, i.today_fabricated_qty, i.today_erected_qty, i.is_structural_stage_progress from `tabDaily Progress Item` i
        inner join `tabDaily Progress Report` d on d.name=i.parent
        where d.docstatus=1 and i.parenttype='Daily Progress Report' and i.drawing=%s
        """ + locking, (drawing.name,), as_dict=True)
    stages = {}
    for row in rows:
        line = next((b for b in drawing.boq_items if b.boq_line_id == row.boq_line_id), None) if row.boq_line_id else None
        if line and line.uom == row.uom:
            state = stages.setdefault(line.boq_line_id, {"legacy": 0, "fabricated": 0, "erected": 0})
            if not row.is_structural_stage_progress:
                state["legacy"] += number(row.qty)
            state["fabricated"] += number(row.today_fabricated_qty)
            state["erected"] += number(row.today_erected_qty)
    for line in drawing.boq_items:
        state = stages.get(line.boq_line_id, {"legacy": 0, "fabricated": 0, "erected": 0})
        if line.discipline == "Structural":
            totals[line.boq_line_id] = structural_progress_values(
                line.estimated_qty, line.fabrication_progress_weight, line.erection_progress_weight,
                state["fabricated"], state["erected"], state["legacy"]
            )["executed_qty"]
        else:
            totals[line.boq_line_id] = state["legacy"]
    return totals


def drawing_stage_totals(drawing, for_update=False):
    """Raw fabrication/erection totals for server-side DPR validation and reports."""
    locking = " for update" if for_update else ""
    rows = frappe.db.sql("""select i.boq_line_id, i.today_executed_qty, i.today_fabricated_qty, i.today_erected_qty, i.is_structural_stage_progress
        from `tabDaily Progress Item` i inner join `tabDaily Progress Report` d on d.name=i.parent
        where d.docstatus=1 and i.parenttype='Daily Progress Report' and i.drawing=%s""" + locking,
        (drawing.name,), as_dict=True)
    totals = {}
    for row in rows:
        state = totals.setdefault(row.boq_line_id, {"legacy": 0, "fabricated": 0, "erected": 0})
        if not row.is_structural_stage_progress:
            state["legacy"] += number(row.today_executed_qty)
        state["fabricated"] += number(row.today_fabricated_qty)
        state["erected"] += number(row.today_erected_qty)
    return totals


def populate_operational_quantities(drawing):
    """Replace client/cached counters with authoritative transaction quantities."""
    from amp.amp.transactions import material_totals
    execution = drawing_totals(drawing, for_update=True)
    stage_totals = drawing_stage_totals(drawing, for_update=True)
    materials = material_totals(drawing.name)
    for row in drawing.boq_items:
        quantities = materials.get(row.boq_line_id, {})
        factor = stock_factor(row.item_code, row.uom)
        row.executed_qty = execution.get(row.boq_line_id, 0)
        if row.discipline == "Structural":
            stage = stage_totals.get(row.boq_line_id, {})
            row.fabricated_qty = stage.get("fabricated", 0)
            row.erected_qty = stage.get("erected", 0)
            row.legacy_executed_qty = stage.get("legacy", 0)
        for field in ("requested_qty", "ordered_qty", "received_qty", "draft_requested_qty"):
            row.set(field, quantities.get(field, 0) / factor)
        row.calculate_quantities()


def refresh_drawing(name):
    lock_drawing(name)
    drawing = frappe.get_doc("Project Drawing", name, for_update=True)
    populate_operational_quantities(drawing)
    for row in drawing.boq_items:
        frappe.db.set_value("Drawing BOQ Item", row.name, {f: row.get(f) for f in (
            "executed_qty", "fabricated_qty", "erected_qty", "legacy_executed_qty", "fabrication_balance_qty", "erection_balance_qty", "requested_qty", "ordered_qty", "received_qty", "draft_requested_qty",
            "balance_to_order", "balance_to_execute")}, update_modified=False)
    drawing.calculate_totals_and_progress()
    frappe.db.set_value("Project Drawing", name, "percent_progress", drawing.percent_progress, update_modified=False)
