# Copyright (c) 2026, PMG Team and contributors
# For license information, please see license.txt

import frappe
from frappe import _

@frappe.whitelist()
def compare_revisions(rev_1, rev_2):
	"""
	Compares two Drawing Revisions and produces an item-by-item delta analysis
	showing quantity changes, additions, and removals.
	"""
	if not rev_1 or not rev_2:
		frappe.throw(_("Please select both revisions to compare."))

	doc1 = frappe.get_doc("Drawing Revision", rev_1)
	doc2 = frappe.get_doc("Drawing Revision", rev_2)
	doc1.check_permission("read")
	doc2.check_permission("read")
	if doc1.drawing != doc2.drawing:
		frappe.throw(_("Compare revisions of the same drawing."))

	# Build lookup maps for items: key = (item_code, discipline)
	map1 = {}
	for item in (doc1.items or []):
		key = (item.item_code, item.discipline or "", item.boq_line_id or item.name)
		map1[key] = item

	map2 = {}
	for item in (doc2.items or []):
		key = (item.item_code, item.discipline or "", item.boq_line_id or item.name)
		map2[key] = item

	all_keys = set(map1.keys()).union(set(map2.keys()))
	delta_items = []

	for key in sorted(all_keys, key=lambda k: (k[1], k[0])):
		i1 = map1.get(key)
		i2 = map2.get(key)

		qty1 = float(i1.total_budget_qty or 0) if i1 else 0.0
		qty2 = float(i2.total_budget_qty or 0) if i2 else 0.0
		variance = round(qty2 - qty1, 3)

		item_code = key[0]
		discipline = key[1]
		item_name = (i2.item_name if i2 else (i1.item_name if i1 else ""))
		uom = (i2.uom if i2 else (i1.uom if i1 else ""))

		if not i1:
			status = "Added"
		elif not i2:
			status = "Removed"
		elif variance > 0:
			status = "Increased"
		elif variance < 0:
			status = "Decreased"
		else:
			status = "Unchanged"

		delta_items.append({
			"item_code": item_code,
			"item_name": item_name,
			"discipline": discipline,
			"uom": uom,
			"rev1_qty": qty1,
			"rev2_qty": qty2,
			"variance": variance,
			"status": status
		})

	return {
		"rev1_title": f"{doc1.drawing} ({doc1.revision_no})",
		"rev2_title": f"{doc2.drawing} ({doc2.revision_no})",
		"items": delta_items
	}
