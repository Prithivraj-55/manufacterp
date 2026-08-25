"""Create Revision: cancel one drawing and open its next revision, without taking the
rest of the Sales Order with it.

Revising a drawing is cancel-then-amend. Doing it with the standard Cancel button is
where it comes apart: Frappe sees the Sales Order pointing at the drawing, walks on to
everything else that order points at, and offers to **Cancel All Documents** -- which on
an order with twenty-two drawings means cancelling twenty-two to revise one. The dialog
looks routine. Anybody who clicks through it has lost the order.

The button does the pair in one step and lands you on the draft. What it has to get
right, and what is checked here:

  * exactly one drawing is cancelled -- every sibling on the order is still submitted;
  * the new draft is a real amendment: amended_from set, rev_no one higher, Working;
  * the Sales Order row is released while the revision is a draft, because a draft
    should not stand in for a submitted drawing; and
  * submitting the revision re-attaches that row to it.

Everything here runs inside a transaction and is rolled back.

Run: bench --site manufact execute manufyxinvenzaerp.tests.verify_drawing_create_revision.run
"""

import frappe

from manufyxinvenzaerp.drawing_management.drawing_utils import create_revision

checks = []


def check(label, got, want):
    ok = got == want
    checks.append(ok)
    print("  %-4s %-52s got=%r want=%r" % ("OK" if ok else "FAIL", label, got, want))


def run():
    drawing = frappe.db.get_value(
        "Drawing", {"docstatus": 1, "sales_order": ["!=", ""]},
        ["name", "sales_order", "duno_mark_no", "rev_no"], as_dict=True)
    if not drawing:
        print("=== no submitted drawing with a Sales Order on this site ===")
        print("   The behaviour cannot be measured against real data right now, so only")
        print("   the wiring is checked below.")
        _check_the_wiring()
        _summary()
        return

    print("=== revising %s on %s ===" % (drawing.name, drawing.sales_order))
    row = frappe.db.get_value(
        "Sales Order DUNO Item",
        {"parent": drawing.sales_order, "duno_mark_no": drawing.duno_mark_no},
        ["name", "drawing"], as_dict=True)
    siblings_before = frappe.db.count(
        "Drawing", {"sales_order": drawing.sales_order, "docstatus": 1})
    print("   %d drawings submitted on that order" % siblings_before)

    try:
        revision = create_revision(drawing.name)

        print()
        print("=== one drawing cancelled, not the whole order ===")
        check("the one being revised is cancelled",
              frappe.db.get_value("Drawing", drawing.name, "docstatus"), 2)
        check("and marked Old Revision",
              frappe.db.get_value("Drawing", drawing.name, "status"), "Old Revision")
        check("every sibling is still submitted",
              frappe.db.count("Drawing", {"sales_order": drawing.sales_order, "docstatus": 1}),
              siblings_before - 1)

        print()
        print("=== the draft is a real amendment ===")
        new = frappe.db.get_value("Drawing", revision,
                                  ["docstatus", "amended_from", "rev_no", "status"], as_dict=True)
        check("it is a draft", new.docstatus, 0)
        check("amended from the one just cancelled", new.amended_from, drawing.name)
        check("with the next revision number", new.rev_no, (drawing.rev_no or 0) + 1)
        check("and back to Working", new.status, "Working")

        print()
        print("=== the Sales Order row waits for the revision to be submitted ===")
        # A draft standing in for a submitted drawing is what the release exists to
        # prevent -- the order would show a drawing nobody has signed off.
        if row:
            check("released while the revision is a draft",
                  frappe.db.get_value("Sales Order DUNO Item", row.name, "drawing") or "", "")
            frappe.get_doc("Drawing", revision).submit()
            check("and re-attached once it is submitted",
                  frappe.db.get_value("Sales Order DUNO Item", row.name, "drawing"), revision)

        print()
        print("=== revising it twice over is refused ===")
        # The second revision would be amended from a drawing that already has one, and
        # only one of them could hold the Sales Order row.
        frappe.db.rollback()
        drawing2 = frappe.db.get_value("Drawing", {"docstatus": 1, "sales_order": ["!=", ""]},
                                       "name")
        first = create_revision(drawing2)
        try:
            create_revision(drawing2)
            check("the second attempt is refused", "no error", "an error")
        except frappe.ValidationError as e:
            check("the second attempt names the revision that exists",
                  first in frappe.utils.strip_html(str(e)), True)
    finally:
        frappe.db.rollback()

    _check_the_wiring()
    _summary()


def _check_the_wiring():
    print()
    print("=== and the button is on the form ===")
    js = open(frappe.get_app_path("manufyxinvenzaerp", "drawing_management", "doctype",
                                  "drawing", "drawing.js")).read()
    check("Create Revision exists", 'add_custom_button(__("Create Revision")' in js, True)
    check("on a submitted drawing only", "frm.doc.docstatus === 1" in js, True)
    check("and it calls the one server method",
          "manufyxinvenzaerp.drawing_management.drawing_utils.create_revision" in js, True)

    src = open(frappe.get_app_path("manufyxinvenzaerp", "drawing_management",
                                   "drawing_utils.py")).read()
    body = src[src.index("def create_revision(drawing_name):"):]
    body = body[:body.index("\n@frappe.whitelist()")]
    # The link check is skipped for one reason only: the link it objects to is the
    # Sales Order row, which this drawing's own on_cancel releases.
    check("the link cascade is stepped around", "doc.flags.ignore_links = True" in body, True)
    check("permission is still checked", 'doc.check_permission("cancel")' in body, True)
    check("and the drawing's own on_cancel still runs", "doc.cancel()" in body, True)

    controller = open(frappe.get_app_path("manufyxinvenzaerp", "drawing_management", "doctype",
                                          "drawing", "drawing.py")).read()
    check("which is what releases the Sales Order row",
          "_release_sales_order_row(self)" in controller, True)


def _summary():
    print()
    print("=== SUMMARY ===")
    if all(checks):
        print("ALL %d CHECKS PASSED" % len(checks))
    else:
        print("%d of %d CHECKS FAILED" % (checks.count(False), len(checks)))
