"""Verify: Material Planning Consolidate Item's "Alternate Item" section
(added so a bulk purchasing substitution decision can be made once for a
whole consolidated/deduped-by-item_code purchase line instead of per original
drawing row). Unlike Unavailable Item's own Alternate Item fields, Consolidate
Item does NOT duplicate Length/Width/Thickness/Sec Qty -- once Alternate Item
is set, the row's own (shared) Length/Sec Qty are reinterpreted as describing
the alternate item, and only its Unit Weight/Parent Item Group are looked up
separately, so Purchase Kg/Difference Kg recalculate correctly off the same
fields.

Scenario: identical setup to verify_pr_sequential_allocation.py -- item
ZZTEST-ALT-ORIG needed by two drawings (DUNO-A: 50 Kg, DUNO-B: 30 Kg),
consolidated into one Consolidate Item row (required_kg=80) -- but this time
an Alternate Item (ZZTEST-ALT-SUB) is set directly on the Consolidate Item
row before ordering, so the Material Request/PO/PR are placed against the
ALTERNATE item, not the original. Only 60 Kg is actually received (partial),
same as the Phase 2.5 test, to also confirm the sequential-split-by-idx
allocation still works when routed through the new alternate-item path.

Verifies:
  1. make_material_request_from_consolidate orders the ALTERNATE item (not
     the original), using the row's own alternate_* dimensions, with a
     "[Alt for <original>]" description suffix.
  2. After the PR (for the alternate item) submits, allocate_pr_stock_to_mp
     allocates into MATERIAL MAPPING (not Available Raw Materials) -- with
     item_code = the ORIGINAL item and planned_item = the ALTERNATE/purchased
     item -- split sequentially across DUNO-A (filled first, fully) and
     DUNO-B (partially covered), exactly like the existing non-alternate
     Phase 2.5 sequential-split test, just landing in a different table.
  3. DUNO-A's Unavailable Item row is fully consumed (removed); DUNO-B's is
     shrunk to its remaining shortfall (20 Kg).

Run via: bench --site manufact execute manufyxinvenzaerp.tests.verify_consolidate_alternate_item.run
"""

import frappe
from frappe.utils import flt, today
from manufyxinvenzaerp.tests.create_full_test_entry import get_ctx, ensure_item, ensure_batch


