# Copyright (c) 2026, PMG Team and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document

class DrawingRevision(Document):
	def validate(self):
		if self.revision_no:
			self.revision_no = self.revision_no.strip().upper()
		self.total_items_count = len(self.items or [])
		self.calculate_item_totals()

	def calculate_item_totals(self):
		for item in (self.items or []):
			item.calculate_quantities()

	def on_update(self):
		self.sync_with_parent_drawing()

	def sync_with_parent_drawing(self):
		if not self.drawing:
			return

		# If this revision is Approved - GFC, mark older revisions as Superseded
		if self.revision_status == "Approved - GFC":
			older_revs = frappe.get_all(
				"Drawing Revision",
				filters={
					"drawing": self.drawing,
					"name": ["!=", self.name],
					"revision_status": "Approved - GFC"
				}
			)
			for old in older_revs:
				frappe.db.set_value("Drawing Revision", old.name, "revision_status", "Superseded")

			# Update parent drawing metadata
			parent_dwg = frappe.get_doc("Project Drawing", self.drawing)
			parent_dwg.current_revision = self.revision_no
			parent_dwg.status = "Good For Construction (GFC)"
			if self.drawing_file:
				parent_dwg.drawing_file = self.drawing_file

			# Synchronize active BOQ items on Project Drawing
			parent_dwg.boq_items = []
			for row in (self.items or []):
				parent_dwg.append("boq_items", {
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
			parent_dwg.flags.ignore_validate_update_after_submit = True
			parent_dwg.save(ignore_permissions=True)
