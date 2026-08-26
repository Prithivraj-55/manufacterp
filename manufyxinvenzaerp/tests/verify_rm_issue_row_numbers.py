"""Every raw-material verification issue leads with the row it is about.

Verification runs over a sheet of hundreds of rows and reports what is wrong with them.
It used to report only what the row IS:

    Drawing BEAM-1B16 -SHT-16 OF 291 / ISMB250 (Item 1w11): Structurals do not use
    Thickness — clear that column in the sheet.

That is the drawing's name, not a place to go. Finding it meant scrolling a grid looking
for a matching drawing number and item number, on every issue in the list.

Each line now leads with the row:

    Raw Materials row 100 · Drawing BEAM-1B22 ... : row weighs 14.593 Kg but ...

The table is named with it because the Sales Order has two the issues come from --
Drawing List on the Drawing Import tab, and Raw Materials -- and row 16 of one is not
row 16 of the other.

Everything here runs inside a transaction and is rolled back.

Run: bench --site manufact execute manufyxinvenzaerp.tests.verify_rm_issue_row_numbers.run
"""

import re

import frappe

from manufyxinvenzaerp.drawing_management.so_drawing_import import (
    DRAWING_LIST,
    RAW_MATERIALS,
    _at,
    verify_raw_materials,
)

checks = []


def check(label, got, want):
    ok = got == want
    checks.append(ok)
    print("  %-4s %-54s got=%r want=%r" % ("OK" if ok else "FAIL", label, got, want))


def _plain(issue):
    return frappe.utils.strip_html(issue).replace("&middot;", "·")


def run():
    print("=== the shape of a located issue ===")
    check("it leads with the table and the row",
          _plain(_at(RAW_MATERIALS, 100, "something is wrong")),
          "Raw Materials row 100 · something is wrong")
    check("and the row number is bold, so it is scannable",
          _at(RAW_MATERIALS, 100, "x").startswith("<b>"), True)
    check("the other table names itself too",
          _plain(_at(DRAWING_LIST, 7, "x")).startswith("Drawing List row 7"), True)

    so = frappe.db.get_value("Sales Order", {"docstatus": 1}, "name")
    if not so:
        print()
        print("   No submitted Sales Order on this site to verify against.")
        _summary()
        return

    print()
    print("=== against a real Sales Order: %s ===" % so)
    rm = frappe.get_all("Sales Order Drawing Raw Material", filters={"parent": so},
                        fields=["name", "idx", "parent_item_group"], order_by="idx desc", limit=1)
    duno = frappe.get_all("Sales Order DUNO Item", filters={"parent": so},
                          fields=["name", "idx"], order_by="idx desc", limit=1)

    try:
        # Two faults, one in each table, so the run has to distinguish them.
        if rm:
            frappe.db.set_value("Sales Order Drawing Raw Material", rm[0].name,
                                {"thickness": 12, "is_locked": 0}, update_modified=False)
        if duno:
            # The header checks only look at drawings not yet created, so the row has to
            # be put back into that state for its fault to be reachable at all.
            frappe.db.set_value("Sales Order DUNO Item", duno[0].name,
                                {"total_quantity": 0, "drawing": ""}, update_modified=False)

        issues = verify_raw_materials(so)["issues"]
        print("   %d issue(s):" % len(issues))
        for i in issues[:6]:
            print("      • %s" % _plain(i))

        check("every issue names a row", 
              [i for i in issues if not re.match(r"^<b>.+ row \d+</b>", i)], [])
        if rm:
            check("the raw-material fault points at its own row",
                  any(_plain(i).startswith("Raw Materials row %d ·" % rm[0].idx) for i in issues),
                  True)
        if duno:
            check("and the drawing fault at the other table's row",
                  any(_plain(i).startswith("Drawing List row %d ·" % duno[0].idx) for i in issues),
                  True)
        check("the two are not confused for each other",
              len({_plain(i).split(" row ")[0] for i in issues}) >= (2 if (rm and duno) else 1),
              True)
    finally:
        frappe.db.rollback()

    _summary()


def _summary():
    print()
    print("=== SUMMARY ===")
    if all(checks):
        print("ALL %d CHECKS PASSED" % len(checks))
    else:
        print("%d of %d CHECKS FAILED" % (checks.count(False), len(checks)))
