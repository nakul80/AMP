# Copyright (c) 2026, PMG Team and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document

class ProjectDrawing(Document):
	def validate(self):
		if self.drawing_no:
			self.drawing_no = self.drawing_no.strip()
		self.calculate_totals_and_progress()

	def calculate_totals_and_progress(self):
		total_budget = 0.0
		total_executed = 0.0

		for item in (self.boq_items or []):
			item.calculate_quantities()
			total_budget += float(item.total_budget_qty or 0)
			total_executed += float(item.executed_qty or 0)

		if total_budget > 0:
			self.percent_progress = min(100.0, round((total_executed / total_budget) * 100.0, 2))
		else:
			self.percent_progress = 0.0

	def on_update(self):
		# If it's a new drawing with BOQ items and no revision exists yet, automatically create Rev 0
		existing_rev = frappe.db.exists("Drawing Revision", {"drawing": self.name})
		if not existing_rev and self.boq_items:
			rev = frappe.new_doc("Drawing Revision")
			rev.drawing = self.name
			rev.revision_no = "Rev 0"
			rev.issue_date = self.release_date or frappe.utils.nowdate()
			rev.revision_status = "Approved - GFC" if self.status == "Good For Construction (GFC)" else "Draft"
			rev.drawing_file = self.drawing_file
			rev.revision_notes = _("Initial Release")
			for row in self.boq_items:
				rev.append("items", {
					"item_code": row.item_code,
					"item_name": row.item_name,
					"discipline": row.discipline,
					"description": row.description,
					"uom": row.uom,
					"estimated_qty": row.estimated_qty,
					"wastage_percent": row.wastage_percent,
					"total_budget_qty": row.total_budget_qty,
					"requested_qty": row.requested_qty,
					"ordered_qty": row.ordered_qty,
					"received_qty": row.received_qty,
					"executed_qty": row.executed_qty,
					"balance_to_order": row.balance_to_order,
					"balance_to_execute": row.balance_to_execute
				})
			rev.flags.ignore_permissions = True
			rev.insert()
			self.db_set("current_revision", "Rev 0")
