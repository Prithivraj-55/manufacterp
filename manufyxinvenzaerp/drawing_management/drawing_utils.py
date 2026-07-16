import frappe
from frappe import _
from frappe.utils import flt
from manufyxinvenzaerp.utils.dimension_formula import calculate_qty


@frappe.whitelist()
def create_drawings_from_so(so_name):
    """Create one Drawing per Sales Order item. Blocks if any Drawing already exists for this SO."""
    existing = frappe.db.get_value("Drawing", {"sales_order": so_name}, "name")
    if existing:
        frappe.throw(
            _(
                "Drawings already exist for this Sales Order ({0}). "
                "Open the existing drawings from the connections panel."
            ).format(existing)
        )

    so = frappe.get_doc("Sales Order", so_name)
    created = []
    for item in so.items:
        drawing = frappe.get_doc(
            {
                "doctype": "Drawing",
                "sales_order": so_name,
                "so_item_reference": item.name,
                "customer": so.customer,
                "customer_name": so.customer_name,
                "customer_no": so.customer,
                "project": so.get("project"),
                "cust_po_no": so.get("po_no"),
                "fg_item_code": item.item_code,
                "fg_item_name": item.item_name,
                "fg_description": item.description,
                "no_of_qty_to_manufacture": item.qty,
                "status": "Working",
            }
        )
        drawing.insert(ignore_permissions=True)
        created.append(drawing.name)

    return created


@frappe.whitelist()
def mark_as_final_revision(drawing_name):
    """Set Drawing status to Final Revision. Only valid for submitted Working drawings."""
    doc = frappe.get_doc("Drawing", drawing_name)
    if doc.docstatus != 1:
        frappe.throw(_("Drawing must be submitted to mark as Final Revision."))
    if doc.status != "Working":
        frappe.throw(
            _("Cannot mark as Final Revision — current status is '{0}'.").format(doc.status)
        )
    frappe.db.set_value("Drawing", drawing_name, "status", "Final Revision")
    return "Final Revision"


@frappe.whitelist()
def get_batches_for_drawing_item(doctype, txt, searchfield, start, page_len, filters):
    """Return batches with available stock qty for a given item_code."""
    item_code = (
        filters if isinstance(filters, dict) else frappe.parse_json(filters)
    ).get("item_code")
    if not item_code:
        return []
    return frappe.db.sql(
        """
        SELECT
            b.name,
            COALESCE(SUM(sle.actual_qty), 0) AS available_qty,
            b.custom_thickness,
            b.custom_length,
            b.custom_width
        FROM `tabBatch` b
        LEFT JOIN `tabStock Ledger Entry` sle
            ON sle.batch_no = b.name
            AND sle.item_code = %s
            AND sle.is_cancelled = 0
        WHERE b.item = %s
            AND (b.name LIKE %s OR b.batch_id LIKE %s)
            AND COALESCE(b.disabled, 0) = 0
        GROUP BY b.name
        ORDER BY b.name
        LIMIT %s OFFSET %s
        """,
        (item_code, item_code, f"%{txt}%", f"%{txt}%", int(page_len), int(start)),
    )


@frappe.whitelist()
def create_bom_from_drawing(drawing_name):
    drawing = frappe.get_doc("Drawing", drawing_name)
    if drawing.docstatus != 1 or drawing.status != "Final Revision":
        frappe.throw(_("BOM can only be created from a submitted Final Revision drawing."))

    existing_bom = frappe.db.get_value(
        "BOM", {"custom_drawing": drawing_name, "docstatus": ["!=", 2]}, "name"
    )
    if existing_bom:
        frappe.msgprint(
            _("A BOM already exists for this Drawing: {0}. Creating another one.").format(existing_bom),
            indicator="orange",
        )

    company = frappe.defaults.get_user_default("Company") or frappe.db.get_single_value(
        "Global Defaults", "default_company"
    )

    bom = frappe.new_doc("BOM")
    bom.item = drawing.fg_item_code
    bom.item_name = drawing.fg_item_name
    bom.quantity = drawing.no_of_qty_to_manufacture or 1
    bom.custom_drawing = drawing_name
    bom.custom_duno_mark_no = drawing.duno_mark_no or 0
    bom.custom_customer_drawing_number = drawing.customer_drawing_number or ""
    bom.project = drawing.project or ""
    bom.company = company
    bom.currency = (
        frappe.db.get_value("Company", company, "default_currency") if company else "INR"
    )
    bom.rm_cost_as_per = "Valuation Rate"

    for d_item in drawing.items:
        bom.append(
            "items",
            {
                "item_code": d_item.material_code,
                "item_name": d_item.material_name,
                "qty": flt(d_item.total_qty) or 0,
                "uom": d_item.uom,
                "custom_item_number": d_item.item_number,
                "custom_sales_order": drawing.sales_order or "",
                "custom_material_spec": d_item.material_spec,
                "custom_unit_weight": d_item.unit_weight,
                "custom_thickness": d_item.thickness,
                "custom_length": d_item.length,
                "custom_width": d_item.width,
                "custom_sec_qty": flt(d_item.total_sec_qty),
                "custom_sec_uom": d_item.sec_uom,
                "custom_parent_item_group": d_item.parent_item_group or "",
            },
        )

    bom.insert(ignore_permissions=True)
    return bom.name


