"""Verify Phase 6.2: gate Material Planning batch use (reservation) until the
batch's source Purchase Receipt inspection is Completed -- or the item never
required inspection, or the batch has no traceable source Purchase Receipt at
all (e.g. an excess-return recovery batch, or a legacy/manually-created one).

Scenario A (material_mapping / reserve_batches): an item with
Item.custom_inspection_required=1, received via a real Purchase Receipt that
auto-creates its own batch (so Batch.reference_doctype="Purchase Receipt"),
alongside a second, ordinary (non-inspection) row in the same Material
Planning so the call has something reservable and returns normally instead
of throwing "everything is blocked".
  1. Reserving while the PR's custom_inspection_status is still "Open" must
     leave the inspection-gated row unreserved (reported under "blocked"),
     while the ordinary row reserves normally in the same call.
  2. Setting custom_inspection_status="Completed" on the PR and reserving
     again must now reserve the previously-blocked row too.
  3. A Material Planning where EVERY unreserved row is blocked must throw
     with a clear inspection-related message (mirroring the existing "all
     rows already reserved" throw), not silently no-op.

Scenario B (available_raw_materials / reserve_exact_match_batches): same
shape, independent item/batch/PR, confirms the Exact Match table's own
reservation function is gated identically.

Scenario C (fail-open cases): (1) an item WITHOUT custom_inspection_required
reserves normally regardless of any PR's inspection status; (2) a batch with
NO traceable source Purchase Receipt (built via the plain ensure_batch/
make_receipt Stock Entry helpers, matching how excess-return batches are
created) is never blocked even when its item requires inspection.

Run via: bench --site manufact execute manufyxinvenzaerp.tests.verify_mp_inspection_gate.run
"""

import frappe
from frappe.utils import flt, today
from manufyxinvenzaerp.tests.create_full_test_entry import get_ctx, ensure_item, ensure_batch, make_receipt


def _make_inspected_item_and_pr(ctx, item_code, qty=10):
    """Item requiring inspection, received via a real Purchase Receipt that
    auto-creates its own batch (Batch.reference_doctype="Purchase Receipt")."""
    if not frappe.db.exists("Item", item_code):
        frappe.get_doc({
            "doctype": "Item", "item_code": item_code, "item_name": item_code,
            "item_group": ctx.item_group, "stock_uom": "Nos", "is_stock_item": 1,
            "has_batch_no": 1, "create_new_batch": 1, "custom_batch_prefix": "ZZINSP",
            "gst_hsn_code": ctx.hsn_code, "custom_parent_item_group": "Nuts and Bolts",
            "custom_inspection_required": 1,
        }).insert(ignore_permissions=True)
    else:
        frappe.db.set_value("Item", item_code, "custom_inspection_required", 1)

    supplier = frappe.db.get_value("Supplier", {}, "name")
    pr = frappe.get_doc({
        "doctype": "Purchase Receipt",
        "supplier": supplier, "company": ctx.company, "set_warehouse": ctx.warehouse,
        "items": [{"item_code": item_code, "qty": qty, "rate": 10, "warehouse": ctx.warehouse}],
    })
    pr.insert(ignore_permissions=True)
    pr.submit()

    batch_no = frappe.db.get_value(
        "Batch", {"reference_doctype": "Purchase Receipt", "reference_name": pr.name, "item": item_code}, "name"
    )
    assert batch_no, f"Expected the PR to auto-create a batch for {item_code}"
    print(f"  Item {item_code}: PR {pr.name} auto-created batch {batch_no}, status={pr.custom_inspection_status}")
    return pr, batch_no


