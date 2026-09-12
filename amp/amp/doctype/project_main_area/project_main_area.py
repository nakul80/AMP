# Copyright (c) 2026, PMG Team and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

class ProjectMainArea(Document):
	def validate(self):
		if self.area_code:
			self.area_code = self.area_code.strip().upper()
