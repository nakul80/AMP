app_name = "amp"
app_title = "AMP"
app_publisher = "PMG Team"
app_description = "Construction drawings, procurement and site progress"
app_email = "info@example.com"
app_license = "mit"
required_apps = ["erpnext"]
after_install = "amp.setup.install"
after_migrate = "amp.setup.install"
doctype_js = {"Project": "public/js/project.js"}
doctype_list_js = {"Daily Progress Report": "amp/doctype/daily_progress_report/daily_progress_report_list.js"}

doc_events = {
    doctype: {
        "validate": "amp.amp.transactions.validate_transaction",
        "on_update": "amp.amp.transactions.transaction_changed",
        "on_submit": "amp.amp.transactions.transaction_changed",
        "on_cancel": "amp.amp.transactions.transaction_changed",
        "on_update_after_submit": "amp.amp.transactions.transaction_changed",
        "after_delete": "amp.amp.transactions.transaction_changed",
    }
    for doctype in ("Material Request", "Purchase Order", "Purchase Receipt", "Stock Entry")
}
doc_events["Project"] = {"validate": "amp.amp.project.validate_project"}
