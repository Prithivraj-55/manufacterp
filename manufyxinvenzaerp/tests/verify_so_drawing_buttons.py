"""The Drawing group on a Sales Order offers what is left to do, and nothing else.

It used to carry two ways to make a BOM -- "Create and Submit BOM" and "Create BOM" --
which is the same job done twice, the second leaving drafts nobody chased. And once
every BOM had been made, "Create and Submit BOM" stayed on the toolbar and answered a
click with "already created", which is a button whose only purpose is to tell you it
should not be there.

Now the group reads as the sequence it actually is:

    Create Drawing → Submit Drawing → Mark as Final Revision → Create and Submit BOM

and once every final drawing has a submitted BOM, that last entry is replaced by
**View Drawing**. Nothing on the toolbar offers work that is already finished.

Run: bench --site manufact execute manufyxinvenzaerp.tests.verify_so_drawing_buttons.run
"""

import re

import frappe

checks = []


def check(label, got, want):
    ok = got == want
    checks.append(ok)
    print("  %-4s %-54s got=%r want=%r" % ("OK" if ok else "FAIL", label, got, want))


def _script_from_source():
    src = open(frappe.get_app_path("manufyxinvenzaerp", "setup.py")).read()
    m = re.search(r'SO_CLIENT_SCRIPT = """(.*?)\n"""', src, re.S)
    return m.group(1).encode().decode("unicode_escape")


def run():
    js = _script_from_source()
    installed = frappe.db.get_value("Client Script", {"dt": "Sales Order"}, "script") or ""

    print("=== one way to make a BOM, not two ===")
    check("Create and Submit BOM is offered", '__("Create and Submit BOM")' in js, True)
    check("the draft-only Create BOM button is gone",
          'frm.add_custom_button(__("Create BOM")' in js, False)
    # Not a bare '"create_bom"' search: that is also the fieldname of the row
    # checkbox deciding which DUNOs get a BOM, which stays exactly as it was.
    check("no draft-only BOM step is triggered from here",
          '_so_run_step(frm, "create_bom"' in js, False)
    check("the row checkbox that picks the DUNOs is untouched",
          'fieldname: "create_bom"' in js, True)

    print()
    print("=== it appears only once a drawing is a Final Revision ===")
    check("candidates are Final Revision drawings", "final.has(r.drawing)" in js, True)
    check("and only rows ticked for a BOM", "r.create_bom && final.has(r.drawing)" in js, True)

    print()
    print("=== when the work is done, the button changes ===")
    check("View Drawing takes its place", '__("View Drawing")' in js, True)
    check("it opens this order's drawings",
          'frappe.set_route("List", "Drawing", { sales_order: frm.doc.name })' in js, True)
    check("the click-time 'already created' message is gone",
          "BOMs Already Created" in js, False)
    check("what is left is decided before the button is drawn",
          "var pending = bom_candidates.filter" in js, True)
    check("and View Drawing needs every final drawing to have one",
          "final_names.every(function(n) { return done.has(n); })" in js, True)

    print()
    print("=== the earlier steps are untouched ===")
    for label in ("Create Drawing", "Submit Drawing", "Mark as Final Revision", "Submit BOM"):
        check("%s still offered" % label, '__("%s")' % label in js, True)

    print()
    print("=== and the site is running this version ===")
    check("the installed script matches", 'frm.add_custom_button(__("Create BOM")' in installed, False)
    check("View Drawing is live", '__("View Drawing")' in installed, True)

    print()
    print("=== SUMMARY ===")
    if all(checks):
        print("ALL %d CHECKS PASSED" % len(checks))
    else:
        print("%d of %d CHECKS FAILED" % (checks.count(False), len(checks)))
