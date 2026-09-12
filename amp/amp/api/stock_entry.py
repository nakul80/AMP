# Copyright (c) 2026, PMG Team and contributors
# For license information, please see license.txt

import frappe
from frappe import _

def make_stock_entry_from_dpr(dpr):
	"""
	Automatically creates and submits an ERPNext Stock Entry (Material Issue or Transfer)
	from a Daily Progress Report (DPR) to reflect site WIP or actual material consumption.
	"""
	if not dpr.source_warehouse:
		frappe.msgprint(_("Warning: No Source Warehouse selected on DPR {0}. Stock Entry was not generated.").format(dpr.name))
		return None

	consumptions = dpr.material_consumptions or []
	if not consumptions:
		# If no specific materials logged, nothing to deduct from stock
		return None

	se = frappe.new_doc("Stock Entry")
	purpose = dpr.stock_entry_type or "Material Issue"
	se.purpose = purpose
	se.stock_entry_type = purpose
	se.posting_date = dpr.posting_date
	se.project = dpr.project
	se.from_warehouse = dpr.source_warehouse
	if purpose == "Material Transfer":
		se.to_warehouse = dpr.target_warehouse

	se.remarks = _("Automated consumption entry for Daily Progress Report: {0} (Area: {1})").format(
		dpr.name, dpr.main_area
	)

	has_valid_items = False
	for row in consumptions:
		qty = float(row.qty_consumed or 0)
		if qty <= 0:
			continue

		# Check if Item is a stock item in ERPNext
		is_stock_item = frappe.db.get_value("Item", row.item_code, "is_stock_item")
		if not is_stock_item:
			continue

		has_valid_items = True
		se.append("items", {
			"item_code": row.item_code,
			"item_name": row.item_name,
			"uom": row.uom,
			"stock_uom": frappe.db.get_value("Item", row.item_code, "stock_uom") or row.uom,
			"qty": qty,
			"s_warehouse": dpr.source_warehouse,
			"t_warehouse": dpr.target_warehouse if purpose == "Material Transfer" else None,
			"batch_no": row.batch_no if hasattr(row, "batch_no") else None,
			"description": _("Consumed on site against drawing {0}").format(row.drawing or dpr.main_area)
		})

	if not has_valid_items:
		return None

	se.flags.ignore_permissions = True
	se.insert()
	se.submit()

	frappe.msgprint(_("Created and submitted ERPNext Stock Entry {0} for site material consumption.").format(
		frappe.utils.get_link_to_form("Stock Entry", se.name)
	))

	return se
