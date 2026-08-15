import frappe
from frappe.utils import flt
from manufyxinvenzaerp.utils.dimension_formula import calculate_qty


def drawing_calculated_weight(rows, drawing_number):
    """What the raw materials listed under one drawing weigh in total.

    The counterpart to the drawing's Customer Provided Weight, which is typed in
    from the sheet and describes the FINISHED piece. This one is never typed:
    it is the sum of the rows' own calculated weights, and it is normally the
    larger of the two because stock is cut down to the part. A drawing where it
    comes out SMALLER is the case worth looking at -- the material listed cannot
    produce the piece.
    """
    return flt(sum(
        flt(r.get("qty")) for r in (rows or [])
        if r.get("customer_drawing_number") == drawing_number
    ), 3)


def recalculate_raw_material_qty(doc, method):
    """Recalculate qty, total_sec_qty and total_weight on unlocked raw material rows."""
    # Build lookup: drawing_number → total_quantity from the Drawing List table
    total_qty_map = {}
    for dr in (doc.custom_duno_items or []):
        if dr.drawing_number:
            total_qty_map[dr.drawing_number] = flt(dr.total_quantity) or 1.0

    for row in (doc.custom_so_raw_materials or []):
        # row.get("is_locked"), never row.is_locked: frappe's Document class
        # defines is_locked as a property (it reports whether a FILE LOCK is
        # held on the document), and a class property shadows the field of the
        # same name on every instance. The attribute therefore always reads
        # False no matter what the column holds, so this loop was recalculating
        # locked rows too -- rewriting rows a Drawing had already been built
        # from whenever the Sales Order was saved. .get() reads the row's own
        # data and returns the stored value.
        if row.get("is_locked"):
            continue
        pig = row.parent_item_group or ""
        unit_wt = flt(row.unit_weight)
        length = flt(row.length)
        width = flt(row.width)
        thickness = flt(row.thickness)
        sec_qty = flt(row.sec_qty)
        tq = total_qty_map.get(row.customer_drawing_number, 1.0)

        if pig in ("Structurals", "Plates"):
            qty = calculate_qty(pig, length, width, thickness, unit_wt, sec_qty)
            qty = qty if qty is not None else 0.0
        else:
            qty = sec_qty

        row.qty = flt(qty, 3)
        row.total_sec_qty = flt(sec_qty * tq, 3)
        row.total_weight = flt(qty * tq, 3)

    # Roll the row weights up onto each drawing. Done after the loop so it picks
    # up the values just recalculated, and for locked drawings too -- their rows
    # are frozen, so the total simply restates what is already there.
    for dr in (doc.custom_duno_items or []):
        if dr.drawing_number:
            dr.calculated_weight = drawing_calculated_weight(
                doc.custom_so_raw_materials, dr.drawing_number
            )
