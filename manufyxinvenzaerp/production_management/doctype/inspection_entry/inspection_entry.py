import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt


class InspectionEntry(Document):
	def validate(self):
		if self.source_doctype == "Purchase Receipt":
			self._validate_pr_items()
		else:
			self._validate_scalar_result()

	def _validate_scalar_result(self):
		self.rework_qty = flt(flt(self.total_checked_qty) - flt(self.cleared_qty), 3)

		if self.rework_qty < 0:
			frappe.throw(
				_("Cleared Qty ({0}) cannot exceed Total Checked Qty ({1}).").format(
					self.cleared_qty, self.total_checked_qty
				)
			)

		if self.feedback == "Ok" and self.rework_qty > 0:
			frappe.throw(
				_("Feedback cannot be <b>Ok</b> while Cleared Qty is less than Total Checked Qty. "
				  "Set Feedback to <b>Not Ok</b> or clear the full quantity.")
			)

		if self.feedback == "Not Ok" and self.rework_qty == 0:
			frappe.throw(
				_("Feedback cannot be <b>Not Ok</b> when the full quantity is cleared. "
				  "Set Feedback to <b>Ok</b>, or reduce Cleared Qty to reflect the rework quantity.")
			)

		if self.rework_qty > 0 and not (self.rework_remarks or "").strip():
			frappe.throw(_("Rework Remarks is mandatory when Rework Qty is greater than zero."))

	def _validate_pr_items(self):
		if not self.items:
			frappe.throw(_("Add at least one item to inspect."))

		for row in self.items:
			if flt(row.accept_qty) > flt(row.qty):
				frappe.throw(
					_("Row {0}: Accepted Qty ({1}) cannot exceed Received Qty ({2}) for item {3}.").format(
						row.idx, row.accept_qty, row.qty, row.item_code
					)
				)
			row.reject_qty = flt(flt(row.qty) - flt(row.accept_qty), 3)
