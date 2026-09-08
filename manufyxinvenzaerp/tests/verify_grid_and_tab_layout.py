"""Purchase Receipt shows its Accepted Warehouse, and the Job Work Order hides two
tabs nobody uses.

The Purchase Receipt half is the one worth a test. Warehouse was ALREADY flagged
in_list_view by ERPNext; it did not render because Frappe's grid has a hard
11-column budget and this app's six custom columns exhausted it before Warehouse
was reached. When that happens the grid does not wrap or scroll -- it returns
early, and every remaining column vanishes with no error anywhere.

So the thing to assert is not "warehouse is in_list_view" (it always was). It is
that the running total still fits, walked exactly as grid.js walks it. Anything
added to that grid later has to come out of the same budget, and this check is what
says so out loud instead of a column silently disappearing.

Run: bench --site manufact execute manufyxinvenzaerp.tests.verify_grid_and_tab_layout.run
"""

import frappe

checks = []

# frappe/public/js/frappe/form/grid.js -- update_default_colsize. Mirrored here
# because the budget is decided in the browser and there is no server-side copy.
_DEFAULT_COLSIZE = {
    "Int": 2, "Float": 2, "Currency": 2, "Check": 1, "Percent": 2,
    "Data": 3, "Link": 3, "Select": 3, "Small Text": 3, "Text": 3,
    "Date": 2, "Datetime": 3,
}
_LAYOUT_FIELDTYPES = ("Section Break", "Column Break", "Tab Break", "Table Break")


def check(label, got, want):
    ok = got == want
    checks.append(ok)
    print("  %-4s %-62s got=%r want=%r" % ("OK" if ok else "FAIL", label, got, want))


def _visible_columns(doctype):
    """What grid.js would actually render, in order, and where it gives up.

    Mirrors setup_visible_columns: the total starts at 1, each in_list_view field
    adds its colsize, and the FIRST time the total exceeds 11 the loop returns --
    so that field and every field after it is dropped.
    """
    shown, dropped, total = [], [], 1
    for f in frappe.get_meta(doctype).fields:
        if f.hidden or not f.in_list_view or f.fieldtype in _LAYOUT_FIELDTYPES:
            continue
        colsize = f.columns or _DEFAULT_COLSIZE.get(f.fieldtype, 2)
        total += colsize
        (dropped if total > 11 else shown).append(f.fieldname)
    return shown, dropped, total


def run():
    print("=== Purchase Receipt Item grid fits in the budget ===")
    frappe.clear_cache(doctype="Purchase Receipt Item")
    shown, dropped, total = _visible_columns("Purchase Receipt Item")
    print("  shown:   %s" % ", ".join(shown))
    print("  dropped: %s" % (", ".join(dropped) or "(none)"))
    print("  running total: %d (grid.js drops everything once this exceeds 11)" % total)

    check("nothing is silently dropped", dropped, [])
    check("total is within budget", total <= 11, True)
    check("Accepted Warehouse renders", "warehouse" in shown, True)

    # These came back at the same time as Warehouse -- they had been invisible for
    # the same reason, which is worth pinning so a future column steals width from
    # something deliberately rather than from these by accident.
    for fieldname in ("custom_length", "custom_width", "custom_thickness"):
        check("%s renders too" % fieldname, fieldname in shown, True)

    # Paid for by these four. Still on the doctype and still editable by expanding
    # the row -- only their row-view slot was given up.
    for fieldname in ("rate", "amount", "net_amount", "custom_unit_weight"):
        check("%s gave up its grid slot" % fieldname, fieldname in shown, False)
        check("%s still exists on the doctype" % fieldname,
              bool(frappe.get_meta("Purchase Receipt Item").get_field(fieldname)), True)

    print()
    print("=== Job Work Order hides the two unused tabs ===")
    frappe.clear_cache(doctype="Subcontracting Order")
    meta = frappe.get_meta("Subcontracting Order")
    for fieldname, label in (("tab_additional_costs", "Additional Costs"),
                             ("tab_other_info", "Other Info")):
        df = meta.get_field(fieldname)
        check("%s tab exists" % label, bool(df), True)
        check("%s tab is hidden" % label, bool(df and df.hidden), True)

    total_checks, failed = len(checks), checks.count(False)
    print()
    if failed:
        print("%d of %d CHECKS FAILED" % (failed, total_checks))
    else:
        print("ALL %d CHECKS PASSED" % total_checks)
