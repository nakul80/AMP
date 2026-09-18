"""Idempotent ERPNext extensions installed with AMP."""
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def install():
    fields = {}
    for doctype in ("Material Request Item", "Purchase Order Item", "Purchase Receipt Item", "Stock Entry Detail"):
        fields[doctype] = [
            dict(fieldname="custom_amp_drawing", label="AMP Drawing", fieldtype="Link", options="Project Drawing", insert_after="project"),
            dict(fieldname="custom_amp_revision", label="AMP Drawing Revision", fieldtype="Link", options="Drawing Revision", insert_after="custom_amp_drawing", read_only=1),
            dict(fieldname="custom_amp_boq_line_id", label="AMP BOQ Line Reference", fieldtype="Data", insert_after="custom_amp_revision", read_only=1, search_index=1),
        ]
    fields["Stock Entry"] = [dict(fieldname="custom_daily_progress_report", label="Daily Progress Report", fieldtype="Link", options="Daily Progress Report", read_only=1, no_copy=1, insert_after="project", search_index=1)]
    fields["Project"] = [
        dict(fieldname="custom_amp_section", label="AMP Construction", fieldtype="Section Break", insert_after="project_name"),
        dict(fieldname="custom_amp_site_location", label="Site Location", fieldtype="Data", insert_after="custom_amp_section"),
        dict(fieldname="custom_amp_project_engineer", label="Project Engineer", fieldtype="Link", options="User", insert_after="custom_amp_site_location"),
        dict(fieldname="custom_amp_site_warehouse", label="Site Warehouse", fieldtype="Link", options="Warehouse", insert_after="custom_amp_project_engineer"),
        dict(fieldname="custom_amp_wip_warehouse", label="WIP Warehouse", fieldtype="Link", options="Warehouse", insert_after="custom_amp_site_warehouse"),
    ]
    create_custom_fields(fields, update=True)
