# Copyright (c) 2026, PMG Team and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import add_days, nowdate

@frappe.whitelist()
def create_material_request_from_drawing(drawing_no):
	"""Generates an ERPNext Material Request (Purchase Indent) from a Project Drawing's active BOQ"""
	if not drawing_no:
		frappe.throw(_("Drawing Number is required"))

	drawing = frappe.get_doc("Project Drawing", drawing_no)

	if not drawing.boq_items:
		frappe.throw(_("Drawing {0} has no BOQ items defined.").format(drawing_no))

	# Filter items that have remaining balance to order
	items_to_order = [b for b in drawing.boq_items if float(b.balance_to_order or 0) > 0]

	if not items_to_order:
		frappe.throw(_("All BOQ items for Drawing {0} have already been fully requested.").format(drawing_no))

	mr = frappe.new_doc("Material Request")
	mr.material_request_type = "Purchase"
	mr.transaction_date = nowdate()
	mr.schedule_date = add_days(nowdate(), 7)
	mr.project = drawing.project

	# Custom remarks linking back to drawing
	mr.remarks = _("Procurement Indent against Drawing {0} ({1}) - {2}").format(
		drawing.drawing_no, drawing.current_revision or "Rev 0", drawing.drawing_title
	)

	for b_item in items_to_order:
		order_qty = float(b_item.balance_to_order or 0)
		mr.append("items", {
			"item_code": b_item.item_code,
			"item_name": b_item.item_name,
			"description": b_item.description or b_item.item_name,
			"uom": b_item.uom,
			"qty": order_qty,
			"schedule_date": add_days(nowdate(), 7),
			"project": drawing.project
		})

		# Update requested qty on drawing BOQ item
		b_item.requested_qty = float(b_item.requested_qty or 0) + order_qty
		b_item.calculate_quantities()

	mr.flags.ignore_permissions = False
	mr.insert()

	# Save drawing to persist updated requested_qty
	drawing.flags.ignore_validate_update_after_submit = True
	drawing.save(ignore_permissions=True)

	frappe.msgprint(_("Material Request {0} created successfully.").format(
		frappe.utils.get_link_to_form("Material Request", mr.name)
	))

	return mr.name

@frappe.whitelist()
def create_material_request_from_revision(revision_name):
	"""Generates an ERPNext Material Request from a specific Drawing Revision"""
	if not revision_name:
		frappe.throw(_("Revision is required"))

	rev = frappe.get_doc("Drawing Revision", revision_name)
	drawing = frappe.get_doc("Project Drawing", rev.drawing)

	items_to_order = [b for b in rev.items if float(b.balance_to_order or 0) > 0]

	if not items_to_order:
		frappe.throw(_("No items with remaining balance to order in revision {0}.").format(revision_name))

	mr = frappe.new_doc("Material Request")
	mr.material_request_type = "Purchase"
	mr.transaction_date = nowdate()
	mr.schedule_date = add_days(nowdate(), 7)
	mr.project = drawing.project
	mr.remarks = _("Procurement Indent against Drawing {0} ({1})").format(drawing.name, rev.revision_no)

	for b_item in items_to_order:
		order_qty = float(b_item.balance_to_order or 0)
		mr.append("items", {
			"item_code": b_item.item_code,
			"item_name": b_item.item_name,
			"description": b_item.description or b_item.item_name,
			"uom": b_item.uom,
			"qty": order_qty,
			"schedule_date": add_days(nowdate(), 7),
			"project": drawing.project
		})
		b_item.requested_qty = float(b_item.requested_qty or 0) + order_qty
		b_item.calculate_quantities()

	mr.insert()
	rev.save(ignore_permissions=True)

	frappe.msgprint(_("Material Request {0} created successfully.").format(
		frappe.utils.get_link_to_form("Material Request", mr.name)
	))

	return mr.name
