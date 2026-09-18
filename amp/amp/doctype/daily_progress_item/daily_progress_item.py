from frappe.model.document import Document
from amp.amp.quantities import number


class DailyProgressItem(Document):
    def validate(self):
        self.cumulative_executed_qty = round(number(self.previously_executed_qty) + number(self.today_executed_qty), 3)
        self.balance_qty = max(0, round(number(self.drawing_budget_qty) - self.cumulative_executed_qty, 3))
        self.cumulative_fabricated_qty = round(number(self.previously_fabricated_qty) + number(self.today_fabricated_qty), 3)
        self.cumulative_erected_qty = round(number(self.previously_erected_qty) + number(self.today_erected_qty), 3)
