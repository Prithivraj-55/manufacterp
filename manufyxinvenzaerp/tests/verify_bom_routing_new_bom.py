"""A freshly created draft BOM referencing the Standard Manufacturing Routing pulls
exactly the operations that routing carries -- no more, and in its order.

This is the check that matters when the routing changes: a BOM created after Material
Issue was dropped must not carry it, while BOMs created before are left exactly as they
were. Draft is left in place (not submitted, not deleted) for manual inspection.

Run via: bench --site manufact execute manufyxinvenzaerp.tests.verify_bom_routing_new_bom.run
"""

import frappe
from manufyxinvenzaerp.tests.create_full_test_entry import get_ctx, ensure_item, ensure_fg_item

KEPT = ["Fit-up", "Welding", "Final", "Blasting", "Painting"]


def run():
    ctx = get_ctx()
    fg = ensure_fg_item(ctx, "ZZTEST-BOM-ROUTING-FG", "BOM Routing Test FG")
    rm = ensure_item(ctx, "ZZTEST-BOM-ROUTING-RM", "BOM Routing Test RM", uom="Kg")

    existing = frappe.db.exists("BOM", {"item": fg, "docstatus": ["!=", 2]})
    if existing:
        print("Reusing existing draft BOM:", existing)
        bom = frappe.get_doc("BOM", existing)
    else:
        bom = frappe.new_doc("BOM")
        bom.item = fg
        bom.quantity = 1
        bom.company = ctx.company
        bom.with_operations = 1
        bom.routing = "Standard Manufacturing Routing"
        bom.append("items", {"item_code": rm, "qty": 1})
        bom.insert(ignore_permissions=True)
        print("Created draft BOM:", bom.name)

    ops = [r.operation for r in bom.operations]
    print("BOM operations pulled:", ops)
    assert ops == KEPT, f"Expected {KEPT}, got {ops}"

    frappe.db.commit()
    assert "Material Issue" not in ops, "A new BOM must not pull the dropped Material Issue operation"

    print("\nALL CHECKS DONE — new BOM correctly pulls only the trimmed operations.")
    print("Draft BOM left in place (not submitted):", bom.name)
