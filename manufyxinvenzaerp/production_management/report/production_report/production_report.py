# Copyright (c) 2026, Manufyxinvenza and Contributors
# License: GNU General Public License v3. See license.txt

"""Production Report -- one row per drawing, every operation across the columns.

This used to be one row per drawing *per operation*, which meant a four-operation job
with six drawings filled twenty-four rows with the same six drawings repeated, and
answering "where is 1B1 up to" meant reading four rows and holding them in your head.

It is now one row per drawing per Job Work Order, with each operation contributing its
own block of columns -- quantity, status, inspection rounds, last inspection status and
the gap in days. The operations are not a fixed list: they are whichever operations the
jobs in view actually have, in sequence order, so a job routed through Welding and
Blasting shows those and a job routed through Fit-up and Painting shows those.

The first operation is measured in Kg -- it is where raw material is issued -- and every
later one in Nos, since what a fabricator completes downstream is pieces.
"""

import frappe
from frappe import _
from frappe.utils import flt, getdate

CONSUMPTION_ENTRY_TYPE = "Material Consumption for Manufacture"


def execute(filters=None):
	filters = filters or {}
	data, operations = get_data(filters)
	return get_columns(operations), data


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
		return [], []

	if filters.get("from_date") or filters.get("to_date"):
		soes = _filter_by_date(soes, filters)
		if not soes:
			return [], []

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
				return [], []

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
	# Fall back to the Drawing master for Sales Order. The copy held on the drawing rows
	# is blank in practice -- it is only populated when the Production Plan item carried
	# one -- which left the Sales Order column empty, the Customer column empty (it is
	# looked up FROM the sales order) and the Sales Order filter matching nothing at all,
	# on a report whose whole point is to be readable sales-order-wise.
	missing_so = {d.drawing for d in drawing_rows if d.drawing and not d.sales_order}
	if missing_so:
		so_by_drawing = {
			dr.name: dr.sales_order
			for dr in frappe.get_all(
				"Drawing",
				filters={"name": ["in", list(missing_so)]},
				fields=["name", "sales_order"],
			)
			if dr.sales_order
		}
		for d in drawing_rows:
			if not d.sales_order:
				d.sales_order = so_by_drawing.get(d.drawing) or ""

	drawings_by_soe = {}
	for d in drawing_rows:
		drawings_by_soe.setdefault(d.parent, []).append(d)

	sco_names = list({s.subcontracting_order for s in soes if s.subcontracting_order})
	weights, sec_nos, completed = _drawing_figures(sco_names)
	mip_by_sco = _mip_by_sco(sco_names)
	excess = _excess_by_sco(mip_by_sco)
	consumables = _consumables_by_sco(sco_names, {s.production_plan for s in soes})
	rm_cost = _rm_cost_by_drawing(sco_names)
	created_on = {
		s.name: (s.transaction_date or getdate(s.creation))
		for s in frappe.get_all("Subcontracting Order",
								filters={"name": ["in", sco_names]} if sco_names else {"name": ["in", []]},
								fields=["name", "transaction_date", "creation"])
	}

	so_names = list({d.sales_order for d in drawing_rows if d.sales_order})
	so_map = {}
	if so_names:
		for so in frappe.get_all("Sales Order", filters={"name": ["in", so_names]}, fields=["name", "customer", "project"]):
			so_map[so.name] = so

	drawing_names = list({d.drawing for d in drawing_rows if d.drawing})
	rate_map = {}
	if drawing_names:
		for dr in frappe.get_all("Drawing", filters={"name": ["in", drawing_names]},
								 fields=["name", "rate_schedule", "rs_rate_per_kg"]):
			rate_map[dr.name] = dr

	if filters.get("sales_order"):
		wanted = filters["sales_order"]
		soes = [s for s in soes if any(d.sales_order == wanted for d in drawings_by_soe.get(s.name, []))]
		if not soes:
			return [], []

	# The operation columns are whatever the jobs in view are actually routed through,
	# ordered by the sequence they run in. Sequence decides the unit as well: the first
	# operation is where raw material is issued and is read in Kg, everything after it
	# turns pieces out and is read in Nos.
	op_seq = {}
	for s in soes:
		if not s.operation:
			continue
		seq = s.sequence_id or 0
		if s.operation not in op_seq or seq < op_seq[s.operation]:
			op_seq[s.operation] = seq
	operations = _operation_columns(op_seq)
	slug_by_operation = {op["operation"]: op["slug"] for op in operations}

	# One row per drawing per Job Work Order. Each operation writes into its own block
	# of that row rather than adding a row of its own.
	rows_by_key = {}
	order = []
	for s in soes:
		pp = pp_map.get(s.production_plan, frappe._dict())
		for d in (drawings_by_soe.get(s.name) or [frappe._dict()]):
			if filters.get("sales_order") and d.get("sales_order") != filters["sales_order"]:
				continue
			key = (s.subcontracting_order, d.get("drawing") or "")
			row = rows_by_key.get(key)
			if row is None:
				row = _base_row(s, d, pp, so_map, weights, sec_nos, completed, excess,
								consumables, rm_cost, rate_map, created_on)
				rows_by_key[key] = row
				order.append(key)

			slug = slug_by_operation.get(s.operation)
			if not slug:
				continue
			# The issuing operation reports the drawing's transferred weight -- the same
			# figure the Transferred Weight column carries, deliberately, so the two do
			# not disagree. The SOE's own copy of it is the pre-transfer plan and would.
			is_first = op_seq.get(s.operation, 0) <= 1
			row["op_%s_qty" % slug] = (
				flt(row["transferred_weight_kg"], 3) if is_first
				else flt(d.get("completed_qty_nos"), 3)
			)
			row["op_%s_status" % slug] = s.status or ""
			row["op_%s_rounds" % slug] = call_counts.get(s.name, 0)
			row["op_%s_inspection" % slug] = s.custom_inspection_status or ""
			row["op_%s_gap" % slug] = gap_days.get(s.name, 0)

	data = [rows_by_key[k] for k in order]
	data.sort(key=lambda r: (r["sales_order"] or "", r["production_plan"] or "",
							 r["subcontracting_order"] or "", r["drawing"] or ""))
	return data, operations


