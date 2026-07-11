import frappe
from frappe import _
from frappe.utils import flt

FORMULA_GROUPS = {"Structurals", "Plates"}

OPERATIONS = [
	"Material Issue",
	"Cutting Status",
	"Material Matching",
	"Fit-up",
	"Fitup Inspection",
	"Welding",
	"Welding Inspection",
	"Final",
	"Final Inspection",
	"Blasting",
	"Painting",
	"Despatch",
]

ROUTING_NAME = "Standard Manufacturing Routing"


# ─────────────────────────────────────────────────────────────────────────────
# Master data setup — called from setup.py after_migrate (idempotent)
# ─────────────────────────────────────────────────────────────────────────────

def create_operations_workstations_routing():
	"""Idempotently create 12 operations, 12 workstations, and 1 routing."""
	_create_operations()
	_create_workstations()
	_create_routing()
	frappe.db.commit()


def _create_operations():
	for op_name in OPERATIONS:
		if frappe.db.exists("Operation", op_name):
			continue
		frappe.get_doc({
			"doctype": "Operation",
			"name": op_name,
		}).insert(ignore_permissions=True)


def _create_workstations():
	for ws_name in OPERATIONS:
		if frappe.db.exists("Workstation", ws_name):
			continue
		frappe.get_doc({
			"doctype": "Workstation",
			"workstation_name": ws_name,
			"production_capacity": 1,
			"hour_rate_labour": 0,
		}).insert(ignore_permissions=True)
	# Link each operation to its workstation (safe to repeat — set_value is idempotent)
	for op_name in OPERATIONS:
		frappe.db.set_value("Operation", op_name, "workstation", op_name)


def _create_routing():
	if frappe.db.exists("Routing", ROUTING_NAME):
		routing = frappe.get_doc("Routing", ROUTING_NAME)
		routing.operations = []
		for idx, op_name in enumerate(OPERATIONS, start=1):
			routing.append("operations", {
				"operation": op_name,
				"workstation": op_name,
				"time_in_mins": 60,
				"sequence_id": idx,
			})
		routing.save(ignore_permissions=True)
		return

	routing = frappe.get_doc({
		"doctype": "Routing",
		"routing_name": ROUTING_NAME,
	})
	for idx, op_name in enumerate(OPERATIONS, start=1):
		routing.append("operations", {
			"operation": op_name,
			"workstation": op_name,
			"time_in_mins": 60,
			"sequence_id": idx,
		})
	routing.insert(ignore_permissions=True)


# ─────────────────────────────────────────────────────────────────────────────
# Production Plan — routing operations for BOM
# ─────────────────────────────────────────────────────────────────────────────

@frappe.whitelist()
def get_routing_operations_for_bom(bom_name):
	"""Return operations for the BOM — from its routing if set, else from BOM operations directly."""
	if not bom_name:
		return []
	bom = frappe.get_doc("BOM", bom_name)
	if bom.routing:
		return frappe.get_all(
			"BOM Operation",
			filters={"parent": bom.routing, "parenttype": "Routing"},
			fields=["operation", "sequence_id"],
			order_by="sequence_id asc",
		)
	if bom.with_operations and bom.operations:
		return [
			{"operation": op.operation, "sequence_id": op.sequence_id}
			for op in sorted(bom.operations, key=lambda o: o.sequence_id or 0)
		]
	return []


# ─────────────────────────────────────────────────────────────────────────────
# Job Card — raw material population
# ─────────────────────────────────────────────────────────────────────────────

@frappe.whitelist()
def get_raw_materials_for_job_card(job_card_name):
	"""Return enriched raw-material rows for a Job Card's consumption table.
	Called once from the client script onload when the table is empty."""
	jc = frappe.get_doc("Job Card", job_card_name)
	if not jc.work_order:
		return []

	wo = frappe.get_doc("Work Order", jc.work_order)
	wip_warehouse = wo.wip_warehouse
	bom_no = wo.bom_no

	rows = []
	for item in wo.required_items:
		item_data = frappe.db.get_value(
			"Item",
			item.item_code,
			["custom_parent_item_group", "custom_unit_weight", "custom_secondary_uom", "stock_uom"],
			as_dict=True,
		) or {}

		bom_item_data = {}
		if bom_no:
			bom_item_data = frappe.db.get_value(
				"BOM Item",
				{"parent": bom_no, "item_code": item.item_code},
				["custom_length", "custom_width", "custom_thickness"],
				as_dict=True,
			) or {}

		transferred_qty = _get_transferred_qty_for_item(item.item_code, wip_warehouse)
		prev_data = _get_previous_operation_consumed(jc.work_order, item.item_code, jc.sequence_id)

		rows.append({
			"item_code": item.item_code,
			"item_name": item.item_name,
			"parent_item_group": item_data.get("custom_parent_item_group") or "",
			"unit_weight": flt(item_data.get("custom_unit_weight")),
			"stock_uom": item_data.get("stock_uom") or "",
			"sec_uom": item_data.get("custom_secondary_uom") or "",
			"length": flt(bom_item_data.get("custom_length")),
			"width": flt(bom_item_data.get("custom_width")),
			"thickness": flt(bom_item_data.get("custom_thickness")),
			"transferred_qty": transferred_qty,
			"prev_operation_consumed_stock_qty": flt(prev_data.get("consumed_stock_qty")),
			"prev_operation_stock_uom": prev_data.get("stock_uom") or "",
			"prev_operation_sec_qty": flt(prev_data.get("sec_qty")),
			"prev_operation_sec_uom": prev_data.get("sec_uom") or "",
		})
	return rows


