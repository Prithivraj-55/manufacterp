import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt


class InspectionEntry(Document):
	def validate(self):
		self.rework_qty = flt(flt(self.total_checked_qty) - flt(self.cleared_qty), 3)

		if self.rework_qty < 0:
			frappe.throw(
				_("Cleared Qty ({0}) cannot exceed Total Checked Qty ({1}).").format(
					self.cleared_qty, self.total_checked_qty
				)
			)

		if self.status == "Ok" and self.rework_qty > 0:
			frappe.throw(
				_("Status cannot be <b>Ok</b> while Cleared Qty is less than Total Checked Qty. "
				  "Set Status to <b>Not Ok</b> or clear the full quantity.")
			)

		if self.status == "Not Ok" and self.rework_qty == 0:
			frappe.throw(
				_("Status cannot be <b>Not Ok</b> when the full quantity is cleared. "
				  "Set Status to <b>Ok</b>, or reduce Cleared Qty to reflect the rework quantity.")
			)

		if self.rework_qty > 0 and not (self.rework_remarks or "").strip():
			frappe.throw(_("Rework Remarks is mandatory when Rework Qty is greater than zero."))
