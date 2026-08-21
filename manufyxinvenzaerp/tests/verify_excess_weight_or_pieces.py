"""On an excess row, you say which figure you know and the other is worked out.

The off-cut coming back is described in the Excess Material Items table -- entered
through the Excess Material Mapping popup, and edited there afterwards. Sometimes what
is known is the shape and the number of pieces; sometimes it is simply the weight.

  unticked   type Length/Width and Sec Nos, and the weight follows.
             A 500 x 250 x 5 plate, 4 pieces, comes to 19.625 Kg.
  ticked     type the weight, and the Sec Nos follows.
             18 Kg of that same piece is 3.669 of one -- fractional on purpose,
             because rounding it up would claim a piece that is not coming back.

The same choice the Material Planning row offers with "Reserve stock without
dimensions": which of the two figures you have, and which one is arithmetic.

The part that has to be right is what the Stock Entry ends up moving. For Structurals
and Plates the entry recomputes its own qty from Length x Sec Nos, so a typed weight
that did not agree with the Sec Nos on the row would ship a different amount from the
one on screen. The Sec Nos is therefore derived from the weight before the entry is
built, and the two agree by construction.

Run: bench --site manufact execute manufyxinvenzaerp.tests.verify_excess_weight_or_pieces.run
"""

import frappe
from frappe.utils import flt

from manufyxinvenzaerp.utils.dimension_formula import calculate_qty

checks = []
ROW_DT = "SCO Excess Material Item"
FIELD = "enter_weight_instead_of_pieces"


def check(label, got, want):
    ok = got == want
    checks.append(ok)
    print("  %-4s %-54s got=%r want=%r" % ("OK" if ok else "FAIL", label, got, want))


def _js():
    return open(frappe.get_app_path(
        "manufyxinvenzaerp", "subcontracting_management", "doctype",
        "material_issue_plan", "material_issue_plan.js")).read()


def run():
    meta = frappe.get_meta(ROW_DT)
    js = _js()

    print("=== the choice exists, where there is a shape to measure ===")
    field = meta.get_field(FIELD)
    check("the tick is there", bool(field), True)
    check("it is a checkbox", field.fieldtype if field else None, "Check")
    check("offered only for Structurals and Plates",
          field.depends_on if field else None,
          "eval:['Structurals','Plates'].includes(doc.parent_item_group)")
    check("and it is visible in the grid", field.in_list_view if field else None, 1)

    print()
    print("=== whichever you are not typing is read-only ===")
    check("Sec Nos locks when the weight is typed",
          "doc.enter_weight_instead_of_pieces" in (meta.get_field("sec_qty").read_only_depends_on or ""),
          True)
    check("the weight locks when the pieces are typed",
          "!doc.enter_weight_instead_of_pieces" in (meta.get_field("qty").read_only_depends_on or ""),
          True)
    check("a row already shipped locks either way",
          all("stock_entry_created" in (meta.get_field(f).read_only_depends_on or "")
              for f in ("sec_qty", "qty")), True)

    print()
    print("=== both directions are wired on the form ===")
    check("one place works out a piece's weight", "function _mip_excess_kg_per_piece(" in js, True)
    check("pieces -> weight", "function _mip_excess_calc(" in js, True)
    check("weight -> pieces", "function _mip_excess_sec_from_qty(" in js, True)
    check("ticking it recalculates straight away", "\tenter_weight_instead_of_pieces(frm, cdt, cdn) {" in js, True)

    print()
    print("=== a 500 x 250 x 5 plate, unit weight 7.85 ===")
    one = calculate_qty("Plates", 500, 250, 5, 7.85, 1)
    check("one piece", flt(one, 5), 4.90625)
    check("four pieces weigh", flt(calculate_qty("Plates", 500, 250, 5, 7.85, 4), 3), 19.625)
    check("and 18 Kg is this many pieces", flt(18 / one, 3), 3.669)
    check("which weighs back what was typed", flt(flt(18 / one, 3) * one, 1), 18.0)

    print()
    print("=== the return entry derives the count before it ships anything ===")
    transfer = open(frappe.get_app_path(
        "manufyxinvenzaerp", "subcontracting_management", "material_issue_plan_transfer.py")).read()
    check("the weight wins on a ticked row",
          'if r.get("enter_weight_instead_of_pieces") and' in transfer, True)
    check("and dimension overrides step aside for it",
          "_DIMENSION_DRIVEN_GROUPS and not r.get(\"enter_weight_instead_of_pieces\")" in transfer, True)

    print()
    print("=== SUMMARY ===")
    if all(checks):
        print("ALL %d CHECKS PASSED" % len(checks))
    else:
        print("%d of %d CHECKS FAILED" % (checks.count(False), len(checks)))
