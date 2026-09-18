import frappe
from frappe import _
from frappe.utils import add_days, nowdate
from amp.amp.boq import GFC, lock_drawing, refresh_drawing, stock_factor


@frappe.whitelist()
def create_material_request_from_drawing(drawing_no):
    lock_drawing(drawing_no)
    drawing = frappe.get_doc("Project Drawing", drawing_no, for_update=True)
    drawing.check_permission("read")
    if drawing.status != GFC:
        frappe.throw(_("Only approved GFC drawings can be procured."))
    refresh_drawing(drawing_no)
    drawing.reload()
    items = [r for r in drawing.boq_items if r.balance_to_order > 0]
    if not items:
        frappe.throw(_("No remaining budget. Submitted and draft requests already reserve these quantities."))
    revision = frappe.db.get_value("Drawing Revision", {"drawing": drawing.name, "revision_status": "Approved - GFC"}, "name")
    if not revision:
        frappe.throw(_("Approve a Drawing Revision before requesting materials."))
    mr = frappe.new_doc("Material Request")
    mr.material_request_type = "Purchase"
    mr.company = frappe.db.get_value("Project", drawing.project, "company") or frappe.defaults.get_user_default("Company")
    mr.transaction_date = nowdate()
    mr.schedule_date = add_days(nowdate(), 7)
    mr.remarks = _("Procurement against drawing {0}, revision {1}").format(drawing.name, revision)
    warehouse = frappe.db.get_value("Project", drawing.project, "custom_amp_site_warehouse")
    for row in items:
        mr.append("items", dict(item_code=row.item_code, qty=row.balance_to_order, uom=row.uom,
            conversion_factor=stock_factor(row.item_code, row.uom),
            schedule_date=mr.schedule_date, project=drawing.project, warehouse=warehouse,
            custom_amp_drawing=drawing.name, custom_amp_revision=revision, custom_amp_boq_line_id=row.boq_line_id))
    mr.insert()
    return mr.name


@frappe.whitelist()
def create_material_request_from_revision(revision_name):
    rev = frappe.get_doc("Drawing Revision", revision_name)
    rev.check_permission("read")
    lock_drawing(rev.drawing)
    rev.reload()
    if rev.revision_status != "Approved - GFC":
        frappe.throw(_("Only the active approved revision can be procured."))
    return create_material_request_from_drawing(rev.drawing)