def _base_row(s, d, pp, so_map, weights, sec_nos, completed, excess, consumables,
			  rm_cost, rate_map, created_on):
	so = so_map.get(d.get("sales_order"), frappe._dict())
	sco = s.subcontracting_order
	drawing = d.get("drawing") or ""
	w = weights.get((sco, drawing), frappe._dict())
	sn = sec_nos.get((sco, d.get("duno_mark_no") or ""), {})
	done = completed.get((sco, drawing), frappe._dict())
	ex = excess.get(sco, {})
	cons = consumables.get(sco, {})
	rate = rate_map.get(drawing, frappe._dict())

	# Weight of the pieces actually finished, rather than the count on its own: a
	# drawing worth 1814 Kg for two pieces has done 907 Kg when one of them is out.
	qty_to_mfg = flt(done.get("qty_to_manufacture"))
	per_piece = flt(done.get("total_weight_kg")) / qty_to_mfg if qty_to_mfg else 0.0
	completed_nos = flt(done.get("completed_qty_nos"))

	return {
		"sales_order": d.get("sales_order") or "",
		"customer": so.get("customer") or "",
		"project": pp.get("project") or so.get("project") or "",
		"production_plan": s.production_plan,
		"job_type": pp.get("custom_type") or "",
		"subcontracting_order": sco,
		"supplier": s.supplier,
		"drawing": drawing,
		"duno_mark_no": d.get("duno_mark_no") or "",
		"customer_drawing_number": d.get("customer_drawing_number") or "",
		"created_on": created_on.get(sco),
		"customer_weight_kg": flt(w.get("customer_weight_kg")),
		"planned_weight_kg": flt(w.get("total_weight_kg")),
		"planned_sec_nos": flt(sn.get("planned"), 3),
		"transferred_weight_kg": flt(w.get("transferred_weight_kg")),
		"transferred_sec_nos": flt(sn.get("issued"), 3),
		"consumed_rm_cost": flt(rm_cost.get((sco, drawing))),
		"rate_schedule": rate.get("rate_schedule") or "",
		"rate_per_kg": flt(rate.get("rs_rate_per_kg")),
		"consumables_nos": flt(cons.get("nos"), 3),
		"consumable_cost": flt(cons.get("cost")),
		"excess_weight_kg": flt(ex.get("excess"), 3),
		"returned_excess_kg": flt(ex.get("returned"), 3),
		"excess_difference_kg": flt(ex.get("difference"), 3),
		"completed_drawing_weight_kg": flt(per_piece * completed_nos, 3),
		"completed_nos": completed_nos,
	}