def run():
    ctx = get_ctx()
    orig_item = ensure_item(ctx, "ZZTEST-ALT-ORIG", "Alternate Item Test - Original", uom="Kg")
    frappe.db.set_value("Item", orig_item, "custom_parent_item_group", "Structurals")
    frappe.db.set_value("Item", orig_item, "custom_unit_weight", 10)

    alt_item = ensure_item(ctx, "ZZTEST-ALT-SUB", "Alternate Item Test - Substitute", uom="Kg")
    frappe.db.set_value("Item", alt_item, "custom_parent_item_group", "Structurals")
    frappe.db.set_value("Item", alt_item, "custom_unit_weight", 10)

    mp = frappe.new_doc("Material Planning")
    mp.company = ctx.company
    mp.posting_date = today()
    mp.for_warehouse = ctx.warehouse
    mp.append("unavailable_items", {
        "item_code": orig_item, "item_name": "Alternate Item Test - Original",
        "parent_item_group": "Structurals", "unit_weight": 10,
        "qty": 50, "uom": "Kg", "sec_qty": 1, "sec_uom": "Nos",
        "duno_mark_no": "DUNO-ALT-A",
    })
    mp.append("unavailable_items", {
        "item_code": orig_item, "item_name": "Alternate Item Test - Original",
        "parent_item_group": "Structurals", "unit_weight": 10,
        "qty": 30, "uom": "Kg", "sec_qty": 1, "sec_uom": "Nos",
        "duno_mark_no": "DUNO-ALT-B",
    })
    mp.insert(ignore_permissions=True)
    mp.reload()
    print("Created test MP:", mp.name)

    consol_row = next(r for r in mp.consolidate_items if r.item_code == orig_item)
    print("Consolidate Item required_kg (expect 80):", consol_row.required_kg)
    assert flt(consol_row.required_kg) == 80

    # Set the Alternate Item directly on the Consolidate Item row (the new
    # feature) -- mirrors the client-side alternate_item handler: Length/Sec
    # Qty (the row's own shared dimension fields, not separate alternate_*
    # fields) are reinterpreted as describing the ALTERNATE item once one is
    # set, and Purchase/Difference Kg auto-recalculate server-side (validate)
    # using the alternate item's own Unit Weight/Parent Item Group.
    consol_row.alternate_item = alt_item
    consol_row.length = 8000
    consol_row.sec_qty = 1
    consol_row.alternate_unit_weight = 10
    consol_row.alternate_parent_item_group = "Structurals"
    mp.save(ignore_permissions=True)
    mp.reload()
    consol_row = next(r for r in mp.consolidate_items if r.item_code == orig_item)
    print("Consolidate Item alternate_item set:", consol_row.alternate_item,
          "| purchase_kg (expect 80):", consol_row.purchase_kg,
          "| difference_kg (expect 0):", consol_row.difference_kg)
    assert flt(consol_row.purchase_kg) == 80
    assert flt(consol_row.difference_kg) == 0

    from manufyxinvenzaerp.production_management.doctype.material_planning.material_planning import (
        make_material_request_from_consolidate,
    )
    import json as _json

    mr_name = make_material_request_from_consolidate(mp.name, _json.dumps([orig_item]))
    mr = frappe.get_doc("Material Request", mr_name)
    mr.submit()
    print("Created + submitted MR:", mr_name, "| item_code (expect alternate):", mr.items[0].item_code,
          "| qty:", mr.items[0].qty, "| description:", mr.items[0].description)
    assert mr.items[0].item_code == alt_item, f"Expected MR to order the alternate item {alt_item}, got {mr.items[0].item_code}"
    assert f"[Alt for {orig_item}]" in mr.items[0].description

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
    print("Created + submitted PO:", po.name, "| item_code:", po.items[0].item_code)
    assert po.items[0].item_code == alt_item

    from erpnext.buying.doctype.purchase_order.purchase_order import make_purchase_receipt

    pr = make_purchase_receipt(po.name)
    # Partial receipt: only 60 of the 80 Kg ordered actually arrives -- same
    # "reduce Sec Qty proportionally" approach as verify_pr_sequential_allocation.py.
    pr.items[0].custom_sec_qty = 0.75  # (8000/1000)*10*0.75 = 60 Kg
    pr.items[0].qty = 60
    pr.items[0].received_qty = 60
    pr.items[0].accepted_qty = 60
    pr.items[0].rejected_qty = 0
    batch_no = ensure_batch(alt_item, "ZZTEST-ALT-SUB-BATCH-1", L=8000, sec_qty=0.75)
    pr.items[0].use_serial_batch_fields = 1
    pr.items[0].batch_no = batch_no
    pr.insert(ignore_permissions=True)
    pr.submit()
    print("Created + submitted PR:", pr.name, "| item_code:", pr.items[0].item_code, "| received qty:", pr.items[0].qty)
    # Submitting the PR already triggers allocate_pr_stock_to_mp via on_submit_purchase_receipt.

    mp.reload()
    mm_rows = {r.duno_mark_no: r for r in mp.material_mapping if r.item_code == orig_item}
    arm_rows = {r.duno_mark_no: r for r in mp.available_raw_materials if r.item_code == orig_item}
    unavail_rows = {r.duno_mark_no: r for r in mp.unavailable_items if r.item_code == orig_item}

    print("Material Mapping rows created:", {k: (v.planned_item, v.batch_calc_qty) for k, v in mm_rows.items()})
    print("Available Raw Material rows created (expect none):", list(arm_rows.keys()))
    print("Remaining Unavailable Item rows:", {k: v.qty for k, v in unavail_rows.items()})

    assert not arm_rows, "Alternate-item purchase must NOT land in Available Raw Materials (Exact Match)"

    assert "DUNO-ALT-A" in mm_rows, "DUNO-A should have a Material Mapping row (fully covered first)"
    assert mm_rows["DUNO-ALT-A"].item_code == orig_item
    assert mm_rows["DUNO-ALT-A"].planned_item == alt_item, "planned_item should be the purchased ALTERNATE item"
    assert flt(mm_rows["DUNO-ALT-A"].batch_calc_qty) == 50, f"DUNO-A should get its full 50 Kg requirement, got {mm_rows['DUNO-ALT-A'].batch_calc_qty}"
    assert "DUNO-ALT-A" not in unavail_rows, "DUNO-A should be fully covered and removed from Unavailable Items"

    assert "DUNO-ALT-B" in mm_rows, "DUNO-B should have a Material Mapping row for its partial coverage"
    assert mm_rows["DUNO-ALT-B"].planned_item == alt_item
    assert flt(mm_rows["DUNO-ALT-B"].batch_calc_qty) == 10, f"DUNO-B should only get the leftover 10 Kg (60-50), got {mm_rows['DUNO-ALT-B'].batch_calc_qty}"
    assert "DUNO-ALT-B" in unavail_rows, "DUNO-B should still have an Unavailable Item row for its shortfall"
    assert flt(unavail_rows["DUNO-ALT-B"].qty) == 20, f"DUNO-B's remaining shortfall should be 30-10=20, got {unavail_rows['DUNO-ALT-B'].qty}"

    frappe.db.commit()
    print("\nALL CHECKS DONE — Consolidate Item's own Alternate Item correctly drove the Material "
          "Request to order the substitute item, and the received batch was correctly allocated into "
          "Material Mapping (item_code=original, planned_item=alternate), sequentially split across "
          "DUNO-A (fully) and DUNO-B (partially), matching the existing per-row alternate_item behavior.")
    print("Test data left in place:", mp.name, mr_name, po.name, pr.name)
