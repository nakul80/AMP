# Copyright (c) 2026, PMG Team and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document

class DailyProgressReport(Document):
	def validate(self):
		self.validate_items()
		self.sync_material_consumptions()

	def validate_items(self):
		if not self.progress_items:
			frappe.throw(_("At least one progress item must be logged."))

		for row in self.progress_items:
			row.validate()

	def sync_material_consumptions(self):
		# If user didn't manually define consumption, auto-populate from progress items
		if not self.material_consumptions:
			for item in self.progress_items:
				if float(item.today_executed_qty or 0) > 0 and item.boq_item:
					self.append("material_consumptions", {
						"item_code": item.boq_item,
						"item_name": frappe.db.get_value("Item", item.boq_item, "item_name"),
						"uom": item.uom,
						"qty_consumed": item.today_executed_qty,
						"drawing": item.drawing,
						"description": item.activity_description
					})

	def on_submit(self):
		self.update_drawing_executed_quantities(is_cancel=False)
		if self.auto_create_stock_entry:
			from amp.amp.api.stock_entry import make_stock_entry_from_dpr
			stock_entry = make_stock_entry_from_dpr(self)
			if stock_entry:
				self.db_set("stock_entry", stock_entry.name)

	def on_cancel(self):
		self.update_drawing_executed_quantities(is_cancel=True)
		if self.stock_entry:
			se = frappe.get_doc("Stock Entry", self.stock_entry)
			if se.docstatus == 1:
				se.cancel()
				frappe.msgprint(_("Linked Stock Entry {0} has been cancelled.").format(self.stock_entry))

	def update_drawing_executed_quantities(self, is_cancel=False):
		"""Updates the cumulative executed quantities in the corresponding Drawing BOQ Item table"""
		multiplier = -1.0 if is_cancel else 1.0

		for p_item in self.progress_items:
			if not p_item.drawing or not p_item.boq_item:
				continue

			executed_delta = float(p_item.today_executed_qty or 0) * multiplier

			# Update Drawing BOQ Item in Project Drawing
			dwg = frappe.get_doc("Project Drawing", p_item.drawing)
			updated = False
			for b_item in dwg.boq_items:
				if b_item.item_code == p_item.boq_item:
					b_item.executed_qty = max(0.0, float(b_item.executed_qty or 0) + executed_delta)
					b_item.calculate_quantities()
					updated = True

			if updated:
				dwg.calculate_totals_and_progress()
				dwg.flags.ignore_validate_update_after_submit = True
				dwg.save(ignore_permissions=True)


def on_dpr_submit(doc, method):
	pass

def on_dpr_cancel(doc, method):
	pass