def _operation_columns(op_seq):
	"""The operation blocks, in the order the operations run.

	Slugs are what the column fieldnames are built from, so two operations that scrub
	to the same slug ("Fit-up" and "Fit Up", say) are separated rather than silently
	writing into each other's columns."""
	seen = set()
	out = []
	for operation, seq in sorted(op_seq.items(), key=lambda kv: (kv[1], kv[0])):
		slug = frappe.scrub(operation)
		if slug in seen:
			slug = "%s_%s" % (slug, len(out))
		seen.add(slug)
		out.append({"operation": operation, "slug": slug, "sequence_id": seq,
					"unit": _("Kg") if seq <= 1 else _("Nos")})
	return out


def _drawing_figures(sco_names):
	"""Drawing-level weights, piece counts and completion, keyed (job work order, drawing).

	Not read from the SOE Drawing Detail rows: their transferred_weight_kg is only ever
	filled on sequence 1, so every later operation would report 0 Kg transferred for a
	drawing whose material had in fact shipped.

	Preference is the linked Material Issue Plan's own drawing rows -- that is where
	transferred weight is actually maintained (refresh_weight_summary); the
	Subcontracting Order's copy of the same table carries customer/planned/excess but
	leaves transferred at 0. The SCO rows are loaded first as a fallback so a plan with
	no Material Issue Plan yet still reports the three weights it does know.

	Completion goes the other way and is read from the Subcontracting Order's rows only:
	that is the copy the operations write finished pieces back to, and it is a
	job-level figure rather than one operation's share of it."""
	weights, sec_nos, completed = {}, {}, {}
	if not sco_names:
		return weights, sec_nos, completed

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
					"transferred_weight_kg", "excess_weight_kg", "qty_to_manufacture",
					"completed_qty_nos"],
		):
			if not w.drawing:
				continue
			key = (parent_to_sco[w.parent], w.drawing)
			weights[key] = w
			if parenttype == "Subcontracting Order":
				completed[key] = w

	# Sec Nos (piece counts) alongside the weights. No drawing-level table holds
	# these -- Sec Qty lives only on the individual raw-material rows -- so they are
	# aggregated per DUNO/Mark No from the Material Issue Plan's own rows.
	#
	# Issued Sec Nos is derived rather than stored, scaling each row's Sec Qty by the
	# share of its Kg that actually shipped. That is what makes fractional rows add
	# up: where two drawings each hold part of one physical piece (0.098 and 0.102 of
	# it), the pieces they were issued come to 0.49 and 0.51 -- one whole piece
	# between them, which is exactly what left the rack. Issued can legitimately
	# exceed planned, since Sec Nos rounded up at transfer is the normal case and the
	# surplus is booked as excess to return.
	for r in frappe.get_all(
		"Material Issue Plan Raw Material",
		filters={"parent": ["in", list(mip_to_sco)]} if mip_to_sco else {"parent": ["in", []]},
		fields=["parent", "duno_mark_no", "sec_qty", "qty", "transferred_qty"],
	):
		key = (mip_to_sco[r.parent], r.duno_mark_no or "")
		agg = sec_nos.setdefault(key, {"planned": 0.0, "issued": 0.0})
		agg["planned"] += flt(r.sec_qty)
		if flt(r.qty):
			agg["issued"] += flt(r.sec_qty) * flt(r.transferred_qty) / flt(r.qty)

	return weights, sec_nos, completed


