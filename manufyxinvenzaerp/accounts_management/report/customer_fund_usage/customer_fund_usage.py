# Copyright (c) 2026, Manufyxinvenza and Contributors
# License: GNU General Public License v3. See license.txt

import frappe
from frappe import _


def execute(filters=None):
    filters = filters or {}
    columns = get_columns()
    data = get_data(filters)
    return columns, data


def get_columns():
    return [
        {"label": _("Source Reference No"), "fieldname": "source_reference_no", "fieldtype": "Data", "width": 130},
        {"label": _("Source of Funds"), "fieldname": "custom_source_of_funds", "fieldtype": "Link",
         "options": "Payment Entry", "width": 130},
        {"label": _("Source Customer"), "fieldname": "source_customer", "fieldtype": "Data", "width": 130},
        {"label": _("Customer Payment Date"), "fieldname": "customer_payment_date", "fieldtype": "Date", "width": 130},
        {"label": _("Total Customer Payment"), "fieldname": "total_customer_payment", "fieldtype": "Currency", "width": 140},
        {"label": _("Balance Remaining"), "fieldname": "balance_remaining", "fieldtype": "Currency", "width": 130},
        {"label": _("Supplier"), "fieldname": "party", "fieldtype": "Link", "options": "Supplier", "width": 150},
        {"label": _("Payment Type"), "fieldname": "custom_payment_type", "fieldtype": "Data", "width": 110},
        {"label": _("Against"), "fieldname": "reference_name", "fieldtype": "Dynamic Link",
         "options": "reference_doctype", "width": 150},
        {"label": _("Grand Total"), "fieldname": "grand_total", "fieldtype": "Currency", "width": 110},
        {"label": _("Payment Request"), "fieldname": "name", "fieldtype": "Link",
         "options": "Payment Request", "width": 150},
        {"label": _("Transaction Date"), "fieldname": "transaction_date", "fieldtype": "Date", "width": 100},
        {"label": _("Outstanding"), "fieldname": "outstanding_amount", "fieldtype": "Currency", "width": 110},
        {"label": _("Status"), "fieldname": "status", "fieldtype": "Data", "width": 100},
        {"label": _("PE Created"), "fieldname": "custom_payment_entry_created", "fieldtype": "Check", "width": 90},
    ]


# Columns that belong to the customer's payment (the "wallet"), not the individual
# supplier Payment Request -- blanked out on every row but the first within a
# Source of Funds group when group_by_customer_payment is on.
CUSTOMER_PAYMENT_FIELDS = [
    "source_reference_no",
    "custom_source_of_funds",
    "source_customer",
    "customer_payment_date",
    "total_customer_payment",
    "balance_remaining",
]


def get_data(filters):
    # Base conditions shared by both queries: which "wallets" (source Payment Entries)
    # are in scope. The status filter is intentionally excluded here -- already-used
    # amounts must always be computed from ALL Paid requests for a source, even when
    # the display query below is filtered down to only the Unpaid ones.
    base_conditions = ["pr.party_type = 'Supplier'", "pr.docstatus = 1",
                        "pr.custom_source_of_funds is not null", "pr.custom_source_of_funds != ''"]
    base_values = {}

    if filters.get("source_of_funds"):
        base_conditions.append("pr.custom_source_of_funds = %(source_of_funds)s")
        base_values["source_of_funds"] = filters["source_of_funds"]

    if filters.get("customer"):
        base_conditions.append("pe.party = %(customer)s")
        base_values["customer"] = filters["customer"]

    already_used_by_source = {}
    for row in frappe.db.sql(
        f"""
        SELECT pr.custom_source_of_funds, sum(pr.grand_total) as used
        FROM `tabPayment Request` pr
        LEFT JOIN `tabPayment Entry` pe ON pe.name = pr.custom_source_of_funds
        WHERE {" AND ".join(base_conditions)} AND pr.status = 'Paid'
        GROUP BY pr.custom_source_of_funds
        """,
        base_values,
        as_dict=True,
    ):
        already_used_by_source[row.custom_source_of_funds] = row.used or 0

    display_conditions = list(base_conditions)
    display_values = dict(base_values)
    if filters.get("status") == "Paid":
        display_conditions.append("pr.status = 'Paid'")
    elif filters.get("status") == "Unpaid":
        display_conditions.append("pr.status != 'Paid'")

    rows = frappe.db.sql(
        f"""
        SELECT
            pr.name, pr.transaction_date, pr.party, pr.custom_payment_type,
            pr.reference_doctype, pr.reference_name, pr.grand_total, pr.outstanding_amount,
            pr.status, pr.custom_payment_entry_created, pr.custom_source_of_funds,
            pe.party_name as source_customer, pe.reference_no as source_reference_no,
            pe.posting_date as customer_payment_date, pe.paid_amount as total_customer_payment
        FROM `tabPayment Request` pr
        LEFT JOIN `tabPayment Entry` pe ON pe.name = pr.custom_source_of_funds
        WHERE {" AND ".join(display_conditions)}
        ORDER BY pr.custom_source_of_funds, pr.transaction_date
        """,
        display_values,
        as_dict=True,
    )

    for row in rows:
        total = row.total_customer_payment or 0
        used = already_used_by_source.get(row.custom_source_of_funds, 0)
        row["balance_remaining"] = total - used

    group_by_customer_payment = filters.get("group_by_customer_payment")
    if group_by_customer_payment is None:
        group_by_customer_payment = 1  # enabled by default

    if frappe.utils.cint(group_by_customer_payment):
        seen_sources = set()
        for row in rows:
            source = row.custom_source_of_funds
            if source in seen_sources:
                for fieldname in CUSTOMER_PAYMENT_FIELDS:
                    row[fieldname] = None
            else:
                seen_sources.add(source)

    return rows
