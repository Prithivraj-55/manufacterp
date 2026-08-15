"""Fill Drawing.type from its own Rate Schedule where it was left blank.

Type and Rate Schedule describe the same thing from two directions: on the form, Type
narrows the picker when a schedule is chosen by hand. A BOM import sets the schedule
directly, so Type was never filled -- the field showed blank on every imported drawing,
and the picker then filtered on an empty Type and offered nothing.

Both sides now keep it in step (so_drawing_import sets it on creation, and the form
mirrors it when a schedule is selected). This backfills the drawings created before
that, reading the value from the schedule each one already points at, so it cannot
invent anything: a drawing with no schedule, or one whose schedule has no type, is left
alone.

Submitted drawings are updated too, deliberately. Type is a descriptive field with no
bearing on stock, weight or costing -- leaving it blank on historical drawings would
keep the gap visible forever with no way to correct it.
"""

import frappe


def execute():
    rows = frappe.db.sql(
        """
        SELECT d.name, rs.type
        FROM `tabDrawing` d
        JOIN `tabRate Schedule` rs ON rs.name = d.rate_schedule
        WHERE d.rate_schedule IS NOT NULL AND d.rate_schedule != ''
          AND (d.type IS NULL OR d.type = '')
          AND rs.type IS NOT NULL AND rs.type != ''
        """,
        as_dict=True,
    )
    if not rows:
        return

    for row in rows:
        frappe.db.set_value("Drawing", row.name, "type", row.type, update_modified=False)

    frappe.db.commit()
    frappe.logger().info(
        "backfill_drawing_rate_schedule_type: set Type on %d drawing(s)" % len(rows)
    )
