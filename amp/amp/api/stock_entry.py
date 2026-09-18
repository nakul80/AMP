import frappe
from frappe import _
from amp.amp.boq import stock_factor


def make_stock_entry_from_dpr(dpr):
    if not dpr.material_consumptions:
        return None
    se = frappe.new_doc("Stock Entry")
    se.company = frappe.db.get_value("Project", dpr.project, "company") or frappe.defaults.get_user_default("Company")
    se.purpose = se.stock_entry_type = dpr.stock_entry_type or "Material Issue"
    se.posting_date = dpr.posting_date
    se.set_posting_time = 1
    se.project = dpr.project
    se.from_warehouse = dpr.source_warehouse
    se.to_warehouse = dpr.target_warehouse if se.purpose == "Material Transfer" else None
    se.custom_daily_progress_report = dpr.name
    se.remarks = _("Material posting for DPR {0}").format(dpr.name)
    for row in dpr.material_consumptions:
        if not frappe.db.get_value("Item", row.item_code, "is_stock_item"):
            frappe.throw(_("{0} is not a stock item. Disable automatic stock posting or remove it from material consumption.").format(row.item_code))
        se.append("items", dict(item_code=row.item_code, uom=row.uom, qty=row.qty_consumed,
            conversion_factor=stock_factor(row.item_code, row.uom),
            s_warehouse=dpr.source_warehouse, t_warehouse=se.to_warehouse,
            batch_no=row.batch_no, project=dpr.project,
            custom_amp_drawing=row.drawing, custom_amp_revision=row.drawing_revision,
            custom_amp_boq_line_id=row.boq_line_id))
    # Stock permissions apply to the submitting user; no silent permission escalation.
    se.insert()
    se.submit()
    return se
