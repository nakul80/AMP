import json
import frappe
from frappe import _
from amp.amp.boq import GFC, drawing_stage_totals, drawing_totals, validate_location
from amp.amp.quantities import number


@frappe.whitelist()
def get_pending_drawing_items(project, main_area=None, sub_area=None, drawing=None):
    if not project:
        return []
    validate_location(project, main_area, sub_area)
    filters = dict(project=project, status=GFC)
    for field, value in (("main_area", main_area), ("sub_area", sub_area), ("name", drawing)):
        if value:
            filters[field] = value
    results = []
    for name in frappe.get_list("Project Drawing", filters=filters, pluck="name", limit_page_length=0):
        doc = frappe.get_doc("Project Drawing", name)
        totals = drawing_totals(doc)
        stages = drawing_stage_totals(doc)
        for row in doc.boq_items or []:
            executed = totals.get(row.boq_line_id, 0)
            budget = number(row.estimated_qty)
            stage = stages.get(row.boq_line_id, {})
            is_structural = row.discipline == "Structural"
            if executed >= budget and (not is_structural or stage.get("erected", 0) >= budget):
                continue
            results.append(dict(drawing=name, drawing_no=doc.drawing_no, drawing_title=doc.drawing_title,
                discipline=row.discipline or doc.discipline, main_area=doc.main_area, sub_area=doc.sub_area,
                revision=doc.current_revision, boq_line_id=row.boq_line_id, item_code=row.item_code,
                item_name=row.item_name, description=row.description, uom=row.uom,
                total_budget_qty=budget, executed_qty=executed, balance_to_execute=max(0, budget-executed),
                is_structural=is_structural,
                fabricated_qty=stage.get("fabricated", 0), erected_qty=stage.get("erected", 0),
                fabrication_progress_weight=number(row.fabrication_progress_weight),
                erection_progress_weight=number(row.erection_progress_weight),
                is_stock_item=frappe.db.get_value("Item", row.item_code, "is_stock_item")))
    return results


@frappe.whitelist()
def submit_quick_progress(payload):
    data = json.loads(payload) if isinstance(payload, str) else payload
    if not isinstance(data, dict) or not data.get("project") or not data.get("main_area"):
        frappe.throw(_("Project and Main Area are required for a DPR."))
    items = data.get("items") or []
    if any(number(i.get(field)) < 0 for i in items for field in ("today_qty", "fabricated_qty", "erected_qty", "material_qty")):
        frappe.throw(_("Quantities cannot be negative."))
    valid = [i for i in items if any(number(i.get(field)) > 0 for field in ("today_qty", "fabricated_qty", "erected_qty"))]
    if not valid:
        frappe.throw(_("No quantities entered to log progress."))
    dpr = frappe.new_doc("Daily Progress Report")
    for field in ("project", "main_area", "sub_area", "contractor", "source_warehouse"):
        dpr.set(field, data.get(field))
    dpr.posting_date = data.get("posting_date") or frappe.utils.nowdate()
    dpr.general_remarks = data.get("remarks") or ""
    dpr.auto_create_stock_entry = 1 if dpr.source_warehouse else 0
    dpr.stock_entry_type = "Material Issue"
    for item in valid:
        dpr.append("progress_items", dict(drawing=item.get("drawing"), boq_item=item.get("item_code"),
            boq_line_id=item.get("boq_line_id"), activity_description=item.get("description") or item.get("item_name"),
            uom=item.get("uom"), location_grid=item.get("location_grid"),
            today_executed_qty=number(item.get("today_qty")),
            today_fabricated_qty=number(item.get("fabricated_qty")),
            today_erected_qty=number(item.get("erected_qty")), remarks=item.get("remarks")))
        # Material usage is explicit; executing one unit of work need not consume one unit of material.
        if number(item.get("material_qty")) > 0:
            dpr.append("material_consumptions", dict(item_code=item.get("item_code"),
                item_name=item.get("item_name"), uom=item.get("uom"),
                qty_consumed=number(item["material_qty"]), drawing=item.get("drawing"),
                boq_line_id=item.get("boq_line_id")))
    dpr.insert()
    dpr.submit()
    return dict(status="success", dpr_name=dpr.name, stock_entry=dpr.stock_entry)