def _mip_by_sco(sco_names):
	if not sco_names:
		return {}
	out = {}
	for m in frappe.get_all("Material Issue Plan",
							filters={"subcontracting_order": ["in", sco_names]},
							fields=["name", "subcontracting_order"]):
		out.setdefault(m.subcontracting_order, []).append(m.name)
	return out


def _excess_by_sco(mip_by_sco):
	"""Excess booked, excess actually returned, and what is still out there.

	These are job-level rather than drawing-level, and deliberately so: the off-cut a
	transfer leaves over belongs to a batch, not to a drawing, and the excess rows the
	transfer popup writes carry no DUNO to attribute it back with. The same three
	figures therefore repeat on every drawing row of the job -- read them once per job.

	Billed-to-Consume comes off the difference rather than sitting in it forever. That
	material is scrapped by decision, not awaiting collection, which is the same line
	the Excess Material Return Report draws when it builds its chase-list."""
	out = {}
	all_mips = [m for names in mip_by_sco.values() for m in names]
	if not all_mips:
		return out

	rows_by_mip = {}
	for r in frappe.get_all(
		"SCO Excess Material Item",
		filters={"parent": ["in", all_mips], "parenttype": "Material Issue Plan"},
		fields=["parent", "qty", "stock_entry_created", "billed_to_consume"],
	):
		rows_by_mip.setdefault(r.parent, []).append(r)

	for sco, mips in mip_by_sco.items():
		excess = returned = billed = 0.0
		for mip in mips:
			for r in rows_by_mip.get(mip, []):
				excess += flt(r.qty)
				if r.stock_entry_created:
					returned += flt(r.qty)
				elif r.billed_to_consume:
					billed += flt(r.qty)
		out[sco] = {
			"excess": excess,
			"returned": returned,
			"difference": excess - returned - billed,
		}
	return out


def _consumables_by_sco(sco_names, production_plans):
	"""Consumables issued against the job -- welding rods, paint, gas.

	Read from submitted Stock Entries of type "Material Consumption for Manufacture",
	counting only the rows actually marked as consumables. Ticking Consumable Entry on
	such a Stock Entry marks every row for you, so in practice that is all of them; the
	flag matters on an entry somebody built by hand and only partly consumable.

	Job-level, like the excess figures, and repeated on the job's drawing rows: the
	entry names the job through Sales Order and Production Plan and does not say which
	drawing burnt the rod."""
	out = {}
	plans = [p for p in (production_plans or []) if p]
	if not (sco_names or plans):
		return out

	or_filters = []
	if sco_names:
		or_filters.append(["custom_sco_ref", "in", sco_names])
		or_filters.append(["subcontracting_order", "in", sco_names])
	if plans:
		or_filters.append(["custom_consumable_production_plan", "in", plans])

	entries = frappe.get_all(
		"Stock Entry",
		filters={"docstatus": 1, "stock_entry_type": CONSUMPTION_ENTRY_TYPE},
		or_filters=or_filters,
		fields=["name", "custom_sco_ref", "subcontracting_order", "custom_consumable_production_plan"],
	)
	if not entries:
		return out

	sco_by_plan = {}
	if plans and sco_names:
		for m in frappe.get_all("Material Issue Plan",
								filters={"subcontracting_order": ["in", sco_names]},
								fields=["subcontracting_order", "production_plan"]):
			if m.production_plan:
				sco_by_plan[m.production_plan] = m.subcontracting_order

	sco_by_entry = {}
	for e in entries:
		sco = e.custom_sco_ref or e.subcontracting_order or sco_by_plan.get(e.custom_consumable_production_plan)
		if sco:
			sco_by_entry[e.name] = sco
	if not sco_by_entry:
		return out

	for row in frappe.get_all(
		"Stock Entry Detail",
		filters={"parent": ["in", list(sco_by_entry)], "custom_is_consumable": 1},
		fields=["parent", "qty", "amount"],
	):
		agg = out.setdefault(sco_by_entry[row.parent], {"nos": 0.0, "cost": 0.0})
		agg["nos"] += flt(row.qty)
		agg["cost"] += flt(row.amount)
	return out


