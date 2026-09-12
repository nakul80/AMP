# Copyright (c) 2026, PMG Team and contributors
# For license information, please see license.txt

import json
import frappe
from frappe import _

@frappe.whitelist()
def get_pending_drawing_items(project, main_area=None, sub_area=None):
	"""
	Returns all active GFC drawings and their pending BOQ line items
	for a given Project and Area to power the Fast Excel Progress Sheet.
	"""
	if not project:
		return []

	filters = {
		"project": project,
		"status": ["in", ["Good For Construction (GFC)", "Draft", "Issued For Review"]]
	}
	if main_area:
		filters["main_area"] = main_area
	if sub_area:
		filters["sub_area"] = sub_area

	drawings = frappe.get_all(
		"Project Drawing",
		filters=filters,
		fields=["name", "drawing_no", "drawing_title", "discipline", "main_area", "sub_area", "current_revision"]
	)

	results = []
	for dwg in drawings:
		doc = frappe.get_doc("Project Drawing", dwg.name)
		for b in (doc.boq_items or []):
			results.append({
				"drawing": dwg.name,
				"drawing_no": dwg.drawing_no,
				"drawing_title": dwg.drawing_title,
				"discipline": b.discipline or dwg.discipline,
				"main_area": dwg.main_area,
				"sub_area": dwg.sub_area,
				"revision": dwg.current_revision,
				"item_code": b.item_code,
				"item_name": b.item_name,
				"description": b.description,
				"uom": b.uom,
				"total_budget_qty": float(b.total_budget_qty or 0),
				"executed_qty": float(b.executed_qty or 0),
				"balance_to_execute": float(b.balance_to_execute or 0)
			})

	return results

@frappe.whitelist()
def submit_quick_progress(payload):
	"""
	Receives batch progress data directly from the Fast Site Progress Sheet (Excel-like UI)
	and creates/submits a Daily Progress Report and linked Stock Entry in one shot.
	"""
	if isinstance(payload, str):
		data = json.loads(payload)
	else:
		data = payload

	project = data.get("project")
	posting_date = data.get("posting_date") or frappe.utils.nowdate()
	main_area = data.get("main_area")
	sub_area = data.get("sub_area")
	source_warehouse = data.get("source_warehouse")
	contractor = data.get("contractor")
	remarks = data.get("remarks") or ""
	items = data.get("items") or []

	if not project or not main_area:
		frappe.throw(_("Project and Main Area are required."))

	valid_items = [i for i in items if float(i.get("today_qty") or 0) > 0]
	if not valid_items:
		frappe.throw(_("No quantities entered to log progress."))

	dpr = frappe.new_doc("Daily Progress Report")
	dpr.project = project
	dpr.posting_date = posting_date
	dpr.main_area = main_area
	dpr.sub_area = sub_area
	dpr.contractor = contractor
	dpr.general_remarks = remarks
	dpr.auto_create_stock_entry = 1 if source_warehouse else 0
	dpr.source_warehouse = source_warehouse
	dpr.stock_entry_type = "Material Issue"

	for item in valid_items:
		today_qty = float(item.get("today_qty"))
		budget = float(item.get("budget_qty") or 0)
		prev = float(item.get("prev_qty") or 0)

		dpr.append("progress_items", {
			"drawing": item.get("drawing"),
			"boq_item": item.get("item_code"),
			"activity_description": item.get("description") or item.get("item_name"),
			"uom": item.get("uom"),
			"location_grid": item.get("location_grid"),
			"drawing_budget_qty": budget,
			"previously_executed_qty": prev,
			"today_executed_qty": today_qty,
			"cumulative_executed_qty": prev + today_qty,
			"balance_qty": max(0.0, budget - (prev + today_qty)),
			"remarks": item.get("remarks")
		})

		# Also append to material consumption
		dpr.append("material_consumptions", {
			"item_code": item.get("item_code"),
			"item_name": item.get("item_name"),
			"uom": item.get("uom"),
			"qty_consumed": today_qty,
			"drawing": item.get("drawing"),
			"description": item.get("description")
		})

	dpr.insert()
	dpr.submit()

	return {
		"status": "success",
		"dpr_name": dpr.name,
		"stock_entry": dpr.stock_entry
	}
