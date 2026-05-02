import frappe
from frappe import _
from frappe.utils import flt


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
    bom.company = company
    bom.currency = (
        frappe.db.get_value("Company", company, "default_currency") if company else "INR"
    )

    for d_item in drawing.items:
        bom.append(
            "items",
            {
                "item_code": d_item.material_code,
                "item_name": d_item.material_name,
                "qty": flt(d_item.qty) or 0,
                "uom": d_item.uom,
                "rate": flt(d_item.rate) or 0,
                "custom_item_number": d_item.item_number,
                "custom_material_spec": d_item.material_spec,
                "custom_unit_weight": d_item.unit_weight,
                "custom_thickness": d_item.thickness,
                "custom_length": d_item.length,
                "custom_width": d_item.width,
                "custom_sec_qty": d_item.sec_qty,
                "custom_sec_uom": d_item.sec_uom,
            },
        )

    bom.insert(ignore_permissions=True)
    return bom.name


def validate_bom_from_drawing(doc, method):
    if not doc.get("custom_drawing"):
        return

    drawing = frappe.get_doc("Drawing", doc.custom_drawing)
    drawing_map = {(d.item_number or 0): d for d in drawing.items}
    drawing_list = list(drawing.items)
    conversion_rate = flt(doc.conversion_rate) or 1

    qty_warnings = []
    for i, bom_item in enumerate(doc.items):
        d_item = drawing_map.get(bom_item.get("custom_item_number")) or (
            drawing_list[i] if i < len(drawing_list) else None
        )
        if not d_item:
            continue

        # Restore rate from Drawing — must happen AFTER calculate_rm_cost() runs in
        # ERPNext's validate, which blindly overwrites rates for stock items based on
        # rm_cost_as_per. We never call calculate_cost() here to avoid re-triggering that.
        bom_item.rate = flt(d_item.rate) or 0
        bom_item.base_rate = flt(bom_item.rate) * conversion_rate

        if flt(bom_item.qty) != flt(d_item.qty):
            qty_warnings.append(
                _("Row {0}: Quantity changed from {1} to {2} — restored from Drawing.").format(
                    bom_item.idx, d_item.qty, bom_item.qty
                )
            )
            bom_item.qty = flt(d_item.qty) or 0

        bom_item.amount = flt(bom_item.qty) * flt(bom_item.rate)
        bom_item.base_amount = flt(bom_item.amount) * conversion_rate

    # Recalculate BOM header totals from restored item amounts without calling
    # calculate_cost(), which would re-run calculate_rm_cost() and override rates again.
    raw_material_cost = sum(flt(item.amount) for item in doc.items)
    doc.raw_material_cost = flt(raw_material_cost, 2)
    doc.base_raw_material_cost = flt(raw_material_cost * conversion_rate, 2)
    doc.total_cost = flt(flt(doc.operating_cost) + raw_material_cost - flt(doc.scrap_material_cost), 2)
    doc.base_total_cost = flt(
        flt(doc.base_operating_cost) + doc.base_raw_material_cost - flt(doc.base_scrap_material_cost), 2
    )

    # Validate BOM raw material total matches Drawing total
    drawing_total = flt(drawing.total_raw_material_cost, 2)
    bom_total = flt(doc.raw_material_cost, 2)
    if drawing_total and abs(bom_total - drawing_total) > 0.01:
        frappe.msgprint(
            _(
                "Raw material value is not matching — BOM total ({0}) does not match "
                "Drawing total ({1}). Kindly check with system admin to verify the rates."
            ).format(frappe.format(bom_total, {"fieldtype": "Currency"}),
                     frappe.format(drawing_total, {"fieldtype": "Currency"})),
            title=_("Raw Material Cost Mismatch"),
            indicator="orange",
        )

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


def get_so_dashboard_data(data):
    """Extend Sales Order dashboard to include Drawing connections."""
    from frappe import _

    data["transactions"].append({"label": _("Drawing"), "items": ["Drawing"]})
    return data
