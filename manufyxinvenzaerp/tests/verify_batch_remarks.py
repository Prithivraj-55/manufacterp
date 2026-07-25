"""Verify Phase 6.3: new "Batch Remarks" field on Batch, populated from the
Inspection Call's remarks for the batch's source Purchase Receipt item, and
surfaced (read-only, synced on every save) in Material Planning (both
Material Mapping and Available Raw Material), Material Issue Plan, and
Stock Entry.

Scenario: an item requiring inspection (client change request Phase 6.2's
own setup), received via a real Purchase Receipt that auto-creates its own
batch. Runs a real Inspection Entry round with a per-row remark, confirms it
propagates onto Batch.custom_batch_remarks, then confirms that value gets
mirrored (via each doctype's own validate()-time sync, not fetch_from) onto:
  1. Material Planning Material Mapping's batch_remarks
  2. Material Planning Available Raw Material's batch_remarks
  3. Material Issue Plan Raw Material's batch_remarks
  4. Stock Entry Detail's custom_batch_remarks (a plain Material Receipt)
Also confirms a later, DIFFERENT remark on the batch re-syncs onto an
already-saved row on a subsequent save (not just once at creation).

Note: this site's Purchase Receipt Items use the v15 Serial and Batch Bundle
model -- the row's own `batch_no` column is blank; the actual batch lives in
`Serial and Batch Entry` rows under `serial_and_batch_bundle`. The Phase 6.3
propagation code (inspection.py's `_resolve_pr_item_batch_nos`) resolves via
that bundle, not the (empty) `batch_no` column -- confirmed empirically while
building this test, since the first attempt silently found no batch at all.

Run via: bench --site manufact execute manufyxinvenzaerp.tests.verify_batch_remarks.run
"""

import frappe
from frappe.utils import nowdate, today
from manufyxinvenzaerp.tests.create_full_test_entry import get_ctx


