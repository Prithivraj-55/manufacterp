"""Granting a role everything this app owns, in one pass.

A fresh deployment leaves the app's own doctypes reachable by System Manager and
nobody else, so handing over means opening a dozen doctypes and seven reports in
the Role Permissions Manager and ticking the same boxes on each. Missing one is
easy, and it surfaces much later as somebody unable to open a form.

Two different mechanisms are covered, which is the part worth testing: doctype
access is a Custom DocPerm row, while a Report carries its OWN roles table. A role
given every doctype permission still cannot see the reports unless it is added
there too.

Runs against a throwaway role and removes it afterwards.

Run: bench --site manufact execute manufyxinvenzaerp.tests.verify_bulk_permissions.run
"""

import frappe

checks = []
ROLE = "ZZTEST Bulk Perm %s" % frappe.generate_hash(length=4).upper()


def check(label, got, want):
    ok = got == want
    checks.append(ok)
    print("  %-4s %-58s got=%r want=%r" % ("OK" if ok else "FAIL", label, got, want))


def run():
    from manufyxinvenzaerp.permissions_bulk import (
        get_targets, get_role_state, apply_permissions, PERM_TYPES, SUBMITTABLE_ONLY,
    )

    frappe.get_doc({"doctype": "Role", "role_name": ROLE}).insert(ignore_permissions=True)
    frappe.db.commit()
    print("throwaway role:", ROLE)

    try:
        print()
        print("=== it finds what the app owns, from the app's own modules ===")
        targets = get_targets()
        names = [d["name"] for d in targets["doctypes"]]
        check("modules come from the app", "Manufyxinvenzaerp" in targets["modules"], True)
        check("its doctypes are listed", "Material Planning" in names, True)
        check("...including the newest ones", "Cut Sheet" in names, True)
        check("child tables are excluded",
              any(n == "Material Planning Material Mapping" for n in names), False)
        report_names = [r["name"] for r in targets["reports"]]
        check("reports are listed too", "Cut Sheet Report" in report_names, True)
        print("   %d doctype(s), %d report(s)" % (len(names), len(report_names)))

        print()
        print("=== a brand new role starts with nothing ===")
        before = get_role_state(ROLE)
        readable = [d for d, v in before["doctypes"].items() if v["read"]]
        check("no doctype is readable yet", readable, [])

        print()
        print("=== one pass grants the lot ===")
        wanted = ["read", "write", "create", "delete", "export", "import"]
        res = apply_permissions(ROLE, wanted)
        check("every doctype was touched", res["doctype_count"], len(names))
        after = get_role_state(ROLE)
        for perm in wanted:
            granted = [d for d, v in after["doctypes"].items() if v[perm]]
            check("%s granted everywhere" % perm, len(granted), len(names))

        print()
        print("=== submit/cancel/amend only where they mean something ===")
        submittable = [d["name"] for d in targets["doctypes"] if d.get("is_submittable")]
        plain = [d["name"] for d in targets["doctypes"] if not d.get("is_submittable")]
        apply_permissions(ROLE, ["read", "submit"])
        state = get_role_state(ROLE)
        if submittable:
            check("submittable doctypes got Submit",
                  all(state["doctypes"][d]["submit"] for d in submittable), True)
        check("the others did not",
              any(state["doctypes"][d]["submit"] for d in plain), False)
        check("the permission list names them", sorted(SUBMITTABLE_ONLY),
              ["amend", "cancel", "submit"])

        print()
        print("=== running it twice changes nothing the second time ===")
        first = apply_permissions(ROLE, ["read", "write"])
        second = apply_permissions(ROLE, ["read", "write"])
        check("same doctype count both times",
              first["doctype_count"], second["doctype_count"])
        state = get_role_state(ROLE)
        check("still readable everywhere",
              len([d for d, v in state["doctypes"].items() if v["read"]]), len(names))

        print()
        print("=== granting does not take away unless asked ===")
        apply_permissions(ROLE, ["read", "write", "create"])
        apply_permissions(ROLE, ["read"])          # write/create not ticked
        state = get_role_state(ROLE)
        kept = len([d for d, v in state["doctypes"].items() if v["write"]])
        check("write survived a grant that did not mention it", kept, len(names))
        apply_permissions(ROLE, ["read"], remove_others=1)
        state = get_role_state(ROLE)
        check("...and is removed when that is asked for",
              len([d for d, v in state["doctypes"].items() if v["write"]]), 0)
        check("read is still there",
              len([d for d, v in state["doctypes"].items() if v["read"]]), len(names))

        print()
        print("=== reports need their own roles table, not just doctype rights ===")
        restricted = None
        for name in report_names:
            if frappe.get_all("Has Role", filters={"parent": name, "parenttype": "Report"},
                              limit=1):
                restricted = name
                break
        if not restricted:
            print("   (every report on this site is open to all roles -- nothing to restrict)")
            res = apply_permissions(ROLE, ["read"], reports=report_names)
            check("they are reported as left alone, not silently restricted",
                  len(res["skipped"]), len(report_names))
        else:
            res = apply_permissions(ROLE, ["read"], reports=[restricted])
            granted = frappe.get_all("Has Role", filters={"parent": restricted,
                                                          "parenttype": "Report"}, pluck="role")
            check("the role was added to %s" % restricted, ROLE in granted, True)

        print()
        print("=== only a System Manager may run it ===")
        check("the caller is checked", "System Manager" in frappe.get_roles(), True)
        try:
            apply_permissions(ROLE, [])
            refused = False
        except Exception as e:
            refused = "at least one permission" in frappe.utils.strip_html(str(e))
        check("an empty permission list is refused", refused, True)
        try:
            apply_permissions("ZZ Not A Real Role", ["read"])
            refused = False
        except Exception as e:
            refused = "does not exist" in frappe.utils.strip_html(str(e))
        check("an unknown role is refused", refused, True)

    finally:
        for p in frappe.get_all("Custom DocPerm", filters={"role": ROLE}, pluck="name"):
            frappe.delete_doc("Custom DocPerm", p, force=1, ignore_permissions=True)
        # Take the role off through the Report document, not with a direct delete.
        # Saving a Report on a bench with developer_mode on re-exports it to the
        # app's source, so adding the role wrote it into the shipped JSON -- and a
        # raw delete would leave a throwaway test role committed in the app.
        touched = {r.parent for r in frappe.get_all(
            "Has Role", filters={"role": ROLE, "parenttype": "Report"},
            fields=["parent"])}
        for name in touched:
            if not frappe.db.exists("Report", name):
                continue
            report = frappe.get_doc("Report", name)
            report.roles = [r for r in (report.roles or []) if r.role != ROLE]
            report.save(ignore_permissions=True)
        if frappe.db.exists("Role", ROLE):
            frappe.delete_doc("Role", ROLE, force=1, ignore_permissions=True)
        frappe.db.commit()
        frappe.clear_cache()
        print()
        print("throwaway role removed")

    print()
    print("=== SUMMARY ===")
    if all(checks):
        print("ALL %d CHECKS PASSED" % len(checks))
    else:
        print("%d of %d CHECKS FAILED" % (checks.count(False), len(checks)))
