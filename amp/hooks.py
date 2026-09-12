app_name = "amp"
app_title = "AMP"
app_publisher = "PMG Team"
app_description = "App for Managing Projects - Drawings, BOQs, Procurement Indents & Daily Progress Reports with WIP Stock Integration"
app_email = "info@example.com"
app_license = "mit"

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/amp/css/amp.css"
# app_include_js = "/assets/amp/js/amp.js"

# Document Events
# ---------------
# Hook on document methods and events

doc_events = {
	"Daily Progress Report": {
		"on_submit": "amp.amp.doctype.daily_progress_report.daily_progress_report.on_dpr_submit",
		"on_cancel": "amp.amp.doctype.daily_progress_report.daily_progress_report.on_dpr_cancel"
	}
}

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# Permissions
# -----------
# Permissions evaluated in scripted ways

# Scheduled Tasks
# ---------------

# scheduler_events = {
# 	"daily": [
# 		"amp.amp.tasks.daily"
# 	],
# }
