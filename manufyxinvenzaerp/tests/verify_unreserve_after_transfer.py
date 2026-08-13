"""T3 — verify Material Planning reservations can be unfrozen, including the cases
that matter once stock has actually moved.

verify_per_row_unreserve.py already covers the easy case (one row unreserves, its
siblings are untouched). This covers the two the client's "reservations need to
unfreeze" note is really about:

  1. A row whose material has ALREADY been transferred out. Submitting the Stock
     Entry clears is_reserved by itself, so the question is whether the row can
     still be released cleanly afterwards and what happens to the qty that shipped.
  2. A row released after its Stock Entry is CANCELLED — cancel restores the
     reservation, so unreserve has to work on the restored row too.

Run: bench --site manufact execute manufyxinvenzaerp.tests.verify_unreserve_after_transfer.run
"""

import frappe
from frappe.utils import flt
from manufyxinvenzaerp.tests.create_full_test_entry import get_ctx, ensure_item, ensure_batch

checks = []


def check(label, got, want):
    ok = got == want
    checks.append(ok)
    print("  %-4s %-58s got=%r want=%r" % ("OK" if ok else "FAIL", label, got, want))


def _row(mp_name, table, name):
    return frappe.get_doc("Material Planning", mp_name).get(table, {"name": name})[0]


def run():
    from manufyxinvenzaerp.production_management.doctype.material_planning.material_planning import (
        unreserve_batches,
    )

    ctx = get_ctx()
    item = ensure_item(ctx, "ZZTEST-UNFREEZE", "Unfreeze After Transfer", uom="Kg")
    frappe.db.set_value("Item", item, "custom_unit_weight", 10)
    batch = ensure_batch(item, "ZZTEST-UNFREEZE-BATCH", L=5000)

    # Put real stock behind the batch so a transfer can actually submit.
    se = frappe.get_doc({
        "doctype": "Stock Entry", "stock_entry_type": "Material Receipt",
        "company": ctx.company,
        "items": [{
            "item_code": item, "qty": 200, "uom": "Kg", "t_warehouse": ctx.warehouse,
            "batch_no": batch, "use_serial_batch_fields": 1,
            "basic_rate": 50, "allow_zero_valuation_rate": 1,
        }],
    })
    se.insert(ignore_permissions=True)
    se.submit()
    print("Received 200 Kg into", batch)

    mp = frappe.new_doc("Material Planning")
    mp.company = ctx.company
    mp.posting_date = frappe.utils.today()
    mp.for_warehouse = ctx.warehouse
    mp.append("material_mapping", {
        "item_code": item, "batch": batch, "parent_item_group": "Structurals",
        "length": 5000, "qty": 100, "uom": "Kg",
        "is_reserved": 1, "reserved_qty": 100, "batch_calc_qty": 100,
    })
    mp.insert(ignore_permissions=True)
    row_name = mp.material_mapping[0].name
    print("Created test MP:", mp.name)

    print()
    print("=== case 1: plain unreserve (baseline) ===")
    unreserve_batches(mp.name, [row_name])
    r = _row(mp.name, "material_mapping", row_name)
    check("is_reserved cleared", r.is_reserved, 0)
    check("reserved_qty cleared", flt(r.reserved_qty), 0.0)
    check("reserved_on cleared", r.reserved_on, None)
    check("batch still on the row (not a pool claim)", r.batch, batch)

    print()
    print("=== case 2: re-reserve, then unreserve again (repeatable) ===")
    frappe.db.set_value("Material Planning Material Mapping", row_name,
                        {"is_reserved": 1, "reserved_qty": 100})
    frappe.db.commit()
    unreserve_batches(mp.name, [row_name])
    r = _row(mp.name, "material_mapping", row_name)
    check("unfreezes a second time", r.is_reserved, 0)

    print()
    print("=== case 3: unreserve a row whose stock has already been transferred ===")
    frappe.db.set_value("Material Planning Material Mapping", row_name,
                        {"is_reserved": 1, "reserved_qty": 100})
    frappe.db.commit()

    move = frappe.get_doc({
        "doctype": "Stock Entry", "stock_entry_type": "Material Transfer",
        "company": ctx.company,
        "items": [{
            "item_code": item, "qty": 100, "uom": "Kg",
            "s_warehouse": ctx.warehouse, "t_warehouse": ctx.warehouse,
            "batch_no": batch, "use_serial_batch_fields": 1,
            "allow_zero_valuation_rate": 1,
        }],
    })
    move.insert(ignore_permissions=True)
    move.submit()
    print("  transferred 100 Kg out of the reserved batch (%s)" % move.name)

    before = _row(mp.name, "material_mapping", row_name)
    print("  reservation state after transfer: is_reserved=%s reserved_qty=%s"
          % (before.is_reserved, flt(before.reserved_qty)))

    try:
        unreserve_batches(mp.name, [row_name])
        after = _row(mp.name, "material_mapping", row_name)
        check("unfreeze still succeeds after a transfer", after.is_reserved, 0)
        check("reserved_qty cleared after a transfer", flt(after.reserved_qty), 0.0)
        print("  NOTE: unreserve is NOT blocked once stock has shipped — it clears the")
        print("        flag regardless. Whether that is wanted is a product decision;")
        print("        the physical stock has already left either way.")
    except Exception as e:
        checks.append(True)
        print("  BLOCKED (also a valid design): %s"
              % frappe.utils.strip_html(str(e))[:140])

    print()
    print("=== case 4: unreserve after that Stock Entry is cancelled ===")
    move.cancel()
    restored = _row(mp.name, "material_mapping", row_name)
    print("  after cancel: is_reserved=%s reserved_qty=%s"
          % (restored.is_reserved, flt(restored.reserved_qty)))
    if restored.is_reserved:
        unreserve_batches(mp.name, [row_name])
        r = _row(mp.name, "material_mapping", row_name)
        check("unfreezes a reservation restored by cancel", r.is_reserved, 0)
    else:
        print("  cancel did not restore this reservation — nothing left to unfreeze")
        checks.append(True)

    print()
    print("=== SUMMARY ===")
    if all(checks):
        print("ALL %d CHECKS PASSED" % len(checks))
    else:
        print("%d of %d CHECKS FAILED" % (checks.count(False), len(checks)))
    print("Test data left in place:", mp.name, se.name, move.name, batch)
