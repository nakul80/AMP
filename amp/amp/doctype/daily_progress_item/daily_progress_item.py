# Copyright (c) 2026, PMG Team and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

class DailyProgressItem(Document):
	def validate(self):
		prev = float(self.previously_executed_qty or 0)
		today = float(self.today_executed_qty or 0)
		budget = float(self.drawing_budget_qty or 0)

		self.cumulative_executed_qty = round(prev + today, 3)
		if budget > 0:
			self.balance_qty = max(0.0, round(budget - self.cumulative_executed_qty, 3))
