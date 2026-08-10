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
"""

import frappe


def execute():
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
