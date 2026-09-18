import frappe
from frappe import _


def validate_project(doc, method=None):
    for field in ("custom_amp_site_warehouse", "custom_amp_wip_warehouse"):
        warehouse = doc.get(field)
        if warehouse:
            values = frappe.db.get_value("Warehouse", warehouse, ["company", "is_group"], as_dict=True)
            if not values or values.is_group or (doc.company and values.company != doc.company):
                frappe.throw(_("AMP warehouses must be non-group warehouses in the Project Company."))
