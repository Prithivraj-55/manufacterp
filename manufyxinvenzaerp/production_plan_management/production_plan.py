import frappe
import json
from frappe import _
from frappe.utils import flt
from collections import defaultdict
from frappe.query_builder.functions import IfNull, Sum
from erpnext.stock.get_item_details import get_conversion_factor
from erpnext.setup.doctype.item_group.item_group import get_item_group_defaults
from frappe.utils import (
	add_days,
	ceil,
	cint,
	comma_and,
	flt,
	get_link_to_form,
	getdate,
	now_datetime,
	nowdate,
)

def get_sbb_available_qty(item_code, warehouse, dimensions, location=None):
	"""
	Fetch available qty per batch for an item in a warehouse, optionally filtered
	by Store Location (Inventory Dimension: store_location on Stock Ledger Entry).

	Flow when location is given:
	  SLE (item + warehouse + store_location) → SBB → SBE → aggregate by batch_no
	Flow without location:
	  SBB (item + warehouse) → SBE → aggregate by batch_no

	Returns (total_qty, matched_batches) where each matched_batch includes
	batch_no, qty (Kg), custom_sec_qty (NOS), custom_sec_uom.
	Only batches whose dimensions exactly match the required dimensions are returned.
	"""
	total_qty = 0
	matched_batches = []

	if location:
		# Filter SLEs by location → collect their SBB names
		sle_filters = {
			"item_code": item_code,
			"warehouse": warehouse,
			"is_cancelled": 0,
			"store_location": location,
			"serial_and_batch_bundle": ("is", "set"),
		}
		sle_list = frappe.get_all(
			"Stock Ledger Entry",
			filters=sle_filters,
			fields=["serial_and_batch_bundle"],
		)
		if not sle_list:
			return 0, []
		sbb_names = list({s.serial_and_batch_bundle for s in sle_list if s.serial_and_batch_bundle})
	else:
		sbb_list = frappe.get_all(
			"Serial and Batch Bundle",
			filters={"item_code": item_code, "warehouse": warehouse},
			fields=["name"],
		)
		if not sbb_list:
			return 0, []
		sbb_names = [d.name for d in sbb_list]

	entries = frappe.get_all(
		"Serial and Batch Entry",
		filters={"parent": ["in", sbb_names]},
		fields=["parent", "batch_no", "qty"],
	)
	if not entries:
		return 0, []

	batch_nos = list({e.batch_no for e in entries if e.batch_no})

	batch_map = {}
	if batch_nos:
		batch_data = frappe.get_all(
			"Batch",
			filters={"name": ["in", batch_nos]},
			fields=["name", "custom_length", "custom_thickness", "custom_width",
			        "custom_sec_qty", "custom_sec_uom"],
		)
		batch_map = {b.name: b for b in batch_data}

	# Net qty per batch across all SBB entries (outgoing SBEs have negative qty)
	batch_qty_map = defaultdict(float)
	for row in entries:
		if row.batch_no:
			batch_qty_map[row.batch_no] += flt(row.qty)

	for batch_no, qty in batch_qty_map.items():
		if qty <= 0:
			continue
		batch = batch_map.get(batch_no)
		if not batch:
			continue

		if (
			flt(batch.custom_length) == flt(dimensions.get("custom_length"))
			and flt(batch.custom_thickness) == flt(dimensions.get("custom_thickness"))
			and flt(batch.custom_width) == flt(dimensions.get("custom_width"))
		):
			total_qty += qty
			matched_batches.append({
				"batch_no": batch_no,
				"qty": qty,
				"custom_sec_qty": flt(batch.custom_sec_qty),
				"custom_sec_uom": batch.custom_sec_uom,
			})

	return total_qty, matched_batches


