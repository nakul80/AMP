"""Read-only site diagnostics callable from bench console/execute by an administrator."""
import frappe


def dpr_visibility(name, user):
    """Compare stored status with a user's document/list visibility without changing permissions.

    bench --site SITE execute amp.amp.api.diagnostics.dpr_visibility \
      --kwargs '{"name":"DPR-2026-00001","user":"engineer@example.com"}'
    """
    frappe.only_for("System Manager")
    doc = frappe.get_doc("Daily Progress Report", name)
    result = dict(name=doc.name, docstatus=doc.docstatus, project=doc.project,
                  main_area=doc.main_area, posting_date=doc.posting_date, stock_entry=doc.stock_entry)
    original_user = frappe.session.user
    try:
        frappe.set_user(user)
        result["can_read_document"] = bool(frappe.has_permission("Daily Progress Report", "read", doc=doc))
        try:
            result["visible_in_unfiltered_list"] = bool(frappe.get_list("Daily Progress Report", filters={"name": name}, pluck="name"))
        except frappe.PermissionError:
            result["visible_in_unfiltered_list"] = False
    finally:
        frappe.set_user(original_user)
    return result
