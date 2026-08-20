"""A customer weight correction has to reach Operation Entry, not stop before it.

_cascade_customer_weight pushed the new figure into Production Plan Item, SCO
Drawing Item, the Job Work Order header and the Material Issue Plan summary -- and
stopped there. SOE Drawing Detail carries its own customer_provided_weight_kg and
was never updated, so every planning document agreed on the corrected weight while
the sheet the shop floor actually works from still showed the old one, with
nothing on screen to say the two disagreed.

Submitted and cancelled entries are updated too. The weight is descriptive -- it
drives no stock movement and no costing -- so leaving a correction out of a
submitted entry would freeze the wrong number into the document people read.

Run: bench --site manufact execute manufyxinvenzaerp.tests.verify_weight_cascade_reaches_soe.run
"""

import inspect

import frappe
from frappe.utils import flt

checks = []


def check(label, got, want):
    ok = got == want
    checks.append(ok)
    print("  %-4s %-58s got=%r want=%r" % ("OK" if ok else "FAIL", label, got, want))


def run():
    from manufyxinvenzaerp.drawing_management import drawing_utils

    src = inspect.getsource(drawing_utils._cascade_customer_weight)

    print("=== the field exists and is the one Operation Entry shows ===")
    meta = frappe.get_meta("SOE Drawing Detail")
    field = meta.get_field("customer_provided_weight_kg")
    check("SOE Drawing Detail carries it", bool(field), True)
    check("it is a weight field", field.fieldtype if field else None, "Float")

    print()
    print("=== the cascade now reaches it ===")
    check("SOE rows are collected", '"SOE Drawing Detail",' in src, True)
    check("scoped to Operation Entry parents",
          '"parenttype": "Supplier Operation Entry"' in src, True)
    check("and written with the new weight",
          '"SOE Drawing Detail", row.name, "customer_provided_weight_kg", new_weight' in src, True)
    check("the count is reported back",
          '"operation_entry_rows_updated": len(soe_detail_rows)' in src, True)

    print()
    print("=== the documents it already covered are untouched ===")
    for existing in ("Production Plan Item", "SCO Drawing Item",
                     "custom_customer_weight_kg", "refresh_weight_summary"):
        check("still handles %s" % existing, existing in src, True)

    print()
    print("=== the form tells the user about it ===")
    import os
    js_path = os.path.join(frappe.get_app_path("manufyxinvenzaerp"),
                           "drawing_management", "doctype", "drawing", "drawing.js")
    with open(js_path) as f:
        js = f.read()
    check("the message names the new count",
          "Operation Entry drawing rows updated" in js, True)
    check("and passes it through", "m.operation_entry_rows_updated" in js, True)

    print()
    print("=== against live data ===")
    rows = frappe.get_all("SOE Drawing Detail",
                          filters={"parenttype": "Supplier Operation Entry"},
                          fields=["parent", "drawing", "customer_provided_weight_kg"],
                          limit_page_length=0)
    print("   %d Operation Entry drawing row(s) on this site" % len(rows))
    if not rows:
        print("   (none to compare -- the transaction layer was cleared)")
    else:
        stale = []
        for r in rows:
            if not r.drawing:
                continue
            drawing_wt = flt(frappe.db.get_value("Drawing", r.drawing, "customer_provided_wt"))
            if abs(drawing_wt - flt(r.customer_provided_weight_kg)) > 0.001:
                stale.append((r.parent, r.drawing, r.customer_provided_weight_kg, drawing_wt))
        for s in stale[:5]:
            print("      %s / %s: entry says %s, drawing says %s" % s)
        check("no entry disagrees with its drawing", len(stale), 0)

    print()
    print("=== SUMMARY ===")
    if all(checks):
        print("ALL %d CHECKS PASSED" % len(checks))
    else:
        print("%d of %d CHECKS FAILED" % (checks.count(False), len(checks)))
