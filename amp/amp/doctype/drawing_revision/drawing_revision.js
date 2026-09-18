// Copyright (c) 2026, PMG Team and contributors
// For license information, please see license.txt

frappe.ui.form.on('Drawing Revision', {
	refresh: function(frm) {
		if (!frm.is_new()) {
			// Compare with another revision button
			frm.add_custom_button(__('Compare Revisions'), function() {
				frappe.prompt([
					{
						fieldname: 'compare_with',
						fieldtype: 'Link',
						label: __('Compare With Revision'),
						options: 'Drawing Revision',
						get_query: function() {
							return {
								filters: {
									'drawing': frm.doc.drawing,
									'name': ['!=', frm.doc.name]
								}
							};
						},
						reqd: 1
					}
				], function(data) {
					frappe.call({
						method: 'amp.amp.api.revision_delta.compare_revisions',
						args: {
							rev_1: data.compare_with,
							rev_2: frm.doc.name
						},
						callback: function(r) {
							if (r.message) {
								show_delta_dialog(r.message);
							}
						}
					});
				}, __('Select Revision to Compare'));
			}, __('Actions'));

			// Create Material Request button if GFC
			if (frm.doc.revision_status === 'Approved - GFC') {
				frm.add_custom_button(__('Create Material Request'), function() {
					frappe.call({
						method: 'amp.amp.api.procurement.create_material_request_from_revision',
						args: {
							revision_name: frm.doc.name
						},
						callback: function(r) {
							if (r.message) {
								frappe.set_route('Form', 'Material Request', r.message);
							}
						}
					});
				}, __('Actions'));
			}
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
	estimated_qty: function(frm, cdt, cdn) {
		calculate_boq_row(frm, cdt, cdn);
	},
	wastage_percent: function(frm, cdt, cdn) {
		calculate_boq_row(frm, cdt, cdn);
	}
});

function calculate_boq_row(frm, cdt, cdn) {
	let row = locals[cdt][cdn];
	let est = flt(row.estimated_qty || 0);
	let wastage = flt(row.wastage_percent || 0);
	let total = est * (1 + (wastage / 100));
	frappe.model.set_value(cdt, cdn, 'total_budget_qty', total);
	let req = flt(row.requested_qty || 0) + flt(row.draft_requested_qty || 0);
	frappe.model.set_value(cdt, cdn, 'balance_to_order', Math.max(0, total - req));
	let executed = flt(row.executed_qty || 0);
	frappe.model.set_value(cdt, cdn, 'balance_to_execute', Math.max(0, est - executed));
}

function show_delta_dialog(delta) {
	let rows_html = delta.items.map(function(item) {
		let color = item.variance > 0 ? 'text-danger' : (item.variance < 0 ? 'text-success' : '');
		let sign = item.variance > 0 ? '+' : '';
		return `<tr>
			<td>${frappe.utils.escape_html(item.item_code)}</td>
			<td>${frappe.utils.escape_html(item.item_name || '')}</td>
			<td>${frappe.utils.escape_html(item.discipline || '')}</td>
			<td>${frappe.utils.escape_html(item.uom || '')}</td>
			<td class="text-right">${item.rev1_qty.toFixed(2)}</td>
			<td class="text-right">${item.rev2_qty.toFixed(2)}</td>
			<td class="text-right font-weight-bold ${color}">${sign}${item.variance.toFixed(2)}</td>
		</tr>`;
	}).join('');

	let html = `
		<div style="max-height: 400px; overflow-y: auto;">
			<table class="table table-bordered table-sm">
				<thead class="thead-light">
					<tr>
						<th>Item</th>
						<th>Description</th>
						<th>Discipline</th>
						<th>UOM</th>
						<th class="text-right">${frappe.utils.escape_html(delta.rev1_title)}</th>
						<th class="text-right">${frappe.utils.escape_html(delta.rev2_title)}</th>
						<th class="text-right">Delta (Variance)</th>
					</tr>
				</thead>
				<tbody>
					${rows_html}
				</tbody>
			</table>
		</div>
	`;

	let d = new frappe.ui.Dialog({
		title: __('Drawing Revision Quantity Comparison'),
		fields: [
			{
				fieldname: 'comparison_html',
				fieldtype: 'HTML',
				options: html
			}
		],
		primary_action_label: __('Close'),
		primary_action: function() {
			d.hide();
		}
	});
	d.show();
}
