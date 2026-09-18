import frappe
from frappe import _
from frappe.model.document import Document
from amp.amp.boq import GFC, drawing_stage_totals, drawing_totals, lock_drawing, refresh_drawing, resolve_line, validate_location
from amp.amp.quantities import number, structural_progress_values


class DailyProgressReport(Document):
    def validate(self):
        validate_location(self.project, self.main_area, self.sub_area)
        if not self.progress_items:
            frappe.throw(_("At least one progress item must be logged."))
        drawings = {}
        for name in sorted({r.drawing for r in self.progress_items if r.drawing}):
            lock_drawing(name)
            drawing = frappe.get_doc("Project Drawing", name, for_update=True)
            drawing.check_permission("read")
            if drawing.project != self.project or drawing.main_area != self.main_area or (self.sub_area and drawing.sub_area != self.sub_area):
                frappe.throw(_("DPR drawing must belong to its Project, Main Area and selected Sub Area."))
            if drawing.status != GFC:
                frappe.throw(_("Progress can only be logged against GFC drawings."))
            drawings[name] = (
                drawing,
                drawing_totals(drawing, for_update=True),
                drawing_stage_totals(drawing, for_update=True),
            )
        seen = set()
        for row in self.progress_items:
            drawing, totals, stages = drawings[row.drawing]
            line = resolve_line(drawing, row.boq_line_id, row.boq_item, row.uom)
            key = (drawing.name, line.boq_line_id)
            if key in seen:
                frappe.throw(_("Log each BOQ line only once per DPR."))
            seen.add(key)
            if any(number(row.get(field)) < 0 for field in (
                "today_executed_qty", "today_fabricated_qty", "today_erected_qty"
            )):
                frappe.throw(_("Executed quantities cannot be negative."))
            row.boq_line_id = line.boq_line_id
            row.drawing_revision = frappe.db.get_value("Drawing Revision", {"drawing": drawing.name, "revision_status": "Approved - GFC"}, "name")
            row.uom = line.uom
            row.drawing_budget_qty = line.estimated_qty
            row.previously_executed_qty = totals.get(line.boq_line_id, 0)
            stage = stages.get(line.boq_line_id, {})
            row.previously_fabricated_qty = stage.get("fabricated", 0)
            row.previously_erected_qty = stage.get("erected", 0)
            if line.discipline == "Structural":
                if number(row.today_executed_qty):
                    frappe.throw(_("Use Fabricated Qty or Erected Qty for Structural BOQ lines; Combined Executed Qty is for legacy records only."))
                progress = structural_progress_values(
                    line.estimated_qty, line.fabrication_progress_weight, line.erection_progress_weight,
                    number(row.previously_fabricated_qty) + number(row.today_fabricated_qty),
                    number(row.previously_erected_qty) + number(row.today_erected_qty),
                )
                row.today_executed_qty = round(progress["executed_qty"] - number(row.previously_executed_qty), 3)
                row.is_structural_stage_progress = 1
            row.validate()
        if not any(
            number(r.today_executed_qty) > 0 or number(r.today_fabricated_qty) > 0 or number(r.today_erected_qty) > 0
            for r in self.progress_items
        ):
            frappe.throw(_("Enter a positive executed quantity for at least one activity."))
        for row in self.material_consumptions or []:
            if number(row.qty_consumed) <= 0:
                frappe.throw(_("Material quantities must be positive."))
            if row.drawing:
                drawing = frappe.get_doc("Project Drawing", row.drawing)
                drawing.check_permission("read")
                if drawing.project != self.project or drawing.main_area != self.main_area or (self.sub_area and drawing.sub_area != self.sub_area):
                    frappe.throw(_("Material drawing must belong to the DPR location."))
                line = resolve_line(drawing, row.boq_line_id, row.item_code, row.uom)
                row.boq_line_id = line.boq_line_id
                row.drawing_revision = frappe.db.get_value("Drawing Revision", {"drawing": drawing.name, "revision_status": "Approved - GFC"}, "name")
            elif row.boq_line_id or row.drawing_revision:
                frappe.throw(_("Select a drawing for the material BOQ reference."))
        if self.auto_create_stock_entry and self.material_consumptions:
            if not self.source_warehouse:
                frappe.throw(_("Select a source warehouse for stock posting."))
            if self.stock_entry_type == "Material Transfer" and not self.target_warehouse:
                frappe.throw(_("Select a WIP target warehouse for material transfer."))

    def on_submit(self):
        for name in sorted({r.drawing for r in self.progress_items}):
            refresh_drawing(name)
        if self.auto_create_stock_entry:
            from amp.amp.api.stock_entry import make_stock_entry_from_dpr
            entry = make_stock_entry_from_dpr(self)
            if entry:
                self.db_set("stock_entry", entry.name)

    def on_cancel(self):
        if self.stock_entry:
            entry = frappe.get_doc("Stock Entry", self.stock_entry)
            if entry.docstatus == 1:
                entry.cancel()

        for name in sorted({r.drawing for r in self.progress_items}):
            refresh_drawing(name)
