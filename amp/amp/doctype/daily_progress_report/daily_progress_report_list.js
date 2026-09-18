frappe.listview_settings['Daily Progress Report'] = {
    add_fields: ['docstatus', 'project', 'posting_date', 'main_area', 'stock_entry'],
    has_indicator_for_draft: true,
    has_indicator_for_cancelled: true,
    get_indicator(doc) {
        const statuses = {0: [__('Draft'), 'orange'], 1: [__('Submitted'), 'blue'], 2: [__('Cancelled'), 'red']};
        const [label, color] = statuses[doc.docstatus];
        return [label, color, `docstatus,=,${doc.docstatus}`];
    },
    onload(listview) {
        listview.page.add_inner_button(__('Show All DPRs'), () => {
            listview.filter_area.clear();
            listview.refresh();
        });
        listview.page.add_inner_button(__('Submitted DPRs'), () => {
            listview.filter_area.clear();
            listview.filter_area.add([['Daily Progress Report', 'docstatus', '=', 1]]);
            listview.refresh();
        });
        listview.page.add_inner_button(__('Project Progress'), () => {
            frappe.set_route('query-report', 'Project Progress Summary');
        });
    }
};
