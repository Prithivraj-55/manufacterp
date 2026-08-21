"""Return Type is gone; Billed to Consume says what it used to try to say.

Return Type offered two answers -- "Return to Own Warehouse" and "Retain at Supplier
(Virtual)" -- and the second was a paper promise: material that never came back, was
never a batch, and could still be claimed by another job from the row itself. Two jobs
could end up counting on one off-cut that nothing in the ledger knew about.

What replaces it is narrower and truthful. **Billed to Consume**: the off-cut is not
coming back, it is charged to its own job, and the job's final Stock Entry consumes it
out of the supplier's warehouse -- so the cost lands on the job that created it rather
than in a free pool. No return entry, no batch, and no other plan can take it.

Everything else is simply a return. There is no third case left to branch on, which is
why the field could go rather than be renamed.

Run: bench --site manufact execute manufyxinvenzaerp.tests.verify_billed_to_consume.run
"""

import frappe

checks = []
ROW_DT = "SCO Excess Material Item"


def check(label, got, want):
    ok = got == want
    checks.append(ok)
    print("  %-4s %-54s got=%r want=%r" % ("OK" if ok else "FAIL", label, got, want))


def _src(*parts):
    return open(frappe.get_app_path("manufyxinvenzaerp", *parts)).read()


def run():
    meta = frappe.get_meta(ROW_DT)
    present = {f.fieldname for f in meta.fields}

    print("=== Return Type has gone ===")
    check("the field is gone", "return_type" in present, False)

    mp = _src("production_management", "doctype", "material_planning", "material_planning.py")
    mpjs = _src("production_management", "doctype", "material_planning", "material_planning.js")
    mip = _src("subcontracting_management", "doctype", "material_issue_plan", "material_issue_plan.py")
    transfer = _src("subcontracting_management", "material_issue_plan_transfer.py")
    rep = _src("subcontracting_management", "report", "excess_material_return_report",
               "excess_material_return_report.py")
    repjs = _src("subcontracting_management", "report", "excess_material_return_report",
                 "excess_material_return_report.js")

    for src, label in ((mp, "Material Planning"), (mpjs, "its form"), (mip, "the issue plan"),
                       (transfer, "the transfer"), (rep, "the report"), (repjs, "its filters")):
        check("%s no longer mentions it" % label, "return_type" in src, False)
    check("and nothing still tests for a virtual off-cut",
          any("Retain at Supplier" in s for s in (mp, mpjs, mip, transfer, rep, repjs)), False)

    print()
    print("=== Billed to Consume took its place ===")
    field = meta.get_field("billed_to_consume")
    check("the field is there", bool(field), True)
    check("a plain tick", field.fieldtype if field else None, "Check")
    check("settable after submission, like the row's other decisions",
          field.allow_on_submit if field else None, 1)
    check("visible in the grid", field.in_list_view if field else None, 1)
    check("it says what it means", bool(field and field.description), True)
    check("a return warehouse is pointless for one",
          meta.get_field("return_warehouse").depends_on, "eval:!doc.billed_to_consume")

    print()
    print("=== what a ticked row does, and does not, do ===")
    check("no return entry is made for it",
          'if r.get("billed_to_consume"):' in transfer, True)
    check("it does not hold the plan open", "if row.billed_to_consume:" in mip, True)
    check("it is not offered to another plan's picker",
          '"billed_to_consume": 0,' in mp, True)
    check("and claiming one directly is refused",
          "if excess.billed_to_consume:" in mp, True)

    print()
    print("=== the report stops chasing it ===")
    check("it is not a missed return", "if not r.billed_to_consume" in rep, True)
    check("it gets a status of its own", '_("Billed to Consume")' in rep, True)
    check("and a filter of its own", 'fieldname: "billed_to_consume"' in repjs, True)

    print()
    print("=== SUMMARY ===")
    if all(checks):
        print("ALL %d CHECKS PASSED" % len(checks))
    else:
        print("%d of %d CHECKS FAILED" % (checks.count(False), len(checks)))