def run():
    ctx = get_ctx()
    from manufyxinvenzaerp.production_management.doctype.material_planning.material_planning import (
        reserve_batches, reserve_exact_match_batches,
    )

    # ── Scenario A: material_mapping / reserve_batches ──────────────────────
    item_a = "ZZTEST-INSP-GATE-A"
    pr_a, batch_a = _make_inspected_item_and_pr(ctx, item_a, qty=10)
    assert pr_a.custom_inspection_status != "Completed", "Fresh PR should not already be Completed"

    item_a2 = ensure_item(ctx, "ZZTEST-INSP-GATE-A-PLAIN", "Plain Reservable Item", uom="Kg")
    batch_a2 = ensure_batch(item_a2, "ZZTEST-INSP-GATE-A-PLAIN-BATCH", sec_qty=1)
    make_receipt(ctx, item_a2, batch_a2, 5)

    mp = frappe.new_doc("Material Planning")
    mp.company = ctx.company
    mp.posting_date = today()
    mp.for_warehouse = ctx.warehouse
    mp.append("material_mapping", {
        "item_code": item_a, "item_name": item_a,
        "parent_item_group": "Nuts and Bolts", "unit_weight": 1,
        "qty": 10, "uom": "Kg", "sec_qty": 10, "sec_uom": "Nos",
        "batch": batch_a, "batch_calc_qty": 0,
    })
    mp.append("material_mapping", {
        "item_code": item_a2, "item_name": item_a2,
        "parent_item_group": ctx.item_group, "unit_weight": 0,
        "qty": 5, "uom": "Kg", "sec_qty": 1, "sec_uom": "Nos",
        "batch": batch_a2, "batch_calc_qty": 0,
    })
    mp.insert(ignore_permissions=True)
    print("Created MP:", mp.name)

    result = reserve_batches(mp.name)
    row = next(r for r in result["rows"] if r["batch"] == batch_a)
    row2 = next(r for r in result["rows"] if r["batch"] == batch_a2)
    print("Reserve attempt while PR inspection Open -- gated row is_reserved (expect 0):", row["is_reserved"],
          "| plain row is_reserved (expect 1):", row2["is_reserved"],
          "| blocked:", [b["batch"] for b in result.get("blocked", [])])
    assert row["is_reserved"] == 0, "Row must stay unreserved while inspection is not Completed"
    assert row2["is_reserved"] == 1, "The ordinary row should still reserve normally in the same call"
    assert any(b["batch"] == batch_a for b in result.get("blocked", [])), "Row should be reported as blocked"

    frappe.db.set_value("Purchase Receipt", pr_a.name, "custom_inspection_status", "Completed")
    result = reserve_batches(mp.name)
    row = next(r for r in result["rows"] if r["batch"] == batch_a)
    print("Reserve attempt after PR inspection Completed -- is_reserved (expect 1):", row["is_reserved"],
          "| reserved_qty:", row["reserved_qty"])
    assert row["is_reserved"] == 1, "Row should now reserve once inspection is Completed"
    assert flt(row["reserved_qty"]) == 10

    # A Material Planning where the ONLY unreserved row is inspection-blocked
    # must throw with a clear, inspection-specific message.
    item_a3 = "ZZTEST-INSP-GATE-A3"
    pr_a3, batch_a3 = _make_inspected_item_and_pr(ctx, item_a3, qty=6)
    mp_solo = frappe.new_doc("Material Planning")
    mp_solo.company = ctx.company
    mp_solo.posting_date = today()
    mp_solo.for_warehouse = ctx.warehouse
    mp_solo.append("material_mapping", {
        "item_code": item_a3, "item_name": item_a3,
        "parent_item_group": "Nuts and Bolts", "unit_weight": 1,
        "qty": 6, "uom": "Kg", "sec_qty": 6, "sec_uom": "Nos",
        "batch": batch_a3, "batch_calc_qty": 0,
    })
    mp_solo.insert(ignore_permissions=True)
    threw = False
    try:
        reserve_batches(mp_solo.name)
    except frappe.ValidationError as e:
        threw = True
        print("Solo blocked row -- throws (expect True):", threw, "| message:", str(e)[:150])
    assert threw, "Expected reserve_batches to throw when every unreserved row is inspection-blocked"

    # ── Scenario B: available_raw_materials / reserve_exact_match_batches ───
    item_b = "ZZTEST-INSP-GATE-B"
    pr_b, batch_b = _make_inspected_item_and_pr(ctx, item_b, qty=8)

    item_b2 = ensure_item(ctx, "ZZTEST-INSP-GATE-B-PLAIN", "Plain Reservable Item B", uom="Kg")
    batch_b2 = ensure_batch(item_b2, "ZZTEST-INSP-GATE-B-PLAIN-BATCH", sec_qty=1)
    make_receipt(ctx, item_b2, batch_b2, 4)

    mp2 = frappe.new_doc("Material Planning")
    mp2.company = ctx.company
    mp2.posting_date = today()
    mp2.for_warehouse = ctx.warehouse
    mp2.append("available_raw_materials", {
        "item_code": item_b, "item_name": item_b,
        "parent_item_group": "Nuts and Bolts",
        "required_qty": 8, "uom": "Kg", "sec_qty": 8, "sec_uom": "Nos",
        "batch_no": batch_b,
    })
    mp2.append("available_raw_materials", {
        "item_code": item_b2, "item_name": item_b2,
        "parent_item_group": ctx.item_group,
        "required_qty": 4, "uom": "Kg", "sec_qty": 1, "sec_uom": "Nos",
        "batch_no": batch_b2,
    })
    mp2.insert(ignore_permissions=True)
    print("Created MP2:", mp2.name)

    result2 = reserve_exact_match_batches(mp2.name)
    row2 = next(r for r in result2["rows"] if r["batch_no"] == batch_b)
    row2b = next(r for r in result2["rows"] if r["batch_no"] == batch_b2)
    print("Exact Match reserve attempt while PR inspection Open -- gated row is_reserved (expect 0):", row2["is_reserved"],
          "| plain row is_reserved (expect 1):", row2b["is_reserved"],
          "| blocked:", [b["batch"] for b in result2.get("blocked", [])])
    assert row2["is_reserved"] == 0
    assert row2b["is_reserved"] == 1
    assert any(b["batch"] == batch_b for b in result2.get("blocked", []))

    frappe.db.set_value("Purchase Receipt", pr_b.name, "custom_inspection_status", "Completed")
    result2 = reserve_exact_match_batches(mp2.name)
    row2 = next(r for r in result2["rows"] if r["batch_no"] == batch_b)
    print("Exact Match reserve attempt after PR inspection Completed -- is_reserved (expect 1):", row2["is_reserved"])
    assert row2["is_reserved"] == 1

    # ── Scenario C1: item does NOT require inspection -- reserves normally
    # regardless of any linked PR's inspection status. ──────────────────────
    item_c = ensure_item(ctx, "ZZTEST-INSP-GATE-NOREQ", "No Inspection Required Item", uom="Kg")
    frappe.db.set_value("Item", item_c, "custom_inspection_required", 0)
    batch_c = ensure_batch(item_c, "ZZTEST-INSP-GATE-NOREQ-BATCH", sec_qty=1)
    make_receipt(ctx, item_c, batch_c, 20)

    mp3 = frappe.new_doc("Material Planning")
    mp3.company = ctx.company
    mp3.posting_date = today()
    mp3.for_warehouse = ctx.warehouse
    mp3.append("material_mapping", {
        "item_code": item_c, "item_name": item_c,
        "parent_item_group": ctx.item_group, "unit_weight": 0,
        "qty": 20, "uom": "Kg", "sec_qty": 1, "sec_uom": "Nos",
        "batch": batch_c, "batch_calc_qty": 0,
    })
    mp3.insert(ignore_permissions=True)
    result3 = reserve_batches(mp3.name)
    row3 = next(r for r in result3["rows"] if r["batch"] == batch_c)
    print("Item without custom_inspection_required -- is_reserved (expect 1):", row3["is_reserved"])
    assert row3["is_reserved"] == 1
    assert not result3.get("blocked")

    # ── Scenario C2: item requires inspection but the batch has NO
    # traceable source Purchase Receipt (e.g. excess-return style, or a
    # plain manually-created batch) -- must NOT be blocked (fail-open). ─────
    item_d = ensure_item(ctx, "ZZTEST-INSP-GATE-NOPR", "Inspection Required But No PR Item", uom="Kg")
    frappe.db.set_value("Item", item_d, "custom_inspection_required", 1)
    batch_d = ensure_batch(item_d, "ZZTEST-INSP-GATE-NOPR-BATCH", sec_qty=1)
    make_receipt(ctx, item_d, batch_d, 15)
    batch_d_ref = frappe.db.get_value("Batch", batch_d, ["reference_doctype", "reference_name"], as_dict=True)
    print("Batch with no traceable PR -- reference_doctype:", batch_d_ref.reference_doctype)
    assert batch_d_ref.reference_doctype != "Purchase Receipt", "This batch must NOT trace to a Purchase Receipt for this scenario"

    mp4 = frappe.new_doc("Material Planning")
    mp4.company = ctx.company
    mp4.posting_date = today()
    mp4.for_warehouse = ctx.warehouse
    mp4.append("material_mapping", {
        "item_code": item_d, "item_name": item_d,
        "parent_item_group": ctx.item_group, "unit_weight": 0,
        "qty": 15, "uom": "Kg", "sec_qty": 1, "sec_uom": "Nos",
        "batch": batch_d, "batch_calc_qty": 0,
    })
    mp4.insert(ignore_permissions=True)
    result4 = reserve_batches(mp4.name)
    row4 = next(r for r in result4["rows"] if r["batch"] == batch_d)
    print("Inspection-required item, batch with no source PR -- is_reserved (expect 1, fail-open):", row4["is_reserved"])
    assert row4["is_reserved"] == 1
    assert not result4.get("blocked")

    frappe.db.commit()
    print("\nALL CHECKS DONE — batch reservation is correctly blocked while the source Purchase "
          "Receipt's inspection is not Completed (both Material Mapping and Exact Match tables), "
          "succeeds once Completed, and stays unaffected for items that don't require inspection or "
          "batches with no traceable source Purchase Receipt.")
    print("Test data left in place:", mp.name, mp2.name, mp3.name, mp4.name, mp_solo.name,
          pr_a.name, pr_a3.name, pr_b.name, batch_a, batch_a2, batch_a3, batch_b, batch_b2, batch_c, batch_d)