def validate_bom_from_drawing(doc, method):
    if not doc.get("custom_drawing"):
        return

    drawing = frappe.get_doc("Drawing", doc.custom_drawing)
    drawing_map = {d.item_number: d for d in drawing.items if d.item_number}
    drawing_list = list(drawing.items)

    # Guard against actual row deletion (not item_number mismatch from type migrations)
    if len(doc.items) < len(drawing.items):
        frappe.throw(
            _("Not allowed to remove items from BOM. Please maintain all items as per Drawing.")
        )

    qty_warnings = []
    for i, bom_item in enumerate(doc.items):
        d_item = drawing_map.get(bom_item.get("custom_item_number")) or (
            drawing_list[i] if i < len(drawing_list) else None
        )
        if not d_item:
            continue

        bom_item.uom = d_item.uom
        bom_item.custom_item_number = d_item.item_number
        bom_item.custom_sales_order = drawing.sales_order or ""
        bom_item.custom_parent_item_group = d_item.parent_item_group or ""
        bom_item.custom_thickness = flt(d_item.thickness)
        bom_item.custom_length = flt(d_item.length)
        bom_item.custom_width = flt(d_item.width)
        bom_item.custom_unit_weight = flt(d_item.unit_weight)
        bom_item.custom_sec_qty = flt(d_item.total_sec_qty)
        bom_item.custom_sec_uom = d_item.sec_uom or ""

        drawing_qty = flt(d_item.total_qty)
        if drawing_qty and flt(bom_item.qty) != drawing_qty:
            qty_warnings.append(
                _("Row {0}: Quantity changed from {1} to {2} — restored from Drawing.").format(
                    bom_item.idx, flt(bom_item.qty), drawing_qty
                )
            )
            bom_item.qty = drawing_qty

    if qty_warnings:
        frappe.msgprint(
            _(
                "Not allowed to edit item details in BOM level. "
                "Kindly make corrections in Drawing master.<br><br>"
            )
            + "<br>".join(qty_warnings),
            title=_("BOM Items Restored from Drawing"),
            indicator="orange",
        )


@frappe.whitelist()
def create_production_plan_from_bom(bom_name):
    bom = frappe.get_doc("BOM", bom_name)
    if bom.docstatus != 1:
        frappe.throw(_("BOM must be submitted to create a Production Plan."))
    if not bom.get("custom_drawing"):
        frappe.throw(_("Production Plan creation is only available for BOMs linked to a Drawing."))

    stock_uom = frappe.db.get_value("Item", bom.item, "stock_uom") or ""

    pp = frappe.new_doc("Production Plan")
    pp.company = bom.company
    pp.posting_date = frappe.utils.today()
    pp.get_items_from = ""

    pp.append(
        "po_items",
        {
            "item_code": bom.item,
            "bom_no": bom_name,
            "planned_qty": flt(bom.quantity) or 1,
            "planned_start_date": frappe.utils.now_datetime(),
            "stock_uom": stock_uom,
            "custom_drawing": bom.get("custom_drawing") or "",
            "custom_duno_mark_no": bom.get("custom_duno_mark_no") or 0,
        },
    )

    # Auto-populate Process Planning from BOM routing or BOM operations
    operations = []
    if bom.routing:
        operations = frappe.get_all(
            "BOM Operation",
            filters={"parent": bom.routing, "parenttype": "Routing"},
            fields=["operation", "sequence_id"],
            order_by="sequence_id asc",
        )
    elif bom.with_operations and bom.operations:
        operations = [
            {"operation": op.operation, "sequence_id": op.sequence_id}
            for op in sorted(bom.operations, key=lambda o: o.sequence_id or 0)
        ]

    for op in operations:
        pp.append("custom_process_planning", {
            "operation_name": op.get("operation"),
            "work_type": "Internal Jobcard",
        })

    pp.insert(ignore_permissions=True)
    return pp.name


