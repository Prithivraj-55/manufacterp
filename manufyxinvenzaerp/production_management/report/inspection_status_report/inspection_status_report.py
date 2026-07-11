# Copyright (c) 2026, Manufyxinvenza and Contributors
# License: GNU General Public License v3. See license.txt

import frappe
from frappe import _
from frappe.utils import flt

from manufyxinvenzaerp.production_management.inspection import (
	INSPECTION_OPERATIONS,
	_resolve_traceability,
)


def execute(filters=None):
	filters = filters or {}
	columns = get_columns()
	data = get_data(filters)
	return columns, data


def get_data(filters):
	rows = []
	rows += _collect_rows("Job Card", "Work Order", "work_order", filters)
	rows += _collect_rows("Supplier Operation Entry", "Subcontracting Order", "subcontracting_order", filters)
	rows.sort(key=lambda r: (r["active_document"], r["round_no"] or 0))
	return rows


def _collect_rows(parent_doctype, reference_type, reference_fieldname, filters):
	operations = [filters["operation"]] if filters.get("operation") else list(INSPECTION_OPERATIONS)

	parent_fields = ["name", "operation", "custom_inspection_status", "work_order"]
	if parent_doctype == "Supplier Operation Entry":
		parent_fields += ["production_plan", "subcontracting_order"]

	parents = frappe.get_all(
		parent_doctype,
		filters={"operation": ["in", operations]},
		fields=parent_fields,
	)
	if not parents:
		return []
	parent_map = {p.name: p for p in parents}

	if filters.get("inspection_status"):
		parent_map = {
			name: p for name, p in parent_map.items()
			if p.custom_inspection_status == filters["inspection_status"]
		}
	if not parent_map:
		return []

	call_logs = frappe.get_all(
		"Inspection Call Log",
		filters={"parenttype": parent_doctype, "parent": ["in", list(parent_map.keys())]},
		fields=["parent", "round_no", "call_date", "round_status", "inspection_entry", "remarks"],
		order_by="parent asc, round_no asc",
	)
	if not call_logs:
		return []

	entry_names = [c.inspection_entry for c in call_logs if c.inspection_entry]
	entry_map = {}
	if entry_names:
		entries = frappe.get_all(
			"Inspection Entry",
			filters={"name": ["in", entry_names]},
			fields=["name", "total_checked_qty", "cleared_qty", "rework_qty", "rework_remarks"],
		)
		entry_map = {e.name: e for e in entries}

	trace_cache = {}
	rows = []
	for c in call_logs:
		parent = parent_map.get(c.parent)
		if not parent:
			continue

		if c.parent not in trace_cache:
			trace_cache[c.parent] = _traceability_for_parent(parent_doctype, parent)
		sales_order, customer, production_plan = trace_cache[c.parent]

		if filters.get("sales_order") and sales_order != filters["sales_order"]:
			continue
		if filters.get("production_plan") and production_plan != filters["production_plan"]:
			continue

		entry = entry_map.get(c.inspection_entry, frappe._dict())

		rows.append({
			"production_plan": production_plan,
			"sales_order": sales_order,
			"customer": customer,
			"reference_type": reference_type,
			"reference": parent.get(reference_fieldname),
			"active_doctype": parent_doctype,
			"active_document": c.parent,
			"operation": parent.operation,
			"round_no": c.round_no,
			"call_date": c.call_date,
			"inspection_status": parent.custom_inspection_status,
			"round_status": c.round_status,
			"total_checked_qty": flt(entry.get("total_checked_qty")),
			"cleared_qty": flt(entry.get("cleared_qty")),
			"rework_qty": flt(entry.get("rework_qty")),
			"rework_remarks": entry.get("rework_remarks") or c.remarks or "",
		})

	return rows


def _traceability_for_parent(parent_doctype, parent):
	doc = frappe.get_doc(parent_doctype, parent.name)
	sales_order, customer = _resolve_traceability(doc)
	if parent_doctype == "Job Card":
		production_plan = frappe.db.get_value("Work Order", doc.work_order, "production_plan") if doc.work_order else ""
	else:
		production_plan = doc.production_plan
	return sales_order, customer, production_plan


def get_columns():
	return [
		{"label": _("Production Plan"), "fieldname": "production_plan", "fieldtype": "Link", "options": "Production Plan", "width": 130},
		{"label": _("Sales Order"), "fieldname": "sales_order", "fieldtype": "Link", "options": "Sales Order", "width": 120},
		{"label": _("Customer"), "fieldname": "customer", "fieldtype": "Link", "options": "Customer", "width": 140},
		{"label": _("Reference Type"), "fieldname": "reference_type", "fieldtype": "Data", "width": 110},
		{"label": _("Reference"), "fieldname": "reference", "fieldtype": "Dynamic Link", "options": "reference_type", "width": 130},
		{"label": _("Active Doctype"), "fieldname": "active_doctype", "fieldtype": "Data", "width": 130},
		{"label": _("Active Document"), "fieldname": "active_document", "fieldtype": "Dynamic Link", "options": "active_doctype", "width": 150},
		{"label": _("Operation"), "fieldname": "operation", "fieldtype": "Link", "options": "Operation", "width": 120},
		{"label": _("Round No"), "fieldname": "round_no", "fieldtype": "Int", "width": 80},
		{"label": _("Inspection Call Date"), "fieldname": "call_date", "fieldtype": "Date", "width": 130},
		{"label": _("Inspection Status"), "fieldname": "inspection_status", "fieldtype": "Data", "width": 110},
		{"label": _("Round Status"), "fieldname": "round_status", "fieldtype": "Data", "width": 100},
		{"label": _("Total Checked Qty"), "fieldname": "total_checked_qty", "fieldtype": "Float", "width": 120},
		{"label": _("Cleared Qty"), "fieldname": "cleared_qty", "fieldtype": "Float", "width": 100},
		{"label": _("Rework Qty"), "fieldname": "rework_qty", "fieldtype": "Float", "width": 100},
		{"label": _("Rework Remarks"), "fieldname": "rework_remarks", "fieldtype": "Data", "width": 200},
	]
