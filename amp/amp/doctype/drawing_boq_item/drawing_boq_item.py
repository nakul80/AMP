from frappe.model.document import Document
from amp.amp.quantities import number, structural_progress_values


class DrawingBOQItem(Document):
    def validate(self):
        self.calculate_quantities()

    def calculate_quantities(self):
        self.total_budget_qty = round(number(self.estimated_qty) * (1 + number(self.wastage_percent) / 100), 3)
        self.balance_to_order = max(0, round(self.total_budget_qty - number(self.requested_qty) - number(self.draft_requested_qty), 3))
        if self.discipline == "Structural":
            progress = structural_progress_values(
                self.estimated_qty, self.fabrication_progress_weight, self.erection_progress_weight,
                self.fabricated_qty, self.erected_qty, self.legacy_executed_qty
            )
            # executed_qty is a weighted physical-equivalent, not fabricated + erected.
            self.executed_qty = round(progress["executed_qty"], 3)
            self.fabrication_balance_qty = max(0, round(number(self.estimated_qty) - number(self.fabricated_qty), 3))
            self.erection_balance_qty = max(0, round(number(self.estimated_qty) - number(self.erected_qty), 3))
        # Physical work does not include procurement wastage.
        self.balance_to_execute = max(0, round(number(self.estimated_qty) - number(self.executed_qty), 3))
