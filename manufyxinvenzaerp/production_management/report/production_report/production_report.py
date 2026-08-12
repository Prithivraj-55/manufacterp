# Copyright (c) 2026, Manufyxinvenza and Contributors
# License: GNU General Public License v3. See license.txt

import frappe
from frappe import _
from frappe.utils import flt, getdate


def execute(filters=None):
	filters = filters or {}
	columns = get_columns()
	data = get_data(filters)
	return columns, data


def get_data(filters):
	soe_filters = {}
	if filters.get("subcontracting_order"):
		soe_filters["subcontracting_order"] = filters["subcontracting_order"]
	if filters.get("production_plan"):
		soe_filters["production_plan"] = filters["production_plan"]
	if filters.get("status"):
		soe_filters["status"] = filters["status"]
	if filters.get("supplier"):
		soe_filters["supplier"] = filters["supplier"]
	if filters.get("operation"):
		soe_filters["operation"] = filters["operation"]

	soes = frappe.get_all(
		"Supplier Operation Entry",
		filters=soe_filters,
		fields=["name", "production_plan", "subcontracting_order", "supplier", "operation",
				"sequence_id", "status", "custom_inspection_status", "custom_inspection_mandatory",
				"total_consumed_kg", "total_completed_nos", "creation"],
	)
	if not soes:
		return []

	if filters.get("from_date") or filters.get("to_date"):
		soes = _filter_by_date(soes, filters)
		if not soes:
			return []

	pp_names = list({s.production_plan for s in soes if s.production_plan})
	pp_map = {}
	if pp_names:
		pp_filters = {"name": ["in", pp_names]}
		if filters.get("job_type"):
			pp_filters["custom_type"] = filters["job_type"]
		for p in frappe.get_all("Production Plan", filters=pp_filters,
								fields=["name", "custom_type", "project", "company"]):
			pp_map[p.name] = p
		if filters.get("job_type"):
			soes = [s for s in soes if s.production_plan in pp_map]
			if not soes:
				return []

	# "Operation gap in days" has no dedicated start/end field anywhere in
	# this data model (Supplier Operation Entry carries no date fields of its
	# own beyond the inspection-specific custom_inspection_call_date) -- the
	# best available proxy is the creation-timestamp gap between consecutive
	# sequence_id rows of the same Subcontracting Order, since SOEs are
	# created in sequence order as each prior operation's consumption chains
	# into the next (subcontracting.py's _get_soe_creation_loop). Flagged as
	# approximate in the column label/description so it isn't mistaken for a
	# precise measurement.
	by_sco = {}
	for s in soes:
		by_sco.setdefault(s.subcontracting_order, []).append(s)
	gap_days = {}
	for sco, rows in by_sco.items():
		rows_sorted = sorted(rows, key=lambda r: (r.sequence_id or 0))
		prev_creation = None
		for r in rows_sorted:
			if prev_creation:
				gap_days[r.name] = (getdate(r.creation) - getdate(prev_creation)).days
			else:
				gap_days[r.name] = 0
			prev_creation = r.creation

	call_counts = {}
	for c in frappe.get_all(
		"Inspection Call Log", filters={"parenttype": "Supplier Operation Entry", "parent": ["in", [s.name for s in soes]]},
		fields=["parent"],
	):
		call_counts[c.parent] = call_counts.get(c.parent, 0) + 1

	drawing_rows = frappe.get_all(
		"SOE Drawing Detail",
		filters={"parent": ["in", [s.name for s in soes]]},
		fields=["parent", "drawing", "customer_drawing_number", "duno_mark_no", "sales_order",
				"qty_to_manufacture", "planned_weight_kg", "transferred_weight_kg", "completed_qty_nos"],
	)
	drawings_by_soe = {}
	for d in drawing_rows:
		drawings_by_soe.setdefault(d.parent, []).append(d)

	# Drawing-level weights, keyed (subcontracting_order, drawing).
	#
	# Not read from the SOE Drawing Detail rows already fetched above: their
	# transferred_weight_kg is only ever filled on sequence 1, so every later operation
	# would report 0 Kg transferred for a drawing whose material had in fact shipped.
	#
	# Preference is the linked Material Issue Plan's own drawing rows -- that is where
	# transferred weight is actually maintained (refresh_weight_summary); the
	# Subcontracting Order's copy of the same table carries customer/planned/excess but
	# leaves transferred at 0. The SCO rows are loaded first as a fallback so a plan with
	# no Material Issue Plan yet still reports the three weights it does know.
	weights = {}
	sco_names = list({s.subcontracting_order for s in soes if s.subcontracting_order})
	if sco_names:
		mip_to_sco = {
			m.name: m.subcontracting_order
			for m in frappe.get_all(
				"Material Issue Plan",
				filters={"subcontracting_order": ["in", sco_names]},
				fields=["name", "subcontracting_order"],
			)
		}
		sources = [("Subcontracting Order", {s: s for s in sco_names})]
		if mip_to_sco:
			sources.append(("Material Issue Plan", mip_to_sco))

		for parenttype, parent_to_sco in sources:
			for w in frappe.get_all(
				"SCO Drawing Item",
				filters={"parent": ["in", list(parent_to_sco)], "parenttype": parenttype},
				fields=["parent", "drawing", "customer_weight_kg", "total_weight_kg",
						"transferred_weight_kg", "excess_weight_kg"],
			):
				if not w.drawing:
					continue
				weights[(parent_to_sco[w.parent], w.drawing)] = w

	so_names = list({d.sales_order for d in drawing_rows if d.sales_order})
	so_map = {}
	if so_names:
		for so in frappe.get_all("Sales Order", filters={"name": ["in", so_names]}, fields=["name", "customer", "project"]):
			so_map[so.name] = so

	if filters.get("sales_order"):
		wanted = filters["sales_order"]
		soes = [s for s in soes if any(d.sales_order == wanted for d in drawings_by_soe.get(s.name, []))]
		if not soes:
			return []

	data = []
	for s in soes:
		pp = pp_map.get(s.production_plan, frappe._dict())
		rows = drawings_by_soe.get(s.name) or [frappe._dict()]
		for d in rows:
			if filters.get("sales_order") and d.get("sales_order") != filters["sales_order"]:
				continue
			so = so_map.get(d.get("sales_order"), frappe._dict())
			w = weights.get((s.subcontracting_order, d.get("drawing")), frappe._dict())
			data.append({
				"production_plan": s.production_plan,
				"project": pp.get("project") or so.get("project") or "",
				"job_type": pp.get("custom_type") or "",
				"subcontracting_order": s.subcontracting_order,
				"supplier": s.supplier,
				"sales_order": d.get("sales_order") or "",
				"customer": so.get("customer") or "",
				"drawing": d.get("drawing") or "",
				"duno_mark_no": d.get("duno_mark_no") or "",
				"customer_drawing_number": d.get("customer_drawing_number") or "",
				"operation": s.operation,
				"sequence_id": s.sequence_id,
				"status": s.status,
				"inspection_mandatory": s.custom_inspection_mandatory,
				"inspection_status": s.custom_inspection_status or "",
				"inspection_count": call_counts.get(s.name, 0),
				"operation_gap_days": gap_days.get(s.name, 0),
				"customer_weight_kg": flt(w.get("customer_weight_kg")),
				"planned_weight_kg": flt(w.get("total_weight_kg")),
				"transferred_weight_kg": flt(w.get("transferred_weight_kg")),
				"excess_weight_kg": flt(w.get("excess_weight_kg")),
				"consumed_kg": flt(s.total_consumed_kg),
				"completed_nos": flt(d.get("completed_qty_nos") or s.total_completed_nos),
				"creation_date": getdate(s.creation) if s.creation else None,
				"supplier_operation_entry": s.name,
			})

	data.sort(key=lambda d: (d["production_plan"] or "", d["subcontracting_order"] or "", d["sequence_id"] or 0))
	return data


