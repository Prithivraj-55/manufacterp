"""Confirm Material Planning Consolidate Item's Sec Qty is never auto-populated
from the source Unavailable Item rows during consolidation (stays blank/0 even
when the source rows carry a nonzero sec_qty), remains freely user-editable, and
that Purchase Kg is correctly computed from whatever Sec Qty the user manually
enters (server-side recalculate(), same formula the client-side live handler in
material_planning.js's _recalc_consolidate_item uses).

Run via: bench --site manufact execute manufyxinvenzaerp.tests.verify_consolidate_sec_qty_editable.run
"""

import frappe
from frappe.utils import flt
from manufyxinvenzaerp.tests.create_full_test_entry import get_ctx, ensure_item


def run():
    ctx = get_ctx()
    item = ensure_item(ctx, "ZZTEST-CONSOL-SECQTY", "Consolidate Sec Qty Test Item", uom="Kg")
    frappe.db.set_value("Item", item, "custom_parent_item_group", "Structurals")
    frappe.db.set_value("Item", item, "custom_unit_weight", 10)

    mp = frappe.new_doc("Material Planning")
    mp.company = ctx.company
    mp.posting_date = frappe.utils.today()
    mp.for_warehouse = ctx.warehouse

    # Source Unavailable Item row carries a nonzero sec_qty of its own (5 Nos) --
    # this must NOT leak into the Consolidate Item row's sec_qty.
    mp.append("unavailable_items", {
        "item_code": item, "item_name": "Consolidate Sec Qty Test Item",
        "parent_item_group": "Structurals", "unit_weight": 10,
        "qty": 50, "uom": "Kg", "sec_qty": 5, "sec_uom": "Nos",
        "duno_mark_no": "DUNO-SECQTY-1",
    })
    mp.insert(ignore_permissions=True)
    print("Created test MP:", mp.name)

    mp.reload()
    row = next(r for r in mp.consolidate_items if r.item_code == item)
    print("Consolidate Item sec_qty right after consolidation (expect 0/blank):", row.sec_qty)
    assert not flt(row.sec_qty), "sec_qty must NOT be copied from the source Unavailable Item row"
    print("required_kg (expect 50, summed from the source row's qty):", row.required_kg)
    assert flt(row.required_qty if hasattr(row, "required_qty") else row.required_kg) == 50

    # Now manually set length + sec_qty (simulating the user editing the row) and
    # confirm purchase_kg computes from it via the server-side recalculate() --
    # same formula the JS live handler uses, here exercised directly.
    row.length = 5000
    row.sec_qty = 3
    mp.save(ignore_permissions=True)
    mp.reload()
    row = next(r for r in mp.consolidate_items if r.item_code == item)

    # Structurals formula: (length/1000) * unit_weight * sec_qty = 5 * 10 * 3 = 150
    expected_purchase_kg = (5000 / 1000) * 10 * 3
    print("sec_qty after manual edit:", row.sec_qty)
    print("purchase_kg (expect", expected_purchase_kg, "):", row.purchase_kg)
    assert flt(row.sec_qty) == 3, "sec_qty must hold exactly what was manually entered"
    assert flt(row.purchase_kg) == expected_purchase_kg, "purchase_kg must be computed from the manually-entered sec_qty"
    print("difference_kg (required_kg - purchase_kg, expect 50-150=-100):", row.difference_kg)
    assert flt(row.difference_kg) == flt(row.required_kg) - expected_purchase_kg

    frappe.db.commit()
    print("\nALL CHECKS DONE — Consolidate Item's Sec Qty is never inherited, stays editable, "
          "and Purchase Kg correctly derives from whatever the user enters.")
    print("Test MP left in place:", mp.name)
