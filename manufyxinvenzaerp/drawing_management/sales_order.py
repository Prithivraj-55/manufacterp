import frappe
from frappe import _


def on_submit_sales_order(doc, method):
    """Auto-create one Drawing per DUNO/Mark No row when Is Production Order is enabled."""
    if not doc.get("custom_is_production_order"):
        return

    if not doc.get("custom_duno_items"):
        frappe.throw(
            _("DUNO/Mark No table is empty. Please add item rows before submitting a Production Order.")
        )

    created = []
    for row in doc.custom_duno_items:
        item_data = frappe.db.get_value(
            "Item", row.item, ["item_name", "description"], as_dict=True
        ) or {}

        drawing = frappe.get_doc({
            "doctype": "Drawing",
            "sales_order": doc.name,
            "customer": doc.customer,
            "customer_name": doc.customer_name,
            "customer_no": doc.customer,
            "project": doc.get("project"),
            "cust_po_no": doc.get("po_no"),
            "fg_item_code": row.item,
            "fg_item_name": item_data.get("item_name") or "",
            "fg_description": item_data.get("description") or "",
            "no_of_qty_to_manufacture": row.total_quantity,
            "duno_mark_no": row.duno_mark_no,
            "status": "Working",
        })
        drawing.insert(ignore_permissions=True)
        created.append(drawing.name)

    links = "".join(
        '<li><a href="/app/drawing/{0}" target="_blank">{0}</a></li>'.format(name)
        for name in created
    )
    frappe.msgprint(
        _("{0} Drawing(s) created:<ul>{1}</ul>").format(len(created), links),
        title=_("Drawings Created"),
        indicator="green",
    )
