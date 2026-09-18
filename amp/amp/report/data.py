"""Permission-aware report inputs. Child rows are read only for accessible parents."""
import frappe
from frappe import _
from frappe.utils import getdate, nowdate
from amp.amp.boq import validate_location


def report_filters(filters=None):
    filters = frappe._dict(filters or {})
    for field in ("show_dprs", "show_transactions"):
        filters[field] = filters.get(field) in (1, "1", True)
    filters.to_date = str(getdate(filters.get("to_date") or nowdate()))
    if filters.get("from_date"):
        filters.from_date = str(getdate(filters.from_date))
        if filters.from_date > filters.to_date:
            frappe.throw(_("From Date must not be after To Date."))
    if filters.get("project"):
        validate_location(filters.project, filters.get("main_area"), filters.get("sub_area"))
    return filters


def projects_and_drawings(filters):
    projects = frappe.get_list("Project", filters={"name": filters.project} if filters.get("project") else {},
        fields=["name", "project_name"], limit_page_length=0)
    names = [p.name for p in projects]
    if not names:
        return [], {}
    conditions = {"project": ["in", names]}
    for field in ("main_area", "sub_area", "drawing"):
        if filters.get(field):
            conditions["name" if field == "drawing" else field] = filters[field]
    drawings = frappe.get_list("Project Drawing", filters=conditions,
        fields=["name", "drawing_title", "project", "main_area", "sub_area", "status"], limit_page_length=0)
    return projects, {d.name: d for d in drawings}


def child_rows(doctype, parents, parenttype, fields=None):
    if not parents:
        return []
    return frappe.get_all(doctype, filters={"parent": ["in", list(parents)], "parenttype": parenttype}, fields=fields or ["*"])


def submitted_dprs(filters, projects):
    if not projects:
        return {}
    conditions = {"project": ["in", [p.name for p in projects]], "docstatus": 1, "posting_date": ["<=", filters.to_date]}
    for field in ("main_area", "sub_area"):
        if filters.get(field):
            conditions[field] = filters[field]
    return {d.name: d for d in frappe.get_list("Daily Progress Report", filters=conditions,
        fields=["name", "posting_date", "project", "main_area", "sub_area"], limit_page_length=0)}


def column(field, label, kind="Float", options=None, width=130):
    result = dict(fieldname=field, label=_(label), fieldtype=kind, width=width)
    if options:
        result["options"] = options
    return result
