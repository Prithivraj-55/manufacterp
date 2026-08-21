"""Auto Purchase refuses to run while the Settings switch is off.

Auto Purchase chains Material Request -> Purchase Order -> Purchase Receipt, each
submitted, with no rollback: a failure part-way leaves a half-built chain of live
documents behind. It stays a testing aid, switched off in production.

Until now "switched off" only meant the button was hidden. `auto_purchase_from_mp`
is whitelisted, so anyone with an API key could call it directly with the switch
off and build the whole chain anyway. The check now lives in the method itself.

Self-contained: it flips the setting, calls the method, and puts the setting back
whatever happens. No document is created either way -- with the switch on, the call
is made against a Material Planning name that does not exist, so it fails on the
missing document, which is exactly the proof that the gate let it through.

Run: bench --site manufact execute manufyxinvenzaerp.tests.verify_auto_purchase_gated.run
"""

import frappe

from manufyxinvenzaerp.production_management.doctype.material_planning.material_planning import (
    auto_purchase_from_mp,
)

checks = []
FLAG = "auto_purchase_from_material_planning"
ABSENT_MP = "MP-DOES-NOT-EXIST-ZZTEST"


def check(label, got, want):
    ok = got == want
    checks.append(ok)
    print("  %-4s %-58s got=%r want=%r" % ("OK" if ok else "FAIL", label, got, want))


def _set_flag(value):
    frappe.db.set_single_value("Manufyxinvenza Settings", FLAG, value)
    frappe.clear_document_cache("Manufyxinvenza Settings", "Manufyxinvenza Settings")


def _call():
    """Call the method and report what stopped it, without letting it raise."""
    try:
        auto_purchase_from_mp(ABSENT_MP)
        return None
    except Exception as e:
        return type(e).__name__


def run():
    original = frappe.db.get_single_value("Manufyxinvenza Settings", FLAG)
    print("=== the switch on this site right now ===")
    print("   %s = %r (restored at the end)" % (FLAG, original))

    try:
        print()
        print("=== switched off: the method refuses ===")
        _set_flag(0)
        err = _call()
        check("it raises rather than running", err is not None, True)
        check("it is refused, not merely broken", err, "PermissionError")

        print()
        print("=== switched on: the gate lets it through ===")
        _set_flag(1)
        err = _call()
        check("it is no longer refused", err == "PermissionError", False)
        check("it fails on the missing Material Planning instead",
              err, "DoesNotExistError")

        print()
        print("=== nothing was created either way ===")
        for dt in ("Material Request", "Purchase Order", "Purchase Receipt"):
            check("no %s for a plan that does not exist" % dt,
                  frappe.db.exists(dt, {"title": ABSENT_MP}), None)
    finally:
        _set_flag(original)
        frappe.db.commit()
        print()
        print("   %s put back to %r" % (FLAG, original))

    print()
    print("=== SUMMARY ===")
    if all(checks):
        print("ALL %d CHECKS PASSED" % len(checks))
    else:
        print("%d of %d CHECKS FAILED" % (checks.count(False), len(checks)))
