import frappe
from frappe import _
from frappe.utils import flt

FORMULA_GROUPS = {"Structurals", "Plates"}

# The standard routing, in the order the shop runs it. Rebuilt on every migrate, so
# this list is the single source of truth for what a new BOM pulls in and therefore
# what operations a new job is raised with.
#
# Material Issue was removed at the client's request on 2026-08-25: issuing material is
# what the Material Issue Plan does, and carrying it as an operation as well made every
# job start on a step nobody worked. Kept here, commented, rather than deleted -- the
# client asked for it back as a one-line change if they change their mind. Put the line
# back and migrate; the routing renumbers itself.
#
#	"Material Issue",
#
# Jobs already raised are untouched: the Operation master still exists and their
# existing Supplier Operation Entries keep referring to it. This only decides what NEW
# BOMs and NEW jobs are built from.
OPERATIONS = [
	"Fit-up",
	"Welding",
	"Final",
	"Blasting",
	"Painting",
]

ROUTING_NAME = "Standard Manufacturing Routing"


# ─────────────────────────────────────────────────────────────────────────────
# Master data setup — called from setup.py after_migrate (idempotent)
# ─────────────────────────────────────────────────────────────────────────────

def create_operations_workstations_routing():
	"""Idempotently create 6 operations, 6 workstations, and 1 routing."""
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
