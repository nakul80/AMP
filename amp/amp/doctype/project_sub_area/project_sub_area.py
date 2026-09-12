# Copyright (c) 2026, PMG Team and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

class ProjectSubArea(Document):
	def validate(self):
		if self.sub_area_code:
			self.sub_area_code = self.sub_area_code.strip().upper()
		if self.main_area and not self.project:
			self.project = frappe.db.get_value("Project Main Area", self.main_area, "project")