def _get_transferred_qty_for_item(item_code, wip_warehouse):
	"""Query actual stock of item_code in wip_warehouse from tabBin."""
	if not wip_warehouse:
		return 0.0
	result = frappe.db.sql(
		"SELECT SUM(actual_qty) FROM `tabBin` WHERE item_code=%s AND warehouse=%s",
		(item_code, wip_warehouse),
	)
	return flt(result[0][0]) if result else 0.0


def _get_previous_operation_consumed(work_order, item_code, current_sequence_id):
	"""Find the immediately preceding Job Card's consumption for item_code.
	Falls back to the last submitted Supplier Operation Entry when there is no
	preceding Job Card to read from — either because the immediately preceding
	Job Card has no consumption data yet, or because this is sequence_id 1 (a
	Work Order's Job Cards are always locally renumbered starting at 1, so the
	Work Order's very first Job Card in a Scenario 3 hybrid plan is where the
	subcontractor → internal handoff must be picked up)."""
	if not current_sequence_id or current_sequence_id < 1:
		return {}

	if current_sequence_id > 1:
		prev_jc = frappe.db.sql(
			"""
			SELECT name
			FROM `tabJob Card`
			WHERE work_order = %s
			  AND sequence_id < %s
			  AND docstatus != 2
			ORDER BY sequence_id DESC
			LIMIT 1
			""",
			(work_order, current_sequence_id),
			as_dict=True,
		)
		if prev_jc:
			row = frappe.db.get_value(
				"Job Card Raw Material",
				{"parent": prev_jc[0]["name"], "item_code": item_code},
				["current_stock_qty", "stock_uom", "current_sec_qty", "sec_uom"],
				as_dict=True,
			)
			if row and (flt(row.current_stock_qty) > 0 or flt(row.current_sec_qty) > 0):
				return {
					"consumed_stock_qty": flt(row.current_stock_qty),
					"stock_uom": row.stock_uom or "",
					"sec_qty": flt(row.current_sec_qty),
					"sec_uom": row.sec_uom or "",
				}

	# Scenario 3 fallback: preceding op was subcontracted (or this is Job Card 1
	# of the Work Order) — look at the last submitted SOE on the sibling SCO.
	return _get_prev_soe_consumed_for_jc(work_order, item_code)


def _get_prev_soe_consumed_for_jc(work_order, item_code):
	"""Return consumption from the last submitted SOE linked to the same Production Plan
	as the Work Order. Used for Scenario 3 (subcontractor → internal Job Card handoff)."""
	pp_name = frappe.db.get_value("Work Order", work_order, "production_plan")
	if not pp_name:
		return {}

	sco_name = frappe.db.get_value(
		"Subcontracting Order",
		{"custom_production_plan": pp_name, "docstatus": 1},
		"name",
	)
	if not sco_name:
		return {}

	last_soe = frappe.db.get_value(
		"Supplier Operation Entry",
		{"subcontracting_order": sco_name, "docstatus": 1},
		"name",
		order_by="sequence_id desc",
	)
	if not last_soe:
		return {}

	row = frappe.db.get_value(
		"Supplier Operation Item",
		{"parent": last_soe, "item_code": item_code},
		["current_sec_qty", "current_stock_qty", "stock_uom", "sec_uom"],
		as_dict=True,
	)
	if not row:
		return {}
	return {
		"consumed_stock_qty": flt(row.current_stock_qty),
		"stock_uom": row.stock_uom or "",
		"sec_qty": flt(row.current_sec_qty),
		"sec_uom": row.sec_uom or "",
	}


# ─────────────────────────────────────────────────────────────────────────────
# Final Work Order consumption check
# ─────────────────────────────────────────────────────────────────────────────

def validate_final_operation_consumption(work_order_name):
	"""Ensure all raw materials have recorded consumption in the last Job Card.
	Called from before_submit on Work Order."""
	wo = frappe.get_doc("Work Order", work_order_name)

	last_jc = frappe.db.sql(
		"""
		SELECT name, sequence_id, operation
		FROM `tabJob Card`
		WHERE work_order = %s AND docstatus != 2
		ORDER BY sequence_id DESC
		LIMIT 1
		""",
		(work_order_name,),
		as_dict=True,
	)
	if not last_jc:
		frappe.throw(_("No Job Cards found for Work Order {0}").format(work_order_name))

	last_jc_name = last_jc[0]["name"]
	required_items = {item.item_code for item in wo.required_items}

	consumed_rows = frappe.get_all(
		"Job Card Raw Material",
		filters={"parent": last_jc_name},
		fields=["item_code", "current_stock_qty", "manual_qty", "parent_item_group"],
	)
	consumed_map = {r.item_code: r for r in consumed_rows}

	missing = []
	for item_code in required_items:
		row = consumed_map.get(item_code)
		if not row:
			missing.append(item_code)
			continue
		group = row.parent_item_group or ""
		if group in FORMULA_GROUPS:
			if flt(row.current_stock_qty) <= 0:
				missing.append(item_code)
		else:
			if flt(row.manual_qty) <= 0:
				missing.append(item_code)

	if missing:
		frappe.throw(
			_(
				"Cannot submit Work Order {0}. The following items have no consumption "
				"recorded in the final Job Card ({1}): {2}"
			).format(work_order_name, last_jc_name, ", ".join(missing))
		)
