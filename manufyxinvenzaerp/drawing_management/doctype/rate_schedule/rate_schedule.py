import frappe
from frappe.model.document import Document
from frappe.utils import now_datetime, today


class RateSchedule(Document):
    def before_insert(self):
        self.created_on = now_datetime()

    def validate(self):
        self.last_updated_on = now_datetime()
        self._track_rate_change()

    def _track_rate_change(self):
        """Keep price_log as a history of Rate/KG over time — a new row opens
        whenever the rate actually changes, closing out the previously open one."""
        if self.is_new():
            if self.rate_per_kg:
                self.append("price_log", {"from_date": today(), "price": self.rate_per_kg})
            return

        previous_rate = frappe.db.get_value("Rate Schedule", self.name, "rate_per_kg")
        if previous_rate == self.rate_per_kg:
            return

        for row in self.price_log:
            if not row.to_date:
                row.to_date = today()

        self.append("price_log", {"from_date": today(), "price": self.rate_per_kg})
