import frappe


def on_submit_payment_entry(doc, method):
    _sync_payment_entry_created_flag(doc, created=True)


def on_cancel_payment_entry(doc, method):
    _sync_payment_entry_created_flag(doc, created=False)


def _sync_payment_entry_created_flag(pe_doc, created):
    """When a Payment Entry created from a Payment Request is submitted/cancelled,
    mirror that onto the Payment Request's custom_payment_entry_created checkbox for
    easy reporting/filtering.

    Note: create_payment_entry() builds the Payment Entry against the Payment
    Request's own reference (Purchase Order/Invoice etc.), so reference_doctype on
    these rows is never "Payment Request" -- the actual link back is the dedicated
    `payment_request` field on Payment Entry Reference (see
    _allocate_payment_request_to_pe_references in erpnext's payment_request.py)."""
    for ref in pe_doc.references:
        if ref.payment_request:
            frappe.db.set_value(
                "Payment Request",
                ref.payment_request,
                "custom_payment_entry_created",
                1 if created else 0,
            )
