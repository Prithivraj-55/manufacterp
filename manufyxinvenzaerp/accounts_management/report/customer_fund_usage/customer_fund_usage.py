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
        # What the customer's payment was booked against -- normally the Sales Order it
        # came in for. Data rather than Dynamic Link because one Payment Entry may be
        # allocated across several documents, and those are shown comma-separated; a
        # Dynamic Link holding a list would render as a broken link.
        {"label": _("Reference Type"), "fieldname": "source_reference_type", "fieldtype": "Data", "width": 110},
        {"label": _("Reference Name"), "fieldname": "source_reference_name", "fieldtype": "Data", "width": 150},
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
    "source_reference_type",
    "source_reference_name",
    "source_customer",
    "customer_payment_date",
    "total_customer_payment",
    "balance_remaining",
]


def _references_by_payment_entry(pe_names):
    """{Payment Entry: (types, names)} from its own Payment Entry Reference rows --
    what the customer's money was booked against.

    Distinct from the "Against" column, which is the supplier Payment Request's
    reference, not the incoming customer payment's.

    One query for the whole report rather than one per row: the report already groups
    many Payment Requests under a single source, so a per-row lookup would repeat the
    same read for every row in the group. Several allocations are joined with ", " --
    ERPNext allows one payment to be split across documents even though this site has
    none today."""
    if not pe_names:
        return {}
    rows = frappe.get_all(
        "Payment Entry Reference",
        filters={"parent": ["in", list(pe_names)], "parenttype": "Payment Entry"},
        fields=["parent", "reference_doctype", "reference_name"],
        order_by="parent, idx",
    )
    grouped = {}
    for r in rows:
        types, names = grouped.setdefault(r.parent, ([], []))
        if r.reference_doctype and r.reference_doctype not in types:
            types.append(r.reference_doctype)
        if r.reference_name:
            names.append(r.reference_name)
    return {pe: (", ".join(t), ", ".join(n)) for pe, (t, n) in grouped.items()}


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

    # Sales Order narrows the wallets in scope to the customer payments booked against
    # that order, so every supplier payment funded out of them comes through. Sits in
    # base_conditions with the customer filter, NOT in display_conditions: both select
    # which sources are in scope, and Balance Remaining has to be computed from all of a
    # source's Paid requests to stay correct.
    if filters.get("sales_order"):
        base_conditions.append(
            """EXISTS (SELECT 1 FROM `tabPayment Entry Reference` per
                       WHERE per.parent = pr.custom_source_of_funds
                         AND per.parenttype = 'Payment Entry'
                         AND per.reference_doctype = 'Sales Order'
                         AND per.reference_name = %(sales_order)s)"""
        )
        base_values["sales_order"] = filters["sales_order"]

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
        ORDER BY pr.custom_source_of_funds, pr.transaction_date, pr.name
        """,
        display_values,
        as_dict=True,
    )

    refs_by_pe = _references_by_payment_entry(
        {r.custom_source_of_funds for r in rows if r.custom_source_of_funds}
    )

    for row in rows:
        total = row.total_customer_payment or 0
        used = already_used_by_source.get(row.custom_source_of_funds, 0)
        row["balance_remaining"] = total - used
        ref_type, ref_name = refs_by_pe.get(row.custom_source_of_funds, ("", ""))
        row["source_reference_type"] = ref_type
        row["source_reference_name"] = ref_name

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
