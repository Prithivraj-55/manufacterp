"""The v16 desktop (apps screen): Manufyx's own tile, and which other apps' tiles show.

v16 builds the desktop from each app's `add_to_apps_screen` hook, surfaced as
`frappe.boot.app_data`, and shows the entries with `on_apps_screen` set. Two of the other
apps' entries cannot be turned off from their side: India Compliance's `has_permission`
passes every desk user, and FAC's (`can_use_faco`) returns a dict, which is always truthy.
So their tiles are hidden here, in `boot_session`, which runs after `app_data` is built.

Hiding is all this does. Both apps stay installed and their features keep working --
GST fields and reports are reached through ERPNext's own documents, not the tile.
"""

import frappe
from frappe.utils.user import is_website_user

# Apps whose desktop tile only a System Manager needs to see.
ADMIN_ONLY_APPS = ("india_compliance", "frappe_assistant_core")


def has_app_permission():
    return not is_website_user()


def hide_admin_only_apps(bootinfo):
    if "System Manager" in frappe.get_roles():
        return

    # An `app_data` row carries the hook's `name`, which need not be the app's own name
    # (FAC declares "FAC"), so match on both.
    hidden = set()
    for app in ADMIN_ONLY_APPS:
        hidden.add(app)
        hidden.update(entry.get("name") for entry in frappe.get_hooks("add_to_apps_screen", app_name=app))

    for row in bootinfo.get("app_data") or []:
        if row.get("app_name") in hidden:
            row["on_apps_screen"] = False
