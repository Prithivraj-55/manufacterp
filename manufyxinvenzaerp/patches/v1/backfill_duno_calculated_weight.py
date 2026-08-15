"""Fill Calculated Weight on Sales Order DUNO Item rows loaded before the field existed.

The field states what the raw materials listed under a drawing add up to, next to
the Customer Provided Weight typed in from the sheet. New imports write it, and
every save recomputes it, but rows already staged -- including those on submitted
orders -- would show a blank until someone happened to save the order again.

Computed from the staged raw-material rows themselves, so it invents nothing: a
drawing with no rows, or rows that have never been costed, is left at zero. The
field is read-only and descriptive, with no bearing on stock, weight cascades or
costing, which is why submitted orders are filled too.
"""

import frappe


def execute():
    if not frappe.db.has_column("Sales Order DUNO Item", "calculated_weight"):
        return

    rows = frappe.db.sql(
        """
        SELECT d.name, COALESCE(SUM(rm.qty), 0) AS calc
        FROM `tabSales Order DUNO Item` d
        LEFT JOIN `tabSales Order Drawing Raw Material` rm
               ON rm.parent = d.parent
              AND rm.parenttype = 'Sales Order'
              AND rm.customer_drawing_number = d.drawing_number
        WHERE d.parenttype = 'Sales Order'
          AND d.drawing_number IS NOT NULL AND d.drawing_number != ''
          AND (d.calculated_weight IS NULL OR d.calculated_weight = 0)
        GROUP BY d.name
        HAVING calc > 0
        """,
        as_dict=True,
    )
    if not rows:
        return

    for row in rows:
        frappe.db.set_value(
            "Sales Order DUNO Item", row.name, "calculated_weight",
            round(row.calc, 3), update_modified=False,
        )

    frappe.db.commit()
    frappe.logger().info(
        "backfill_duno_calculated_weight: filled %d drawing row(s)" % len(rows)
    )
