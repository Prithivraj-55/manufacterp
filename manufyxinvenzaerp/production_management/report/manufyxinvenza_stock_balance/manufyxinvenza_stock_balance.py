# Copyright (c) 2026, Manufyxinvenza and Contributors
# License: GNU General Public License v3. See license.txt

import frappe
from frappe import _
from frappe.utils import cint, flt
from pypika import functions as fn

from erpnext.stock.doctype.warehouse.warehouse import apply_warehouse_filter


def execute(filters=None):
	if not filters:
		filters = {}

	float_precision = cint(frappe.db.get_default("float_precision")) or 3

	columns = get_columns()
	item_map = get_item_details()
	batch_map = get_batch_details()
	iwb_map = get_item_warehouse_batch_map(filters, float_precision)

	data = []
	for item in sorted(iwb_map):
		for wh in sorted(iwb_map[item]):
			for batch in sorted(iwb_map[item][wh]):
				qty_dict = iwb_map[item][wh][batch]
				if flt(qty_dict.bal_qty, float_precision) <= 0:
					continue

				item_details = item_map.get(item, frappe._dict())
				batch_details = batch_map.get(batch, frappe._dict())

				# Proportional available sec qty: scale batch's sec qty by remaining fraction
				batch_sec_qty = flt(batch_details.get("custom_sec_qty", 0))
				received_qty = flt(qty_dict.get("received_qty", 0))
				if received_qty > 0 and batch_sec_qty > 0:
					available_sec_qty = flt(
						batch_sec_qty * (qty_dict.bal_qty / received_qty), float_precision
					)
				else:
					available_sec_qty = batch_sec_qty

				data.append({
					"item_code": item,
					"item_name": item_details.get("item_name", ""),
					"description": item_details.get("description", ""),
					"warehouse": wh,
					"batch_no": batch,
					"available_qty": flt(qty_dict.bal_qty, float_precision),
					"uom": item_details.get("stock_uom", ""),
					"available_sec_qty": available_sec_qty,
					"sec_uom": batch_details.get("custom_sec_uom", ""),
					"thickness": flt(batch_details.get("custom_thickness", 0)),
					"width": flt(batch_details.get("custom_width", 0)),
					"length": flt(batch_details.get("custom_length", 0)),
				})

	return columns, data


def get_columns():
	return [
		{
			"label": _("Item Code"),
			"fieldname": "item_code",
			"fieldtype": "Link",
			"options": "Item",
			"width": 130,
		},
		{
			"label": _("Item Name"),
			"fieldname": "item_name",
			"fieldtype": "Data",
			"width": 160,
		},
		{
			"label": _("Description"),
			"fieldname": "description",
			"fieldtype": "Data",
			"width": 120,
		},
		{
			"label": _("Warehouse"),
			"fieldname": "warehouse",
			"fieldtype": "Link",
			"options": "Warehouse",
			"width": 130,
		},
		{
			"label": _("Batch"),
			"fieldname": "batch_no",
			"fieldtype": "Link",
			"options": "Batch",
			"width": 130,
		},
		{
			"label": _("Available Qty"),
			"fieldname": "available_qty",
			"fieldtype": "Float",
			"width": 120,
		},
		{
			"label": _("UOM"),
			"fieldname": "uom",
			"fieldtype": "Link",
			"options": "UOM",
			"width": 80,
		},
		{
			"label": _("Available Sec Qty"),
			"fieldname": "available_sec_qty",
			"fieldtype": "Float",
			"width": 140,
		},
		{
			"label": _("Sec UOM"),
			"fieldname": "sec_uom",
			"fieldtype": "Link",
			"options": "UOM",
			"width": 90,
		},
		{
			"label": _("Thickness"),
			"fieldname": "thickness",
			"fieldtype": "Float",
			"width": 100,
		},
		{
			"label": _("Width"),
			"fieldname": "width",
			"fieldtype": "Float",
			"width": 100,
		},
		{
			"label": _("Length"),
			"fieldname": "length",
			"fieldtype": "Float",
			"width": 100,
		},
	]


