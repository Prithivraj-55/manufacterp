"""Customer weight downstream is for the whole row, not for one piece.

The Sales Order DUNO row holds customer weight per piece, beside a Total Quantity of
its own. Every planned and transferred weight downstream is for the whole row. The
per-piece figure was being copied straight through, so a drawing making two pieces
reported 890 Kg of customer weight against 1,814 Kg planned -- which reads as 100%
waste next to the single-piece drawing beside it reading 1.9%.

Both write paths are fixed (the Production Plan picker and Update Customer Weight's
cascade). This repairs the rows already written, on every site the app is installed on.

Rows for a drawing making one piece are already right and are left alone -- which is
most of them, and is why the fault went unseen for so long.
"""

import frappe
from frappe.utils import flt


def execute():
    qty_by_drawing = {
        d.name: flt(d.no_of_qty_to_manufacture) or 1
        for d in frappe.get_all("Drawing", fields=["name", "no_of_qty_to_manufacture"])
    }
    multi = {d for d, q in qty_by_drawing.items() if q > 1}
    if not multi:
        return

    wt_by_drawing = {
        d.name: flt(d.customer_provided_wt)
        for d in frappe.get_all("Drawing", filters={"name": ["in", list(multi)]},
                                fields=["name", "customer_provided_wt"])
    }

    touched_scos, touched_mips = set(), set()

    for row in frappe.get_all("Production Plan Item",
                              filters={"custom_drawing": ["in", list(multi)]},
                              fields=["name", "custom_drawing", "custom_customer_weight_kg"]):
        _fix("Production Plan Item", row.name, "custom_customer_weight_kg",
             row.custom_customer_weight_kg, wt_by_drawing, qty_by_drawing, row.custom_drawing)

    for row in frappe.get_all(
        "SCO Drawing Item",
        filters={"drawing": ["in", list(multi)],
                 "parenttype": ["in", ["Subcontracting Order", "Material Issue Plan"]]},
        fields=["name", "drawing", "parent", "parenttype", "customer_weight_kg"],
    ):
        if _fix("SCO Drawing Item", row.name, "customer_weight_kg", row.customer_weight_kg,
                wt_by_drawing, qty_by_drawing, row.drawing):
            (touched_scos if row.parenttype == "Subcontracting Order" else touched_mips).add(row.parent)

    for row in frappe.get_all(
        "SOE Drawing Detail", filters={"drawing": ["in", list(multi)]},
        fields=["name", "drawing", "customer_provided_weight_kg"],
    ):
        _fix("SOE Drawing Detail", row.name, "customer_provided_weight_kg",
             row.customer_provided_weight_kg, wt_by_drawing, qty_by_drawing, row.drawing)

    # The Job Work Order header is the sum of its rows, so it has to be re-added rather
    # than scaled -- some of its rows were already right.
    for sco in touched_scos:
        total = frappe.db.sql(
            "select sum(customer_weight_kg) from `tabSCO Drawing Item` "
            "where parenttype='Subcontracting Order' and parent=%s", (sco,))[0][0]
        frappe.db.set_value("Subcontracting Order", sco, "custom_customer_weight_kg",
                            flt(total, 3), update_modified=False)

    if touched_scos or touched_mips:
        frappe.db.commit()


def _fix(doctype, name, fieldname, current, wt_by_drawing, qty_by_drawing, drawing):
    """Scale a row, unless it looks like it has already been scaled.

    Matched against the drawing's own per-piece weight rather than blindly multiplied,
    so running this twice cannot double anything: a row already holding per-piece times
    quantity is left exactly as it is."""
    per_piece = flt(wt_by_drawing.get(drawing))
    if not per_piece:
        return False
    if flt(current, 2) != flt(per_piece, 2):
        return False
    frappe.db.set_value(doctype, name, fieldname,
                        flt(per_piece * qty_by_drawing[drawing], 3), update_modified=False)
    return True
