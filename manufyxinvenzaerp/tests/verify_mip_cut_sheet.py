"""Verify Phase 5.2: Material Issue Plan Cut Sheet feature.

Scenario: a batch has 150 Kg total stock (5000mm length, Sec Qty 3). A Material
Issue Plan raw material row for it is flagged Cut Sheet: To Use (W1) =
2000mm/3 Nos = 60 Kg, Balance (W2) = 3000mm/3 Nos = 90 Kg (60+90=150, matching
the physical bar being cut into a 2000mm piece used now and a 3000mm piece
remaining).

Verifies:
  1. use_calc_qty/balance_calc_qty compute correctly on save (W1=60, W2=90).
  2. get_mip_pending_items() offers only 60 Kg for transfer (W1), not the full
     150 Kg reserved -- the Balance portion is never offered as "more to send".
  3. After transferring exactly that 60 Kg and submitting the Stock Entry, the
     SAME batch (no new batch created) gets resized: custom_length -> 3000,
     custom_sec_qty -> 3 (the Balance/W2 dimensions).
  4. get_mip_pending_items() now shows 0 pending for this row (fully covered).

Run via: bench --site manufact execute manufyxinvenzaerp.tests.verify_mip_cut_sheet.run
"""

import frappe
from frappe.utils import flt, today
from manufyxinvenzaerp.tests.create_full_test_entry import get_ctx, ensure_item, ensure_batch, make_receipt


