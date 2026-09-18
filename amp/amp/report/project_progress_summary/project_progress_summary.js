frappe.query_reports["Project Progress Summary"] = {
    tree: true,
    name_field: "activity",
    initial_depth: 1,
    filters: [
        {fieldname: 'project', label: __('Project'), fieldtype: 'Link', options: 'Project',
            on_change() {
                frappe.query_report.set_filter_value('main_area', '');
                frappe.query_report.set_filter_value('sub_area', '');
                frappe.query_report.set_filter_value('drawing', '');
                frappe.query_report.refresh();
            }},
        {fieldname: 'main_area', label: __('Main Area (optional)'), fieldtype: 'Link', options: 'Project Main Area',
            get_query: () => ({filters: frappe.query_report.get_filter_value('project') ? {project: frappe.query_report.get_filter_value('project')} : {}}),
            on_change() {
                frappe.query_report.set_filter_value('sub_area', '');
                frappe.query_report.set_filter_value('drawing', '');
                frappe.query_report.refresh();
            }},
        {fieldname: 'sub_area', label: __('Sub Area (optional)'), fieldtype: 'Link', options: 'Project Sub Area',
            get_query() {
                const filters = {};
                for (const field of ['project', 'main_area']) {
                    const value = frappe.query_report.get_filter_value(field);
                    if (value) filters[field] = value;
                }
                return {filters};
            }},
        {fieldname: 'drawing', label: __('Drawing (optional)'), fieldtype: 'Link', options: 'Project Drawing',
            get_query() {
                const filters = {};
                for (const field of ['project', 'main_area', 'sub_area']) {
                    const value = frappe.query_report.get_filter_value(field);
                    if (value) filters[field] = value;
                }
                return {filters};
            }},
        {fieldname: 'from_date', label: __('From Date (optional)'), fieldtype: 'Date'},
        {fieldname: 'to_date', label: __('To Date'), fieldtype: 'Date', default: frappe.datetime.get_today(), reqd: 1},
        {fieldname: 'show_dprs', label: __('Show DPR Entries'), fieldtype: 'Check', default: 1}
    ]
};
