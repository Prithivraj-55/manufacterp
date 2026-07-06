"""
Patch: remove_wo_transfer_fields

Work Order's warehouse-transfer and excess-material-return fields have moved to
the Material Issue Plan doctype (see subcontracting_management/
material_issue_plan_transfer.py) — mirrors remove_sco_transfer_fields, the SCO
round of the same migration. A snapshot of every value being removed was
written to wo_field_removal_snapshot_2026-07-06.json before this patch ran.

Removes these Custom Field records from Work Order (Subcontracting Order's own
copies of the same fieldnames were already removed in the SCO round):
  custom_source_warehouse, custom_cnc_warehouse, custom_tab_excess_return,
  custom_section_excess_return, custom_excess_actions_html,
  custom_excess_return_items, custom_excess_return_total_kg,
  custom_excess_return_total_nos

Unlike SCO, Work Order never had a distinct custom_return_warehouse field — its
excess-return flow reuses the standard fg_warehouse field, which is untouched.

Also deletes now-orphaned SCO Excess Material Item rows parented to Work Order
specifically (Subcontracting Order's own rows were already deleted in the SCO
round's patch).
"""

import frappe

REMOVED_FIELDS = [
    "custom_source_warehouse",
    "custom_cnc_warehouse",
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
            "Custom Field", {"dt": "Work Order", "fieldname": fieldname}
        )
        if name:
            frappe.delete_doc("Custom Field", name, ignore_permissions=True, force=True)

    frappe.db.delete("SCO Excess Material Item", {"parenttype": "Work Order"})

    frappe.db.commit()
