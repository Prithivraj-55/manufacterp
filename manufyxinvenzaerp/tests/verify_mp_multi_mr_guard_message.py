"""Verify the backlog fix logged during the multi-supplier consolidated-purchase
work: Material Planning's "already have an active Material Request" guard
(inside make_material_request) now lists ALL linked, active Material Requests
in its error message, not just the first one found -- relevant now that a
single Material Planning can have more than one Material Request linked
(one per supplier, via the separate manual multi-supplier MR flow).

The companion JS fix (material_planning.js's "Refetch Raw Materials" guard,
_check_mr_then_confirm) is not covered here since it's client-side only --
verified live in the browser instead.

Run via: bench --site manufact execute manufyxinvenzaerp.tests.verify_mp_multi_mr_guard_message.run
"""

import frappe
from frappe.utils import today
from manufyxinvenzaerp.tests.create_full_test_entry import get_ctx, ensure_item


def run():
    ctx = get_ctx()
    item = ensure_item(ctx, "ZZTEST-MULTI-MR-GUARD", "Multi MR Guard Test Item", uom="Kg")
    frappe.db.set_value("Item", item, "custom_parent_item_group", "Structurals")
    frappe.db.set_value("Item", item, "custom_unit_weight", 10)

    mp = frappe.new_doc("Material Planning")
    mp.company = ctx.company
    mp.posting_date = today()
    mp.for_warehouse = ctx.warehouse
    mp.append("unavailable_items", {
        "item_code": item, "item_name": "Multi MR Guard Test Item",
        "parent_item_group": "Structurals", "unit_weight": 10,
        "qty": 50, "uom": "Kg", "sec_qty": 1, "sec_uom": "Nos",
        "duno_mark_no": "DUNO-MULTI-MR-1",
    })
    mp.insert(ignore_permissions=True)
    print("Created MP:", mp.name)

    # Simulate the multi-supplier manual flow: TWO separate Material Requests
    # both linked to this same Material Planning via custom_material_planning
    # (the editable field exposed earlier this session for exactly this case).
    warehouse = ctx.warehouse
    mr_names = []
    for i in range(2):
        mr = frappe.new_doc("Material Request")
        mr.material_request_type = "Purchase"
        mr.company = ctx.company
        mr.transaction_date = today()
        mr.custom_material_planning = mp.name
        mr.append("items", {
            "item_code": item, "qty": 25, "uom": "Kg", "schedule_date": today(),
            "warehouse": warehouse,
        })
        mr.insert(ignore_permissions=True)
        mr_names.append(mr.name)
    print("Created 2 Material Requests linked to the same MP:", mr_names)

    from manufyxinvenzaerp.production_management.doctype.material_planning.material_planning import (
        make_material_request,
    )
    import json as _json

    threw = False
    message = ""
    try:
        make_material_request(mp.name, _json.dumps([item]))
    except frappe.ValidationError as e:
        threw = True
        message = str(e)

    print("Throws when active MRs already exist (expect True):", threw)
    print("Message:", message)
    assert threw, "Expected make_material_request to throw when active MRs already exist"
    for mr_name in mr_names:
        assert mr_name in message, f"Expected {mr_name} to be listed in the guard message, got: {message}"
    assert "2 active Material Request" in message, f"Expected the message to state the count (2), got: {message}"

    frappe.db.commit()
    print("\nALL CHECKS DONE — make_material_request's guard now lists ALL active Material Requests "
          "linked to the plan, not just the first one found.")
    print("Test data left in place:", mp.name, mr_names)
