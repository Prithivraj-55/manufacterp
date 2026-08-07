// Copyright (c) 2026, Manufyxinvenza and Contributors
// License: GNU General Public License v3. See license.txt

frappe.query_reports["Inspection Status Report"] = {
	filters: [
		{
			fieldname: "source_doctype",
			label: __("Source"),
			fieldtype: "Select",
			options: "\nJob Card\nSupplier Operation Entry\nPurchase Receipt",
		},
		{
			fieldname: "operation",
			label: __("Operation"),
			fieldtype: "Select",
			options: "\nFitup Inspection\nFinal Inspection",
			description: __("Only applies to Job Card / Supplier Operation Entry rows."),
		},
		{
			fieldname: "inspection_status",
			label: __("Inspection Status"),
			fieldtype: "Select",
			options: "\nOpen\nWorking\nCompleted",
		},
		{
			fieldname: "production_plan",
			label: __("Production Plan"),
			fieldtype: "Link",
			options: "Production Plan",
		},
		{
			fieldname: "sales_order",
			label: __("Sales Order"),
			fieldtype: "Link",
			options: "Sales Order",
		},
	],
};
