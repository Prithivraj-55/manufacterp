"""Cancelling a drawing lets go of the Sales Order row it was made for.

A Sales Order DUNO row names the Drawing created for it. Cancel that drawing and the
row went on naming it -- and Frappe refuses to save OR submit a document that links to
a cancelled one, reporting it as "Cannot link cancelled document: Row #22: Drawing:
DRW-...". On an order carrying a couple of hundred DUNOs that is a long way from
telling anyone what to do.

Worse, the row still looked answered, so "Create Drawings" never offered that DUNO
again. The obvious way to put it right was closed off by the very thing that broke it.

Now: cancelling releases the row, and submitting an amendment takes it back. An order
already stuck in the old state is rescued the same way, because the amendment also
takes over a row still naming the exact document it amends.

The message cannot be improved server-side and this test says why: Frappe checks links
in _validate_links(), which runs before every hook this app could use, so nothing
raised from validate() or before_submit() is ever reached. The Sales Order form asks
for the same information and says it there instead.

Run: bench --site manufact execute manufyxinvenzaerp.tests.verify_cancelled_drawing_link.run
"""

import frappe

from manufyxinvenzaerp.drawing_management.doctype.drawing.drawing import (
    _link_to_sales_order_row,
    _release_sales_order_row,
    _sales_order_row,
)

checks = []


def check(label, got, want):
    ok = got == want
    checks.append(ok)
    print("  %-4s %-54s got=%r want=%r" % ("OK" if ok else "FAIL", label, got, want))


def _src(*parts):
    return open(frappe.get_app_path("manufyxinvenzaerp", *parts)).read()


def run():
    print("=== the two halves are wired to submit and cancel ===")
    drawing = _src("drawing_management", "doctype", "drawing", "drawing.py")
    check("cancelling releases the row", "_release_sales_order_row(self)" in drawing, True)
    check("submitting attaches it", "_link_to_sales_order_row(self)" in drawing, True)

    print()
    print("=== an amendment takes over the row its ancestor left behind ===")
    check("it replaces a link to what it amends",
          'if row.drawing and row.drawing != doc.amended_from:' in drawing, True)
    check("but never a link to anything else",
          drawing.count("row.drawing != doc.amended_from"), 1)

    print()
    print("=== the row is found by order and DUNO, not by name ===")
    # Row names are regenerated whenever the table is rebuilt; the DUNO is not.
    check("matched on the Sales Order and the DUNO",
          '"parent": doc.sales_order, "duno_mark_no": doc.duno_mark_no' in drawing, True)

    print()
    print("=== a stale form is made to reload, not allowed to overwrite ===")
    # The row is re-pointed with frappe.db.set_value, which does not reach an order
    # already open in somebody's browser. Leaving the order's own timestamp alone
    # meant that form kept the cancelled link AND passed Frappe's "modified since you
    # opened it" guard -- so pressing Submit put the dead link straight back and the
    # original error returned on an order the database had already fixed.
    check("re-pointing moves the order's timestamp",
          "def _touch_sales_order(sales_order):" in drawing, True)
    check("on release", drawing.count("_touch_sales_order(doc.sales_order)"), 2)

    print()
    print("=== the form is where the problem gets named ===")
    imp = _src("drawing_management", "so_drawing_import.py")
    setup = _src("setup.py")
    check("there is a lookup for it", "def get_cancelled_drawing_links(" in imp, True)
    check("the form calls it on refresh", "_so_warn_cancelled_drawings(frm);" in setup, True)
    check("and it names the DUNO, not just a row number",
          'DUNO {1}' in setup, True)

    print()
    print("=== and NOT from a server hook, which could never be reached ===")
    so = _src("drawing_management", "sales_order.py")
    hooks = _src("hooks.py")
    check("no validate-time warning was left behind",
          "warn_cancelled_drawing_links" in so or "warn_cancelled_drawing_links" in hooks, False)

    print()
    print("=== on this site right now ===")
    stuck = frappe.get_all(
        "Sales Order DUNO Item",
        filters={"drawing": ["!=", ""], "docstatus": ["<", 2]},
        fields=["parent", "idx", "duno_mark_no", "drawing"],
        limit=500,
    )
    cancelled = set(frappe.get_all(
        "Drawing", filters={"name": ["in", [r.drawing for r in stuck]] or [""], "docstatus": 2},
        pluck="name",
    )) if stuck else set()
    affected = [r for r in stuck if r.drawing in cancelled]
    print("   %d DUNO row(s) still naming a cancelled drawing" % len(affected))
    for r in affected[:10]:
        print("     %s row %s — DUNO %s — %s" % (r.parent, r.idx, r.duno_mark_no, r.drawing))
    if affected:
        print("   each is fixed by amending that drawing and submitting the amendment")

    print()
    print("=== SUMMARY ===")
    if all(checks):
        print("ALL %d CHECKS PASSED" % len(checks))
    else:
        print("%d of %d CHECKS FAILED" % (checks.count(False), len(checks)))
