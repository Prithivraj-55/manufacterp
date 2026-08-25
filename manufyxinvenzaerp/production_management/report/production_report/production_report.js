// Copyright (c) 2026, Manufyxinvenza and Contributors
// License: GNU General Public License v3. See license.txt

frappe.query_reports["Production Report"] = {
	filters: [
		{
			fieldname: "production_plan",
			label: __("Production Plan (Team)"),
			fieldtype: "Link",
			options: "Production Plan",
		},
		{
			fieldname: "job_type",
			label: __("Job Type"),
			fieldtype: "Select",
			options: "\nInternal Job\nSupplier Job\nSupplier with Material",
		},
		{
			fieldname: "subcontracting_order",
			label: __("Job Work Order"),
			fieldtype: "Link",
			options: "Subcontracting Order",
		},
		{
			fieldname: "supplier",
			label: __("Supplier"),
			fieldtype: "Link",
			options: "Supplier",
		},
		{
			fieldname: "sales_order",
			label: __("Sales Order"),
			fieldtype: "Link",
			options: "Sales Order",
		},
		{
			// Narrows which operation column blocks appear, rather than which rows do:
			// the report is one row per drawing now, and an operation is a set of
			// columns on it.
			fieldname: "operation",
			label: __("Operation"),
			fieldtype: "Link",
			options: "Operation",
		},
		{
			fieldname: "status",
			label: __("Status"),
			fieldtype: "Select",
			options: "\nOpen\nIn Progress\nCompleted",
		},
		{
			fieldname: "from_date",
			label: __("From Date"),
			fieldtype: "Date",
		},
		{
			fieldname: "to_date",
			label: __("To Date"),
			fieldtype: "Date",
		},
	],
};
