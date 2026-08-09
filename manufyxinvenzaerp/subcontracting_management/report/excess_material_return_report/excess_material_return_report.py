# Copyright (c) 2026, Manufyxinvenza and Contributors
# License: GNU General Public License v3. See license.txt

import frappe
from frappe import _
from frappe.utils import flt, getdate, nowdate


def execute(filters=None):
	filters = filters or {}
	columns = get_columns()
	data = get_data(filters)
	return columns, data


def get_data(filters):
	row_filters = {}
	if filters.get("item_code"):
		row_filters["item_code"] = filters["item_code"]

	status = filters.get("status") or "Pending"
	if status == "Pending":
		row_filters["stock_entry_created"] = 0
	elif status == "Returned":
		row_filters["stock_entry_created"] = 1
	# "All" -> no stock_entry_created filter

	if filters.get("return_type"):
		row_filters["return_type"] = filters["return_type"]

	rows = frappe.get_all(
		"SCO Excess Material Item",
		filters=row_filters,
		fields=["name", "parent", "item_code", "item_name", "parent_item_group",
				"length", "width", "thickness", "sec_qty", "sec_uom", "qty", "uom",
				"stock_entry_created", "return_type", "return_reason",
				"source_mip_raw_material_row", "mapped_material_planning"],
	)
	if not rows:
		return []

	mip_filters = {"name": ["in", list({r.parent for r in rows})]}
	if filters.get("material_issue_plan"):
		mip_filters["name"] = filters["material_issue_plan"]
	if filters.get("company"):
		mip_filters["company"] = filters["company"]
	if filters.get("subcontracting_order"):
		mip_filters["subcontracting_order"] = filters["subcontracting_order"]

	posting_date_filter = None
	if filters.get("from_date") and filters.get("to_date"):
		posting_date_filter = ["between", [filters["from_date"], filters["to_date"]]]
	elif filters.get("from_date"):
		posting_date_filter = [">=", filters["from_date"]]
	elif filters.get("to_date"):
		posting_date_filter = ["<=", filters["to_date"]]
	if posting_date_filter:
		mip_filters["posting_date"] = posting_date_filter

	mips = frappe.get_all(
		"Material Issue Plan",
		filters=mip_filters,
		fields=["name", "company", "posting_date", "subcontracting_order",
				"excess_return_warehouse", "production_plan"],
	)
	mip_map = {m.name: m for m in mips}
	if not mip_map:
		return []

	sco_names = list({m.subcontracting_order for m in mips if m.subcontracting_order})
	sco_map = {}
	if sco_names:
		for s in frappe.get_all("Subcontracting Order", filters={"name": ["in", sco_names]}, fields=["name", "supplier"]):
			sco_map[s.name] = s

	pp_names = list({m.production_plan for m in mips if m.production_plan})
	pp_map = {}
	if pp_names:
		for p in frappe.get_all("Production Plan", filters={"name": ["in", pp_names]}, fields=["name", "custom_type"]):
			pp_map[p.name] = p

	if filters.get("job_type"):
		mip_map = {
			name: m for name, m in mip_map.items()
			if pp_map.get(m.production_plan, frappe._dict()).get("custom_type") == filters["job_type"]
		}
		if not mip_map:
			return []

	# DUNO/Cust Drawing No/Sales Order traceability -- the excess row's own
	# source_mip_raw_material_row points at the CURRENT raw_materials row
	# (kept fresh by _sync_excess_return_from_raw_materials on every MIP
	# save), which is where duno_mark_no/sales_order actually live.
	raw_row_names = [r.source_mip_raw_material_row for r in rows if r.source_mip_raw_material_row]
	raw_map = {}
	if raw_row_names:
		for rr in frappe.get_all(
			"Material Issue Plan Raw Material",
			filters={"name": ["in", raw_row_names]},
			fields=["name", "duno_mark_no", "customer_drawing_number", "sales_order"],
		):
			raw_map[rr.name] = rr

	if filters.get("sales_order"):
		raw_map = {
			name: rr for name, rr in raw_map.items() if rr.sales_order == filters["sales_order"]
		}

	today = getdate(nowdate())
	data = []
	for r in rows:
		mip = mip_map.get(r.parent)
		if not mip:
			continue
		raw = raw_map.get(r.source_mip_raw_material_row, frappe._dict())
		if filters.get("sales_order") and raw.get("sales_order") != filters["sales_order"]:
			continue
		sco = sco_map.get(mip.subcontracting_order, frappe._dict())
		pp = pp_map.get(mip.production_plan, frappe._dict())
		days_pending = (today - getdate(mip.posting_date)).days if mip.posting_date and not r.stock_entry_created else 0
		data.append({
			"material_issue_plan": mip.name,
			"posting_date": mip.posting_date,
			"company": mip.company,
			"job_type": pp.get("custom_type") or "",
			"subcontracting_order": mip.subcontracting_order,
			"supplier": sco.get("supplier"),
			"excess_return_warehouse": mip.excess_return_warehouse,
			"item_code": r.item_code,
			"item_name": r.item_name,
			"parent_item_group": r.parent_item_group,
			"duno_mark_no": raw.get("duno_mark_no") or "",
			"customer_drawing_number": raw.get("customer_drawing_number") or "",
			"sales_order": raw.get("sales_order") or "",
			"length": flt(r.length),
			"width": flt(r.width),
			"thickness": flt(r.thickness),
			"sec_qty": flt(r.sec_qty),
			"sec_uom": r.sec_uom,
			"weight_kg": flt(r.qty),
			"uom": r.uom,
			"return_type": r.return_type or "Return to Own Warehouse",
			"status": _("Returned") if r.stock_entry_created else (
				_("Claimed (via Excess Material Mapping)") if r.mapped_material_planning else _("Pending")
			),
			"return_reason": r.return_reason or "",
			"days_pending": days_pending,
		})

	data.sort(key=lambda d: (d["material_issue_plan"], d["item_code"]))
	return data


