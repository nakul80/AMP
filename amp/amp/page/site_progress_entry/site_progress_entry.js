// Copyright (c) 2026, PMG Team and contributors
// For license information, please see license.txt

frappe.pages['site-progress-entry'].on_page_load = function(wrapper) {
	var page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __('Site Progress Quick Entry'),
		single_column: true
	});

	let me = new SiteProgressEntry(page);
	wrapper.site_progress_entry = me;
};

frappe.pages['site-progress-entry'].on_page_show = function(wrapper) {
	let params = frappe.route_options || {};
	frappe.route_options = null;
	if (wrapper.site_progress_entry && params.project) {
		wrapper.site_progress_entry.set_filters(params);
	}
};

class SiteProgressEntry {
	constructor(page) {
		this.page = page;
		this.tasks = [];
		this.load_sequence = 0;
		this.drawing_filter = null;
		this.init_ui();
	}

	init_ui() {
		let me = this;

		// Primary Action: Submit
		this.page.set_primary_action(__('Submit Progress'), function() {
			me.submit_batch_progress();
		}, 'octicon octicon-check');

		// Secondary Action: Refresh
		this.page.add_button(__('Load Open Tasks'), function() {
			me.load_tasks();
		});

		this.page.add_button(__('Project Progress Report'), () => {
			frappe.route_options = {project: this.project_field.get_value()};
			frappe.set_route('query-report', 'Project Progress Summary');
		});

		// Build filter container
		let filter_html = `
			<div class="site-progress-container">
				<div class="site-progress-filter-card">
					<div class="row">
						<div class="col-md-3 col-sm-6 mb-2" id="filter-project"></div>
						<div class="col-md-3 col-sm-6 mb-2" id="filter-main-area"></div>
						<div class="col-md-2 col-sm-6 mb-2" id="filter-sub-area"></div>
						<div class="col-md-2 col-sm-6 mb-2" id="filter-date"></div>
						<div class="col-md-2 col-sm-6 mb-2" id="filter-warehouse"></div>
					</div>
					<div class="row mt-2">
						<div class="col-md-4 col-sm-6" id="filter-contractor"></div>
						<div class="col-md-8 col-sm-6" id="filter-remarks"></div>
					</div>
				</div>

				<div class="site-progress-table-card">
					<div class="site-progress-table-wrapper" id="task-grid-container">
						<div class="text-muted text-center p-5">
							${__('Please select a Project and Main Area above, then click "Load Open Tasks".')}
						</div>
					</div>
				</div>
			</div>
		`;

		this.page.main.html(filter_html);
		this.page.main.find('.site-progress-table-card').prepend($('<p class="text-muted p-3">').text(__('Material Used is optional and independent of work executed. Stock posting requires a warehouse and Stock Entry permissions.')));
		this.setup_fields();
	}

