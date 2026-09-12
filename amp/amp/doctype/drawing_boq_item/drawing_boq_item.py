# Copyright (c) 2026, PMG Team and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

class DrawingBOQItem(Document):
	def validate(self):
		self.calculate_quantities()

	def calculate_quantities(self):
		est = float(self.estimated_qty or 0)
		wastage = float(self.wastage_percent or 0)
		self.total_budget_qty = round(est * (1.0 + (wastage / 100.0)), 3)
		
		req = float(self.requested_qty or 0)
		self.balance_to_order = max(0.0, round(self.total_budget_qty - req, 3))
		
		exec_qty = float(self.executed_qty or 0)
		self.balance_to_execute = max(0.0, round(self.total_budget_qty - exec_qty, 3))
