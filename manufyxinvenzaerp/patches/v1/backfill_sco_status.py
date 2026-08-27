"""
Patch: backfill_sco_status

Job Work Order status now follows its operations -- Open until work starts,
Working once any operation has quantity logged, Completed when every operation
is submitted and the Material Issue Plan's final Stock Entry is submitted (see
CustomSubcontractingOrder.update_status).

Orders submitted before that existed all sat on "Open", and nothing would move
them: the status is re-derived when an operation is saved or submitted, or when
the final Stock Entry is submitted or cancelled, and a finished order has no
such event left to fire. SC-ORD-2026-00003 on the live server is exactly that --
five operations submitted, finished goods booked, still reading "Open".

Re-derives every submitted Production-Plan-flow order once. Standard SCOs are
left alone: their status comes from ERPNext's own receipt-driven logic.

"Working" has to exist as a Status option before any of these can be written,
and the property setter that adds it is created in after_migrate, which runs
AFTER post_model_sync patches -- so add it here first. add_sco_working_status is
idempotent, and after_migrate calls it again later in this same migrate.
"""

import frappe

from manufyxinvenzaerp.setup import add_sco_working_status


def execute():
    add_sco_working_status()
    frappe.clear_cache(doctype="Subcontracting Order")

    names = frappe.get_all(
        "Subcontracting Order",
        filters={"docstatus": 1, "custom_production_plan": ["is", "set"]},
        pluck="name",
    )
    if not names:
        return

    from manufyxinvenzaerp.subcontracting_management.overrides import refresh_sco_status

    changed = 0
    for name in names:
        before = frappe.db.get_value("Subcontracting Order", name, "status")
        try:
            refresh_sco_status(name)
        except Exception:
            # One unreadable order must not stop the migrate; it will correct
            # itself the next time one of its operations is saved.
            frappe.log_error(
                title=f"backfill_sco_status: could not re-derive status for {name}",
                message=frappe.get_traceback(),
            )
            continue
        if frappe.db.get_value("Subcontracting Order", name, "status") != before:
            changed += 1

    frappe.db.commit()
    print(f"backfill_sco_status: re-derived {len(names)} Job Work Order(s), {changed} changed")
