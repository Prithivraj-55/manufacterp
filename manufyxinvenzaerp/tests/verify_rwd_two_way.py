"""Reserve stock without dimensions: which figure is typed, and which is worked out.

On a Material Issue Plan's "Update Batch" dialog the checkbox now swaps the two
figures over:

  unticked   Sec Qty (Nos) is typed; Calc Qty (Kg) follows from it and the batch's
             dimensions. Four pieces of a 500 x 250 x 5 plate come to 19.625 Kg, and
             anything above the row's Required Qty is excess.
  ticked     Calc Qty (Kg) shows the row's own Required Qty -- that is what gets
             reserved -- and Sec Qty (Nos) is worked back out of it, fractional on
             purpose, shown before anything is reserved rather than after.

The figure the dialog shows has to be the figure the server stores, or the fraction
on screen means nothing. That is what the arithmetic half of this test pins down:
the client divides the weight by one piece's weight, and so does
_sec_nos_for_weight, which is what actually lands on the row.

Run: bench --site manufact execute manufyxinvenzaerp.tests.verify_rwd_two_way.run
"""

import frappe
from frappe.utils import flt

from manufyxinvenzaerp.production_management.doctype.material_planning.material_planning import (
    _sec_nos_for_weight,
)

checks = []


def check(label, got, want):
    ok = got == want
    checks.append(ok)
    print("  %-4s %-56s got=%r want=%r" % ("OK" if ok else "FAIL", label, got, want))


def _js():
    return open(frappe.get_app_path(
        "manufyxinvenzaerp", "subcontracting_management", "doctype",
        "material_issue_plan", "material_issue_plan.js")).read()


def run():
    js = _js()

    print("=== the dialog knows both directions ===")
    check("a per-piece weight is worked out", "function _kg_per_piece()" in js, True)
    check("one place decides which figure is derived",
          "function _refresh_alloc_figures()" in js, True)
    check("the Kg -> Nos direction is the checkbox's",
          'if (dialog.get_value("reserve_without_dimensions")) {' in js, True)
    check("the Nos -> Kg direction steps aside when it is ticked",
          'if (dialog.get_value("reserve_without_dimensions")) return;' in js, True)
    check("fetching a batch refreshes whichever is derived",
          "_refresh_alloc_figures();\n\t\t});" in js, True)
    check("Sec Qty is read-only only while ticked",
          'dialog.fields_dict.sec_qty.df.read_only = checked ? 1 : 0;' in js, True)

    print()
    print("=== a 500 x 250 x 5 plate, unit weight 7.85 ===")
    row = frappe._dict({
        "batch_parent_item_group": "Plates",
        "batch_length": 500, "batch_width": 250, "batch_thickness": 5,
        "batch_unit_weight": 7.85,
    })
    one_piece = (500 / 1000) * (250 / 1000) * 5 * 7.85
    check("one piece weighs", flt(one_piece, 5), 4.90625)
    check("four pieces weigh", flt(one_piece * 4, 3), 19.625)

    print()
    print("=== ticked: 18 Kg required, shown as pieces ===")
    check("the server's piece count", _sec_nos_for_weight(row, 18), flt(18 / one_piece, 3))
    check("which is a fraction, not rounded up", _sec_nos_for_weight(row, 18), 3.669)
    check("and it is what 18 Kg actually is",
          flt(_sec_nos_for_weight(row, 18) * one_piece, 1), 18.0)

    print()
    print("=== a batch with no dimensions cannot be split into pieces ===")
    bare = frappe._dict({"batch_parent_item_group": "Plates", "batch_unit_weight": 7.85})
    check("no piece count is invented", _sec_nos_for_weight(bare, 18), 0.0)

    print()
    print("=== SUMMARY ===")
    if all(checks):
        print("ALL %d CHECKS PASSED" % len(checks))
    else:
        print("%d of %d CHECKS FAILED" % (checks.count(False), len(checks)))
