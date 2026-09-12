// Copyright (c) 2026, PMG Team and contributors
// For license information, please see license.txt

frappe.ui.form.on('Daily Progress Report', {
	setup: function(frm) {
		frm.set_query('main_area', function() {
			return {
				filters: {
					'project': frm.doc.project || ''
				}
			};
		});

		frm.set_query('sub_area', function() {
			return {
				filters: {
					'main_area': frm.doc.main_area || ''
				}
			};
		});

		frm.set_query('source_warehouse', function() {
			return {
				filters: {
					'is_group': 0
				}
			};
		});

		frm.set_query('target_warehouse', function() {
			return {
				filters: {
					'is_group': 0
				}
			};
		});
	},

	refresh: function(frm) {
		if (frm.doc.docstatus === 1 && frm.doc.stock_entry) {
			frm.add_custom_button(__('View Stock Entry'), function() {
				frappe.set_route('Form', 'Stock Entry', frm.doc.stock_entry);
			}, __('Inventory'));
		}

		if (frm.doc.docstatus === 0 && !frm.is_new()) {
			frm.add_custom_button(__('Fetch Open Drawing Tasks'), function() {
				if (!frm.doc.project || !frm.doc.main_area) {
					frappe.msgprint(__('Please select Project and Main Area first.'));
					return;
				}

				frappe.call({
					method: 'amp.amp.api.progress.get_pending_drawing_items',
					args: {
						project: frm.doc.project,
						main_area: frm.doc.main_area,
						sub_area: frm.doc.sub_area
					},
					callback: function(r) {
						if (r.message && r.message.length > 0) {
							frm.clear_table('progress_items');
							r.message.forEach(item => {
								let row = frm.add_child('progress_items');
								row.drawing = item.drawing;
								row.boq_item = item.item_code;
								row.activity_description = item.description || item.item_name;
								row.uom = item.uom;
								row.drawing_budget_qty = item.total_budget_qty;
								row.previously_executed_qty = item.executed_qty;
								row.today_executed_qty = 0;
								row.cumulative_executed_qty = item.executed_qty;
								row.balance_qty = item.balance_to_execute;
							});
							frm.refresh_field('progress_items');
							frappe.show_alert({message: __('Loaded {0} drawing tasks', [r.message.length]), indicator: 'green'});
						} else {
							frappe.msgprint(__('No pending drawing items found for this area.'));
						}
					}
				});
			});
		}
	}
});

frappe.ui.form.on('Daily Progress Item', {
	drawing: function(frm, cdt, cdn) {
		let row = locals[cdt][cdn];
		if (row.drawing) {
			frappe.db.get_doc('Project Drawing', row.drawing).then(dwg => {
				if (dwg.boq_items && dwg.boq_items.length === 1) {
					let b = dwg.boq_items[0];
					frappe.model.set_value(cdt, cdn, 'boq_item', b.item_code);
					frappe.model.set_value(cdt, cdn, 'uom', b.uom);
					frappe.model.set_value(cdt, cdn, 'drawing_budget_qty', b.total_budget_qty);
					frappe.model.set_value(cdt, cdn, 'previously_executed_qty', b.executed_qty);
					frappe.model.set_value(cdt, cdn, 'balance_qty', b.balance_to_execute);
				}
			});
		}
	},
	today_executed_qty: function(frm, cdt, cdn) {
		let row = locals[cdt][cdn];
		let prev = flt(row.previously_executed_qty || 0);
		let today = flt(row.today_executed_qty || 0);
		let budget = flt(row.drawing_budget_qty || 0);

		let cumulative = prev + today;
		frappe.model.set_value(cdt, cdn, 'cumulative_executed_qty', cumulative);
		if (budget > 0) {
			frappe.model.set_value(cdt, cdn, 'balance_qty', Math.max(0, budget - cumulative));
		}
	}
});
