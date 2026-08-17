"""Grant a role the same permissions across every doctype and report this app owns.

A fresh deployment gives the app's own doctypes to System Manager and nobody else,
so handing the system to a client means opening a dozen doctypes and seven reports
one at a time in Role Permissions Manager, ticking the same six boxes on each. It
is tedious and it is easy to miss one -- and a missed doctype shows up much later
as somebody unable to open a form with no obvious reason why.

This does the same thing in one pass, over a list the app derives from its own
modules rather than one anybody has to maintain: add a doctype and it is covered
automatically.

Two different mechanisms are involved and both are handled here. Doctype access is
a Custom DocPerm row per (doctype, role, permlevel). Report access is NOT -- a
Report carries its own roles table, and a user needs both that and read on the
report's reference doctype, which is why granting a role "everything" through the
Role Permissions Manager still leaves the reports invisible.

Nothing outside the app's own modules is touched, and only System Manager can run
any of it.

One note for development benches: granting a role access to a Report saves the
Report, and saving a Report while developer_mode is on re-exports it into the
app's source. On a production site developer_mode is off and nothing is written
to disk -- but on a dev bench, expect the report JSON files to show as modified
afterwards.
"""

import frappe
from frappe import _
from frappe.permissions import add_permission, update_permission_property

# Every permission a role can be given here, in the order they are shown.
PERM_TYPES = [
    ("read", "Read"),
    ("write", "Write"),
    ("create", "Create"),
    ("delete", "Delete"),
    ("submit", "Submit"),
    ("cancel", "Cancel"),
    ("amend", "Amend"),
    ("print", "Print"),
    ("email", "Email"),
    ("export", "Export"),
    ("import", "Import"),
    ("report", "Report"),
    ("share", "Share"),
]

# Permissions that only mean something on a submittable doctype. Setting them
# elsewhere is harmless but misleading, so they are skipped rather than written.
SUBMITTABLE_ONLY = {"submit", "cancel", "amend"}


def _app_modules():
    """The app's own modules, read from modules.txt rather than hardcoded."""
    return frappe.get_module_list("manufyxinvenzaerp")


def _guard():
    if "System Manager" not in frappe.get_roles():
        frappe.throw(_("Only a System Manager can change permissions in bulk."),
                     frappe.PermissionError)


@frappe.whitelist()
def get_targets():
    """Everything this app owns, with what the chosen role can reach today."""
    _guard()
    modules = _app_modules()

    doctypes = frappe.get_all(
        "DocType",
        filters={"module": ["in", modules], "istable": 0},
        fields=["name", "issingle", "is_submittable"],
        order_by="name",
    )
    reports = frappe.get_all(
        "Report",
        filters={"module": ["in", modules]},
        fields=["name", "ref_doctype", "report_type"],
        order_by="name",
    )
    return {
        "modules": modules,
        "doctypes": doctypes,
        "reports": reports,
    }


@frappe.whitelist()
def get_role_state(role):
    """What the role can already do, so the page shows the starting point rather
    than implying everything is about to change."""
    _guard()
    targets = get_targets()
    names = [d["name"] for d in targets["doctypes"]]
    existing = {}
    if names:
        for p in frappe.get_all(
            "Custom DocPerm",
            filters={"role": role, "parent": ["in", names], "permlevel": 0},
            fields=["parent"] + [f for f, _label in PERM_TYPES],
        ):
            existing[p.parent] = p
    # A doctype with no Custom DocPerm row may still be reachable through the
    # standard DocPerm shipped with it, so that is read too -- otherwise the page
    # would report "no access" for something the role can already open.
    standard = {}
    if names:
        # Read straight from the table: DocPerm is a child of DocType, and the
        # query builder will not select from a child table on its own.
        fields = ", ".join("`%s`" % f for f, _label in PERM_TYPES)
        for p in frappe.db.sql(
            """SELECT parent, {0} FROM `tabDocPerm`
               WHERE role = %s AND permlevel = 0 AND parent IN ({1})""".format(
                fields, ", ".join(["%s"] * len(names))),
            [role] + names, as_dict=True,
        ):
            standard.setdefault(p.parent, p)

    doctype_state = {}
    for d in targets["doctypes"]:
        row = existing.get(d["name"]) or standard.get(d["name"])
        doctype_state[d["name"]] = {
            f: int(bool(row.get(f))) if row else 0 for f, _label in PERM_TYPES
        }

    report_state = {}
    for r in targets["reports"]:
        roles = frappe.get_all("Has Role", filters={"parent": r["name"],
                                                    "parenttype": "Report"}, pluck="role")
        # A Report with no roles at all is open to everyone who can read its
        # reference doctype, which is worth showing as such.
        report_state[r["name"]] = {
            "granted": (not roles) or (role in roles),
            "unrestricted": not roles,
        }

    return {"doctypes": doctype_state, "reports": report_state}


