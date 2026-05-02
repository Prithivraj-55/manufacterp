import frappe
from frappe import _


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


def get_so_dashboard_data(data):
    """Extend Sales Order dashboard to include Drawing connections."""
    from frappe import _

    data["transactions"].append({"label": _("Drawing"), "items": ["Drawing"]})
    return data