def get_stock_ledger_entries(filters):
	return _get_sle_via_batch_no(filters) + _get_sle_via_batch_bundle(filters)


def _get_sle_via_batch_no(filters):
	"""Handles older-style SLEs that carry batch_no directly on the entry."""
	sle = frappe.qb.DocType("Stock Ledger Entry")
	query = (
		frappe.qb.from_(sle)
		.select(
			sle.item_code,
			sle.warehouse,
			sle.batch_no,
			fn.Sum(sle.actual_qty).as_("actual_qty"),
		)
		.where(
			(sle.docstatus < 2)
			& (sle.is_cancelled == 0)
			& (sle.batch_no.isnotnull())
			& (sle.batch_no != "")
		)
		.groupby(sle.voucher_no, sle.batch_no, sle.item_code, sle.warehouse)
	)

	query = apply_warehouse_filter(query, sle, filters)

	if filters.get("storage_location"):
		query = query.where(sle.storage_location == filters["storage_location"])

	for field in ["item_code", "batch_no", "company"]:
		if filters.get(field):
			query = query.where(sle[field] == filters.get(field))

	return query.run(as_dict=True) or []


def _get_sle_via_batch_bundle(filters):
	"""Handles modern SLEs that use serial-and-batch bundles."""
	sle = frappe.qb.DocType("Stock Ledger Entry")
	batch_package = frappe.qb.DocType("Serial and Batch Entry")

	query = (
		frappe.qb.from_(sle)
		.inner_join(batch_package)
		.on(batch_package.parent == sle.serial_and_batch_bundle)
		.select(
			sle.item_code,
			sle.warehouse,
			batch_package.batch_no,
			fn.Sum(batch_package.qty).as_("actual_qty"),
		)
		.where(
			(sle.docstatus < 2)
			& (sle.is_cancelled == 0)
			& (sle.has_batch_no == 1)
		)
		.groupby(sle.voucher_no, sle.item_code, sle.warehouse, batch_package.batch_no)
	)

	query = apply_warehouse_filter(query, sle, filters)

	if filters.get("storage_location"):
		query = query.where(sle.storage_location == filters["storage_location"])

	for field in ["item_code", "company"]:
		if filters.get(field):
			query = query.where(sle[field] == filters.get(field))

	if filters.get("batch_no"):
		query = query.where(batch_package.batch_no == filters.get("batch_no"))

	return query.run(as_dict=True) or []


def get_item_warehouse_batch_map(filters, float_precision):
	sle = get_stock_ledger_entries(filters)
	iwb_map = {}

	for d in sle:
		iwb_map.setdefault(d.item_code, {}).setdefault(d.warehouse, {}).setdefault(
			d.batch_no,
			frappe._dict({"bal_qty": 0.0, "received_qty": 0.0}),
		)
		qty_dict = iwb_map[d.item_code][d.warehouse][d.batch_no]
		qty_dict.bal_qty = flt(qty_dict.bal_qty, float_precision) + flt(d.actual_qty, float_precision)
		if flt(d.actual_qty) > 0:
			qty_dict.received_qty = (
				flt(qty_dict.received_qty, float_precision) + flt(d.actual_qty, float_precision)
			)

	return iwb_map


def get_item_details():
	item = frappe.qb.DocType("Item")
	return {
		d.name: d
		for d in (
			frappe.qb.from_(item)
			.select(item.name, item.item_name, item.description, item.stock_uom)
			.run(as_dict=True)
		)
	}


def get_batch_details():
	batch = frappe.qb.DocType("Batch")
	return {
		d.name: d
		for d in (
			frappe.qb.from_(batch)
			.select(
				batch.name,
				batch.custom_sec_qty,
				batch.custom_sec_uom,
				batch.custom_thickness,
				batch.custom_width,
				batch.custom_length,
			)
			.run(as_dict=True)
		)
	}
