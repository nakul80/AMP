import frappe
from frappe import _
from frappe.model.document import Document
from amp.amp.boq import GFC, ensure_ids, lock_drawing, refresh_drawing
from amp.amp.doctype.project_drawing.project_drawing import BUDGET_FIELDS, budget_signature


class DrawingRevision(Document):
    def validate(self):
        self.revision_no = (self.revision_no or "").strip().upper()
        lock_drawing(self.drawing)
        drawing = frappe.get_doc("Project Drawing", self.drawing, for_update=True)
        drawing.check_permission("write")
        ensure_ids(self.items or [])
        before = self.get_doc_before_save()
        if before and before.revision_status in ("Approved - GFC", "Superseded"):
            if before.drawing != self.drawing or before.revision_no != self.revision_no or budget_signature(before.items) != budget_signature(self.items):
                frappe.throw(_("Approved revision quantities are immutable. Create a new revision."))
            if before.revision_status != self.revision_status:
                frappe.throw(_("Approve a new revision to supersede the current revision."))
        known = frappe.get_all("Drawing BOQ Item", filters={"parenttype": "Drawing Revision", "parent": ["in", frappe.get_all("Drawing Revision", filters={"drawing": self.drawing}, pluck="name") or [""]]}, fields=["boq_line_id", "item_code", "uom", "discipline"])
        for row in self.items or []:
            for old in known:
                if old.boq_line_id == row.boq_line_id and (old.item_code, old.uom, old.discipline) != (row.item_code, row.uom, row.discipline):
                    frappe.throw(_("An existing BOQ reference must keep its item, discipline and UOM. Add a new row for a different activity."))
            row.calculate_quantities()
        self.total_items_count = len(self.items or [])

    def on_update(self):
        if self.revision_status != "Approved - GFC":
            return
        for old in frappe.get_all("Drawing Revision", filters={"drawing": self.drawing, "name": ["!=", self.name], "revision_status": "Approved - GFC"}, pluck="name"):
            frappe.db.set_value("Drawing Revision", old, "revision_status", "Superseded")
        parent = frappe.get_doc("Project Drawing", self.drawing, for_update=True)
        parent.current_revision = self.revision_no
        parent.status = GFC
        if self.drawing_file:
            parent.drawing_file = self.drawing_file
        # Only design data is copied; operational totals are rebuilt from transactions.
        if budget_signature(parent.boq_items) != budget_signature(self.items):
            parent.set("boq_items", [])
            for row in self.items or []:
                parent.append("boq_items", {f: row.get(f) for f in (*BUDGET_FIELDS, "item_name", "description")})
        parent.flags.from_revision = True
        parent.save(ignore_permissions=True)
        refresh_drawing(parent.name)