@frappe.whitelist()
def get_items_for_material_requests(doc, warehouses=None, get_parent_warehouse_data=None):
	if isinstance(doc, str):
		doc = frappe._dict(json.loads(doc))

	if warehouses:
		warehouses = list(set(get_warehouse_list(warehouses)))

		if (
			doc.get("for_warehouse")
			and not get_parent_warehouse_data
			and doc.get("for_warehouse") in warehouses
		):
			warehouses.remove(doc.get("for_warehouse"))

	doc["mr_items"] = []

	po_items = doc.get("po_items") if doc.get("po_items") else doc.get("items")

	if not po_items or not [row.get("item_code") for row in po_items if row.get("item_code")]:
		frappe.throw(_("Items to Manufacture are required"))

	company = doc.get("company")
	ignore_existing_ordered_qty = doc.get("ignore_existing_ordered_qty")
	include_safety_stock = doc.get("include_safety_stock")

	# so_item_details keyed by (item_code, length, thickness, width) to handle same item at different dims
	so_item_details = frappe._dict()

	# =========================
	# STEP 1: BUILD ITEMS
	# =========================
	for data in po_items:
		planned_qty = data.get("required_qty") or data.get("planned_qty")

		item_details = {}

		if data.get("bom") or data.get("bom_no"):
			bom_no = data.get("bom") or data.get("bom_no")

			item_details = get_exploded_items(
				{},
				company,
				bom_no,
				1,
				planned_qty=planned_qty,
				doc=doc,
			)
			# Raw material dimensions come from the BOM explosion items themselves.
			# The po_item dimension is for the finished good and must NOT override
			# individual raw material dimensions — doing so collapses all structural
			# entries with different lengths into a single merged row.

		elif data.get("item_code"):
			item_master = frappe.get_doc("Item", data["item_code"]).as_dict()

			dim_key = (
				item_master.name,
				flt(data.get("custom_length")),
				flt(data.get("custom_thickness")),
				flt(data.get("custom_width")),
			)
			item_details[dim_key] = frappe._dict({
				"item_name": item_master.item_name,
				"qty": planned_qty or 1,
				"item_code": item_master.name,
				"description": item_master.description,
				"stock_uom": item_master.stock_uom,
				"safety_stock": item_master.safety_stock,
				"custom_thickness": data.get("custom_thickness"),
				"custom_length": data.get("custom_length"),
				"custom_width": data.get("custom_width"),
				"custom_parent_item_group": frappe.db.get_value(
					"Item", item_master.name, "custom_parent_item_group"
				),
				"custom_unit_weight": frappe.db.get_value(
					"Item", item_master.name, "custom_unit_weight"
				),
			})

		# Merge by the item's actual dimensions — two BOM items with the same
		# item_code and identical dimensions from different po_items are combined;
		# same item at different dimensions keeps a separate entry.
		for _sql_key, details in item_details.items():
			final_key = (
				details.item_code,
				flt(details.custom_length),
				flt(details.custom_thickness),
				flt(details.custom_width),
			)
			so_item_details.setdefault(None, frappe._dict())

			if final_key in so_item_details[None]:
				so_item_details[None][final_key]["qty"] += flt(details.qty)
			else:
				so_item_details[None][final_key] = details

	mr_items = []
	available_rows = []

	# =========================
	# STEP 2: SBB CHECK
	# =========================
	for item_dict in so_item_details.values():
		for details in item_dict.values():

			warehouse = doc.get("for_warehouse") or details.get("default_warehouse")
			required_qty = flt(details.qty)

			dimensions = {
				"custom_length": details.get("custom_length"),
				"custom_thickness": details.get("custom_thickness"),
				"custom_width": details.get("custom_width"),
			}

			available_qty, matched_batches = get_sbb_available_qty(
				details.item_code,
				warehouse,
				dimensions
			)

			# Build available-rows list (one row per matching batch)
			for batch in matched_batches:
				available_rows.append({
					"item_code": details.item_code,
					"item_name": details.item_name,
					"batch_no": batch["batch_no"],
					"required_qty": required_qty,
					"available_qty": batch["qty"],
					"custom_sec_qty": batch["custom_sec_qty"],
					"custom_sec_uom": batch["custom_sec_uom"],
					"uom": details.get("stock_uom"),
					"custom_length": dimensions["custom_length"],
					"custom_thickness": dimensions["custom_thickness"],
					"custom_width": dimensions["custom_width"],
					"warehouse": warehouse,
					"custom_parent_item_group": details.get("custom_parent_item_group"),
				})

			shortage_qty = required_qty - available_qty

			# =========================
			# STEP 3: CREATE MR ONLY IF SHORTAGE
			# =========================
			if shortage_qty > 0:
				item_row = get_material_request_items(
					doc,
					details,
					None,
					company,
					ignore_existing_ordered_qty,
					include_safety_stock,
					warehouse,
					{},
					defaultdict(float),
				)

				if item_row:
					item_row["quantity"] = shortage_qty
					item_row["custom_thickness"] = dimensions["custom_thickness"]
					item_row["custom_length"] = dimensions["custom_length"]
					item_row["custom_width"] = dimensions["custom_width"]
					item_row["required_bom_qty"] = shortage_qty
					item_row["custom_parent_item_group"] = details.get("custom_parent_item_group")
					item_row["custom_unit_weight"] = details.get("custom_unit_weight")

					# Calculate NOS (sec_qty) for the shortage
					group = details.get("custom_parent_item_group")
					length = flt(dimensions.get("custom_length"))
					thickness = flt(dimensions.get("custom_thickness"))
					width = flt(dimensions.get("custom_width"))
					unit_weight = flt(details.get("custom_unit_weight"))

					if group == "Structurals" and length and unit_weight:
						denominator = (length / 1000) * unit_weight
						if denominator:
							item_row["custom_sec_qty"] = ceil(shortage_qty / denominator)
					elif group == "Plates" and length and width and thickness and unit_weight:
						denominator = (length / 1000) * (width / 1000) * thickness * unit_weight
						if denominator:
							item_row["custom_sec_qty"] = ceil(shortage_qty / denominator)
					elif group in ("Nuts and Bolts", "Fasteners") and unit_weight:
						# shortage is in Nos; sec_qty = Kg reference
						item_row["custom_sec_qty"] = shortage_qty * unit_weight

					item_row["custom_sec_uom"] = frappe.db.get_value(
						"Item", details.item_code, "custom_secondary_uom"
					)

					mr_items.append(item_row)

	return {"mr_items": mr_items, "available_raw_materials": available_rows}


