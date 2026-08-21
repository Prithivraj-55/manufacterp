"""Manufyx Decision Log -- who decided what, and why.

Not a field-by-field audit trail. The client was offered one and turned it down:
on a 500-drawing order it would be large, slow to write and unreadable. What people
actually argue about later is a handful of decisions -- who reserved this batch, who
moved it to another one, who rounded a quantity up and what they said at the time --
so those are what this records, one entry per decision rather than one per row.

Nothing writes to it from the screen. Entries are made by log_decision() in
utils/decision_log.py at the moment the decision is taken, and are never edited or
removed afterwards; that is the whole point of them. The roles below can read and
export, and nothing more.
"""

import frappe
from frappe.model.document import Document


class ManufyxDecisionLog(Document):
    def on_trash(self):
        if frappe.session.user != "Administrator":
            frappe.throw(frappe._("A decision log entry cannot be removed."))
