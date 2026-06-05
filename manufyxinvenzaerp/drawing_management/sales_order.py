import frappe
from frappe.utils import flt


def recalculate_raw_material_qty(doc, method):
    """Recalculate qty, total_sec_qty and total_weight on unlocked raw material rows."""
    # Build lookup: drawing_number → total_quantity from the Drawing List table
    total_qty_map = {}
    for dr in (doc.custom_duno_items or []):
        if dr.drawing_number:
            total_qty_map[dr.drawing_number] = flt(dr.total_quantity) or 1.0

    for row in (doc.custom_so_raw_materials or []):
        if row.is_locked:
            continue
        pig = row.parent_item_group or ""
        unit_wt = flt(row.unit_weight)
        length = flt(row.length)
        width = flt(row.width)
        thickness = flt(row.thickness)
        sec_qty = flt(row.sec_qty)
        tq = total_qty_map.get(row.customer_drawing_number, 1.0)

        qty = 0.0
        if pig == "Structurals":
            if length and unit_wt and sec_qty:
                qty = (length / 1000.0) * unit_wt * sec_qty
        elif pig == "Plates":
            if length and width and thickness and unit_wt and sec_qty:
                qty = (length / 1000.0) * (width / 1000.0) * thickness * unit_wt * sec_qty
        else:
            qty = sec_qty

        row.qty = flt(qty, 3)
        row.total_sec_qty = flt(sec_qty * tq, 3)
        row.total_weight = flt(qty * tq, 3)
