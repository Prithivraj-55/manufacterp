import re
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
def get_pr_item_uom(doctype, txt, searchfield, start, page_len, filters):
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


def validate_purchase_receipt(doc, method):
    for row in doc.items:
        _copy_from_po_item(row)
        _recalculate_qty(row)
        _check_missing_fields(row, throw=False)


def before_submit_purchase_receipt(doc, method):
    for row in doc.items:
        _check_missing_fields(row, throw=True)


def before_insert_batch(doc, method):
    """Set custom batch name and store dimensions when batch is auto-created from Purchase Receipt."""
    if doc.reference_doctype != "Purchase Receipt" or not doc.reference_name:
        return

    pr_item = frappe.db.get_value(
        "Purchase Receipt Item",
        {"parent": doc.reference_name, "item_code": doc.item},
        ["custom_thickness", "custom_length", "custom_width", "custom_sec_qty", "custom_sec_uom"],
        as_dict=True,
    )
    if not pr_item:
        return

    batch_prefix = frappe.db.get_value("Item", doc.item, "custom_batch_prefix")
    if not batch_prefix:
        return

    receipt_suffix = _get_receipt_suffix(doc.reference_name)
    parts = [batch_prefix]
    if pr_item.custom_thickness:
        parts.append(f"T{int(pr_item.custom_thickness)}")
    if pr_item.custom_length:
        parts.append(f"L{int(pr_item.custom_length)}")
    if pr_item.custom_width:
        parts.append(f"W{int(pr_item.custom_width)}")
    parts.append(f"R{receipt_suffix}")

    batch_id = "-".join(parts)

    counter = 1
    base_id = batch_id
    while frappe.db.exists("Batch", batch_id):
        counter += 1
        batch_id = f"{base_id}-{counter}"

    doc.batch_id = batch_id
    doc.custom_thickness = pr_item.custom_thickness
    doc.custom_length = pr_item.custom_length
    doc.custom_width = pr_item.custom_width
    doc.custom_sec_qty = pr_item.custom_sec_qty
    doc.custom_sec_uom = pr_item.custom_sec_uom


def _get_receipt_suffix(pr_name):
    """Extract last 3 digits from the numeric part of a receipt name (e.g. MAT-PRE-2024-00010 → '010')."""
    match = re.search(r"(\d+)$", pr_name)
    if match:
        return match.group(1)[-3:].zfill(3)
    return pr_name[-3:] if pr_name else "000"


def _copy_from_po_item(row):
    """Copy dimension fields from the linked PO Item when a PR is created from a PO."""
    if not row.purchase_order_item:
        return
    if row.custom_length or row.custom_width or row.custom_thickness or row.custom_sec_qty:
        return
    po_item = frappe.db.get_value(
        "Purchase Order Item",
        row.purchase_order_item,
        ["custom_length", "custom_width", "custom_thickness", "custom_sec_qty"],
        as_dict=True,
    )
    if not po_item:
        return
    row.custom_length = po_item.custom_length
    row.custom_width = po_item.custom_width
    row.custom_thickness = po_item.custom_thickness
    row.custom_sec_qty = po_item.custom_sec_qty


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
