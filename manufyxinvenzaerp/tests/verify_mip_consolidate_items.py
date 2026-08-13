"""T8a — the Material Issue Plan's Consolidate Items table.

One row per item + batch, merged, describing what will physically move. Grouped by
(item, batch, CNC leg), which is as far as consolidation can go: a Stock Entry names a
specific batch, so two batches of one item stay two rows -- merging them would produce
a line that cannot be turned into a transfer.

What the client actually reported was ordering, not arithmetic: rows of one item were
scattered, which made two legitimate batch lines read as a duplicate with a wrong
total. So the sort is part of the contract and is asserted here.

Run: bench --site manufact execute manufyxinvenzaerp.tests.verify_mip_consolidate_items.run
"""

import frappe
from frappe.utils import flt

checks = []


def check(label, got, want):
    ok = got == want
    checks.append(ok)
    print("  %-4s %-58s got=%r want=%r" % ("OK" if ok else "FAIL", label, got, want))


def run():
    from manufyxinvenzaerp.subcontracting_management.doctype.material_issue_plan.material_issue_plan import (
        _sync_consolidate_items,
    )

    print("=== grouping, on a synthetic plan ===")
    # Deliberately scattered, and with an alternate-item row: the requirement is
    # ISMB450 but the batch belongs to ISA150, so it must land under ISA150.
    mip = frappe._dict(
        source_warehouse=None,
        raw_materials=[
            frappe._dict(item_code="ISM150", planned_item=None, batch_no="B-2", duno_mark_no="1B9",
                         sec_qty=1, qty=100, transferred_qty=0, cnc_process=0,
                         parent_item_group="Structurals", length=5000, width=0, thickness=0,
                         unit_weight=10, sec_uom="Nos", uom="Kg"),
            frappe._dict(item_code="ISM100", planned_item=None, batch_no="B-1", duno_mark_no="1B1",
                         sec_qty=2, qty=200, transferred_qty=0, cnc_process=0,
                         parent_item_group="Structurals", length=5000, width=0, thickness=0,
                         unit_weight=10, sec_uom="Nos", uom="Kg"),
            frappe._dict(item_code="ISM150", planned_item=None, batch_no="B-1", duno_mark_no="1B5",
                         sec_qty=3, qty=300, transferred_qty=0, cnc_process=0,
                         parent_item_group="Structurals", length=5000, width=0, thickness=0,
                         unit_weight=10, sec_uom="Nos", uom="Kg"),
            # same item AND batch as the second row -> must merge into it
            frappe._dict(item_code="ISM100", planned_item=None, batch_no="B-1", duno_mark_no="1B3",
                         sec_qty=1, qty=50, transferred_qty=0, cnc_process=0,
                         parent_item_group="Structurals", length=5000, width=0, thickness=0,
                         unit_weight=10, sec_uom="Nos", uom="Kg"),
            # alternate item: requirement ISMB450, batch belongs to ISA150
            frappe._dict(item_code="ISMB450", planned_item="ISA150", batch_no="B-9", duno_mark_no="1B5",
                         sec_qty=1, qty=75, transferred_qty=0, cnc_process=0,
                         parent_item_group="Structurals", length=6900, width=0, thickness=0,
                         unit_weight=10, sec_uom="Nos", uom="Kg"),
            # no batch allocated yet -> nothing to move, must be excluded
            frappe._dict(item_code="ISM200", planned_item=None, batch_no=None, duno_mark_no="1B7",
                         sec_qty=5, qty=500, transferred_qty=0, cnc_process=0,
                         parent_item_group="Structurals", length=5000, width=0, thickness=0,
                         unit_weight=10, sec_uom="Nos", uom="Kg"),
        ],
        consolidate_items=[],
    )
    mip.set = lambda f, v: mip.__setitem__(f, v)
    mip.append = lambda f, v: mip[f].append(frappe._dict(v))
    mip.get = lambda f, *a, **k: mip[f] if f in mip else None

    _sync_consolidate_items(mip)
    rows = mip.consolidate_items
    got = [(r.item_code, r.batch_no, flt(r.qty), flt(r.sec_qty), r.source_rows) for r in rows]
    for r in got:
        print("     ", r)

    check("6 raw rows -> 4 consolidated", len(rows), 4)
    check("same item+batch merged (ISM100/B-1: 200+50)",
          [r for r in got if r[0] == "ISM100"], [("ISM100", "B-1", 250.0, 3.0, 2)])
    check("two batches of one item stay two rows",
          len([r for r in got if r[0] == "ISM150"]), 2)
    check("alternate item lands under the BATCH's item",
          [r[0] for r in got if r[1] == "B-9"], ["ISA150"])
    check("a row with no batch is excluded",
          any(r[0] == "ISM200" for r in got), False)

    print()
    print("=== ordering: an item's rows must sit together ===")
    order = [r[0] for r in got]
    print("      ", order)
    check("sorted by item then batch", order, sorted(order))
    contiguous = all(order.index(v) + order.count(v) > i for i, v in enumerate(order))
    check("no item is split apart by another", contiguous, True)

    print()
    print("=== DUNOs of merged rows are all kept ===")
    ism100 = next(r for r in rows if r.item_code == "ISM100")
    check("both drawings named", sorted(ism100.duno_mark_no.split(", ")), ["1B1", "1B3"])

    print()
    print("=== against the live plan: totals must reconcile ===")
    live = frappe.db.get_value("Material Issue Plan", {"docstatus": ["!=", 2]}, "name")
    if live:
        doc = frappe.get_doc("Material Issue Plan", live)
        raw_total = flt(sum(flt(r.qty) for r in doc.raw_materials if r.batch_no), 3)
        con_total = flt(sum(flt(r.qty) for r in doc.consolidate_items), 3)
        print("      %s: %d raw rows -> %d consolidated" % (live, len(doc.raw_materials), len(doc.consolidate_items)))
        check("consolidated Kg equals the batched raw-material Kg", con_total, raw_total)
        live_order = [r.item_code for r in doc.consolidate_items]
        check("live rows are sorted too", live_order, sorted(live_order))
    else:
        print("   (skipped -- no Material Issue Plan on this site)")

    print()
    print("=== SUMMARY ===")
    if all(checks):
        print("ALL %d CHECKS PASSED" % len(checks))
    else:
        print("%d of %d CHECKS FAILED" % (checks.count(False), len(checks)))
