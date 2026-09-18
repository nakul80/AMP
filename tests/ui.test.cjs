const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

function context(extra = {}) {
    const frappe = {
        query_reports: {}, listview_settings: {}, pages: {'site-progress-entry': {}},
        datetime: {get_today: () => '2026-09-18'},
        ...extra,
    };
    return vm.createContext({frappe, __: value => value, console});
}
function read(ctx, path, suffix = '') {
    vm.runInContext(fs.readFileSync(path, 'utf8') + suffix, ctx);
}

test('progress report runs with no project/area and area query has no empty-project filter', () => {
    const ctx = context({query_report: {get_filter_value: () => ''}});
    read(ctx, 'amp/amp/report/project_progress_summary/project_progress_summary.js');
    const filters = ctx.frappe.query_reports['Project Progress Summary'].filters;
    for (const field of ['project', 'main_area', 'sub_area', 'drawing']) {
        assert.ok(!filters.find(f => f.fieldname === field).reqd, field);
    }
    assert.equal(JSON.stringify(filters.find(f => f.fieldname === 'main_area').get_query()), '{"filters":{}}');
});

test('material area options narrow only when a project is selected', () => {
    const ctx = context({query_report: {get_filter_value: field => field === 'project' ? 'P1' : ''}});
    read(ctx, 'amp/amp/report/project_material_status/project_material_status.js');
    const filters = ctx.frappe.query_reports['Project Material Status'].filters;
    assert.equal(JSON.stringify(filters.find(f => f.fieldname === 'main_area').get_query()), '{"filters":{"project":"P1"}}');
});

test('DPR list provides submitted status and removes stale filters', () => {
    const ctx = context();
    read(ctx, 'amp/amp/doctype/daily_progress_report/daily_progress_report_list.js');
    const settings = ctx.frappe.listview_settings['Daily Progress Report'];
    assert.equal(settings.get_indicator({docstatus: 1})[0], 'Submitted');
    assert.equal(settings.get_indicator({docstatus: 2})[0], 'Cancelled');
    const buttons = {};
    const events = [];
    settings.onload({page: {add_inner_button: (name, action) => buttons[name] = action},
        filter_area: {clear: () => events.push('clear'), add: value => events.push(value)},
        refresh: () => events.push('refresh')});
    buttons['Submitted DPRs']();
    assert.equal(events[0], 'clear');
    assert.equal(JSON.stringify(events[1]), '[["Daily Progress Report","docstatus","=",1]]');
    assert.equal(events[2], 'refresh');
});

test('DPR can fetch BOQ lines before first save', () => {
    const registrations = {};
    const ctx = context({ui: {form: {on: (doctype, events) => registrations[doctype] = events}}});
    read(ctx, 'amp/amp/doctype/daily_progress_report/daily_progress_report.js');
    const buttons = [];
    registrations['Daily Progress Report'].refresh({doc: {docstatus: 0}, is_new: () => true,
        add_custom_button: name => buttons.push(name)});
    assert.ok(buttons.includes('Fetch Open Drawing Tasks'));
});

test('quick entry ignores stale responses after changing area', () => {
    const calls = [];
    const ctx = context({call: options => calls.push(options)});
    read(ctx, 'amp/amp/page/site_progress_entry/site_progress_entry.js', '\nglobalThis.Entry = SiteProgressEntry;');
    const entry = Object.create(ctx.Entry.prototype);
    let area = 'A1';
    Object.assign(entry, {project_field: {get_value: () => 'P1'},
        main_area_field: {get_value: () => area}, sub_area_field: {get_value: () => ''},
        drawing_filter: null, load_sequence: 0, render_grid: () => {}});
    entry.load_tasks();
    area = 'A2';
    entry.load_tasks();
    calls[1].callback({message: ['A2 result']});
    calls[0].callback({message: ['A1 stale result']});
    assert.equal(entry.tasks[0], 'A2 result');
});
