import frappe
from frappe import _
from frappe.utils import flt

FORMULA_GROUPS = {"Structurals", "Plates"}


def validate_stock_entry(doc, method):
	"""Recalculate qty for formula-group items. Show popup only when qty was manually edited."""
	if doc.stock_entry_type not in {"Repack", "Material Receipt", "Material Issue"}:
		return

	manually_edited = []
	for row in doc.items:
		group = (row.get("custom_parent_item_group") or "").strip()
		if group not in FORMULA_GROUPS:
			continue
		formula_qty = flt(_calc_qty(row, group), 3)
		if not formula_qty:
			continue
		if flt(row.qty, 3) != formula_qty:
			manually_edited.append(row.item_code)
		row.qty = formula_qty

	if manually_edited:
		frappe.msgprint(
			_("Quantities for Structurals/Plates have been recalculated from dimensions."),
			indicator="orange",
		)


def on_submit_stock_entry(doc, method):
	"""Reduce custom_sec_qty on batch for consumed items (Repack source rows + Material Issue)."""
	if doc.stock_entry_type == "Material Issue":
		for row in doc.items:
			if row.batch_no and flt(row.get("custom_sec_qty")):
				_reduce_batch_sec_qty(row.batch_no, row.custom_sec_qty)

	elif doc.stock_entry_type == "Repack":
		for row in doc.items:
			if not row.is_finished_item and row.batch_no and flt(row.get("custom_sec_qty")):
				_reduce_batch_sec_qty(row.batch_no, row.custom_sec_qty)


def _reduce_batch_sec_qty(batch_no, consumed_qty):
	current = flt(frappe.db.get_value("Batch", batch_no, "custom_sec_qty"))
	frappe.db.set_value("Batch", batch_no, "custom_sec_qty", flt(current - flt(consumed_qty), 3))


def _calc_qty(row, group):
	l = flt(row.get("custom_length"))
	w = flt(row.get("custom_width"))
	t = flt(row.get("custom_thickness"))
	uw = flt(row.get("custom_unit_weight"))
	sq = flt(row.get("custom_sec_qty"))

	if group == "Structurals" and l and uw and sq:
		return (l / 1000) * uw * sq
	if group == "Plates" and l and w and t and uw and sq:
		return (l / 1000) * (w / 1000) * t * uw * sq
	return 0.0
