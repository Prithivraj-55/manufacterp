import frappe
from frappe import _
from frappe.utils import flt, now

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

	elif doc.stock_entry_type == "Material Receipt" and doc.get("custom_supplier"):
		for row in doc.items:
			batch_nos = set()
			if row.batch_no:
				batch_nos.add(row.batch_no)
			# serial_and_batch_bundle is written via db_set during on_submit,
			# so the in-memory row won't have it — read fresh from DB
			bundle = frappe.db.get_value("Stock Entry Detail", row.name, "serial_and_batch_bundle")
			if bundle:
				entries = frappe.get_all(
					"Serial and Batch Entry",
					filters={"parent": bundle},
					fields=["batch_no"],
				)
				batch_nos.update(e.batch_no for e in entries if e.batch_no)
			for batch_no in batch_nos:
				frappe.db.set_value("Batch", batch_no, "supplier", doc.custom_supplier)

	# Release reservations for all consumed batches
	_release_material_planning_reservations(doc)


def _reduce_batch_sec_qty(batch_no, consumed_qty):
	current = flt(frappe.db.get_value("Batch", batch_no, "custom_sec_qty"))
	frappe.db.set_value("Batch", batch_no, "custom_sec_qty", flt(current - flt(consumed_qty), 3))


def _collect_consumed_batches(doc):
	"""
	Collect batch_nos consumed by this SE.
	v15 SBB system: batch_no on SE Detail may be NULL (or cleared on cancel).
	Always also look up SBBs linked via voucher_no (any docstatus — on cancel they're docstatus=2).
	"""
	batches = set()
	for row in doc.items:
		if row.batch_no and not row.get("is_finished_item"):
			batches.add(row.batch_no)

	# Always supplement from SBBs linked to this SE — handles v15 SBB-tracked batches
	# and the case where batch_no is cleared on SE Detail after cancel.
	voucher_no = getattr(doc, "name", None)
	sbb_list = frappe.get_all(
		"Serial and Batch Bundle",
		filters={"voucher_no": voucher_no} if voucher_no else {"name": "__nonexistent__"},
		fields=["name"],
	) if voucher_no else []
	if sbb_list:
		sbb_names = [d.name for d in sbb_list]
		sbe_rows = frappe.get_all(
			"Serial and Batch Entry",
			filters={"parent": ["in", sbb_names]},
			fields=["batch_no"],
		)
		for r in sbe_rows:
			if r.batch_no:
				batches.add(r.batch_no)

	return batches


def _release_material_planning_reservations(doc):
	"""
	After a Stock Entry is submitted, clear is_reserved on Material Planning Material Mapping
	rows whose batch was consumed. Applies to Manufacture, Material Transfer, and Material Issue.
	"""
	consumed_types = {"Manufacture", "Material Transfer", "Material Issue", "Repack"}
	if doc.stock_entry_type not in consumed_types:
		return

	consumed_batches = _collect_consumed_batches(doc)

	if not consumed_batches:
		return

	# Find all reserved Material Mapping rows that used one of these batches
	reserved_rows = frappe.get_all(
		"Material Planning Material Mapping",
		filters={
			"batch": ["in", list(consumed_batches)],
			"is_reserved": 1,
		},
		fields=["name", "parent"],
	)

	if not reserved_rows:
		return

	for r in reserved_rows:
		frappe.db.set_value(
			"Material Planning Material Mapping",
			r.name,
			{"is_reserved": 0, "reserved_qty": 0, "shortfall_qty": 0, "reserved_on": None},
			update_modified=False,
		)


def on_cancel_stock_entry(doc, method):
	"""When a Stock Entry is cancelled, batch stock returns — restore Material Planning reservations."""
	_restore_material_planning_reservations(doc)


def _restore_material_planning_reservations(doc):
	"""
	Re-apply is_reserved=1 on Material Mapping rows whose batch was consumed by this SE
	(they were cleared on submit). Only restores rows that are currently unreserved and
	still have the batch assigned.
	"""
	consumed_types = {"Manufacture", "Material Transfer", "Material Issue", "Repack"}
	if doc.stock_entry_type not in consumed_types:
		return

	consumed_batches = _collect_consumed_batches(doc)

	if not consumed_batches:
		return

	mapping_rows = frappe.get_all(
		"Material Planning Material Mapping",
		filters={"batch": ["in", list(consumed_batches)], "is_reserved": 0},
		fields=["name", "qty"],
	)
	if not mapping_rows:
		return

	for r in mapping_rows:
		frappe.db.set_value(
			"Material Planning Material Mapping",
			r.name,
			{
				"is_reserved": 1,
				"reserved_qty": flt(r.qty),
				"shortfall_qty": 0,
				"reserved_on": now(),
			},
			update_modified=False,
		)


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