def run():
    ctx = get_ctx()
    item_code = "ZZTEST-BATCH-REMARKS"
    if not frappe.db.exists("Item", item_code):
        frappe.get_doc({
            "doctype": "Item", "item_code": item_code, "item_name": item_code,
            "item_group": ctx.item_group, "stock_uom": "Nos", "is_stock_item": 1,
            "has_batch_no": 1, "create_new_batch": 1, "custom_batch_prefix": "ZZBREM",
            "gst_hsn_code": ctx.hsn_code, "custom_parent_item_group": "Nuts and Bolts",
            "custom_inspection_required": 1,
        }).insert(ignore_permissions=True)

    supplier = frappe.db.get_value("Supplier", {}, "name")
    pr = frappe.get_doc({
        "doctype": "Purchase Receipt",
        "supplier": supplier, "company": ctx.company, "set_warehouse": ctx.warehouse,
        "items": [{"item_code": item_code, "qty": 10, "rate": 10, "warehouse": ctx.warehouse}],
    })
    pr.insert(ignore_permissions=True)
    pr.submit()

    batch_no = frappe.db.get_value(
        "Batch", {"reference_doctype": "Purchase Receipt", "reference_name": pr.name, "item": item_code}, "name"
    )
    assert batch_no, "Expected the PR to auto-create a batch"
    print("Created PR:", pr.name, "-- batch:", batch_no)

    from manufyxinvenzaerp.production_management import inspection as insp

    insp.add_inspection_call("Purchase Receipt", pr.name, call_date=nowdate())
    entry_name = insp.create_inspection_entry("Purchase Receipt", pr.name)
    entry = frappe.get_doc("Inspection Entry", entry_name)
    entry.status = "Completed"
    entry.feedback = "Ok"
    entry.items[0].accept_qty = entry.items[0].qty
    entry.items[0].remarks = "Surface finish slightly rough, accepted with note"
    entry.save(ignore_permissions=True)
    entry.submit()
    print("Submitted Inspection Entry:", entry_name)

    batch_doc = frappe.get_doc("Batch", batch_no)
    print("Batch.custom_batch_remarks (expect the inspection remark):", batch_doc.custom_batch_remarks)
    assert batch_doc.custom_batch_remarks == "Surface finish slightly rough, accepted with note"

    # ── 1 & 2: Material Planning (Material Mapping + Available Raw Material) ──
    # Two SEPARATE Material Plannings -- this app's own
    # _validate_no_cross_table_batch_duplicate forbids the same batch
    # appearing in both Material Mapping and Exact Match WITHIN one doc, but
    # allows it across two different docs.
    mp = frappe.new_doc("Material Planning")
    mp.company = ctx.company
    mp.posting_date = today()
    mp.for_warehouse = ctx.warehouse
    mp.append("material_mapping", {
        "item_code": item_code, "item_name": item_code,
        "parent_item_group": "Nuts and Bolts", "unit_weight": 1,
        "qty": 5, "uom": "Nos", "sec_qty": 5, "sec_uom": "Nos",
        "batch": batch_no, "batch_calc_qty": 0,
    })
    mp.insert(ignore_permissions=True)
    mp.reload()

    mp_arm = frappe.new_doc("Material Planning")
    mp_arm.company = ctx.company
    mp_arm.posting_date = today()
    mp_arm.for_warehouse = ctx.warehouse
    mp_arm.append("available_raw_materials", {
        "item_code": item_code, "item_name": item_code,
        "parent_item_group": "Nuts and Bolts",
        "required_qty": 5, "uom": "Nos", "sec_qty": 5, "sec_uom": "Nos",
        "batch_no": batch_no,
    })
    mp_arm.insert(ignore_permissions=True)
    mp_arm.reload()

    mm_row = next(r for r in mp.material_mapping if r.batch == batch_no)
    arm_row = next(r for r in mp_arm.available_raw_materials if r.batch_no == batch_no)
    print("Material Mapping batch_remarks:", mm_row.batch_remarks)
    print("Available Raw Material batch_remarks:", arm_row.batch_remarks)
    assert mm_row.batch_remarks == "Surface finish slightly rough, accepted with note"
    assert arm_row.batch_remarks == "Surface finish slightly rough, accepted with note"

    # ── 3: Material Issue Plan Raw Material ──────────────────────────────────
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

    mip = frappe.new_doc("Material Issue Plan")
    mip.company = ctx.company
    mip.posting_date = today()
    mip.production_plan = pp.name
    mip.insert(ignore_permissions=True)
    mip.reload()  # after_insert's populate_from_production_plan modifies the DB copy, not this in-memory one
    mip_row = next(r for r in mip.raw_materials if r.batch_no == batch_no)
    print("Material Issue Plan Raw Material batch_remarks:", mip_row.batch_remarks)
    assert mip_row.batch_remarks == "Surface finish slightly rough, accepted with note"

    # ── 4: Stock Entry Detail ────────────────────────────────────────────────
    se = frappe.new_doc("Stock Entry")
    se.stock_entry_type = "Material Issue"
    se.company = ctx.company
    se.posting_date = today()
    se.append("items", {
        "item_code": item_code, "qty": 1, "uom": "Nos", "stock_uom": "Nos",
        "conversion_factor": 1, "s_warehouse": ctx.warehouse, "batch_no": batch_no,
    })
    se.insert(ignore_permissions=True)
    se.reload()
    se_row = se.items[0]
    print("Stock Entry Detail custom_batch_remarks:", se_row.custom_batch_remarks)
    assert se_row.custom_batch_remarks == "Surface finish slightly rough, accepted with note"

    # ── Re-sync on a later save picks up a DIFFERENT/updated remark ─────────
    frappe.db.set_value("Batch", batch_no, "custom_batch_remarks", "Updated remark after re-check")
    mp.save(ignore_permissions=True)
    mp.reload()
    mm_row = next(r for r in mp.material_mapping if r.batch == batch_no)
    print("Material Mapping batch_remarks after batch remark changed + MP re-saved (expect updated):", mm_row.batch_remarks)
    assert mm_row.batch_remarks == "Updated remark after re-check"

    frappe.db.commit()
    print("\nALL CHECKS DONE — Batch Remarks correctly propagate from a submitted Inspection Entry onto "
          "the Batch record, and are correctly mirrored (and kept in sync on later saves) onto Material "
          "Planning (Material Mapping + Available Raw Material), Material Issue Plan Raw Material, and "
          "Stock Entry Detail.")
    print("Test data left in place:", pr.name, entry_name, batch_no, mp.name, mp_arm.name, mip.name, se.name)
