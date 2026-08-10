// Copyright (c) 2026, Manufyxinvenza and Contributors
// License: GNU General Public License v3. See license.txt

frappe.query_reports["Customer Fund Usage"] = {
	filters: [
		{
			fieldname: "customer",
			label: __("Customer"),
			fieldtype: "Link",
			options: "Customer",
		},
		{
			fieldname: "source_of_funds",
			label: __("Source of Funds (Customer Payment Entry)"),
			fieldtype: "Link",
			options: "Payment Entry",
			get_query: function () {
				return {
					query: "manufyxinvenzaerp.accounts_management.payment_request.payment_entry_query",
				};
			},
		},
		{
			fieldname: "status",
			label: __("Status"),
			fieldtype: "Select",
			options: ["", "Paid", "Unpaid"],
		},
		{
			fieldname: "group_by_customer_payment",
			label: __("Group by Customer Payment"),
			fieldtype: "Check",
			default: 1,
		},
	],
};
