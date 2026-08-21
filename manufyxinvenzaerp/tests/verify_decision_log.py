"""The decision log: who decided what, and why.

Offered three options, the client picked "log the decisions" over "log every field
change on every document" -- which on a 500-drawing order would be large, slow to
write and unreadable. So this records a handful of things people actually argue about
later: who reserved a batch, who released it, who moved it to another one, who rounded
a quantity up and what they said at the time.

Two properties matter more than the fields themselves, and both are checked here.

  One entry per DECISION, not per row. Reserving a plan is one press of one button
  covering however many rows, so it is one entry carrying the count and the weight.
  Reassigning a batch really is per row, so that is one entry each.

  Logging can never break the thing it is logging. A reservation that went through and
  then failed because its log entry could not be written would be worse than having no
  log at all, so a failure here is swallowed and sent to the error log instead.

It leaves its own entries behind. That is the point of an append-only log; nothing in
the app can remove them, including this test.

Run: bench --site manufact execute manufyxinvenzaerp.tests.verify_decision_log.run
"""

import frappe

from manufyxinvenzaerp.utils.decision_log import ACTIONS, log_decision

checks = []
DOCTYPE = "Manufyx Decision Log"


def check(label, got, want):
    ok = got == want
    checks.append(ok)
    print("  %-4s %-56s got=%r want=%r" % ("OK" if ok else "FAIL", label, got, want))


def _source(*parts):
    return open(frappe.get_app_path("manufyxinvenzaerp", *parts)).read()


def run():
    print("=== an entry records who and when for free ===")
    before = frappe.db.count(DOCTYPE)
    name = log_decision(
        "Reserve",
        reference_doctype="Item",
        reference_name=frappe.get_all("Item", limit=1, pluck="name")[0],
        rows_affected=7,
        qty=123.456,
        details="Verification run -- verify_decision_log.",
    )
    check("it was written", bool(name), True)
    entry = frappe.get_doc(DOCTYPE, name)
    check("the decision", entry.action, "Reserve")
    check("who made it", entry.owner, frappe.session.user)
    check("when", bool(entry.creation), True)
    check("how many rows it covered", entry.rows_affected, 7)
    check("the weight", entry.qty, 123.456)

    print()
    print("=== a decision it does not know about is refused, not invented ===")
    count = frappe.db.count(DOCTYPE)
    check("nothing is written", log_decision("Reticulate Splines"), None)
    check("and the table is unchanged", frappe.db.count(DOCTYPE), count)

    print()
    print("=== a broken entry never reaches the caller ===")
    # A reference to a doctype that does not exist fails link validation inside.
    check("it returns quietly",
          log_decision("Reserve", reference_doctype="No Such DocType",
                       reference_name="X", details="deliberately broken"), None)
    check("the caller carries on", True, True)

    print()
    print("=== every decision point is wired ===")
    mp = _source("production_management", "doctype", "material_planning", "material_planning.py")
    mip = _source("subcontracting_management", "material_issue_plan_transfer.py")
    cs = _source("production_management", "doctype", "cut_sheet", "cut_sheet.py")
    se = _source("production_management", "stock_entry.py")

    check("reserving is logged", mp.count('log_decision(\n        "Reserve"'), 2)
    check("releasing is logged", mp.count('log_decision(\n        "Unreserve"'), 2)
    check("reassigning is logged", mp.count('"Reassign Batch"'), 2)
    check("rounding up is logged", '"Round Up at Transfer"' in mip, True)
    check("the cut sheet balance is logged, in place", '"Cut Sheet Balance"' in cs, True)
    check("and as a new batch", '"Cut Sheet Balance"' in se, True)

    print()
    print("=== reserving is one entry, not one per row ===")
    check("it carries the row count instead", "rows_affected=reserved_count" in mp, True)
    check("and the total weight", "qty=sum(flt(r.reserved_qty)" in mp, True)
    check("releasing too", "rows_affected=unreserved_count" in mp, True)
    check("reassigning names the row it was made on", "row_reference=row_name" in mp, True)

    print()
    print("=== the log is append-only ===")
    meta = frappe.get_meta(DOCTYPE)
    perms = frappe.get_all("DocPerm", filters={"parent": DOCTYPE},
                           fields=["role", "read", "write", "create", "delete"])
    check("somebody can read it", any(p.read for p in perms), True)
    check("nobody can write to it", any(p.write for p in perms), False)
    check("nobody can create one by hand", any(p.create for p in perms), False)
    check("nobody can delete one", any(p.delete for p in perms), False)
    check("and it does not track its own changes", meta.track_changes, 0)

    print()
    print("=== the log never holds its subject hostage ===")
    # Frappe refuses to delete anything a Link still points at. Without the hook
    # below, recording a Cut Sheet's balance made that Cut Sheet undeletable -- an
    # audit trail stopping the very thing it was describing from being tidied away.
    check("deletion ignores links from the log",
          "Manufyx Decision Log" in frappe.get_hooks("ignore_links_on_delete"), True)

    print()
    print("=== the actions it accepts ===")
    field = frappe.get_meta(DOCTYPE).get_field("action")
    options = {o for o in (field.options or "").split("\n") if o}
    check("the field offers exactly what the helper accepts", options, ACTIONS)

    frappe.db.commit()
    print()
    print("   %d entries before, %d after -- entries are never removed"
          % (before, frappe.db.count(DOCTYPE)))

    print()
    print("=== SUMMARY ===")
    if all(checks):
        print("ALL %d CHECKS PASSED" % len(checks))
    else:
        print("%d of %d CHECKS FAILED" % (checks.count(False), len(checks)))