def _filter_by_date(soes, filters):
	from_date = getdate(filters["from_date"]) if filters.get("from_date") else None
	to_date = getdate(filters["to_date"]) if filters.get("to_date") else None
	out = []
	for s in soes:
		d = getdate(s.creation) if s.creation else None
		if not d:
			continue
		if from_date and d < from_date:
			continue
		if to_date and d > to_date:
			continue
		out.append(s)
	return out


def get_columns():
	return [
		{"label": _("Production Plan (Team)"), "fieldname": "production_plan", "fieldtype": "Link", "options": "Production Plan", "width": 130},
		{"label": _("Project"), "fieldname": "project", "fieldtype": "Link", "options": "Project", "width": 120},
		{"label": _("Job Type"), "fieldname": "job_type", "fieldtype": "Data", "width": 120},
		{"label": _("Subcontracting Order"), "fieldname": "subcontracting_order", "fieldtype": "Link", "options": "Subcontracting Order", "width": 150},
		{"label": _("Supplier"), "fieldname": "supplier", "fieldtype": "Link", "options": "Supplier", "width": 130},
		{"label": _("Sales Order"), "fieldname": "sales_order", "fieldtype": "Link", "options": "Sales Order", "width": 120},
		{"label": _("Customer"), "fieldname": "customer", "fieldtype": "Link", "options": "Customer", "width": 130},
		{"label": _("Drawing"), "fieldname": "drawing", "fieldtype": "Link", "options": "Drawing", "width": 120},
		{"label": _("DUNO/Mark No"), "fieldname": "duno_mark_no", "fieldtype": "Data", "width": 120},
		{"label": _("Cust Drawing No"), "fieldname": "customer_drawing_number", "fieldtype": "Data", "width": 120},
		{"label": _("Operation"), "fieldname": "operation", "fieldtype": "Link", "options": "Operation", "width": 120},
		{"label": _("Seq"), "fieldname": "sequence_id", "fieldtype": "Int", "width": 60},
		{"label": _("Status"), "fieldname": "status", "fieldtype": "Data", "width": 100},
		{"label": _("Inspection Mandatory"), "fieldname": "inspection_mandatory", "fieldtype": "Check", "width": 100},
		{"label": _("Inspection Status"), "fieldname": "inspection_status", "fieldtype": "Data", "width": 110},
		{"label": _("Inspection Count"), "fieldname": "inspection_count", "fieldtype": "Int", "width": 100},
		{"label": _("Operation Gap (Days, approx.)"), "fieldname": "operation_gap_days", "fieldtype": "Int", "width": 150},
		# Drawing-level weights -- the same figures on every operation row for a given
		# drawing, since they describe the drawing rather than the operation.
		{"label": _("Customer Weight (Kg)"), "fieldname": "customer_weight_kg", "fieldtype": "Float", "width": 130},
		{"label": _("Planned Weight (Kg)"), "fieldname": "planned_weight_kg", "fieldtype": "Float", "width": 130},
		{"label": _("Transferred Weight (Kg)"), "fieldname": "transferred_weight_kg", "fieldtype": "Float", "width": 145},
		{"label": _("Excess Weight (Kg)"), "fieldname": "excess_weight_kg", "fieldtype": "Float", "width": 125},
		{"label": _("Consumed (Kg)"), "fieldname": "consumed_kg", "fieldtype": "Float", "width": 110},
		{"label": _("Completed (Nos)"), "fieldname": "completed_nos", "fieldtype": "Float", "width": 110},
		{"label": _("Created On"), "fieldname": "creation_date", "fieldtype": "Date", "width": 100},
		{"label": _("Supplier Operation Entry"), "fieldname": "supplier_operation_entry", "fieldtype": "Link", "options": "Supplier Operation Entry", "width": 150},
	]
