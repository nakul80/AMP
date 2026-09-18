"""Propagate row-level drawing references and reconcile ERPNext transactions."""
import frappe
from frappe import _
from amp.amp.boq import GFC, lock_drawing, resolve_line, stock_factor
from amp.amp.quantities import number

TRANSACTIONS = (
    ("Material Request", "Material Request Item", "transaction_date"),
    ("Purchase Order", "Purchase Order Item", "transaction_date"),
    ("Purchase Receipt", "Purchase Receipt Item", "posting_date"),
    ("Stock Entry", "Stock Entry Detail", "posting_date"),
)
REFERENCES = ("custom_amp_drawing", "custom_amp_revision", "custom_amp_boq_line_id")


def stock_qty(row):
    # ERPNext's persisted stock quantity includes the transaction's conversion factor.
    field = "transfer_qty" if row.get("doctype") == "Stock Entry Detail" else "stock_qty"
    if row.get(field) is not None:
        return number(row.get(field))
    return number(row.get("qty")) * number(row.get("conversion_factor") or 1)


def material_totals(drawing, exclude_request=None):
    totals = {}
    for parenttype, childtype, _date in TRANSACTIONS[:3]:
        extra = " and p.material_request_type='Purchase'" if parenttype == "Material Request" else ""
        # Table names are fixed constants, values are parameterized.
        rows = frappe.db.sql(f"""select i.*, p.docstatus as parent_status from `tab{childtype}` i
            inner join `tab{parenttype}` p on p.name=i.parent
            where i.custom_amp_drawing=%s and i.parenttype=%s and p.docstatus<2{extra} for update""",
            (drawing, parenttype), as_dict=True)
        for row in rows:
            if parenttype == "Material Request" and row.parent == exclude_request:
                continue
            if not row.custom_amp_boq_line_id:
                continue
            field = {"Material Request": "requested_qty", "Purchase Order": "ordered_qty", "Purchase Receipt": "received_qty"}[parenttype]
            if row.parent_status == 0:
                if parenttype != "Material Request":
                    continue
                field = "draft_requested_qty"
            bucket = totals.setdefault(row.custom_amp_boq_line_id, {})
            bucket[field] = bucket.get(field, 0) + stock_qty(row)
    return totals


def validate_transaction(doc, method=None):
    for row in doc.get("items") or []:
        source = None
        if doc.doctype == "Purchase Order" and row.get("material_request_item"):
            source = frappe.db.get_value("Material Request Item", row.material_request_item, [*REFERENCES, "parent"], as_dict=True)
            if source and row.material_request != source.parent:
                frappe.throw(_("Material Request row does not belong to the selected request."))
        elif doc.doctype == "Purchase Receipt" and row.get("purchase_order_item"):
            source = frappe.db.get_value("Purchase Order Item", row.purchase_order_item, [*REFERENCES, "parent"], as_dict=True)
            if source and row.purchase_order != source.parent:
                frappe.throw(_("Purchase Order row does not belong to the selected order."))
        if source:
            for field in REFERENCES:
                row.set(field, source.get(field))
        if not row.get("custom_amp_drawing"):
            if row.get("custom_amp_boq_line_id") or row.get("custom_amp_revision"):
                frappe.throw(_("A drawing is required for an AMP BOQ reference."))
            continue
        drawing = frappe.get_doc("Project Drawing", row.custom_amp_drawing)
        drawing.check_permission("read")
        project = row.get("project") or doc.get("project")
        if project and project != drawing.project:
            frappe.throw(_("Transaction Project must match the drawing Project."))
        row.project = drawing.project
        company = frappe.db.get_value("Project", drawing.project, "company")
        if company and doc.company != company:
            frappe.throw(_("Transaction Company must match the drawing Project Company."))
        # Downstream transactions may legitimately reference a superseded revision.
        if doc.doctype == "Material Request" and not row.get("custom_amp_revision"):
            row.custom_amp_revision = frappe.db.get_value("Drawing Revision", {"drawing": drawing.name, "revision_status": "Approved - GFC"}, "name")
            if not row.custom_amp_revision:
                frappe.throw(_("Approve a revision before requesting materials."))
        revision = row.get("custom_amp_revision")
        if revision:
            rev = frappe.get_doc("Drawing Revision", revision)
            rev.check_permission("read")
            if rev.drawing != drawing.name:
                frappe.throw(_("Revision does not belong to the selected drawing."))
            if doc.doctype != "Material Request":
                drawing.boq_items = rev.items
        line = resolve_line(drawing, row.get("custom_amp_boq_line_id"), row.item_code)
        row.custom_amp_boq_line_id = line.boq_line_id
        if doc.doctype == "Material Request" and (drawing.status != GFC or doc.material_request_type != "Purchase"):
            frappe.throw(_("AMP material requests require a GFC drawing and Purchase purpose."))
        if doc.doctype == "Material Request" and revision and rev.revision_status != "Approved - GFC":
            frappe.throw(_("Material requests must use the active approved revision."))
    if doc.doctype == "Material Request":
        validate_request_budget(doc)


def validate_request_budget(doc):
    names = sorted({r.custom_amp_drawing for r in doc.items if r.get("custom_amp_drawing")})
    for name in names:
        lock_drawing(name)
        drawing = frappe.get_doc("Project Drawing", name, for_update=True)
        existing = material_totals(name, exclude_request=doc.name)
        requested = {}
        for row in doc.items:
            if row.get("custom_amp_drawing") == name:
                qty = number(row.qty) * stock_factor(row.item_code, row.uom)
                requested[row.custom_amp_boq_line_id] = requested.get(row.custom_amp_boq_line_id, 0) + qty
        for line_id, qty in requested.items():
            line = resolve_line(drawing, line_id)
            used = existing.get(line_id, {})
            available = number(line.total_budget_qty) * stock_factor(line.item_code, line.uom) - used.get("requested_qty", 0) - used.get("draft_requested_qty", 0)
            if qty > available + 0.000001:
                frappe.throw(_("Material request exceeds the remaining BOQ budget for {0}. Draft requests also reserve quantities.").format(line.item_code))


def transaction_changed(doc, method=None):
    from amp.amp.boq import refresh_drawing
    names = {r.get("custom_amp_drawing") for r in doc.get("items") or []}
    before = doc.get_doc_before_save()
    if before:
        names.update(r.get("custom_amp_drawing") for r in before.get("items") or [])
    for name in sorted(n for n in names if n):
        refresh_drawing(name)