def run():
    ctx = get_ctx()
    item = ensure_item(ctx, "ZZTEST-CUT-SHEET", "Cut Sheet Test Item", uom="Kg")
    frappe.db.set_value("Item", item, "custom_parent_item_group", "Structurals")
    frappe.db.set_value("Item", item, "custom_unit_weight", 10)

    batch = ensure_batch(item, "ZZTEST-CUT-SHEET-BATCH", L=5000, sec_qty=3)
    # Physically receive 150 Kg of this batch into the source warehouse.
    make_receipt(ctx, item, batch, 150)
    print("Received 150 Kg into batch:", batch)

    # 1. Material Planning with the batch fully reserved (150 Kg).
    mp = frappe.new_doc("Material Planning")
    mp.company = ctx.company
    mp.posting_date = today()
    mp.for_warehouse = ctx.warehouse
    mp.append("material_mapping", {
        "item_code": item, "item_name": "Cut Sheet Test Item",
        "parent_item_group": "Structurals", "unit_weight": 10,
        "qty": 150, "uom": "Kg", "sec_qty": 3, "sec_uom": "Nos",
        "duno_mark_no": "DUNO-CUT-SHEET",
        "batch": batch, "batch_calc_qty": 150, "batch_sec_qty": 3,
        "batch_parent_item_group": "Structurals", "batch_length": 5000,
        "is_reserved": 1, "reserved_qty": 150,
    })
    mp.insert(ignore_permissions=True)
    print("Created MP:", mp.name)

    # 2. Production Plan (linking its item to this MP) + real Subcontracting
    # Order (Internal Job -- reuses the pattern already exercised elsewhere
    # this session).
    bom = frappe.db.get_value("BOM", {"docstatus": 1, "is_active": 1}, ["name", "item", "quantity"], as_dict=True)
    stock_uom = frappe.db.get_value("Item", bom.item, "stock_uom") or "Nos"

    pp = frappe.new_doc("Production Plan")
    pp.custom_type = "Internal Job"
    pp.company = ctx.company
    pp.posting_date = today()
    pp.get_items_from = ""
    pp.append("po_items", {
        "item_code": bom.item, "bom_no": bom.name, "planned_qty": bom.quantity or 1,
        "stock_uom": stock_uom, "custom_material_planning": mp.name,
    })
    pp.append("custom_process_planning", {"operation_name": "Material Issue", "work_type": "Internal Jobcard"})
    pp.insert(ignore_permissions=True)
    pp.submit()
    print("Created Production Plan:", pp.name)

    from manufyxinvenzaerp.subcontracting_management.subcontracting import create_sco_from_production_plan
    sco_name = create_sco_from_production_plan(pp.name)
    print("Created SCO:", sco_name)

    # 3. Material Issue Plan -- after_insert auto-populates drawing_items/
    # raw_materials from the Production Plan's po_items (custom_material_planning
    # set above), source_warehouse/supplier_warehouse set for a real transfer.
    mip = frappe.new_doc("Material Issue Plan")
    mip.company = ctx.company
    mip.posting_date = today()
    mip.production_plan = pp.name
    mip.subcontracting_order = sco_name
    supplier_warehouse = frappe.db.get_value("Warehouse", {"is_group": 0, "name": ["!=", ctx.warehouse]}, "name")
    mip.source_warehouse = ctx.warehouse
    mip.supplier_warehouse = supplier_warehouse
    mip.insert(ignore_permissions=True)
    mip.reload()
    # after_insert's populate_from_production_plan unconditionally re-derives
    # supplier_warehouse from the SCO (blank for an Internal Job SCO) -- force
    # it back to our test warehouse afterward so get_target_context() has one.
    mip.supplier_warehouse = supplier_warehouse
    mip.save(ignore_permissions=True)
    mip.reload()
    print("Populated MIP:", mip.name)

    row = next(r for r in mip.raw_materials if r.item_code == item)
    row.cut_sheet = 1
    row.use_length = 2000
    row.use_sec_qty = 3
    row.balance_length = 3000
    row.balance_sec_qty = 3
    mip.save(ignore_permissions=True)
    mip.reload()

    row = next(r for r in mip.raw_materials if r.item_code == item)
    print("use_calc_qty (expect 60):", row.use_calc_qty, "| balance_calc_qty (expect 90):", row.balance_calc_qty)
    assert flt(row.use_calc_qty) == 60, f"Expected use_calc_qty=60, got {row.use_calc_qty}"
    assert flt(row.balance_calc_qty) == 90, f"Expected balance_calc_qty=90, got {row.balance_calc_qty}"

    # 4. get_mip_pending_items should offer only 60 Kg (W1), not the full 150 Kg reserved.
    from manufyxinvenzaerp.subcontracting_management.material_issue_plan_transfer import (
        get_mip_pending_items, create_mip_partial_transfer,
    )
    import json as _json

    pending = get_mip_pending_items(mip.name)
    matching = [p for p in pending if p["item_code"] == item and p["batch_no"] == batch]
    print("Pending items before transfer:", matching)
    assert len(matching) == 1
    assert flt(matching[0]["qty"]) == 60, f"Expected pending qty capped at 60 (W1), got {matching[0]['qty']}"

    # 5. Transfer exactly that 60 Kg and submit.
    se_name = create_mip_partial_transfer(mip.name, _json.dumps(matching), "primary")
    se = frappe.get_doc("Stock Entry", se_name)
    for r in se.items:
        r.allow_zero_valuation_rate = 1
    se.save(ignore_permissions=True)
    se.submit()
    print("Created + submitted transfer Stock Entry:", se_name, "| qty:", se.items[0].qty)
    assert flt(se.items[0].qty) == 60

    # 6. The SAME batch should now be resized to the Balance (W2) dimensions.
    batch_doc = frappe.get_doc("Batch", batch)
    print("Batch after submit -- custom_length (expect 3000):", batch_doc.custom_length,
          "| custom_sec_qty (expect 3):", batch_doc.custom_sec_qty)
    assert flt(batch_doc.custom_length) == 3000, f"Expected batch resized to 3000mm, got {batch_doc.custom_length}"
    assert flt(batch_doc.custom_sec_qty) == 3, f"Expected batch Sec Qty still 3, got {batch_doc.custom_sec_qty}"

    # Confirm no NEW batch was created for this item -- still exactly one.
    all_batches = frappe.get_all("Batch", filters={"item": item}, pluck="name")
    print("Total batches for this item (expect 1 -- no new batch created):", len(all_batches))
    assert len(all_batches) == 1

    # 7. Pending should now be 0 for this row -- fully covered by the capped W1 transfer.
    # (Something in the transfer/submit path re-derives supplier_warehouse from the
    # SCO again in between -- re-assert our test override right before this call;
    # unrelated to what's actually being verified here.)
    frappe.db.set_value("Material Issue Plan", mip.name, "supplier_warehouse", supplier_warehouse)
    pending_after = get_mip_pending_items(mip.name)
    matching_after = [p for p in pending_after if p["item_code"] == item and p["batch_no"] == batch]
    print("Pending items after transfer (expect none):", matching_after)
    assert not matching_after, "Row should show no further pending qty after its capped W1 was transferred"

    frappe.db.commit()
    print("\nALL CHECKS DONE — Cut Sheet correctly capped the transfer at W1 (60 Kg), left the "
          "Balance (90 Kg) untransferred, and resized the SAME batch's own dimensions to the "
          "Balance (W2) values after the transfer submitted -- no new batch created.")
    print("Test data left in place:", pp.name, sco_name, mp.name, mip.name, se_name, batch)