def get_columns():
	return [
		{"label": _("Material Issue Plan"), "fieldname": "material_issue_plan", "fieldtype": "Link", "options": "Material Issue Plan", "width": 140},
		{"label": _("Date"), "fieldname": "posting_date", "fieldtype": "Date", "width": 100},
		{"label": _("Company"), "fieldname": "company", "fieldtype": "Link", "options": "Company", "width": 140},
		{"label": _("Job Type"), "fieldname": "job_type", "fieldtype": "Data", "width": 120},
		{"label": _("Subcontracting Order"), "fieldname": "subcontracting_order", "fieldtype": "Link", "options": "Subcontracting Order", "width": 150},
		{"label": _("Supplier"), "fieldname": "supplier", "fieldtype": "Link", "options": "Supplier", "width": 140},
		{"label": _("Finished Goods Warehouse"), "fieldname": "excess_return_warehouse", "fieldtype": "Link", "options": "Warehouse", "width": 160},
		{"label": _("Item Code"), "fieldname": "item_code", "fieldtype": "Link", "options": "Item", "width": 130},
		{"label": _("Item Name"), "fieldname": "item_name", "fieldtype": "Data", "width": 160},
		{"label": _("Item Group"), "fieldname": "parent_item_group", "fieldtype": "Data", "width": 100},
		{"label": _("DUNO/Mark No"), "fieldname": "duno_mark_no", "fieldtype": "Data", "width": 120},
		{"label": _("Cust Drawing No"), "fieldname": "customer_drawing_number", "fieldtype": "Data", "width": 120},
		{"label": _("Sales Order"), "fieldname": "sales_order", "fieldtype": "Link", "options": "Sales Order", "width": 120},
		{"label": _("Length (mm)"), "fieldname": "length", "fieldtype": "Float", "width": 100},
		{"label": _("Width (mm)"), "fieldname": "width", "fieldtype": "Float", "width": 100},
		{"label": _("Thickness (mm)"), "fieldname": "thickness", "fieldtype": "Float", "width": 100},
		{"label": _("Sec Qty"), "fieldname": "sec_qty", "fieldtype": "Float", "width": 90},
		{"label": _("Sec UOM"), "fieldname": "sec_uom", "fieldtype": "Link", "options": "UOM", "width": 80},
		{"label": _("Weight (Kg)"), "fieldname": "weight_kg", "fieldtype": "Float", "width": 100},
		{"label": _("UOM"), "fieldname": "uom", "fieldtype": "Link", "options": "UOM", "width": 80},
		{"label": _("Return Type"), "fieldname": "return_type", "fieldtype": "Data", "width": 170},
		{"label": _("Status"), "fieldname": "status", "fieldtype": "Data", "width": 120},
		{"label": _("Return Reason"), "fieldname": "return_reason", "fieldtype": "Data", "width": 180},
		{"label": _("Days Pending"), "fieldname": "days_pending", "fieldtype": "Int", "width": 100},
	]
