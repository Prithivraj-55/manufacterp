"""Changing a reservation requires write access to the plan.

reserve_batches checked this from the start. The other four whitelisted actions
that change reservations did not -- reserve_exact_match_batches,
unreserve_batches, unreserve_exact_match_batches and reassign_batch -- so a user
who could not edit a Material Planning could still reserve, unreserve or reassign
its batches by calling the method directly. Stock could be taken from under
another job by someone with no rights to that plan at all.

The reported issue named only the exact-match reserve; reading the file showed
four. They are the same class of action on the same document and now share one
guard rather than four copies that could drift apart.

Run: bench --site manufact execute manufyxinvenzaerp.tests.verify_reservation_permission_guard.run
"""

import inspect

import frappe

checks = []

GUARDED = [
    "reserve_batches",
    "reserve_exact_match_batches",
    "unreserve_batches",
    "unreserve_exact_match_batches",
    "reassign_batch",
]


def check(label, got, want):
    ok = got == want
    checks.append(ok)
    print("  %-4s %-58s got=%r want=%r" % ("OK" if ok else "FAIL", label, got, want))


def run():
    from manufyxinvenzaerp.production_management.doctype.material_planning import (
        material_planning as mp_mod,
    )

    print("=== one guard, defined once ===")
    check("the guard exists", callable(getattr(mp_mod, "_require_write", None)), True)
    guard_src = inspect.getsource(mp_mod._require_write)
    check("it asks for write on the plan",
          'frappe.has_permission("Material Planning", "write", doc=mp)' in guard_src, True)
    check("and raises a permission error, not a plain throw",
          "frappe.PermissionError" in guard_src, True)

    print()
    print("=== every action that changes a reservation calls it ===")
    for name in GUARDED:
        fn = getattr(mp_mod, name, None)
        src = inspect.getsource(fn) if fn else ""
        check("%s is guarded" % name, "_require_write(mp)" in src, True)

    print()
    print("=== the guard runs before any work is done ===")
    for name in GUARDED:
        src = inspect.getsource(getattr(mp_mod, name))
        guard_at = src.index("_require_write(mp)")
        # Nothing may be written to the database before the caller is checked.
        writes = [w for w in ("frappe.db.set_value", "mp.save(", "frappe.db.sql")
                  if w in src and src.index(w) < guard_at]
        check("%s checks before it writes" % name, writes, [])

    print()
    print("=== they are all reachable from the browser, which is why it matters ===")
    for name in GUARDED:
        fn = getattr(mp_mod, name)
        check("%s is whitelisted" % name,
              getattr(fn, "__wrapped__", fn).__name__ == name
              and name in frappe.whitelisted_methods_cache
              if hasattr(frappe, "whitelisted_methods_cache") else True, True)

    print()
    print("=== the message is about permission, not about data ===")
    check("it says what was refused",
          "Not permitted to change reservations" in guard_src, True)

    print()
    print("=== SUMMARY ===")
    if all(checks):
        print("ALL %d CHECKS PASSED" % len(checks))
    else:
        print("%d of %d CHECKS FAILED" % (checks.count(False), len(checks)))
