"""Verify Phase 5.6: "Return Excess Entry" now requires editing Qty + a
mandatory Reason before it creates the actual return Stock Entry, and the
finalized (possibly-edited) qty is pushed back onto the source raw_materials
row's Excess Qty so it stays accurate.

Scenario: reuses the Phase 5.5 Cut Sheet auto-suggest setup (150 Kg batch,
Balance/W2 = 90 Kg auto-suggested into excess_return_items) as a realistic
"planned" excess row, then exercises the Phase 5.6 Return Excess Entry flow
on top of it.

NOTE on why the override is Length/Sec Qty, not a direct Qty override: this
item is in the Structurals group, and Stock Entry's own validate_stock_entry
hook (production_management/stock_entry.py) unconditionally recalculates Qty
from custom_length/custom_sec_qty/custom_unit_weight for Structurals/Plates
items on a Material Receipt entry -- a directly-set Qty override would be
silently discarded the moment the Stock Entry is inserted. So editing the
planned return means editing the row's own Length/Sec Qty (its dimensions),
exactly as this row already behaves everywhere else in the app.

Verifies:
  1. Calling create_mip_excess_return_entry with a row override missing
     return_reason throws (Reason is mandatory).
  2. Calling it with an edited Length (2500mm instead of the auto-suggested
     3000mm, recomputing Qty to 75 Kg instead of 90) + a reason succeeds: the
     Stock Entry is created for 75 Kg (not 90), the excess_return_items row
     persists the edited Length/Qty and the reason, and the row is marked
     stock_entry_created.
  3. The source raw_materials row's excess_calc_qty is updated to 75 (the
     actual returned qty), not left at the original 90 Kg suggestion.
  4. A direct/scripted call with no rows_json still enforces the Reason
     against whatever is already saved on the row (regression check against
     the pre-existing verify_excess_material_mapping.py usage pattern).

Run via: bench --site manufact execute manufyxinvenzaerp.tests.verify_mip_return_excess_reason.run
"""

import frappe
from frappe.utils import flt, today
from manufyxinvenzaerp.tests.create_full_test_entry import get_ctx, ensure_item, ensure_batch, make_receipt


def run():
    ctx = get_ctx()
    item = ensure_item(ctx, "ZZTEST-RETURN-REASON", "Return Reason Test Item", uom="Kg")
    frappe.db.set_value("Item", item, "custom_parent_item_group", "Structurals")
    frappe.db.set_value("Item", item, "custom_unit_weight", 10)

    batch = ensure_batch(item, "ZZTEST-RETURN-REASON-BATCH", L=5000, sec_qty=3)
    make_receipt(ctx, item, batch, 150)

    mp = frappe.new_doc("Material Planning")
    mp.company = ctx.company
    mp.posting_date = today()
    mp.for_warehouse = ctx.warehouse
    mp.append("material_mapping", {
        "item_code": item, "item_name": "Return Reason Test Item",
        "parent_item_group": "Structurals", "unit_weight": 10,
        "qty": 150, "uom": "Kg", "sec_qty": 3, "sec_uom": "Nos",
        "duno_mark_no": "DUNO-RETURN-REASON",
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
    mip.excess_return_warehouse = ctx.warehouse
    mip.insert(ignore_permissions=True)
    mip.reload()
    mip.supplier_warehouse = supplier_warehouse
    mip.excess_return_warehouse = ctx.warehouse
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
    print("balance_calc_qty (expect 90, auto-suggested):", row.balance_calc_qty)
    assert flt(row.balance_calc_qty) == 90

    excess_row = next(r for r in mip.excess_return_items if r.source_mip_raw_material_row == row.name)
    print("Auto-suggested excess_return_items qty (expect 90):", excess_row.qty)
    assert flt(excess_row.qty) == 90

    from manufyxinvenzaerp.subcontracting_management.material_issue_plan_transfer import create_mip_excess_return_entry
    import json as _json

    # 1. Override with NO return_reason must throw.
    threw = False
    try:
        create_mip_excess_return_entry(mip.name, _json.dumps([
            {"name": excess_row.name, "length": 2500, "sec_qty": 3, "return_reason": ""},
        ]))
    except frappe.ValidationError:
        threw = True
    print("Throws without a Return Reason (expect True):", threw)
    assert threw, "Expected create_mip_excess_return_entry to throw when Return Reason is blank"

    # 2. Override WITH an edited Length (2500mm instead of the auto-suggested
    # 3000mm -> Qty recomputes to 75 Kg) + a reason -- must succeed.
    se_name = create_mip_excess_return_entry(mip.name, _json.dumps([
        {"name": excess_row.name, "length": 2500, "sec_qty": 3,
         "return_reason": "Measured off-cut was less than the calculated balance"},
    ]))
    se = frappe.get_doc("Stock Entry", se_name)
    print("Created SE:", se_name, "| item qty (expect 75, from the EDITED length 2500mm, not 90):", se.items[0].qty)
    assert flt(se.items[0].qty) == 75, f"Expected the recomputed qty (75) from the edited length to be used, got {se.items[0].qty}"

    mip.reload()
    excess_row = next(r for r in mip.excess_return_items if r.source_mip_raw_material_row == row.name)
    print("excess_return_items after return -- length:", excess_row.length, "| qty:", excess_row.qty,
          "| return_reason:", excess_row.return_reason, "| stock_entry_created:", excess_row.stock_entry_created)
    assert flt(excess_row.length) == 2500
    assert flt(excess_row.qty) == 75
    assert excess_row.return_reason == "Measured off-cut was less than the calculated balance"
    assert excess_row.stock_entry_created == 1

    # 3. The source raw_materials row's Excess Qty should now reflect the
    # ACTUAL returned qty (75), not the original 90 Kg suggestion.
    row = next(r for r in mip.raw_materials if r.item_code == item)
    print("raw_materials row excess_calc_qty after return (expect 75, not 90):", row.excess_calc_qty)
    assert flt(row.excess_calc_qty) == 75, f"Expected excess_calc_qty synced to actual returned qty (75), got {row.excess_calc_qty}"

    # 4. A direct/scripted call with no rows_json still enforces the Reason
    # against a row that has none saved -- build a second, independent excess row with no reason.
    mip.append("excess_return_items", {
        "item_code": item, "parent_item_group": "Structurals",
        "length": 1000, "sec_qty": 1, "qty": 10, "uom": "Kg",
    })
    mip.save(ignore_permissions=True)
    mip.reload()

    threw_no_payload = False
    try:
        create_mip_excess_return_entry(mip.name)
    except frappe.ValidationError:
        threw_no_payload = True
    print("Direct call (no rows_json) throws when a row has no saved Return Reason (expect True):", threw_no_payload)
    assert threw_no_payload

    frappe.db.commit()
    print("\nALL CHECKS DONE — Return Excess Entry now requires a Reason (missing Reason throws, "
          "including a direct/scripted call with no override payload), an edited Qty is honored in the "
          "created Stock Entry, and the source raw_materials row's Excess Qty is synced to the actual "
          "returned amount after the return completes.")
    print("Test data left in place:", pp.name, sco_name, mp.name, mip.name, se_name, batch)
