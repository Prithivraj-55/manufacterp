"""Verify Phase 5.3: Material Issue Plan Raw Material's new fields --
Description/UOM (new), Reqd Qty/Issued Qty (relabeled existing qty/
transferred_qty), Excess Qty (new, = Reqd Qty - drawing's planned RM weight),
and the Excess Return Applicable checkbox that auto-populates (and keeps in
sync, without duplicating) a row in the plan's excess_return_items table.

Worked example matching the client's own (11/13/14 Kg): drawing-planned RM
weight = 13 Kg (from Sales Order Drawing Raw Material's Total Weight), batch
actually mapped/reserved = 14 Kg (Reqd Qty) -> Excess Qty = 1 Kg.

Run via: bench --site manufact execute manufyxinvenzaerp.tests.verify_mip_excess_qty_fields.run
"""

import frappe
from frappe.utils import flt, today
from manufyxinvenzaerp.tests.create_full_test_entry import get_ctx, ensure_item, ensure_fg_item


def run():
    ctx = get_ctx()
    item = ensure_item(ctx, "ZZTEST-EXCESS-FIELDS", "MIP Excess Fields Test Item", uom="Kg")
    frappe.db.set_value("Item", item, "custom_parent_item_group", "Structurals")
    frappe.db.set_value("Item", item, "custom_unit_weight", 10)
    fg_item = ensure_fg_item(ctx, "ZZTEST-EXCESS-FIELDS-FG", "MIP Excess Fields Test FG")

    customer = frappe.db.get_value("Customer", {}, "name")

    # 1. Sales Order carrying the drawing's own planned RM weight (13 Kg).
    so = frappe.new_doc("Sales Order")
    so.customer = customer
    so.company = ctx.company
    so.transaction_date = today()
    so.delivery_date = today()
    so.append("items", {"item_code": fg_item, "qty": 1, "rate": 1000, "delivery_date": today()})
    so.append("custom_so_raw_materials", {
        "customer_drawing_number": "CDN-EXCESS-FIELDS", "item_no": "1",
        "material_code": item, "parent_item_group": "Structurals",
        "length": 1000, "sec_qty": 1.3, "unit_weight": 10, "qty": 13, "uom": "Kg",
    })
    so.insert(ignore_permissions=True)
    print("Created SO:", so.name)

    # 2. Material Planning with a reserved Material Mapping row for the same
    # item/SO/drawing, mapped batch weight = 14 Kg (Reqd Qty).
    mp = frappe.new_doc("Material Planning")
    mp.company = ctx.company
    mp.posting_date = today()
    mp.for_warehouse = ctx.warehouse
    mp.append("material_mapping", {
        "item_code": item, "item_name": "MIP Excess Fields Test Item",
        "parent_item_group": "Structurals", "unit_weight": 10,
        "qty": 14, "uom": "Kg", "sec_qty": 1.4, "sec_uom": "Nos",
        "duno_mark_no": "DUNO-EXCESS-FIELDS", "customer_drawing_number": "CDN-EXCESS-FIELDS",
        "sales_order": so.name,
        "batch_calc_qty": 14, "batch_sec_qty": 1.4, "is_reserved": 0,
    })
    mp.insert(ignore_permissions=True)
    print("Created MP:", mp.name)

    # 3. Production Plan + Material Issue Plan linking to this Material Planning.
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

    mip = frappe.new_doc("Material Issue Plan")
    mip.company = ctx.company
    mip.posting_date = today()
    mip.production_plan = pp.name
    mip.insert(ignore_permissions=True)

    from manufyxinvenzaerp.subcontracting_management.doctype.material_issue_plan.material_issue_plan import (
        populate_from_production_plan,
    )
    populate_from_production_plan(mip.name)
    print("Populated MIP:", mip.name)

    mip.reload()
    rows = [r for r in mip.raw_materials if r.item_code == item]
    assert len(rows) == 1, f"Expected 1 raw_materials row, got {len(rows)}"
    row = rows[0]
    print("description:", row.description, "| uom:", row.uom)
    print("Reqd Qty (qty):", row.qty, "| drawing_planned_weight:", row.drawing_planned_weight, "| excess_qty:", row.excess_qty)

    assert row.description, "Description should be fetched from the Item"
    assert row.uom == "Kg", f"UOM should be Kg, got {row.uom}"
    assert flt(row.qty) == 14, f"Reqd Qty should be 14, got {row.qty}"
    assert flt(row.drawing_planned_weight) == 13, f"drawing_planned_weight should be 13, got {row.drawing_planned_weight}"
    assert flt(row.excess_qty) == 1, f"Excess Qty should be 14-13=1, got {row.excess_qty}"

    # 4. Flag Excess Return Applicable with dimensions, save, confirm auto-populate.
    row.excess_return_applicable = 1
    row.excess_length = 1000
    row.excess_sec_qty = 0.1  # (1000/1000)*10*0.1 = 1 Kg
    mip.save(ignore_permissions=True)
    mip.reload()

    row = next(r for r in mip.raw_materials if r.item_code == item)
    print("excess_calc_qty (expect 1.0):", row.excess_calc_qty)
    assert flt(row.excess_calc_qty) == 1.0, f"Expected excess_calc_qty=1.0, got {row.excess_calc_qty}"

    matching_excess_rows = [r for r in mip.excess_return_items if r.source_mip_raw_material_row == row.name]
    print("Matching excess_return_items rows (expect 1):", len(matching_excess_rows))
    assert len(matching_excess_rows) == 1
    excess_row = matching_excess_rows[0]
    assert excess_row.item_code == item
    assert flt(excess_row.qty) == 1.0
    print("Auto-populated excess_return_items row: item=", excess_row.item_code, "qty=", excess_row.qty)

    # 5. Re-save WITHOUT changes -- must not duplicate.
    mip.save(ignore_permissions=True)
    mip.reload()
    matching_excess_rows = [r for r in mip.excess_return_items if r.source_mip_raw_material_row == row.name]
    print("Matching excess_return_items rows after no-op re-save (expect still 1):", len(matching_excess_rows))
    assert len(matching_excess_rows) == 1, "Re-saving without changes must not duplicate the excess_return_items row"

    # 6. Change excess_sec_qty and re-save -- same row should update, not duplicate.
    row = next(r for r in mip.raw_materials if r.item_code == item)
    row.excess_sec_qty = 0.2  # -> 2 Kg
    mip.save(ignore_permissions=True)
    mip.reload()
    matching_excess_rows = [r for r in mip.excess_return_items if r.source_mip_raw_material_row == row.name]
    print("Matching excess_return_items rows after qty change (expect still 1):", len(matching_excess_rows))
    assert len(matching_excess_rows) == 1, "Changing dims must update the SAME row, not create a new one"
    assert flt(matching_excess_rows[0].qty) == 2.0, f"Expected updated qty=2.0, got {matching_excess_rows[0].qty}"

    frappe.db.commit()
    print("\nALL CHECKS DONE — Description/UOM populated, Excess Qty correctly computed from the "
          "drawing's planned weight, and Excess Return Applicable correctly syncs (creates once, "
          "updates thereafter, never duplicates) a row in excess_return_items.")
    print("Test data left in place:", so.name, mp.name, pp.name, mip.name)
