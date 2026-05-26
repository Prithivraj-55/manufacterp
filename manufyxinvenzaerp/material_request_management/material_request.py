import frappe
from frappe import _

STRUCTURALS_REQUIRED = ["custom_length", "custom_unit_weight", "custom_sec_qty"]
PLATES_REQUIRED = ["custom_length", "custom_width", "custom_thickness", "custom_unit_weight", "custom_sec_qty"]
FIELD_LABELS = {
    "custom_length": "Length",
    "custom_width": "Width",
    "custom_thickness": "Thickness",
    "custom_unit_weight": "Unit Weight",
    "custom_sec_qty": "Sec Qty",
}


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
    if group == "Structurals":
        if row.custom_length and row.custom_unit_weight and row.custom_sec_qty:
            row.qty = (row.custom_length / 1000) * row.custom_unit_weight * row.custom_sec_qty
    elif group == "Plates":
        if all(getattr(row, f, None) for f in PLATES_REQUIRED):
            row.qty = (
                (row.custom_length / 1000)
                * (row.custom_width / 1000)
                * row.custom_thickness
                * row.custom_unit_weight
                * row.custom_sec_qty
            )
    elif group == "Nuts and Bolts":
        if row.qty and row.custom_unit_weight:
            row.custom_sec_qty = row.qty * row.custom_unit_weight


def _check_missing_fields(row, throw):
    group = row.custom_parent_item_group
    if group == "Structurals":
        required = STRUCTURALS_REQUIRED
    elif group == "Plates":
        required = PLATES_REQUIRED
    else:
        return
    missing = [FIELD_LABELS[f] for f in required if not getattr(row, f, None)]
    if missing:
        msg = _("Row {0}: {1} required for {2} formula").format(
            row.idx, ", ".join(missing), group
        )
        if throw:
            frappe.throw(msg)
        else:
            frappe.msgprint(msg, indicator="orange", title=_("Missing Fields"))