def get_exploded_items(item_details, company, bom_no, include_non_stock_items, planned_qty=1, doc=None):
	# Delegate to the dimension-aware direct query so all rows with different
	# custom dimensions are kept separate (ERPNext's BOM Explosion merges rows
	# by item_code+UOM without considering custom_length/thickness/width).
	return get_bom_items_direct(item_details, company, bom_no, include_non_stock_items, planned_qty)


def get_bom_items_direct(item_details, company, bom_no, include_non_stock_items, planned_qty=1):
	"""
	Query BOM Item rows directly instead of BOM Explosion Item.

	ERPNext's explosion pre-aggregates rows by (item_code, stock_uom), ignoring
	custom dimension fields. Two rows of the same item at different lengths would
	be collapsed to one. This function preserves each row independently and merges
	only when (item_code, length, thickness, width) are truly identical.
	"""
	bi = frappe.qb.DocType("BOM Item")
	bom = frappe.qb.DocType("BOM")
	item = frappe.qb.DocType("Item")
	item_default = frappe.qb.DocType("Item Default")
	item_uom = frappe.qb.DocType("UOM Conversion Detail")

	data = (
		frappe.qb.from_(bi)
		.join(bom)
		.on(bom.name == bi.parent)
		.join(item)
		.on(item.name == bi.item_code)
		.left_join(item_default)
		.on((item_default.parent == item.name) & (item_default.company == company))
		.left_join(item_uom)
		.on((item.name == item_uom.parent) & (item_uom.uom == item.purchase_uom))
		.select(
			(bi.stock_qty / IfNull(bom.quantity, 1) * planned_qty).as_("qty"),
			item.item_name,
			item.name.as_("item_code"),
			bi.description,
			bi.stock_uom,
			item.min_order_qty,
			bi.source_warehouse,
			item.default_material_request_type,
			item_default.default_warehouse,
			item.purchase_uom,
			item_uom.conversion_factor,
			item.safety_stock,
			bom.item.as_("main_bom_item"),
			bi.custom_length,
			bi.custom_thickness,
			bi.custom_width,
			item.custom_parent_item_group,
			bi.custom_unit_weight,
		)
		.where(
			(bi.docstatus < 2)
			& (bom.name == bom_no)
			& (item.is_stock_item.isin([0, 1]) if include_non_stock_items else item.is_stock_item == 1)
		)
		# No GROUP BY — each BOM Item row is kept as-is to preserve dimension uniqueness
	).run(as_dict=True)

	for d in data:
		if not d.conversion_factor and d.purchase_uom:
			d.conversion_factor = get_uom_conversion_factor(d.item_code, d.purchase_uom)

		dim_key = (
			d.get("item_code"),
			flt(d.get("custom_length")),
			flt(d.get("custom_thickness")),
			flt(d.get("custom_width")),
		)
		if dim_key in item_details:
			# Same item at identical dimensions from a different po_item: sum qty
			item_details[dim_key]["qty"] = flt(item_details[dim_key]["qty"]) + flt(d.get("qty"))
		else:
			item_details[dim_key] = d

	return item_details