def _rm_cost_by_drawing(sco_names):
	"""What the raw material issued to each drawing was worth, from the Stock Entries
	that issued it -- the valuation the stock ledger itself used, not a recalculation.

	Attributed by the drawing stamped on the Stock Entry row (custom_drawing), which the
	transfer flows copy forward; a row carrying no drawing is left out rather than
	spread across the job's drawings, since guessing whose material it was is worse than
	reporting nothing."""
	if not sco_names:
		return {}
	entries = frappe.get_all(
		"Stock Entry",
		filters={"docstatus": 1},
		or_filters=[["custom_sco_ref", "in", sco_names], ["subcontracting_order", "in", sco_names]],
		fields=["name", "custom_sco_ref", "subcontracting_order"],
	)
	if not entries:
		return {}
	sco_by_entry = {e.name: (e.custom_sco_ref or e.subcontracting_order) for e in entries}

	out = {}
	for row in frappe.get_all(
		"Stock Entry Detail",
		filters={"parent": ["in", list(sco_by_entry)], "custom_drawing": ["!=", ""]},
		fields=["parent", "custom_drawing", "amount"],
	):
		key = (sco_by_entry[row.parent], row.custom_drawing)
		out[key] = flt(out.get(key, 0)) + flt(row.amount)
	return out


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


