// Copyright (c) 2026, PMG Team and contributors
// For license information, please see license.txt

frappe.ui.form.on('Project Sub Area', {
	main_area: function(frm) {
		if (frm.doc.main_area) {
			frappe.db.get_value('Project Main Area', frm.doc.main_area, 'project', (r) => {
				if (r && r.project) {
					frm.set_value('project', r.project);
				}
			});
		}
	}
});