def get_uom_conversion_factor(item_code, uom):
	return frappe.db.get_value(
		"UOM Conversion Detail", {"parent": item_code, "uom": uom}, "conversion_factor"
	)


def get_warehouse_list(warehouses):
	warehouse_list = []

	if isinstance(warehouses, str):
		warehouses = json.loads(warehouses)

	for row in warehouses:
		child_warehouses = frappe.db.get_descendants("Warehouse", row.get("warehouse"))
		if child_warehouses:
			warehouse_list.extend(child_warehouses)
		else:
			warehouse_list.append(row.get("warehouse"))

	return warehouse_list


def get_material_request_items(
	doc,
	row,
	sales_order,
	company,
	ignore_existing_ordered_qty,
	include_safety_stock,
	warehouse,
	bin_dict,
	consumed_qty,
):
	required_qty = 0
	item_code = row.get("item_code")

	if ignore_existing_ordered_qty or bin_dict.get("projected_qty", 0) < 0:
		required_qty = flt(row.get("qty"))
	else:
		key = (item_code, warehouse)
		available_qty = flt(bin_dict.get("projected_qty", 0)) - consumed_qty[key]
		if available_qty > 0:
			required_qty = max(0, flt(row.get("qty")) - available_qty)
			consumed_qty[key] += min(flt(row.get("qty")), available_qty)
		else:
			required_qty = flt(row.get("qty"))

	if doc.get("consider_minimum_order_qty") and required_qty > 0 and required_qty < row["min_order_qty"]:
		required_qty = row["min_order_qty"]

	item_group_defaults = get_item_group_defaults(row.item_code, company)

	if not row["purchase_uom"]:
		row["purchase_uom"] = row["stock_uom"]

	if row["purchase_uom"] != row["stock_uom"]:
		if not (row["conversion_factor"] or frappe.flags.show_qty_in_stock_uom):
			frappe.throw(
				_("UOM Conversion factor ({0} -> {1}) not found for item: {2}").format(
					row["purchase_uom"], row["stock_uom"], row.item_code
				)
			)

			required_qty = required_qty / row["conversion_factor"]

	if frappe.db.get_value("UOM", row["purchase_uom"], "must_be_whole_number"):
		required_qty = ceil(required_qty)

	if include_safety_stock:
		required_qty += flt(row["safety_stock"])

	item_details = frappe.get_cached_value("Item", row.item_code, ["purchase_uom", "stock_uom"], as_dict=1)

	conversion_factor = 1.0
	if (
		row.get("default_material_request_type") == "Purchase"
		and item_details.purchase_uom
		and item_details.purchase_uom != item_details.stock_uom
	):
		conversion_factor = (
			get_conversion_factor(row.item_code, item_details.purchase_uom).get("conversion_factor") or 1.0
		)

	if required_qty > 0:
		return {
			"item_code": row.item_code,
			"item_name": row.item_name,
			"quantity": required_qty / conversion_factor,
			"conversion_factor": conversion_factor,
			"required_bom_qty": row.get("qty"),
			"stock_uom": row.get("stock_uom"),
			"warehouse": warehouse
			or row.get("source_warehouse")
			or row.get("default_warehouse")
			or item_group_defaults.get("default_warehouse"),
			"safety_stock": row.safety_stock,
			"actual_qty": bin_dict.get("actual_qty", 0),
			"projected_qty": bin_dict.get("projected_qty", 0),
			"ordered_qty": bin_dict.get("ordered_qty", 0),
			"reserved_qty_for_production": bin_dict.get("reserved_qty_for_production", 0),
			"min_order_qty": row["min_order_qty"],
			"material_request_type": row.get("default_material_request_type"),
			"sales_order": sales_order,
			"description": row.get("description"),
			"uom": row.get("purchase_uom") or row.get("stock_uom"),
			"main_bom_item": row.get("main_bom_item"),
		}



