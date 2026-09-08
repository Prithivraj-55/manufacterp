"""Process Planning rows may now mix Work Type in any order.

The rule that came out: every Subcontractor row had to come before every Internal
Jobcard row. The reasoning was that a subcontractor cannot hand off to internal ops
and then get material back mid-stream. The shop does exactly that -- out for
cutting, back for fit-up, out again for painting -- so the rule was removed at the
client's request.

What must NOT have come out with it, and is the real point of this file:

  - a row with no Work Type at all is still refused;
  - a plan with any Subcontractor row still requires a Vendor/Contractor, which is
    the only thing standing between a Subcontracting Order and no supplier on it.

Nothing downstream ever depended on the ordering -- Supplier Operation Entries are
built one per row in sequence_id order and read work_type only to decide whether
that entry carries a supplier -- which verify_mixed_sco_regression covers live.

Run: bench --site manufact execute manufyxinvenzaerp.tests.verify_work_type_any_order.run
"""

import frappe

checks = []


def check(label, got, want):
    ok = got == want
    checks.append(ok)
    print("  %-4s %-62s got=%r want=%r" % ("OK" if ok else "FAIL", label, got, want))


def _plan(rows, vendor="Some Vendor"):
    """A stand-in for a Production Plan carrying just what the validator reads."""
    return frappe._dict({
        "custom_process_planning": [
            frappe._dict({"idx": i + 1, "operation_name": op, "work_type": wt})
            for i, (op, wt) in enumerate(rows)
        ],
        "custom_vendor_contractor": vendor,
    })


def _throws(fn):
    try:
        fn()
        return False
    except frappe.ValidationError:
        return True


def run():
    from manufyxinvenzaerp.production_plan_management.production_plan import (
        validate_process_planning,
    )

    SUB, INT = "Subcontractor", "Internal Jobcard"

    print("=== interleaving is allowed ===")
    for label, rows in [
        ("Sub -> Internal -> Sub (the case that used to throw)",
         [("Cutting", SUB), ("Fit-up", INT), ("Painting", SUB)]),
        ("Internal first, then Sub",
         [("Fit-up", INT), ("Cutting", SUB)]),
        ("alternating four deep",
         [("A", INT), ("B", SUB), ("C", INT), ("D", SUB)]),
        ("all Subcontractor", [("A", SUB), ("B", SUB)]),
        ("all Internal", [("A", INT), ("B", INT)]),
    ]:
        check(label, _throws(lambda r=rows: validate_process_planning(_plan(r), None)), False)

    print()
    print("=== the two rules that stay ===")
    check("a row with no Work Type is still refused",
          _throws(lambda: validate_process_planning(
              _plan([("Cutting", SUB), ("Fit-up", None)]), None)), True)
    check("Subcontractor without Vendor/Contractor is still refused",
          _throws(lambda: validate_process_planning(
              _plan([("Cutting", SUB)], vendor=None), None)), True)
    check("Internal-only without Vendor/Contractor is fine",
          _throws(lambda: validate_process_planning(
              _plan([("Fit-up", INT)], vendor=None), None)), False)

    print()
    print("=== the old rule is gone from the source, not just bypassed ===")
    import inspect
    from manufyxinvenzaerp.production_plan_management import production_plan
    src = inspect.getsource(production_plan)
    check("no 'Invalid Operation Sequence' throw left",
          "Invalid Operation Sequence" in src, False)
    check("the hook name matches the function",
          "validate_process_planning_contiguity" in src, False)

    hooks_src = inspect.getsource(frappe.get_module("manufyxinvenzaerp.hooks"))
    check("hooks.py points at the renamed function",
          "production_plan.validate_process_planning\"" in hooks_src, True)

    total, failed = len(checks), checks.count(False)
    print()
    if failed:
        print("%d of %d CHECKS FAILED" % (failed, total))
    else:
        print("ALL %d CHECKS PASSED" % total)