def get_columns(operations):
	columns = [
		{"label": _("Sales Order"), "fieldname": "sales_order", "fieldtype": "Link", "options": "Sales Order", "width": 130},
		{"label": _("Customer"), "fieldname": "customer", "fieldtype": "Link", "options": "Customer", "width": 140},
		{"label": _("Project"), "fieldname": "project", "fieldtype": "Link", "options": "Project", "width": 110},
		{"label": _("Production Plan (Team)"), "fieldname": "production_plan", "fieldtype": "Link", "options": "Production Plan", "width": 150},
		{"label": _("Job Type"), "fieldname": "job_type", "fieldtype": "Data", "width": 110},
		{"label": _("Job Work Order"), "fieldname": "subcontracting_order", "fieldtype": "Link", "options": "Subcontracting Order", "width": 150},
		{"label": _("Supplier"), "fieldname": "supplier", "fieldtype": "Link", "options": "Supplier", "width": 140},
		{"label": _("Drawing"), "fieldname": "drawing", "fieldtype": "Link", "options": "Drawing", "width": 130},
		{"label": _("DUNO/Mark No"), "fieldname": "duno_mark_no", "fieldtype": "Data", "width": 110},
		{"label": _("Cust Drawing No"), "fieldname": "customer_drawing_number", "fieldtype": "Data", "width": 150},
		# Taken from the Job Work Order rather than from the operation entry: the date
		# people mean by "when was this job raised" is the order's own date, and it is
		# the same on every operation of it.
		{"label": _("Created On"), "fieldname": "created_on", "fieldtype": "Date", "width": 100,
		 "description": _("Date of the Job Work Order this drawing belongs to.")},
	]

	# One block per operation, in sequence order. Everything an operation has to say
	# about a drawing sits together under that operation's name, so reading across the
	# row walks the job forward in the order it actually runs.
	for op in operations:
		label = op["operation"]
		columns += [
			{"label": "%s (%s)" % (label, op["unit"]), "fieldname": "op_%s_qty" % op["slug"],
			 "fieldtype": "Float", "precision": 3, "width": 140,
			 "description": _("Kg issued at this operation.") if op["unit"] == _("Kg")
			 else _("Pieces completed at this operation.")},
			{"label": _("{0} Status").format(label), "fieldname": "op_%s_status" % op["slug"],
			 "fieldtype": "Data", "width": 110},
			{"label": _("{0} Inspection Rounds").format(label), "fieldname": "op_%s_rounds" % op["slug"],
			 "fieldtype": "Int", "width": 130},
			{"label": _("{0} Last Inspection Status").format(label), "fieldname": "op_%s_inspection" % op["slug"],
			 "fieldtype": "Data", "width": 150},
			{"label": _("{0} Gap (Days, approx.)").format(label), "fieldname": "op_%s_gap" % op["slug"],
			 "fieldtype": "Int", "width": 140,
			 "description": _("Days between the previous operation being raised and this one.")},
		]

	columns += [
		# Drawing-level weights. Sec Nos sit beside the weight they belong to -- the two
		# are read together, and a weight without its piece count has repeatedly been the
		# thing that hides a problem (a rounded-up transfer looks identical in Kg terms
		# until you see Nos).
		{"label": _("Customer Weight (Kg)"), "fieldname": "customer_weight_kg", "fieldtype": "Float", "width": 130},
		{"label": _("Planned Weight (Kg)"), "fieldname": "planned_weight_kg", "fieldtype": "Float", "width": 130},
		{"label": _("Planned Sec Nos"), "fieldname": "planned_sec_nos", "fieldtype": "Float", "precision": 3, "width": 120},
		{"label": _("Transferred Weight (Kg)"), "fieldname": "transferred_weight_kg", "fieldtype": "Float", "width": 145},
		{"label": _("Transferred Sec Nos"), "fieldname": "transferred_sec_nos", "fieldtype": "Float", "precision": 3, "width": 140},
		{"label": _("Consumed RM Cost"), "fieldname": "consumed_rm_cost", "fieldtype": "Currency", "width": 140,
		 "description": _("Value of the raw material issued to this drawing, from the Stock Entries that issued it.")},
		{"label": _("Rate Schedule"), "fieldname": "rate_schedule", "fieldtype": "Link", "options": "Rate Schedule", "width": 130},
		{"label": _("Rate / Kg"), "fieldname": "rate_per_kg", "fieldtype": "Currency", "width": 100,
		 "description": _("The job-work rate on this drawing's Rate Schedule.")},
		{"label": _("Consumables (Nos)"), "fieldname": "consumables_nos", "fieldtype": "Float", "precision": 3, "width": 130,
		 "description": _("Job-level. From Material Consumption for Manufacture Stock Entries, repeated on every drawing row of the job.")},
		{"label": _("Consumable Cost"), "fieldname": "consumable_cost", "fieldtype": "Currency", "width": 130,
		 "description": _("Job-level. Value of those same consumable rows.")},
		{"label": _("Excess Weight (Kg)"), "fieldname": "excess_weight_kg", "fieldtype": "Float", "precision": 3, "width": 130,
		 "description": _("Job-level. Excess booked by the Material Issue Plan transfer popup.")},
		{"label": _("Returned Excess Weight (Kg)"), "fieldname": "returned_excess_kg", "fieldtype": "Float", "precision": 3, "width": 160,
		 "description": _("Job-level. The part of it already brought back in by a Return Excess Entry.")},
		{"label": _("Difference (Kg)"), "fieldname": "excess_difference_kg", "fieldtype": "Float", "precision": 3, "width": 120,
		 "description": _("Excess less what has been returned, less what was billed to consume -- what is still out there.")},
		{"label": _("Completed Drawing Weight (Kg)"), "fieldname": "completed_drawing_weight_kg", "fieldtype": "Float", "precision": 3, "width": 175,
		 "description": _("Completed pieces valued at the drawing's own weight per piece.")},
		{"label": _("Completed Drawing (Nos)"), "fieldname": "completed_nos", "fieldtype": "Float", "precision": 3, "width": 150},
	]
	return columns
