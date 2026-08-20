"""The Operation Entry "Testing" button only appears where testing is switched on.

"Add All Drawing" fills the Consumption Log with one row per drawing at its full
available quantity in a single click. That is a data-entry shortcut, not a step in
the real process, and it sat on every Operation Entry where an operator could
reach it.

It is now shown only where Manufyxinvenza Settings enables Auto Purchase -- the
same switch that reveals the Auto Purchase section on Material Planning. Both are
testing conveniences, so one switch governs both and there is nothing new for
anyone to know about.

Run: bench --site manufact execute manufyxinvenzaerp.tests.verify_testing_button_gated.run
"""

import re

import frappe

checks = []
FLAG = "auto_purchase_from_material_planning"


def check(label, got, want):
    ok = got == want
    checks.append(ok)
    print("  %-4s %-58s got=%r want=%r" % ("OK" if ok else "FAIL", label, got, want))


def _soe_script():
    """The Operation Entry client script exactly as setup.py installs it."""
    src = open(frappe.get_app_path("manufyxinvenzaerp", "setup.py")).read()
    m = re.search(r'SOE_CLIENT_SCRIPT = """(.*?)\n"""', src, re.S)
    return m.group(1).encode().decode("unicode_escape")


def run():
    js = _soe_script()

    print("=== the switch exists and is the Auto Purchase one ===")
    meta = frappe.get_meta("Manufyxinvenza Settings")
    field = meta.get_field(FLAG)
    check("the setting is there", bool(field), True)
    check("it is a checkbox", field.fieldtype if field else None, "Check")

    print()
    print("=== the button is behind it ===")
    check("the setting is read before the button is added",
          'get_single_value("Manufyxinvenza Settings", "%s")' % FLAG in js, True)
    check("nothing is added when it is off", "if (!enabled) return;" in js, True)
    check("the button is inside the callback",
          js.index("if (!enabled) return;") < js.index('__("Add All Drawing")'), True)
    check("it is still in the Testing group", '__("Testing")' in js, True)

    print()
    print("=== the conditions it already had are kept ===")
    check("draft only", "frm.doc.docstatus === 0" in js, True)
    check("not on an unsaved document", "!frm.is_new()" in js, True)

    print()
    print("=== the same switch governs Material Planning's Auto Purchase ===")
    mp = open(frappe.get_app_path(
        "manufyxinvenzaerp", "production_management", "doctype",
        "material_planning", "material_planning.js")).read()
    check("Material Planning reads the same setting",
          'get_single_value("Manufyxinvenza Settings", "%s")' % FLAG in mp, True)
    check("and hides its section the same way", "if (!enabled) return;" in mp, True)

    print()
    print("=== what the setting says on this site right now ===")
    enabled = frappe.db.get_single_value("Manufyxinvenza Settings", FLAG)
    print("   %s = %r" % (FLAG, enabled))
    print("   so the Testing button is currently %s"
          % ("SHOWN" if enabled else "HIDDEN"))
    print("   (switch it in Manufyxinvenza Settings to change both this and the")
    print("    Auto Purchase section on Material Planning)")

    print()
    print("=== the installed Client Script matches the source ===")
    installed = frappe.db.get_value(
        "Client Script", {"dt": "Supplier Operation Entry"}, "script") or ""
    if not installed:
        print("   (no Client Script installed yet -- runs on the next migrate)")
    else:
        check("the live script is gated too",
              'get_single_value("Manufyxinvenza Settings", "%s")' % FLAG in installed, True)

    print()
    print("=== SUMMARY ===")
    if all(checks):
        print("ALL %d CHECKS PASSED" % len(checks))
    else:
        print("%d of %d CHECKS FAILED" % (checks.count(False), len(checks)))