	setup_fields() {
		let me = this;

		this.project_field = frappe.ui.form.make_control({
			df: {
				fieldtype: 'Link',
				options: 'Project',
				label: __('Project'),
				fieldname: 'project',
				reqd: 1,
				change: function() {
					me.drawing_filter = null;
						me.load_sequence++;
						me.tasks = [];
						me.render_grid();
						me.main_area_field.set_input('');
					me.sub_area_field.set_input('');
				}
			},
			parent: this.page.main.find('#filter-project'),
			render_input: true
		});

		this.main_area_field = frappe.ui.form.make_control({
			df: {
				fieldtype: 'Link',
				options: 'Project Main Area',
				label: __('Main Area'),
				fieldname: 'main_area',
				reqd: 1,
				get_query: function() {
					return {
						filters: {
							'project': me.project_field.get_value() || ''
						}
					};
				},
				change: function() {
					me.sub_area_field.set_input('');
					if (me.project_field.get_value() && me.main_area_field.get_value()) {
						me.load_tasks();
					}
				}
			},
			parent: this.page.main.find('#filter-main-area'),
			render_input: true
		});

		this.sub_area_field = frappe.ui.form.make_control({
			df: {
				fieldtype: 'Link',
				options: 'Project Sub Area',
				label: __('Sub Area (Optional)'),
				fieldname: 'sub_area',
				get_query: function() {
					return {
						filters: {
							'main_area': me.main_area_field.get_value() || ''
						}
					};
				},
				change: function() {
					if (me.project_field.get_value() && me.main_area_field.get_value()) {
						me.load_tasks();
					}
				}
			},
			parent: this.page.main.find('#filter-sub-area'),
			render_input: true
		});

		this.date_field = frappe.ui.form.make_control({
			df: {
				fieldtype: 'Date',
				label: __('Posting Date'),
				default: frappe.datetime.get_today(),
				fieldname: 'posting_date'
			},
			parent: this.page.main.find('#filter-date'),
			render_input: true
		});
		this.date_field.set_input(frappe.datetime.get_today());

		this.warehouse_field = frappe.ui.form.make_control({
			df: {
				fieldtype: 'Link',
				options: 'Warehouse',
				label: __('Site Warehouse (Stock Deduction)'),
				fieldname: 'source_warehouse',
				get_query: function() {
					return { filters: { 'is_group': 0 } };
				}
			},
			parent: this.page.main.find('#filter-warehouse'),
			render_input: true
		});

		this.contractor_field = frappe.ui.form.make_control({
			df: {
				fieldtype: 'Link',
				options: 'Supplier',
				label: __('Contractor / Gang (Optional)'),
				fieldname: 'contractor'
			},
			parent: this.page.main.find('#filter-contractor'),
			render_input: true
		});

		this.remarks_field = frappe.ui.form.make_control({
			df: {
				fieldtype: 'Data',
				label: __('Daily Remarks / Log Summary'),
				fieldname: 'remarks'
			},
			parent: this.page.main.find('#filter-remarks'),
			render_input: true
		});
	}

	set_filters(params) {
		if (params.project) this.project_field.set_input(params.project);
		if (params.main_area) this.main_area_field.set_input(params.main_area);
		if (params.sub_area) this.sub_area_field.set_input(params.sub_area);
		this.drawing_filter = params.drawing || null;
		this.load_tasks();
	}

	load_tasks() {
		let me = this;
		let project = this.project_field.get_value();
		let main_area = this.main_area_field.get_value();
		let sub_area = this.sub_area_field.get_value();

		if (!project || !main_area) {
			frappe.msgprint(__('Please select both Project and Main Area.'));
			return;
		}

		const sequence = ++this.load_sequence;
		frappe.call({
			method: 'amp.amp.api.progress.get_pending_drawing_items',
			args: {
				project: project,
				main_area: main_area,
				sub_area: sub_area,
				drawing: this.drawing_filter
			},
			callback: function(r) {
				if (sequence !== me.load_sequence) return;
				me.tasks = r.message || [];
				me.render_grid();
			}
		});
	}

