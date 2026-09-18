frappe.ui.form.on('Project', {
    setup(frm) {
        for (const field of ['custom_amp_site_warehouse', 'custom_amp_wip_warehouse']) {
            frm.set_query(field, () => ({filters: {company: frm.doc.company, is_group: 0}}));
        }
    },
    refresh(frm) {
        if (frm.is_new()) return;
        for (const report of ['Project Progress Summary', 'Project Material Status']) {
            frm.add_custom_button(__(report), () => {
                frappe.route_options = {project: frm.doc.name};
                frappe.set_route('query-report', report);
            }, __('AMP Reports'));
        }
        for (const doctype of ['Project Main Area', 'Project Sub Area', 'Project Drawing', 'Daily Progress Report']) {
            frm.add_custom_button(__(doctype), () => {
                frappe.route_options = {project: frm.doc.name};
                frappe.set_route('List', doctype, 'List');
            }, __('AMP Records'));
        }
    }
});
