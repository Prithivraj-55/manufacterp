import frappe
from frappe import _
from manufyxinvenzaerp.utils.dimension_formula import (
    calculate_qty,
    calculate_sec_qty_from_qty,
    check_missing_fields,
)


@frappe.whitelist()
def get_mr_item_uom(doctype, txt, searchfield, start, page_len, filters):
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


def validate_material_request(doc, method):
    for row in doc.items:
        _recalculate_qty(row)
        _check_missing_fields(row, throw=False)


def before_submit_material_request(doc, method):
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