@frappe.whitelist()
def parse_drawing_items_csv(csv_content):
	"""Parse CSV text and return processed Drawing Item rows.

	Expected columns (order-independent, case-insensitive):
	  item_number, material_code, sec_qty, thickness, length, width

	Fetches item master data and calculates qty server-side so the client
	only needs to set_value on each child row.
	"""
	import csv as csv_module
	import io

	if not csv_content or not csv_content.strip():
		frappe.throw(_("The uploaded CSV file is empty."))

	# Strip BOM character that Excel sometimes adds
	csv_content = csv_content.lstrip("﻿")

	reader = csv_module.DictReader(io.StringIO(csv_content))

	# Normalise headers: lowercase + strip whitespace so both "material_code"
	# and "Material Code" (or "item_code" from PO-style CSVs) are accepted.
	if not reader.fieldnames:
		frappe.throw(_("CSV file has no header row."))

	normalised_headers = {h.strip().lower(): h for h in reader.fieldnames}

	def _col(row, *candidates):
		"""Return value of first matching column (case-insensitive)."""
		for c in candidates:
			orig = normalised_headers.get(c.lower())
			if orig and orig in row:
				val = (row[orig] or "").strip()
				if val:
					return val
		return ""

	rows = []
	errors = []
	auto_number = 1

	for line_no, row in enumerate(reader, start=2):
		material_code = _col(row, "material_code", "item_code")
		if not material_code:
			continue  # blank rows are silently skipped

		if not frappe.db.exists("Item", material_code):
			errors.append(_("Row {0}: Item <b>{1}</b> not found.").format(line_no, material_code))
			continue

		item_data = frappe.db.get_value(
			"Item",
			material_code,
			[
				"item_name", "item_group", "description",
				"custom_material_spec", "custom_unit_weight",
				"custom_secondary_uom", "custom_parent_item_group", "stock_uom",
			],
			as_dict=True,
		) or {}

		def _flt(val):
			try:
				return flt(str(val).strip().replace(",", ""))
			except Exception:
				return 0.0

		raw_item_number = _col(row, "item_number", "item no", "item no.")
		item_number = str(raw_item_number).strip() if raw_item_number else str(auto_number)
		sec_qty   = _flt(_col(row, "sec_qty",   "sec qty",   "custom_sec_qty"))
		thickness = _flt(_col(row, "thickness",  "thickness (mm)", "custom_thickness"))
		length    = _flt(_col(row, "length",     "length (mm)",    "custom_length"))
		width     = _flt(_col(row, "width",      "width (mm)",     "custom_width"))

		unit_weight        = flt(item_data.get("custom_unit_weight"))
		parent_item_group  = (item_data.get("custom_parent_item_group") or "").strip()

		# Calculate primary qty using the same formula as drawing.py
		qty = 0.0
		if parent_item_group in ("Structurals", "Plates"):
			calc = calculate_qty(parent_item_group, length, width, thickness, unit_weight, sec_qty)
			if calc is not None:
				qty = calc

		rows.append({
			"item_number":           item_number,
			"material_code":         material_code,
			"material_name":         item_data.get("item_name") or "",
			"item_group":            item_data.get("item_group") or "",
			"parent_item_group":     parent_item_group,
			"raw_material_description": item_data.get("description") or "",
			"material_spec":         item_data.get("custom_material_spec") or "",
			"unit_weight":           unit_weight,
			"thickness":             thickness,
			"length":                length,
			"width":                 width,
			"sec_qty":               sec_qty,
			"sec_uom":               item_data.get("custom_secondary_uom") or "",
			"qty":                   flt(qty, 3),
			"uom":                   item_data.get("stock_uom") or "",
		})
		auto_number += 1

	if errors:
		frappe.throw("<br>".join(errors), title=_("CSV Upload Errors"))

	if not rows:
		frappe.throw(_("No valid item rows found in the CSV file."))

	return rows


def get_so_dashboard_data(data):
    """Extend Sales Order dashboard to include Drawing connections."""
    from frappe import _

    data["transactions"].append({"label": _("Drawing"), "items": ["Drawing"]})
    return data


#####################
