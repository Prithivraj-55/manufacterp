"""Shared "copy reference/dimension fields forward from the parent
transaction's linked row" helper (Report 3 Finding H-08, Report 6 Finding
RB-02) -- consolidates the pattern previously re-implemented independently
in purchase_order.py (_copy_from_mr_item), purchase_receipt.py
(_copy_from_po_item), and request_for_quotation.py (_copy_from_mr_item).

Supplier Quotation's own _copy_from_rfq_item_if_blank has a genuinely
different two-source fallback chain and a narrower blank-check basis than
the other three, so it is not forced through copy_reference_fields_if_blank
below (that would change its behavior) -- it instead reuses fetch_fields()
to remove its own duplicated frappe.db.get_value calls while keeping its
fallback logic exactly as it was.
"""

import frappe


def fetch_fields(source_doctype, source_name, fields):
    """Thin, shared wrapper around the (doctype, name, [fields], as_dict=True)
    frappe.db.get_value shape used by every reference-copy-forward call site
    in this app. Returns None if source_name is falsy or no matching row exists."""
    if not source_name:
        return None
    return frappe.db.get_value(source_doctype, source_name, fields, as_dict=True)


def copy_reference_fields_if_blank(row, source_doctype, source_link_field, fields, blank_check_fields=None):
    """Copy `fields` onto `row` from the `source_doctype` row named by
    `row.get(source_link_field)`.

    `blank_check_fields` controls which subset of fields is inspected to
    decide whether `row` already "has data" (defaults to `fields` itself,
    matching Purchase Order's and Purchase Receipt's existing behavior).

    Pass `blank_check_fields=False` to always copy regardless of existing
    data -- matches Request for Quotation's existing unconditional
    copy-forward-on-every-validate behavior, preserved here rather than
    silently changed to a blank-check.

    Returns True if a copy was performed, False otherwise.
    """
    source_name = row.get(source_link_field)
    if not source_name:
        return False

    if blank_check_fields is not False:
        check_fields = fields if blank_check_fields is None else blank_check_fields
        if any(row.get(f) for f in check_fields):
            return False

    source = fetch_fields(source_doctype, source_name, fields)
    if not source:
        return False

    for field in fields:
        row.set(field, source.get(field))
    return True
