"""Verify Phase 2.5: a consolidated purchase line (created via
make_material_request_from_consolidate, so it carries NO DUNO reference) that
receives less than the combined requirement of its source Unavailable Item
rows must split SEQUENTIALLY across them -- fill the first (by original idx)
fully, then the next -- rather than crediting the full received qty to every
matched row independently.

Scenario: item ZZTEST-PR-SEQ needed by two drawings (DUNO-A: 50 Kg, DUNO-B: 30
Kg), consolidated into one Consolidate Item row (required_kg=80), purchased as
one Material Request -> Purchase Order -> Purchase Receipt line, but only 60
Kg actually received. Expect: DUNO-A's row fully covered (50 Kg), DUNO-B's row
partially covered (10 of its 30 Kg), leaving a 20 Kg shortfall on DUNO-B only
-- not "both rows fully covered" (which the old, unsplit logic would have
produced by crediting the full 60 Kg to each row independently).

Run via: bench --site manufact execute manufyxinvenzaerp.tests.verify_pr_sequential_allocation.run
"""

import frappe
from frappe.utils import flt, today
from manufyxinvenzaerp.tests.create_full_test_entry import get_ctx, ensure_item, ensure_batch


def run():
    ctx = get_ctx()
    item = ensure_item(ctx, "ZZTEST-PR-SEQ", "PR Sequential Allocation Test Item", uom="Kg")
    frappe.db.set_value("Item", item, "custom_parent_item_group", "Structurals")
    frappe.db.set_value("Item", item, "custom_unit_weight", 10)

    mp = frappe.new_doc("Material Planning")
    mp.company = ctx.company
    mp.posting_date = today()
    mp.for_warehouse = ctx.warehouse
    mp.append("unavailable_items", {
        "item_code": item, "item_name": "PR Sequential Allocation Test Item",
        "parent_item_group": "Structurals", "unit_weight": 10,
        "qty": 50, "uom": "Kg", "sec_qty": 1, "sec_uom": "Nos",
        "duno_mark_no": "DUNO-A",
    })
    mp.append("unavailable_items", {
        "item_code": item, "item_name": "PR Sequential Allocation Test Item",
        "parent_item_group": "Structurals", "unit_weight": 10,
        "qty": 30, "uom": "Kg", "sec_qty": 1, "sec_uom": "Nos",
        "duno_mark_no": "DUNO-B",
    })
    mp.insert(ignore_permissions=True)
    print("Created test MP:", mp.name)

    mp.reload()
    consol_row = next(r for r in mp.consolidate_items if r.item_code == item)
    print("Consolidate Item required_kg (expect 80):", consol_row.required_kg)
    assert flt(consol_row.required_kg) == 80

    # Fill in dimensions on the Consolidate Item row (as a user would before
    # ordering) so purchase_kg computes and Material Request's own pre-existing
    # Structurals-formula-fields-required-before-submit validation is satisfied.
    consol_row.length = 8000
    consol_row.sec_qty = 1
    mp.save(ignore_permissions=True)
    mp.reload()
    consol_row = next(r for r in mp.consolidate_items if r.item_code == item)
    print("purchase_kg after filling dimensions (expect 80):", consol_row.purchase_kg)

    from manufyxinvenzaerp.production_management.doctype.material_planning.material_planning import (
        make_material_request_from_consolidate,
    )
    import json as _json

    mr_name = make_material_request_from_consolidate(mp.name, _json.dumps([item]))
    mr = frappe.get_doc("Material Request", mr_name)
    mr.submit()
    print("Created + submitted MR:", mr_name, "| item qty:", mr.items[0].qty, "| duno (expect blank):", mr.items[0].custom_duno_mark_no)
    assert not mr.items[0].custom_duno_mark_no, "Consolidated MR item must carry no DUNO reference"

    from erpnext.stock.doctype.material_request.material_request import make_purchase_order

    supplier = frappe.db.get_value("Supplier", {}, "name")
    if not supplier:
        frappe.throw("No supplier found in DB — create one first")

    po = make_purchase_order(mr_name)
    po.supplier = supplier
    for row in po.items:
        row.rate = 80
    po.insert(ignore_permissions=True)
    po.submit()
    print("Created + submitted PO:", po.name)

    from erpnext.buying.doctype.purchase_order.purchase_order import make_purchase_receipt

    pr = make_purchase_receipt(po.name)
    # Partial receipt: only 60 of the 80 Kg ordered actually arrives. This app's own
    # validate_purchase_receipt hook recalculates qty from dimensions for Structurals
    # items (custom_length/custom_sec_qty/custom_unit_weight), so the realistic way to
    # represent a partial receipt is to reduce Sec Qty proportionally (0.75 of the
    # original 1 Nos), not fight the recalculation by setting qty directly -- Length
    # stays 8000mm (same physical stock length ordered), just less of it arrived.
    pr.items[0].custom_sec_qty = 0.75  # (8000/1000)*10*0.75 = 60 Kg
    pr.items[0].qty = 60
    pr.items[0].received_qty = 60
    pr.items[0].accepted_qty = 60
    pr.items[0].rejected_qty = 0
    batch_no = ensure_batch(item, "ZZTEST-PR-SEQ-BATCH-1", L=8000, sec_qty=0.75)
    pr.items[0].use_serial_batch_fields = 1
    pr.items[0].batch_no = batch_no
    pr.insert(ignore_permissions=True)
    pr.submit()
    print("Created + submitted PR:", pr.name, "| received qty:", pr.items[0].qty)
    # Submitting the PR already triggers allocate_pr_stock_to_mp automatically via
    # on_submit_purchase_receipt -- do NOT call it again manually here. A second,
    # redundant call reloads the MP fresh (now down to just the still-short row) and
    # re-applies the ORIGINAL full received_qty against it via the single-match
    # shortcut in _split_allocation, incorrectly over-consuming an already-reduced
    # row. That's a pre-existing idempotency gap in allocate_pr_stock_to_mp (calling
    # it twice for the same PR was never safe, even before this phase's changes) --
    # out of scope here; the fix is to simply not double-call it, matching how the
    # app itself only ever calls it once, from the submit hook.

    mp.reload()
    arm_rows = {r.duno_mark_no: r for r in mp.available_raw_materials}
    unavail_rows = {r.duno_mark_no: r for r in mp.unavailable_items}

    print("Available Raw Material rows created:", list(arm_rows.keys()))
    print("Remaining Unavailable Item rows:", list(unavail_rows.keys()))

    assert "DUNO-A" in arm_rows, "DUNO-A should have an Available Raw Material row (fully covered first)"
    assert flt(arm_rows["DUNO-A"].available_qty) == 50, f"DUNO-A should get its full 50 Kg requirement, got {arm_rows['DUNO-A'].available_qty}"
    assert "DUNO-A" not in unavail_rows, "DUNO-A should be fully covered and removed from Unavailable Items"

    assert "DUNO-B" in arm_rows, "DUNO-B should have an Available Raw Material row for its partial coverage"
    assert flt(arm_rows["DUNO-B"].available_qty) == 10, f"DUNO-B should only get the leftover 10 Kg (60-50), got {arm_rows['DUNO-B'].available_qty}"
    assert "DUNO-B" in unavail_rows, "DUNO-B should still have an Unavailable Item row for its shortfall"
    assert flt(unavail_rows["DUNO-B"].qty) == 20, f"DUNO-B's remaining shortfall should be 30-10=20, got {unavail_rows['DUNO-B'].qty}"

    frappe.db.commit()
    print("\nALL CHECKS DONE — sequential split correctly filled DUNO-A first, then partially "
          "covered DUNO-B, leaving the shortfall only on DUNO-B (not spread/duplicated across both).")
    print("Test data left in place:", mp.name, mr_name, po.name, pr.name)
