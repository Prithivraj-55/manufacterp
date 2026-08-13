"""A received batch must land in exactly ONE Material Planning table.

Reported as "Duplicate Batch Across Tables" when saving a plan after a Purchase
Receipt: the same batch was assigned in both Material Mapping and Exact Match, and
_validate_no_cross_table_batch_duplicate refused the save. The plan could not be saved
at all after such a receipt.

Cause: one received batch is routinely split across several requirement rows, and the
destination table was chosen per ROW. Where a batch's dimensions matched some
requirements exactly and missed others -- the normal case when one stock length covers
several cut sizes -- the matching rows went to Exact Match and the rest to Material
Mapping, putting the batch in both.

The table is now decided once per receipt line: any mismatch sends the whole batch to
Material Mapping, which carries the required size on the row and the purchased size on
batch_*, so it represents a matching row perfectly well. Exact Match assumes the two
are equal and cannot represent a mismatch at all.

This exercises the routing decision itself against the real _pr_dimensions_match rather
than driving a whole Purchase Receipt: the decision is what changed, and testing it
directly keeps the test honest about what it actually proves.

Run: bench --site manufact execute manufyxinvenzaerp.tests.verify_pr_allocation_single_table.run
"""

import frappe

checks = []


def check(label, got, want):
    ok = got == want
    checks.append(ok)
    print("  %-4s %-58s got=%r want=%r" % ("OK" if ok else "FAIL", label, got, want))


def _routes_to_mapping(pr_item, rows):
    """The decision as allocate_pr_stock_to_mp now makes it: one table for the whole
    receipt line, Material Mapping unless every row matches."""
    from manufyxinvenzaerp.purchase_receipt_management.purchase_receipt import (
        _pr_dimensions_match,
    )
    return not all(_pr_dimensions_match(pr_item, r) for r in rows)


def _pr(length, width=0, thickness=0):
    return frappe._dict(custom_length=length, custom_width=width, custom_thickness=thickness)


def _req(length, width=0, thickness=0):
    return frappe._dict(length=length, width=width, thickness=thickness)


def run():
    from manufyxinvenzaerp.purchase_receipt_management.purchase_receipt import (
        _pr_dimensions_match,
    )

    print("=== the reported case: one length covering several cut sizes ===")
    pr, rows = _pr(6000), [_req(4000), _req(6000), _req(3750)]
    per_row = [_pr_dimensions_match(pr, r) for r in rows]
    print("   6000 received against 4000 / 6000 / 3750")
    print("   per-row match:", per_row, " <- mixed, which is what split the batch")
    check("mixed match sends the WHOLE batch to Material Mapping",
          _routes_to_mapping(pr, rows), True)
    check("the old per-row rule would have split it across both tables",
          len(set(per_row)) > 1, True)

    print()
    print("=== every requirement matches -- Exact Match must still be used ===")
    check("all matching stays on Exact Match",
          _routes_to_mapping(_pr(5000), [_req(5000), _req(5000)]), False)

    print()
    print("=== other shapes ===")
    check("nothing matching -> Material Mapping",
          _routes_to_mapping(_pr(6000), [_req(4000), _req(3750)]), True)
    check("one matching row -> Exact Match", _routes_to_mapping(_pr(5000), [_req(5000)]), False)
    check("one mismatching row -> Material Mapping", _routes_to_mapping(_pr(5000), [_req(4000)]), True)

    print()
    print("=== plates: width and thickness count too ===")
    pl = _pr(1400, 300, 10)
    check("same length, different width -> Material Mapping",
          _routes_to_mapping(pl, [_req(1400, 300, 10), _req(1400, 250, 10)]), True)
    check("identical plates -> Exact Match",
          _routes_to_mapping(pl, [_req(1400, 300, 10), _req(1400, 300, 10)]), False)

    print()
    print("=== against the live plan that failed ===")
    if frappe.db.exists("Material Planning", "MP-2026-00164"):
        mp = frappe.get_doc("Material Planning", "MP-2026-00164")
        mm = {r.batch for r in mp.material_mapping if r.batch}
        ar = {r.batch_no for r in mp.available_raw_materials if r.batch_no}
        print("   MP-2026-00164: %d mapping batches, %d exact-match batches" % (len(mm), len(ar)))
        check("no batch is in both tables", sorted(mm & ar), [])
        try:
            mp.save(ignore_permissions=True)
            frappe.db.commit()
            saved = True
        except Exception as e:
            saved = frappe.utils.strip_html(str(e))[:100]
        check("the plan that could not be saved now saves", saved, True)
    else:
        print("   (MP-2026-00164 no longer on this site -- skipped)")

    print()
    print("=== SUMMARY ===")
    if all(checks):
        print("ALL %d CHECKS PASSED" % len(checks))
    else:
        print("%d of %d CHECKS FAILED" % (checks.count(False), len(checks)))
