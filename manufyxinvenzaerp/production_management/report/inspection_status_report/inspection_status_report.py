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
	source = filters.get("source_doctype")
	rows = []
	if not source or source == "Job Card":
		rows += _collect_rows("Job Card", "Work Order", "work_order", filters)
	if not source or source == "Supplier Operation Entry":
		rows += _collect_rows("Supplier Operation Entry", "Subcontracting Order", "subcontracting_order", filters)
	if not source or source == "Purchase Receipt":
		rows += _collect_pr_rows(filters)

	_apply_project(rows)
	rows.sort(key=lambda r: (r["active_document"], r["round_no"] or 0))
	return rows


def _apply_project(rows):
	"""Project (client change request Phase 7.3) -- joined via Sales Order first
	(each row's own `sales_order`, if any), falling back to Production Plan's
	native `project` field. Neither Inspection Entry nor Inspection Call Log
	carries Project directly, so this is always a join, done once in bulk here
	rather than per-row."""
	so_names = list({r["sales_order"] for r in rows if r.get("sales_order")})
	so_project = {}
	if so_names:
		for s in frappe.get_all("Sales Order", filters={"name": ["in", so_names]}, fields=["name", "project"]):
			so_project[s.name] = s.project

	pp_names = list({r["production_plan"] for r in rows if r.get("production_plan")})
	pp_project = {}
	if pp_names:
		for p in frappe.get_all("Production Plan", filters={"name": ["in", pp_names]}, fields=["name", "project"]):
			pp_project[p.name] = p.project

	for r in rows:
		r["project"] = so_project.get(r.get("sales_order")) or pp_project.get(r.get("production_plan")) or ""
		r["rework_attempts"] = max(0, (r.get("round_no") or 1) - 1)


def _collect_rows(parent_doctype, reference_type, reference_fieldname, filters):
	parent_fields = ["name", "operation", "custom_inspection_status", "work_order"]
	if parent_doctype == "Supplier Operation Entry":
		parent_fields += ["production_plan", "subcontracting_order"]

	if parent_doctype == "Supplier Operation Entry":
		# Phase 4.3 replaced the old hardcoded Fitup/Final Inspection
		# operation-name gate with the per-row "Inspection Mandatory"
		# checkbox (any operation can now require inspection) -- so
		# candidate SOEs are whichever ones actually have a logged
		# Inspection Call, not a fixed operation-name list. Job Card's
		# inspection hooks are disabled (Phase 0.4) and stay on the old
		# operation-name lookup below since it's a frozen/dead path, kept
		# only so historical rows remain visible.
		parent_names = list(set(frappe.get_all(
			"Inspection Call Log", filters={"parenttype": parent_doctype}, pluck="parent",
		)))
		if not parent_names:
			return []
		parents = frappe.get_all(parent_doctype, filters={"name": ["in", parent_names]}, fields=parent_fields)
	else:
		operations = [filters["operation"]] if filters.get("operation") else list(INSPECTION_OPERATIONS)
		parents = frappe.get_all(parent_doctype, filters={"operation": ["in", operations]}, fields=parent_fields)
	if not parents:
		return []
	parent_map = {p.name: p for p in parents}

	if parent_doctype == "Supplier Operation Entry" and filters.get("operation"):
		parent_map = {name: p for name, p in parent_map.items() if p.operation == filters["operation"]}
		if not parent_map:
			return []

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
			fields=["name", "total_checked_qty", "cleared_qty", "rework_qty", "rework_remarks", "supplier"],
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
			"supplier": entry.get("supplier") or "",
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