	render_grid() {
		let me = this;
		let container = this.page.main.find('#task-grid-container');

		if (!this.tasks || this.tasks.length === 0) {
			container.html(`
				<div class="text-muted text-center p-5">
					<i class="octicon octicon-info" style="font-size: 24px;"></i>
					<div class="mt-2">${__('No pending drawing items found for this area. Make sure Drawings are created and marked GFC.')}</div>
				</div>
			`);
			return;
		}

		let rows_html = this.tasks.map((task, idx) => {
			let pct = task.total_budget_qty > 0 ? ((task.executed_qty / task.total_budget_qty) * 100).toFixed(1) : 0;
			let disc_class = `discipline-${(task.discipline || 'Other').replace(/[^a-zA-Z0-9_-]/g, '-')}`;

			let work_entry = task.is_structural
				? `<td class="text-center text-muted">—</td>
					<td class="text-center"><input type="number" step="any" min="0" class="site-input-progress site-input-fabrication" data-idx="${idx}" placeholder="0.00" tabindex="${idx + 1}" /></td>
					<td class="text-center"><input type="number" step="any" min="0" class="site-input-progress site-input-erection" data-idx="${idx}" placeholder="0.00" tabindex="${idx + 1}" /></td>`
				: `<td class="text-center"><input type="number" step="any" min="0" class="site-input-progress site-input-qty" data-idx="${idx}" placeholder="0.00" tabindex="${idx + 1}" /></td>
					<td class="text-center text-muted">—</td><td class="text-center text-muted">—</td>`;

			return `
				<tr data-idx="${idx}">
					<td class="font-weight-bold">
						<a href="/app/project-drawing/${encodeURIComponent(task.drawing)}" target="_blank">${frappe.utils.escape_html(task.drawing_no)}</a>
						<span class="text-muted small">(${frappe.utils.escape_html(task.revision || 'Rev 0')})</span>
					</td>
					<td>
						<span class="discipline-badge ${disc_class}">${frappe.utils.escape_html(task.discipline || '')}</span>
					</td>
					<td>
						<div class="font-weight-500">${frappe.utils.escape_html(task.item_name || task.item_code)}</div>
						<div class="text-muted small">${frappe.utils.escape_html(task.description || '')}</div>
					</td>
					<td><span class="badge badge-light">${frappe.utils.escape_html(task.uom)}</span></td>
					<td class="text-right font-weight-500">${task.total_budget_qty.toFixed(2)}</td>
					<td class="text-right text-muted">${task.executed_qty.toFixed(2)}</td>
					${work_entry}
					<td><input type="number" step="any" min="0" class="site-input-material" data-idx="${idx}" placeholder="Optional" ${task.is_stock_item ? "" : "disabled"} /></td>
					<td class="text-nowrap" id="cell-progress-${idx}">
						<div class="progress-bar-container">
							<div class="progress-bar-fill" id="progress-fill-${idx}" style="width: ${Math.min(100, pct)}%"></div>
						</div>
						<span class="small font-weight-500" id="progress-text-${idx}">${pct}%</span>
					</td>
					<td>
						<input type="text" class="site-input-text site-input-loc" data-idx="${idx}" placeholder="e.g. Grid A-C" />
					</td>
					<td>
						<input type="text" class="site-input-text site-input-rem" data-idx="${idx}" placeholder="Remarks" />
					</td>
				</tr>
			`;
		}).join('');

		let table_html = `
			<table class="site-progress-table">
				<thead>
					<tr>
						<th>Drawing No</th>
						<th>Discipline</th>
						<th>BOQ Item / Activity</th>
						<th>UOM</th>
						<th class="text-right">Budget Qty</th>
						<th class="text-right">Prev Done</th>
						<th class="text-center" style="background-color: #ecfdf5; color: #047857;">Today's Executed Qty</th>
						<th class="text-center" style="background-color: #eff6ff; color: #1d4ed8;">Today Fabricated Qty</th>
						<th class="text-center" style="background-color: #fef3c7; color: #92400e;">Today Erected Qty</th>
						<th>Material Used (same UOM)</th>
						<th>Cumulative Progress</th>
						<th>Location / Grid</th>
						<th>Remarks</th>
					</tr>
				</thead>
				<tbody>
					${rows_html}
				</tbody>
			</table>
		`;

		container.html(table_html);

		// Event listeners for Excel-like rapid entry
		container.find('.site-input-progress').on('input', function() {
			let idx = parseInt($(this).data('idx'));
			let task = me.tasks[idx];
			let direct = flt(container.find(`.site-input-qty[data-idx="${idx}"]`).val() || 0);
			let fabricated = flt(container.find(`.site-input-fabrication[data-idx="${idx}"]`).val() || 0);
			let erected = flt(container.find(`.site-input-erection[data-idx="${idx}"]`).val() || 0);
			let val = task.is_structural
				? fabricated * flt(task.fabrication_progress_weight || 0) / 100 + erected * flt(task.erection_progress_weight || 0) / 100
				: direct;

			let cumulative = task.executed_qty + val;
			let pct = task.total_budget_qty > 0 ? ((cumulative / task.total_budget_qty) * 100).toFixed(1) : 0;

			$(`#progress-fill-${idx}`).css('width', `${Math.min(100, pct)}%`);
			$(`#progress-text-${idx}`).text(`${pct}%`);
			if (pct > 100) {
				$(`#progress-fill-${idx}`).css('background-color', '#ef4444');
			} else {
				$(`#progress-fill-${idx}`).css('background-color', '#10b981');
			}
		});

		// Arrow key down / up navigation (Excel navigation)
		container.find('.site-input-progress').on('keydown', function(e) {
			let idx = parseInt($(this).data('idx'));
			if (e.key === 'ArrowDown' || e.key === 'Enter') {
				e.preventDefault();
				let inputs = container.find('.site-input-progress');
				let current = inputs.index(this);
				let next = inputs.eq(current + 1);
				if (next.length) next.focus().select();
			} else if (e.key === 'ArrowUp') {
				e.preventDefault();
				let inputs = container.find('.site-input-progress');
				let current = inputs.index(this);
				let prev = inputs.eq(current - 1);
				if (prev.length) prev.focus().select();
			}
		});
	}

