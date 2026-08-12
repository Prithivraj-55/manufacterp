"""Reservations must be released when their material physically leaves, and restored
if that entry is cancelled -- on BOTH Material Planning tables.

Two defects found by auditing the live site: batches showed as reserved with zero stock
on hand, which under-reports free qty to every later plan.

  1. 'Send to Subcontractor' was not in the list of Stock Entry types that release
     reservations -- and it is THE primary transfer in this flow, Stores to supplier.
     The main path released nothing at all.

  2. The finished-goods entry sets only the core `subcontracting_order` field, so the
     plan could not be resolved from it and the code fell through to a fallback that
     covered Material Mapping only. Exact-match (Available Raw Material) reservations
     were left held forever.

Run: bench --site manufact execute manufyxinvenzaerp.tests.verify_reservation_release_on_transfer.run
"""

import frappe
from frappe.utils import flt
from manufyxinvenzaerp.tests.create_full_test_entry import get_ctx, ensure_item, ensure_batch

checks = []


def check(label, got, want):
    ok = got == want
    checks.append(ok)
    print("  %-4s %-58s got=%r want=%r" % ("OK" if ok else "FAIL", label, got, want))


def _reserved(mp, table, row):
    return frappe.db.get_value(table, row, "is_reserved")


def run():
    from manufyxinvenzaerp.production_management.stock_entry import (
        RESERVATION_RELEASING_SE_TYPES, _linked_material_plannings,
    )

    print("=== the transfer types that release a reservation ===")
    for t in ("Send to Subcontractor", "Material Transfer", "Manufacture",
              "Material Issue", "Repack"):
        check("%s releases" % t, t in RESERVATION_RELEASING_SE_TYPES, True)
    check("an unrelated type does not", "Material Receipt" in RESERVATION_RELEASING_SE_TYPES, False)

    print()
    print("=== a plan is resolvable from the core subcontracting_order field ===")
    sco = frappe.db.get_value("Subcontracting Order", {"custom_production_plan": ["!=", ""]}, "name")
    if sco:
        fake = frappe._dict(subcontracting_order=sco, items=[])
        fake.get = lambda f, *a, **k: fake[f] if f in fake else None
        mps = _linked_material_plannings(fake)
        check("resolved via subcontracting_order alone", bool(mps), True)
        print("       %s -> %s" % (sco, sorted(mps)))
    else:
        print("   (skipped -- no Subcontracting Order with a Production Plan on this site)")

    print()
    print("=== end to end: reserve on both tables, ship it, cancel it ===")
    ctx = get_ctx()
    item = ensure_item(ctx, "ZZTEST-RELEASE", "Reservation Release", uom="Kg")
    frappe.db.set_value("Item", item, "custom_unit_weight", 10)
    suffix = frappe.generate_hash(length=6).upper()
    b_mm = ensure_batch(item, "ZZTEST-REL-MM-%s" % suffix, L=5000)
    b_arm = ensure_batch(item, "ZZTEST-REL-ARM-%s" % suffix, L=5000)

    for b in (b_mm, b_arm):
        r = frappe.get_doc({
            "doctype": "Stock Entry", "stock_entry_type": "Material Receipt",
            "company": ctx.company,
            "items": [{"item_code": item, "qty": 100, "uom": "Kg", "t_warehouse": ctx.warehouse,
                       "batch_no": b, "use_serial_batch_fields": 1,
                       "basic_rate": 50, "allow_zero_valuation_rate": 1}],
        })
        r.insert(ignore_permissions=True)
        r.submit()

    mp = frappe.new_doc("Material Planning")
    mp.company = ctx.company
    mp.posting_date = frappe.utils.today()
    mp.for_warehouse = ctx.warehouse
    mp.append("material_mapping", {
        "item_code": item, "batch": b_mm, "parent_item_group": "Structurals",
        "length": 5000, "qty": 100, "uom": "Kg",
        "is_reserved": 1, "reserved_qty": 100, "batch_calc_qty": 100,
    })
    mp.append("available_raw_materials", {
        "item_code": item, "batch_no": b_arm, "parent_item_group": "Structurals",
        "length": 5000, "sec_qty": 2, "required_qty": 100, "overall_required_qty": 100,
        "uom": "Kg", "is_reserved": 1, "reserved_qty": 100,
    })
    mp.insert(ignore_permissions=True)
    mm_row, arm_row = mp.material_mapping[0].name, mp.available_raw_materials[0].name
    print("   MP:", mp.name)

    check("Material Mapping starts reserved",
          _reserved(mp.name, "Material Planning Material Mapping", mm_row), 1)
    check("Exact Match starts reserved",
          _reserved(mp.name, "Material Planning Available Raw Material", arm_row), 1)

    # Ship both batches on a Send to Subcontractor -- the path that released nothing.
    target_wh = frappe.db.get_value(
        "Warehouse", {"company": ctx.company, "is_group": 0, "name": ["!=", ctx.warehouse]}, "name")
    if not target_wh:
        print("   (skipped -- this company has only one leaf warehouse)")
        return
    se = frappe.get_doc({
        "doctype": "Stock Entry", "stock_entry_type": "Send to Subcontractor",
        "company": ctx.company,
        "items": [
            {"item_code": item, "qty": 100, "uom": "Kg", "s_warehouse": ctx.warehouse,
             "t_warehouse": target_wh, "batch_no": b, "use_serial_batch_fields": 1,
             "allow_zero_valuation_rate": 1}
            for b in (b_mm, b_arm)
        ],
    })
    se.insert(ignore_permissions=True)
    se.submit()
    print("   shipped on", se.name, "(Send to Subcontractor)")

    check("Material Mapping released on transfer",
          _reserved(mp.name, "Material Planning Material Mapping", mm_row), 0)
    check("Exact Match released on transfer",
          _reserved(mp.name, "Material Planning Available Raw Material", arm_row), 0)

    se.cancel()
    print("   cancelled", se.name)
    check("Material Mapping restored on cancel",
          _reserved(mp.name, "Material Planning Material Mapping", mm_row), 1)
    check("Exact Match restored on cancel",
          _reserved(mp.name, "Material Planning Available Raw Material", arm_row), 1)

    print()
    print("=== SUMMARY ===")
    if all(checks):
        print("ALL %d CHECKS PASSED" % len(checks))
    else:
        print("%d of %d CHECKS FAILED" % (checks.count(False), len(checks)))
    print("Test data left in place:", mp.name, b_mm, b_arm, se.name)
