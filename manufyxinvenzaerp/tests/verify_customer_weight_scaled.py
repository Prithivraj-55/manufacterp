"""Customer weight downstream is for the whole row, not for one piece.

The Sales Order DUNO row holds customer weight PER PIECE, beside a Total Quantity of
its own. Every planned and transferred weight downstream is for the WHOLE row. The
per-piece figure was copied straight through, so on the Production Report a drawing
making two pieces read:

    1B1   customer 890.080   planned 1814.089   -> 104% waste
    1B5   customer 547.280   planned  555.891   ->   1.6% waste

Both are the same job, cut the same way. 1B1 was not wasting a hundred percent of its
steel; its customer weight was one piece's worth being compared against two pieces of
planned material. Every drawing making one piece was right, which is why it went unseen.

The planned and transferred figures were never wrong -- the BOM makes two pieces and
carries two pieces of material, and that is what was reserved and transferred. Only the
column it was being read against was.

Checked here: every downstream copy is per-piece times quantity, the two write paths
scale it, and the repair patch cannot double a row it has already fixed.

Run: bench --site manufact execute manufyxinvenzaerp.tests.verify_customer_weight_scaled.run
"""

import frappe
from frappe.utils import flt

checks = []


def check(label, got, want):
    ok = got == want
    checks.append(ok)
    print("  %-4s %-52s got=%r want=%r" % ("OK" if ok else "FAIL", label, got, want))


def run():
    drawings = {
        d.name: d for d in frappe.get_all(
            "Drawing", fields=["name", "duno_mark_no", "no_of_qty_to_manufacture",
                               "customer_provided_wt", "total_weight"])
    }
    multi = [d for d in drawings.values() if flt(d.no_of_qty_to_manufacture) > 1]

    print("=== every downstream copy is the row's total, not one piece ===")
    if not multi:
        print("   No drawing on this site makes more than one piece, so the fault this")
        print("   guards against cannot show itself here. The wiring is checked below.")
    for doctype, field, link in (
        ("Production Plan Item", "custom_customer_weight_kg", "custom_drawing"),
        ("SCO Drawing Item", "customer_weight_kg", "drawing"),
        ("SOE Drawing Detail", "customer_provided_weight_kg", "drawing"),
    ):
        rows = frappe.get_all(doctype, filters={link: ["in", [d.name for d in multi]]},
                              fields=["name", link, field]) if multi else []
        if not rows:
            print("   %-22s no rows on a multi-piece drawing" % doctype)
            continue
        wrong = []
        for r in rows:
            d = drawings[r.get(link)]
            want = flt(flt(d.customer_provided_wt) * flt(d.no_of_qty_to_manufacture), 2)
            if flt(r.get(field), 2) != want:
                wrong.append((r.name, r.get(field), want))
        check("%s: all %d rows scaled" % (doctype, len(rows)), wrong, [])

    print()
    print("=== and it reads sensibly against planned ===")
    # The real symptom was the ratio, so measure the ratio. Cutting steel wastes a few
    # percent; anything near a whole multiple of the quantity is the old fault back.
    for row in frappe.get_all("SCO Drawing Item",
                              filters={"parenttype": "Subcontracting Order",
                                       "drawing": ["in", list(drawings)]},
                              fields=["drawing", "customer_weight_kg", "total_weight_kg"]):
        cust, planned = flt(row.customer_weight_kg), flt(row.total_weight_kg)
        if not (cust and planned):
            continue
        qty = flt(drawings[row.drawing].no_of_qty_to_manufacture) or 1
        check("%s (%s pcs) planned is within a tenth of customer"
              % (drawings[row.drawing].duno_mark_no, qty),
              planned / cust < 1.10, True)

    print()
    print("=== the patch cannot double a row it already fixed ===")
    from manufyxinvenzaerp.patches.v1.scale_customer_weight_by_qty import execute as repatch

    target = frappe.db.get_value(
        "SCO Drawing Item",
        {"drawing": ["in", [d.name for d in multi]], "parenttype": "Subcontracting Order"},
        ["name", "customer_weight_kg"], as_dict=True) if multi else None
    if not target:
        print("   No already-scaled row to run it over.")
    else:
        try:
            repatch()
            check("running it again changes nothing",
                  flt(frappe.db.get_value("SCO Drawing Item", target.name, "customer_weight_kg"), 3),
                  flt(target.customer_weight_kg, 3))
        finally:
            frappe.db.rollback()

    print()
    print("=== both write paths scale on the way out ===")
    js = open(frappe.get_app_path("manufyxinvenzaerp", "public", "js",
                                  "production_plan.js")).read()
    check("the Production Plan picker multiplies by planned qty",
          "flt(s.customer_weight || 0) * flt(child.planned_qty)" in js, True)
    py = open(frappe.get_app_path("manufyxinvenzaerp", "drawing_management",
                                  "drawing_utils.py")).read()
    check("and Update Customer Weight's cascade multiplies too",
          'flt(new_weight) * (flt(frappe.db.get_value(' in py, True)
    check("cascading the scaled figure, not the per-piece one",
          'set_value("Production Plan Item", row.name, "custom_customer_weight_kg", row_weight)' in py,
          True)

    print()
    print("=== SUMMARY ===")
    if all(checks):
        print("ALL %d CHECKS PASSED" % len(checks))
    else:
        print("%d of %d CHECKS FAILED" % (checks.count(False), len(checks)))