	submit_batch_progress() {
		let me = this;
		let project = this.project_field.get_value();
		let main_area = this.main_area_field.get_value();
		let sub_area = this.sub_area_field.get_value();
		let posting_date = this.date_field.get_value();
		let source_warehouse = this.warehouse_field.get_value();
		let contractor = this.contractor_field.get_value();
		let remarks = this.remarks_field.get_value();

		if (!project || !main_area) {
			frappe.msgprint(__('Please select Project and Main Area.'));
			return;
		}

		let items_to_log = [];
		this.tasks.forEach((task, idx) => {
			let qty = flt(me.page.main.find(`.site-input-qty[data-idx="${idx}"]`).val() || 0);
			let fabricated = flt(me.page.main.find(`.site-input-fabrication[data-idx="${idx}"]`).val() || 0);
			let erected = flt(me.page.main.find(`.site-input-erection[data-idx="${idx}"]`).val() || 0);
			if (qty > 0 || fabricated > 0 || erected > 0) {
				let task = me.tasks[idx];
				let loc = me.page.main.find(`.site-input-loc[data-idx="${idx}"]`).val() || '';
				let rem = me.page.main.find(`.site-input-rem[data-idx="${idx}"]`).val() || '';

				items_to_log.push({
					drawing: task.drawing,
					discipline: task.discipline,
					item_code: task.item_code,
					boq_line_id: task.boq_line_id,
					material_qty: flt(me.page.main.find(`.site-input-material[data-idx="${idx}"]`).val() || 0),
					item_name: task.item_name,
					description: task.description,
					uom: task.uom,
					budget_qty: task.total_budget_qty,
					prev_qty: task.executed_qty,
					today_qty: qty,
					fabricated_qty: fabricated,
					erected_qty: erected,
					location_grid: loc,
					remarks: rem
				});
			}
		});

		if (items_to_log.length === 0) {
			frappe.msgprint(__('Enter executed, fabricated, or erected quantity for at least one item.'));
			return;
		}

		frappe.confirm(__('Submit progress for {0} items? Entered material usage is posted to stock only when a source warehouse is selected.', [items_to_log.length]), function() {
			frappe.call({
				method: 'amp.amp.api.progress.submit_quick_progress',
				args: {
					payload: {
						project: project,
						main_area: main_area,
						sub_area: sub_area,
						posting_date: posting_date,
						source_warehouse: source_warehouse,
						contractor: contractor,
						remarks: remarks,
						items: items_to_log
					}
				},
				freeze: true,
				freeze_message: __('Recording daily progress and updating stock ledger...'),
				callback: function(r) {
					if (r.message && r.message.status === 'success') {
						let msg = __('Daily Progress Report {0} created and submitted successfully.', [
							frappe.utils.get_link_to_form('Daily Progress Report', r.message.dpr_name)
						]);
						if (r.message.stock_entry) {
							msg += '<br>' + __('ERPNext Stock Entry {0} generated.', [
								frappe.utils.get_link_to_form('Stock Entry', r.message.stock_entry)
							]);
						}
						frappe.msgprint({
							title: __('Progress Saved'),
							message: msg,
							indicator: 'green',
							primary_action: {
								label: __('View Submitted DPR'),
								action() { frappe.set_route('Form', 'Daily Progress Report', r.message.dpr_name); }
							}
						});

						// Reload tasks to reflect updated execution numbers
						me.load_tasks();
					}
				}
			});
		});
	}
}
