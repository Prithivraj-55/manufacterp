"""The Job Work Order's Operations tab shows what is LEFT to consume, not what arrived.

An operation that had consumed all eight of its pieces read "Available 8, Consumed 8" --
the same eight in two columns, one of which had already been used up. Read down the
Available column of a finished job and every row still offered its full quantity, which
is the one thing that column must never do.

The figure the drawing rows hold, available_to_consume_nos, is what the PREVIOUS
operation handed over. It does not move as this operation works, so the consumption is
taken off in the summary. The gross stays beside it -- "0.000 of 8.000" -- because
"nothing left" and "nothing ever arrived" are different problems and used to look
identical.

Op-1 is left alone: it consumes weight off the rack, not pieces, so its Available is in
Kg and there is nothing in Nos to deduct.

Difference is now measured from Overall Qty on every row. It used to be measured from
Available on Op-2+, which is what the Available column now shows -- a column that agrees
with its neighbour by construction tells you nothing. Against Overall Qty it answers what
the row is really asked: how many of this job's pieces does this operation still owe.

Run: bench --site manufact execute manufyxinvenzaerp.tests.verify_soe_summary_available.run
"""

import frappe
from frappe.utils import flt

from manufyxinvenzaerp.subcontracting_management.subcontracting import get_soe_summary

checks = []


def check(label, got, want):
    ok = got == want
    checks.append(ok)
    print("  %-4s %-52s got=%r want=%r" % ("OK" if ok else "FAIL", label, got, want))


def run():
    sco = frappe.db.get_value("Subcontracting Order", {"docstatus": 1}, "name")
    if not sco:
        print("=== no submitted Job Work Order on this site ===")
        _check_the_wiring()
        _summary()
        return

    rows = get_soe_summary(sco)
    print("=== %s ===" % sco)
    print("  %-4s %-14s %10s %12s %10s %10s %10s" % (
        "seq", "operation", "overall", "avail", "of", "consumed", "diff"))
    for d in rows:
        print("  %-4s %-14s %10.3f %12.3f %10.3f %10.3f %10.3f" % (
            d.sequence_id, d.operation, d.total_qty_to_mfg, d.avail_nos,
            d.avail_gross_nos, d.total_completed_nos, d.diff_nos))

    print()
    print("=== Op-2 onward: available is net of what this operation consumed ===")
    later = [d for d in rows if (d.sequence_id or 1) > 1]
    if not later:
        print("   This job has only one operation.")
    for d in later:
        check("%s: %s less %s" % (d.operation, d.avail_gross_nos, d.total_completed_nos),
              flt(d.avail_nos, 3),
              flt(flt(d.avail_gross_nos) - flt(d.total_completed_nos), 3))
    fully = [d for d in later
             if d.total_completed_nos and flt(d.total_completed_nos, 3) >= flt(d.avail_gross_nos, 3)]
    if fully:
        check("an operation that consumed everything offers nothing",
              [flt(d.avail_nos, 3) for d in fully], [0.0] * len(fully))
    else:
        print("   No operation on this job has consumed everything it was handed.")
    untouched = [d for d in later if not flt(d.total_completed_nos)]
    if untouched:
        check("and one that has consumed nothing still offers it all",
              [flt(d.avail_nos, 3) for d in untouched],
              [flt(d.avail_gross_nos, 3) for d in untouched])

    print()
    print("=== Op-1 is in Kg and is not deducted ===")
    first = next((d for d in rows if (d.sequence_id or 1) == 1), None)
    if first:
        check("available is the weight transferred, untouched",
              flt(first.avail_nos, 3), flt(first.avail_gross_nos, 3))
        check("which is not the pieces it completed",
              flt(first.avail_nos, 3) == flt(first.total_completed_nos, 3), False)

    print()
    print("=== Difference is measured the same way on every row ===")
    for d in rows:
        check("%s: overall less consumed" % d.operation, flt(d.diff_nos, 3),
              flt(flt(d.total_qty_to_mfg) - flt(d.total_completed_nos), 3))

    _check_the_wiring()
    _summary()


def _check_the_wiring():
    print()
    print("=== and the grid shows both numbers ===")
    src = open(frappe.get_app_path("manufyxinvenzaerp", "setup.py")).read()
    check("the gross is carried to the client", "avail_gross_nos" in src, True)
    check("shown as \"of <gross>\" once something is consumed",
          'consumed ? " <small class' in src, True)
    check("over-consumption shows red", "avail < 0 ?" in src, True)
    check("and the footnote says what Available means",
          "what is still left to consume" in src, True)

    py = open(frappe.get_app_path("manufyxinvenzaerp", "subcontracting_management",
                                  "subcontracting.py")).read()
    check("the deduction happens once, on the server",
          'soe["avail_nos"] = flt(soe["avail_gross_nos"]) - flt(soe["total_completed_nos"])' in py,
          True)


def _summary():
    print()
    print("=== SUMMARY ===")
    if all(checks):
        print("ALL %d CHECKS PASSED" % len(checks))
    else:
        print("%d of %d CHECKS FAILED" % (checks.count(False), len(checks)))