@frappe.whitelist()
def make_material_request(doc, submit):
	self = frappe.get_doc("Production Plan", doc)
	material_request_list = []
	material_request_map = {}

	for item in self.mr_items:
		item_doc = frappe.get_cached_doc("Item", item.item_code)

		material_request_type = item.material_request_type or item_doc.default_material_request_type

		key = "{}:{}:{}".format(item.sales_order, material_request_type, item_doc.customer or "")
		schedule_date = item.schedule_date or add_days(nowdate(), cint(item_doc.lead_time_days))

		if key not in material_request_map:
			material_request_map[key] = frappe.new_doc("Material Request")
			material_request = material_request_map[key]
			material_request.update(
				{
					"transaction_date": nowdate(),
					"status": "Draft",
					"company": self.company,
					"material_request_type": material_request_type,
					"customer": item_doc.customer or "",
				}
			)
			material_request_list.append(material_request)
		else:
			material_request = material_request_map[key]

		material_request.append(
			"items",
			{
				"item_code": item.item_code,
				"from_warehouse": item.from_warehouse
				if material_request_type == "Material Transfer"
				else None,
				"qty": item.quantity,
				"custom_length": item.custom_length,
				"custom_thickness": item.custom_thickness,
				"custom_width": item.custom_width,
				"custom_sec_qty": item.custom_sec_qty,
				"custom_sec_uom": item.custom_sec_uom,
				"schedule_date": schedule_date,
				"warehouse": item.warehouse,
				"sales_order": item.sales_order,
				"production_plan": self.name,
				"material_request_plan_item": item.name,
				"project": frappe.db.get_value("Sales Order", item.sales_order, "project")
				if item.sales_order
				else None,
			},
		)

	for material_request in material_request_list:
		material_request.flags.ignore_permissions = 1
		material_request.run_method("set_missing_values")
		material_request.save()
		if self.get("submit_material_request"):
			material_request.submit()

	frappe.flags.mute_messages = False

	if material_request_list:
		material_request_list = [
			get_link_to_form("Material Request", m.name) for m in material_request_list
		]
		frappe.msgprint(_("{0} created").format(comma_and(material_request_list)))
	else:
		frappe.msgprint(_("No material request created"))


def after_save_production_plan(doc, method):
	for row in doc.mr_items:
		_recalculate_sec_qty(row)


PLATES_REQUIRED = ["custom_length", "custom_width", "custom_thickness", "custom_unit_weight", "quantity"]


def _recalculate_sec_qty(row):
	group = row.custom_parent_item_group

	if group == "Structurals":
		if row.custom_length and row.custom_unit_weight:
			denominator = (row.custom_length / 1000) * row.custom_unit_weight
			if denominator:
				row.custom_sec_qty = row.quantity / denominator

	elif group == "Plates":
		if all(getattr(row, f, None) for f in PLATES_REQUIRED):
			denominator = (
				(row.custom_length / 1000)
				* (row.custom_width / 1000)
				* row.custom_thickness
				* row.custom_unit_weight
			)
			if denominator:
				row.custom_sec_qty = row.quantity / denominator
