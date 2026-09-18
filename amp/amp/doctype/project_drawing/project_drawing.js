// Copyright (c) 2026, PMG Team and contributors
// For license information, please see license.txt

frappe.ui.form.on('Project Drawing', {
	setup: function(frm) {
		// Filter main area by selected project
		frm.set_query('main_area', function() {
			return {
				filters: {
					'project': frm.doc.project || ''
				}
			};
		});

		// Filter sub area by selected main area
		frm.set_query('sub_area', function() {
			return {
				filters: {
					'main_area': frm.doc.main_area || ''
				}
			};
		});
	},

	refresh: function(frm) {
		if (!frm.is_new()) {
			// Button to create new revision
			frm.add_custom_button(__('New Revision'), function() {
				frappe.model.with_doctype('Drawing Revision', function() {
					let new_rev = frappe.model.get_new_doc('Drawing Revision');
					new_rev.drawing = frm.doc.name;
					// Pre-copy existing BOQ items to the new revision for easy incremental editing
					(frm.doc.boq_items || []).forEach(item => {
						let row = frappe.model.add_child(new_rev, 'items');
						row.boq_line_id = item.boq_line_id;
						row.progress_weight = item.progress_weight;
						row.item_code = item.item_code;
						row.item_name = item.item_name;
						row.discipline = item.discipline;
						row.description = item.description;
						row.uom = item.uom;
						row.estimated_qty = item.estimated_qty;
						row.wastage_percent = item.wastage_percent;
						row.total_budget_qty = item.total_budget_qty;
					});
					frappe.set_route('Form', 'Drawing Revision', new_rev.name);
				});
			}, __('Actions'));

			// Button to create ERPNext Material Request (Procurement Indent)
			if (frm.doc.status === 'Good For Construction (GFC)') {
				frm.add_custom_button(__('Create Material Request'), function() {
					frappe.call({
						method: 'amp.amp.api.procurement.create_material_request_from_drawing',
						args: {
							drawing_no: frm.doc.name
						},
						callback: function(r) {
							if (r.message) {
								frappe.set_route('Form', 'Material Request', r.message);
							}
						}
					});
				}, __('Actions'));
			}

			// Shortcut to Site Progress Entry
			frm.add_custom_button(__('Log Daily Progress'), function() {
				frappe.set_route('site-progress-entry', {
					project: frm.doc.project,
					main_area: frm.doc.main_area,
					drawing: frm.doc.name
				});
			}, __('Actions'));
		}
	}
});

frappe.ui.form.on('Drawing BOQ Item', {
	discipline: function(frm, cdt, cdn) {
		let row = locals[cdt][cdn];
		if (row.discipline === 'Structural' && !flt(row.fabrication_progress_weight) && !flt(row.erection_progress_weight)) {
			frappe.model.set_value(cdt, cdn, 'fabrication_progress_weight', 50);
			frappe.model.set_value(cdt, cdn, 'erection_progress_weight', 50);
		}
	},
	item_code: function(frm, cdt, cdn) {
		let row = locals[cdt][cdn];
		if (row.item_code) {
			frappe.db.get_value('Item', row.item_code, ['item_name', 'stock_uom'], function(r) {
				if (r) {
					frappe.model.set_value(cdt, cdn, 'item_name', r.item_name);
					frappe.model.set_value(cdt, cdn, 'uom', r.stock_uom);
				}
			});
		}
	},
	estimated_qty: function(frm, cdt, cdn) {
		recalculate_drawing_boq_row(frm, cdt, cdn);
	},
	wastage_percent: function(frm, cdt, cdn) {
		recalculate_drawing_boq_row(frm, cdt, cdn);
	}
});

function recalculate_drawing_boq_row(frm, cdt, cdn) {
	let row = locals[cdt][cdn];
	let est = flt(row.estimated_qty || 0);
	let wastage = flt(row.wastage_percent || 0);
	let total = est * (1 + (wastage / 100));
	frappe.model.set_value(cdt, cdn, 'total_budget_qty', total);
	let req = flt(row.requested_qty || 0) + flt(row.draft_requested_qty || 0);
	frappe.model.set_value(cdt, cdn, 'balance_to_order', Math.max(0, total - req));
	let exec = flt(row.executed_qty || 0);
	frappe.model.set_value(cdt, cdn, 'balance_to_execute', Math.max(0, est - exec));
}
