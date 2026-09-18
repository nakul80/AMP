import frappe
from frappe import _
from frappe.model.document import Document
from amp.amp.boq import GFC, ensure_ids, populate_operational_quantities, validate_location
from amp.amp.quantities import weighted_completion

BUDGET_FIELDS = (
    "boq_line_id", "item_code", "uom", "discipline", "estimated_qty", "wastage_percent", "progress_weight",
    "fabrication_progress_weight", "erection_progress_weight",
)


def budget_signature(rows):
    return [tuple(row.get(f) for f in BUDGET_FIELDS) for row in rows or []]


class ProjectDrawing(Document):
    def validate(self):
        self.drawing_no = (self.drawing_no or "").strip()
        validate_location(self.project, self.main_area, self.sub_area)
        ensure_ids(self.boq_items or [])
        before = self.get_doc_before_save()
        if before and before.status in (GFC, "As-Built", "Superseded") and not self.flags.from_revision:
            if budget_signature(before.boq_items) != budget_signature(self.boq_items):
                frappe.throw(_("Change an approved drawing's BOQ through a new Drawing Revision."))
        if before and before.status != GFC and self.status == GFC and not self.flags.from_revision:
            frappe.throw(_("Approve a Drawing Revision to release this drawing for construction."))
        if before:
            populate_operational_quantities(self)
        else:
            for row in self.boq_items or []:
                for field in ("executed_qty", "fabricated_qty", "erected_qty", "legacy_executed_qty", "requested_qty", "ordered_qty", "received_qty", "draft_requested_qty"):
                    row.set(field, 0)
        self.calculate_totals_and_progress()

    def calculate_totals_and_progress(self):
        for item in self.boq_items or []:
            item.calculate_quantities()
        self.percent_progress = weighted_completion([
            dict(budget_qty=i.estimated_qty, executed_qty=i.executed_qty, progress_weight=i.progress_weight)
            for i in self.boq_items or []])

    def on_update(self):
        if not self.boq_items or frappe.db.exists("Drawing Revision", {"drawing": self.name}):
            return
        rev = frappe.new_doc("Drawing Revision")
        rev.drawing = self.name
        rev.revision_no = "REV 0"
        rev.issue_date = self.release_date or frappe.utils.nowdate()
        rev.revision_status = "Approved - GFC" if self.status == GFC else "Draft"
        rev.drawing_file = self.drawing_file
        rev.revision_notes = _("Initial Release")
        for row in self.boq_items:
            rev.append("items", {f: row.get(f) for f in (*BUDGET_FIELDS, "item_name", "description")})
        rev.insert(ignore_permissions=True)
        self.db_set("current_revision", "REV 0")