def _collect_pr_rows(filters):
	"""Purchase Receipt inspections (client change request Phase 6.1) have a
	different shape from Job Card/SOE: no `operation`, results recorded per
	item row on the Inspection Entry rather than as a single scalar, and
	traceability comes from the item rows' own custom_sales_order rather than
	a drawing-details table. Aggregated here into the same flat row shape as
	_collect_rows so both sources sit in one report -- qty columns become
	SUMS across the Inspection Entry's items."""
	# custom_inspection_call_log is a child table, so "has at least one call
	# logged" has to be checked via the child table directly rather than a
	# top-level Purchase Receipt filter.
	pr_names_with_calls = list(set(frappe.get_all(
		"Inspection Call Log", filters={"parenttype": "Purchase Receipt"}, pluck="parent",
	)))
	if not pr_names_with_calls:
		return []
	parents = frappe.get_all(
		"Purchase Receipt",
		filters={"name": ["in", pr_names_with_calls]},
		fields=["name", "custom_inspection_status", "supplier"],
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
		filters={"parenttype": "Purchase Receipt", "parent": ["in", list(parent_map.keys())]},
		fields=["parent", "round_no", "call_date", "round_status", "inspection_entry", "remarks"],
		order_by="parent asc, round_no asc",
	)
	if not call_logs:
		return []

	entry_names = [c.inspection_entry for c in call_logs if c.inspection_entry]
	items_by_entry = {}
	if entry_names:
		for it in frappe.get_all(
			"Inspection Entry Item",
			filters={"parent": ["in", entry_names]},
			fields=["parent", "qty", "accept_qty", "reject_qty", "remarks"],
		):
			items_by_entry.setdefault(it.parent, []).append(it)
	entries = {}
	if entry_names:
		for e in frappe.get_all(
			"Inspection Entry", filters={"name": ["in", entry_names]}, fields=["name", "overall_remarks"],
		):
			entries[e.name] = e

	trace_cache = {}
	rows = []
	for c in call_logs:
		parent = parent_map.get(c.parent)
		if not parent:
			continue
		if c.parent not in trace_cache:
			doc = frappe.get_doc("Purchase Receipt", c.parent)
			trace_cache[c.parent] = _resolve_traceability(doc)
		sales_order, customer = trace_cache[c.parent]

		if filters.get("sales_order") and sales_order != filters["sales_order"]:
			continue

		items = items_by_entry.get(c.inspection_entry, [])
		entry = entries.get(c.inspection_entry, frappe._dict())
		remarks = entry.get("overall_remarks") or "; ".join(i.remarks for i in items if i.remarks) or c.remarks or ""

		rows.append({
			"production_plan": "",
			"sales_order": sales_order,
			"customer": customer,
			"supplier": parent.supplier or "",
			"reference_type": "Supplier",
			"reference": parent.supplier,
			"active_doctype": "Purchase Receipt",
			"active_document": c.parent,
			"operation": "",
			"round_no": c.round_no,
			"call_date": c.call_date,
			"inspection_status": parent.custom_inspection_status,
			"round_status": c.round_status,
			"total_checked_qty": flt(sum(flt(i.qty) for i in items)),
			"cleared_qty": flt(sum(flt(i.accept_qty) for i in items)),
			"rework_qty": flt(sum(flt(i.reject_qty) for i in items)),
			"rework_remarks": remarks,
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
		{"label": _("Project"), "fieldname": "project", "fieldtype": "Link", "options": "Project", "width": 130},
		{"label": _("Sales Order"), "fieldname": "sales_order", "fieldtype": "Link", "options": "Sales Order", "width": 120},
		{"label": _("Customer"), "fieldname": "customer", "fieldtype": "Link", "options": "Customer", "width": 140},
		{"label": _("Supplier"), "fieldname": "supplier", "fieldtype": "Link", "options": "Supplier", "width": 140},
		{"label": _("Reference Type"), "fieldname": "reference_type", "fieldtype": "Data", "width": 110},
		{"label": _("Reference"), "fieldname": "reference", "fieldtype": "Dynamic Link", "options": "reference_type", "width": 130},
		{"label": _("Active Doctype"), "fieldname": "active_doctype", "fieldtype": "Data", "width": 130},
		{"label": _("Active Document"), "fieldname": "active_document", "fieldtype": "Dynamic Link", "options": "active_doctype", "width": 150},
		{"label": _("Operation"), "fieldname": "operation", "fieldtype": "Link", "options": "Operation", "width": 120},
		{"label": _("Round No"), "fieldname": "round_no", "fieldtype": "Int", "width": 80},
		{"label": _("Rework Attempts"), "fieldname": "rework_attempts", "fieldtype": "Int", "width": 110},
		{"label": _("Inspection Call Date"), "fieldname": "call_date", "fieldtype": "Date", "width": 130},
		{"label": _("Inspection Status"), "fieldname": "inspection_status", "fieldtype": "Data", "width": 110},
		{"label": _("Round Status"), "fieldname": "round_status", "fieldtype": "Data", "width": 100},
		{"label": _("Total Checked Qty"), "fieldname": "total_checked_qty", "fieldtype": "Float", "width": 120},
		{"label": _("Cleared Qty"), "fieldname": "cleared_qty", "fieldtype": "Float", "width": 100},
		{"label": _("Rework Qty"), "fieldname": "rework_qty", "fieldtype": "Float", "width": 100},
		{"label": _("Rework Remarks"), "fieldname": "rework_remarks", "fieldtype": "Data", "width": 200},
	]
