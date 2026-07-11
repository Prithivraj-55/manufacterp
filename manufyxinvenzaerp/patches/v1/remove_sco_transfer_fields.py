"""
Patch: remove_sco_transfer_fields

Subcontracting Order's warehouse-transfer and excess-material-return fields have
moved to the new Material Issue Plan doctype (see subcontracting_management/
material_issue_plan_transfer.py). A snapshot of every value being removed was
written to sco_field_removal_snapshot_2026-07-04.json before this patch ran.

Removes these Custom Field records from Subcontracting Order (Work Order's own
copies of the same fieldnames are untouched — they are separate Custom Field
records on a different dt, deferred to the WO round):
  custom_source_warehouse, custom_cnc_warehouse, custom_return_warehouse,
  custom_tab_excess_return, custom_section_excess_return,
  custom_excess_actions_html, custom_excess_return_items,
  custom_excess_return_total_kg, custom_excess_return_total_nos

Also deletes now-orphaned SCO Excess Material Item rows parented to
Subcontracting Order specifically (Work Order's own rows are untouched).
"""

import frappe

REMOVED_FIELDS = [
    "custom_source_warehouse",
    "custom_cnc_warehouse",
    "custom_return_warehouse",
    "custom_tab_excess_return",
    "custom_section_excess_return",
    "custom_excess_actions_html",
    "custom_excess_return_items",
    "custom_excess_return_total_kg",
    "custom_excess_return_total_nos",
]


def execute():
    for fieldname in REMOVED_FIELDS:
        name = frappe.db.get_value(
            "Custom Field", {"dt": "Subcontracting Order", "fieldname": fieldname}
        )
        if name:
            frappe.delete_doc("Custom Field", name, ignore_permissions=True, force=True)

    if frappe.db.table_exists("SCO Excess Material Item"):
        frappe.db.delete("SCO Excess Material Item", {"parenttype": "Subcontracting Order"})

    frappe.db.commit()
