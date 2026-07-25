import frappe
from frappe import _
from manufyxinvenzaerp.utils.dimension_formula import calculate_qty, calculate_sec_qty_from_qty, check_missing_fields
from manufyxinvenzaerp.utils.reference_copy import copy_reference_fields_if_blank

REFERENCE_FIELDS = ["custom_drawing", "custom_duno_mark_no", "custom_customer_drawing_number", "custom_sales_order"]


@frappe.whitelist()
def get_po_item_uom(doctype, txt, searchfield, start, page_len, filters):
    item_code = (filters if isinstance(filters, dict) else frappe.parse_json(filters)).get("item_code")
    if not item_code:
        return []
    return frappe.db.sql(
        """
        SELECT uom FROM `tabUOM Conversion Detail`
        WHERE parent = %s AND uom LIKE %s
        UNION
        SELECT stock_uom FROM `tabItem` WHERE name = %s AND stock_uom LIKE %s
        LIMIT %s
        """,
        (item_code, f"%{txt}%", item_code, f"%{txt}%", int(page_len)),
    )


def validate_purchase_order(doc, method):
    for row in doc.items:
        _copy_from_mr_item(row)
        _recalculate_qty(row)
        _check_missing_fields(row, throw=False)
    doc.custom_total_weight = sum(
        row.qty for row in doc.items
        if row.custom_parent_item_group in ("Structurals", "Plates")
    )


def _copy_from_mr_item(row):
    """Copy drawing/DUNO/sales order references from the linked MR Item when a PO is created from a Material Request."""
    copy_reference_fields_if_blank(row, "Material Request Item", "material_request_item", REFERENCE_FIELDS)


def before_submit_purchase_order(doc, method):
    for row in doc.items:
        _check_missing_fields(row, throw=True)


def _recalculate_qty(row):
    group = row.custom_parent_item_group
    if group in ("Structurals", "Plates"):
        qty = calculate_qty(
            group, row.custom_length, row.custom_width, row.custom_thickness,
            row.custom_unit_weight, row.custom_sec_qty,
        )
        if qty is not None:
            row.qty = qty
    elif group == "Nuts and Bolts":
        sec_qty = calculate_sec_qty_from_qty(row.custom_unit_weight, row.qty)
        if sec_qty is not None:
            row.custom_sec_qty = sec_qty


def _check_missing_fields(row, throw):
    check_missing_fields(row, throw)
