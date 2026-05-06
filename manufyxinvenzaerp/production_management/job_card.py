import frappe
from frappe import _
from frappe.utils import flt

FORMULA_GROUPS = {"Structurals", "Plates"}


def validate_job_card(doc, method):
	"""Blocking server-side validation for custom_raw_material_consumption.
	Called via hooks.py: Job Card → validate."""
	if not doc.get("custom_raw_material_consumption"):
		return

	wip_warehouse = doc.wip_warehouse
	sequence_id = doc.sequence_id or 1

	for row in doc.custom_raw_material_consumption:
		group = (row.parent_item_group or "").strip()

		if group in FORMULA_GROUPS:
			transferred = flt(row.transferred_qty)
			current_qty = flt(row.current_stock_qty)

			# Block save if consumed qty exceeds what was transferred to WIP
			if transferred > 0 and current_qty > transferred:
				frappe.throw(
					_("Row {0}: Item <b>{1}</b> — current qty {2} Kg exceeds transferred qty "
					  "{3} Kg in WIP warehouse. Reduce the quantity and try again.").format(
						row.idx, row.item_code, current_qty, transferred
					)
				)

			# Block save if this operation's Nos exceed the previous operation's Nos
			if sequence_id > 1:
				prev_sec = flt(row.prev_operation_sec_qty)
				curr_sec = flt(row.current_sec_qty)
				if prev_sec > 0 and curr_sec > prev_sec:
					frappe.throw(
						_("Row {0}: Item <b>{1}</b> — {2} Nos entered, but only {3} Nos were "
						  "completed in the previous operation. Cannot exceed previous operation "
						  "quantity.").format(
							row.idx, row.item_code, curr_sec, prev_sec
						)
					)
		else:
			# Nuts and Bolts — validate manual_qty against actual WIP stock
			if wip_warehouse:
				wip_stock = _get_wip_stock(row.item_code, wip_warehouse)
				manual_qty = flt(row.manual_qty)
				if manual_qty > wip_stock:
					frappe.throw(
						_("Row {0}: Item <b>{1}</b> — manual qty {2} Kg exceeds available WIP "
						  "warehouse stock {3} Kg.").format(
							row.idx, row.item_code, manual_qty, wip_stock
						)
					)


def _get_wip_stock(item_code, warehouse):
	result = frappe.db.sql(
		"SELECT SUM(actual_qty) FROM `tabBin` WHERE item_code=%s AND warehouse=%s",
		(item_code, warehouse),
	)
	return flt(result[0][0]) if result else 0.0


def before_submit_manufacture_stock_entry(doc, method):
	"""Validate final raw-material consumption before the Manufacture Stock Entry
	is submitted (the final step that converts WIP to finished goods).
	Called via hooks.py: Stock Entry → before_submit."""
	if doc.stock_entry_type != "Manufacture" or not doc.work_order:
		return
	from manufyxinvenzaerp.production_management.production_utils import (
		validate_final_operation_consumption,
	)
	validate_final_operation_consumption(doc.work_order)
