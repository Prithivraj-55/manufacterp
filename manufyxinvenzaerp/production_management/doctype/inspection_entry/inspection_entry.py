import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, nowdate


class InspectionEntry(Document):
	def validate(self):
		if self.source_doctype == "Purchase Receipt":
			self._validate_pr_items()
		elif self.source_doctype == "Supplier Operation Entry":
			self._validate_soe_items()
		else:
			self._autofill_total_qty_to_check()
			self._validate_scalar_result()

		if self.source_doctype == "Supplier Operation Entry":
			self._derive_rework_remarks()
		self._set_partly_completed()
		self._set_inspection_complete_date()

	def _autofill_total_qty_to_check(self):
		"""Job Card only -- Supplier Operation Entry uses the row-wise soe_items table
		instead (see _validate_soe_items), which already carries its own per-drawing
		Completed Qty copied from the source SOE's inspection_items at creation time."""
		if self.job_card:
			self.total_qty_to_check = flt(frappe.db.get_value("Job Card", self.job_card, "for_quantity"))

	def _set_inspection_complete_date(self):
		"""Set once, the first time Status is saved as Completed -- not re-derived on
		later saves so it reflects when the inspection was actually completed, not
		today's date on every subsequent edit."""
		if self.status == "Completed" and not self.inspection_complete_date:
			self.inspection_complete_date = nowdate()

	def before_submit(self):
		if self.status != "Completed":
			frappe.throw(
				_("Status must be <b>Completed</b> before this Inspection Entry can be submitted."),
				title=_("Inspection Not Completed"),
			)

	def _row_label(self, row):
		if self.source_doctype == "Supplier Operation Entry":
			return _("Row {0} ({1})").format(row.idx, row.customer_drawing_number or row.drawing)
		return _("Row {0} ({1})").format(row.idx, row.item_code)

	def _derive_rework_remarks(self):
		"""The header Rework Remarks summarise the rows, so the call-log remarks read the
		same field as before."""
		self.rework_remarks = "\n".join(
			"%s: %s" % (r.customer_drawing_number or r.drawing, r.rework_remarks.strip())
			for r in (self.soe_items or []) if flt(r.reject_qty) > 0 and (r.rework_remarks or "").strip()
		)

	def _quantities(self):
		"""(to check, cleared) for this inspection, whatever its source."""
		if self.source_doctype == "Supplier Operation Entry":
			rows = self.soe_items or []
			return sum(flt(r.qty_nos) for r in rows), sum(flt(r.accept_qty) for r in rows)
		if self.source_doctype == "Purchase Receipt":
			rows = self.items or []
			return sum(flt(r.qty) for r in rows), sum(flt(r.accept_qty) for r in rows)
		return flt(self.total_checked_qty) or flt(self.total_qty_to_check), flt(self.cleared_qty)

	def _set_partly_completed(self):
		"""Partly Completed is not chosen, it is read off the quantities (client, Oct
		2026): some cleared, not all. The cleared part already moves on to the next
		process; this only says so in the status and the list. Completed stays the
		inspector's own call -- it is what submits the entry."""
		if self.docstatus != 0 or self.status == "Completed":
			return
		total, cleared = self._quantities()
		if 0 < flt(cleared, 3) < flt(total, 3):
			self.status = "Partly Completed"
		elif self.status == "Partly Completed":
			self.status = "Working"

	def _validate_scalar_result(self):
		self.rework_qty = flt(flt(self.total_checked_qty) - flt(self.cleared_qty), 3)

		if self.is_new():
			# create_inspection_entry() inserts a bare draft prefilled only from the
			# source document (Total Checked Qty defaults from Total Qty to Check,
			# Cleared Qty starts at 0) so the inspector has something to open and edit --
			# it must not fail before that draft even exists. Everything below applies
			# from the inspector's first real save onward instead.
			return

		if flt(self.total_checked_qty) <= 0:
			frappe.throw(_("Total Checked Qty cannot be zero."))

		if self.rework_qty < 0:
			frappe.throw(
				_("Cleared Qty ({0}) cannot exceed Total Checked Qty ({1}).").format(
					self.cleared_qty, self.total_checked_qty
				)
			)

		if self.rework_qty > 1 and not (self.rework_remarks or "").strip():
			frappe.throw(_("Rework Remarks is mandatory when Rework Qty is greater than 1."))

	def _validate_soe_items(self):
		"""Row-wise inspection for a Supplier Operation Entry source -- replaces the
		scalar Total Checked/Cleared Qty fields with per-drawing Accepted/Rejected Qty
		(client change: "instead of entering the Overall checked quantity, user need to
		enter in the item table"). Accepted Qty is what on_submit_inspection_entry /
		_apply_soe_inspection_results later adds onto the source SOE's
		drawing_details.completed_qty_nos; Rejected Qty is not pushed anywhere -- it
		naturally reappears in the SOE's own inspection_items table (see
		_sync_soe_inspection_items) the moment it's logged again in Consumption Log."""
		if not self.soe_items:
			if self.is_new():
				return
			frappe.throw(_("Add at least one drawing to inspect."))

		for row in self.soe_items:
			if flt(row.accept_qty) > flt(row.qty_nos):
				frappe.throw(
					_("Row {0}: Accepted Qty ({1}) cannot exceed Completed Qty ({2}) for drawing {3}.").format(
						row.idx, row.accept_qty, row.qty_nos, row.customer_drawing_number or row.drawing
					)
				)
			row.reject_qty = flt(flt(row.qty_nos) - flt(row.accept_qty), 3)

		# Mirror aggregates onto the header scalar fields -- kept in sync so the
		# Inspection Status Report and any other reader of total_checked_qty /
		# cleared_qty / rework_qty keeps working for an SOE source too, even though the
		# UI shows the item table instead of these fields in that case.
		self.total_checked_qty = flt(sum(flt(r.qty_nos) for r in self.soe_items), 3)
		self.cleared_qty = flt(sum(flt(r.accept_qty) for r in self.soe_items), 3)
		self.rework_qty = flt(sum(flt(r.reject_qty) for r in self.soe_items), 3)

		if self.is_new():
			return

		if self.total_checked_qty <= 0:
			frappe.throw(_("Total Completed Qty cannot be zero."))

		missing = [self._row_label(r) for r in self.soe_items
		           if flt(r.reject_qty) > 0 and not (r.rework_remarks or "").strip()]
		if missing:
			frappe.throw(
				_("Rework Remarks is mandatory on a row with a Rejected Qty:<br>{0}").format("<br>".join(missing)),
				title=_("Rework Remarks Missing"),
			)

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