@frappe.whitelist()
def apply_permissions(role, permissions, doctypes=None, reports=None, remove_others=0):
    """Give `role` the ticked permissions on the chosen doctypes, and access to the
    chosen reports.

    permissions: list of permission fieldnames, e.g. ["read", "write", "create"].
    doctypes / reports: names to act on. Omitted means everything the app owns.
    remove_others: when set, permissions NOT ticked are explicitly turned off, so
    the role ends up with exactly what was asked for rather than what it happens to
    have accumulated. Off by default -- granting should not silently take away.
    """
    _guard()
    if isinstance(permissions, str):
        permissions = frappe.parse_json(permissions)
    if isinstance(doctypes, str):
        doctypes = frappe.parse_json(doctypes)
    if isinstance(reports, str):
        reports = frappe.parse_json(reports)
    remove_others = frappe.utils.cint(remove_others)

    if not role:
        frappe.throw(_("Choose a role first."))
    if not frappe.db.exists("Role", role):
        frappe.throw(_("Role {0} does not exist.").format(role))
    if not permissions:
        frappe.throw(_("Tick at least one permission."))

    targets = get_targets()
    all_doctypes = {d["name"]: d for d in targets["doctypes"]}
    all_reports = {r["name"]: r for r in targets["reports"]}

    chosen_doctypes = [d for d in (doctypes or list(all_doctypes)) if d in all_doctypes]
    chosen_reports = [r for r in (reports or list(all_reports)) if r in all_reports]

    changed, skipped = [], []

    for name in chosen_doctypes:
        meta = all_doctypes[name]
        # add_permission is a no-op when the row already exists, which is what
        # makes running this twice safe.
        add_permission(name, role, 0)
        applied = []
        for field, _label in PERM_TYPES:
            if field in SUBMITTABLE_ONLY and not meta.get("is_submittable"):
                continue
            wanted = 1 if field in permissions else 0
            if not wanted and not remove_others:
                continue
            update_permission_property(name, role, 0, field, wanted)
            if wanted:
                applied.append(field)
        changed.append({"type": "DocType", "name": name, "applied": applied})

    for name in chosen_reports:
        report = frappe.get_doc("Report", name)
        existing = [r.role for r in (report.roles or [])]
        if not existing:
            # No roles listed means the report is already open to anyone who can
            # read its reference doctype. Adding this role would RESTRICT it to
            # that role alone, which is the opposite of what was asked for.
            skipped.append({"type": "Report", "name": name,
                            "reason": _("already open to every role")})
            continue
        if role in existing:
            skipped.append({"type": "Report", "name": name,
                            "reason": _("role already listed")})
            continue
        report.append("roles", {"role": role})
        report.save(ignore_permissions=True)
        changed.append({"type": "Report", "name": name, "applied": ["access"]})

    frappe.clear_cache()
    frappe.db.commit()

    return {
        "role": role,
        "permissions": permissions,
        "changed": changed,
        "skipped": skipped,
        "doctype_count": len([c for c in changed if c["type"] == "DocType"]),
        "report_count": len([c for c in changed if c["type"] == "Report"]),
    }
