"""
Patch: backfill_payment_entry_created_flag

The on_submit/on_cancel hook for custom_payment_entry_created (Payment Request)
originally checked `Payment Entry Reference.reference_doctype == "Payment Request"`,
which is never true -- create_payment_entry() builds the Payment Entry against the
Payment Request's own reference document (Purchase Order/Invoice etc.), and the
actual link back to the Payment Request is the dedicated `payment_request` field on
Payment Entry Reference. The hook has been fixed (see accounts_management/
payment_entry.py) to use that field; this patch backfills the flag for Payment
Requests whose Payment Entry was already submitted before the fix.

custom_payment_entry_created is a Custom Field, and post_model_sync patches run
*before* sync_fixtures()/sync_customizations()/after_migrate -- so on a site
receiving this app version for the first time the column does not exist yet and a
plain UPDATE dies with "Unknown column ... in 'SET'". Create the field here first
(create_custom_fields is idempotent, and after_migrate makes the same call later in
this very migrate), then backfill.
"""

import frappe

from manufyxinvenzaerp.setup import create_payment_request_custom_fields

FIELDNAME = "custom_payment_entry_created"


def execute():
    create_payment_request_custom_fields()

    if not frappe.db.has_column("Payment Request", FIELDNAME):
        # Never fail a migrate over a backfill -- after_migrate will add the column
        # later in this run, so only the historical flag is missed.
        frappe.log_error(
            title="backfill_payment_entry_created_flag skipped",
            message=f"Payment Request.{FIELDNAME} still missing after field creation.",
        )
        return

    frappe.db.sql(
        """
        UPDATE `tabPayment Request` pr
        SET custom_payment_entry_created = 1
        WHERE EXISTS (
            SELECT 1
            FROM `tabPayment Entry Reference` per
            JOIN `tabPayment Entry` pe ON pe.name = per.parent
            WHERE per.payment_request = pr.name AND pe.docstatus = 1
        )
        """
    )
    frappe.db.commit()
