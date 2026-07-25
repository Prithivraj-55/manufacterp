"""Verify Phase 5.5: auto-suggest an Excess Material Return row from a Cut
Sheet row's Balance (W2).

Scenario: same Cut Sheet setup as verify_mip_cut_sheet.py (150 Kg batch, To
Use (W1) = 2000mm/3 Nos = 60 Kg, Balance (W2) = 3000mm/3 Nos = 90 Kg).

Verifies:
  1. On save, the raw_materials row auto-gets excess_return_applicable=1 and
     excess_length/width/sec_qty copied from balance_length/width/sec_qty --
     WITHOUT the user ever checking the box by hand.
  2. The existing Phase 5.3 sync machinery picks that up in the SAME save and
     creates a matching excess_return_items row (qty == balance_calc_qty).
  3. The suggestion only fires ONCE: if the user then manually edits
     excess_length away from the balance value, a later save does NOT stomp
     it back -- "left editable" per the plan's own wording.

Run via: bench --site manufact execute manufyxinvenzaerp.tests.verify_mip_excess_auto_suggest.run
"""

import frappe
from frappe.utils import flt, today
from manufyxinvenzaerp.tests.create_full_test_entry import get_ctx, ensure_item, ensure_batch, make_receipt


def run():
    ctx = get_ctx()
    item = ensure_item(ctx, "ZZTEST-EXCESS-SUGGEST", "Excess Auto-Suggest Test Item", uom="Kg")
    frappe.db.set_value("Item", item, "custom_parent_item_group", "Structurals")
    frappe.db.set_value("Item", item, "custom_unit_weight", 10)

    batch = ensure_batch(item, "ZZTEST-EXCESS-SUGGEST-BATCH", L=5000, sec_qty=3)
    make_receipt(ctx, item, batch, 150)
    print("Received 150 Kg into batch:", batch)

    mp = frappe.new_doc("Material Planning")
    mp.company = ctx.company
    mp.posting_date = today()
    mp.for_warehouse = ctx.warehouse
    mp.append("material_mapping", {
        "item_code": item, "item_name": "Excess Auto-Suggest Test Item",
        "parent_item_group": "Structurals", "unit_weight": 10,
        "qty": 150, "uom": "Kg", "sec_qty": 3, "sec_uom": "Nos",
        "duno_mark_no": "DUNO-EXCESS-SUGGEST",
        "batch": batch, "batch_calc_qty": 150, "batch_sec_qty": 3,
        "batch_parent_item_group": "Structurals", "batch_length": 5000,
        "is_reserved": 1, "reserved_qty": 150,
    })
    mp.insert(ignore_permissions=True)
    print("Created MP:", mp.name)

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
    print("balance_calc_qty (expect 90):", row.balance_calc_qty)
    assert flt(row.balance_calc_qty) == 90

    # 1. Auto-suggested WITHOUT the user checking the box.
    print("excess_return_applicable (expect 1):", row.excess_return_applicable)
    print("excess_length (expect 3000):", row.excess_length)
    print("excess_sec_qty (expect 3):", row.excess_sec_qty)
    assert row.excess_return_applicable == 1, "Expected excess_return_applicable to be auto-suggested"
    assert flt(row.excess_length) == 3000, f"Expected excess_length seeded from balance_length, got {row.excess_length}"
    assert flt(row.excess_sec_qty) == 3, f"Expected excess_sec_qty seeded from balance_sec_qty, got {row.excess_sec_qty}"
    assert flt(row.excess_calc_qty) == 90, f"Expected excess_calc_qty computed to 90, got {row.excess_calc_qty}"

    # 2. Existing Phase 5.3 sync created a matching excess_return_items row in
    # the SAME save.
    excess_row = next((r for r in mip.excess_return_items if r.source_mip_raw_material_row == row.name), None)
    assert excess_row is not None, "Expected an auto-populated excess_return_items row"
    print("excess_return_items row qty (expect 90):", excess_row.qty)
    assert flt(excess_row.qty) == 90

    # 3. Suggestion fires ONCE -- a manual edit away from the balance value
    # must survive a later save, not get stomped back.
    row.excess_length = 2500
    mip.save(ignore_permissions=True)
    mip.reload()
    row = next(r for r in mip.raw_materials if r.item_code == item)
    print("excess_length after manual edit + re-save (expect still 2500, NOT reset to 3000):", row.excess_length)
    assert flt(row.excess_length) == 2500, (
        f"Expected manual edit to survive a re-save (still 2500), got {row.excess_length} "
        "-- auto-suggestion must only fire the first time, not overwrite every save"
    )

    frappe.db.commit()
    print("\nALL CHECKS DONE — Cut Sheet Balance auto-suggested an editable Excess Return row "
          "in the same save, and a subsequent manual edit was preserved (not reset) on re-save.")
    print("Test data left in place:", pp.name, sco_name, mp.name, mip.name, batch)
