// Copyright (c) 2026, Manufyxinvenza and Contributors
// License: GNU General Public License v3. See license.txt

frappe.query_reports["Excess Material Return Report"] = {
	filters: [
		{
			fieldname: "status",
			label: __("Status"),
			fieldtype: "Select",
			options: "Pending\nReturned\nAll",
			default: "Pending",
		},
		{
			fieldname: "company",
			label: __("Company"),
			fieldtype: "Link",
			options: "Company",
		},
		{
			fieldname: "material_issue_plan",
			label: __("Material Issue Plan"),
			fieldtype: "Link",
			options: "Material Issue Plan",
		},
		{
			fieldname: "subcontracting_order",
			label: __("Subcontracting Order"),
			fieldtype: "Link",
			options: "Subcontracting Order",
		},
		{
			fieldname: "item_code",
			label: __("Item Code"),
			fieldtype: "Link",
			options: "Item",
		},
		{
			fieldname: "sales_order",
			label: __("Sales Order"),
			fieldtype: "Link",
			options: "Sales Order",
		},
		{
			fieldname: "job_type",
			label: __("Job Type"),
			fieldtype: "Select",
			options: "\nInternal Job\nSupplier Job\nSupplier with Material",
		},
		{
			fieldname: "return_type",
			label: __("Return Type"),
			fieldtype: "Select",
			options: "\nReturn to Own Warehouse\nRetain at Supplier (Virtual)",
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
	formatter(value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);
		// Highlight excess items pending return/claim for a while, so the
		// team notices ageing off-cuts without a separate notification
		// channel (client change request Phase 7.1).
		if (column.fieldname === "days_pending" && data && data.days_pending > 7) {
			value = `<span style="color:#e03131;font-weight:600;">${value}</span>`;
		}
		return value;
	},
};
