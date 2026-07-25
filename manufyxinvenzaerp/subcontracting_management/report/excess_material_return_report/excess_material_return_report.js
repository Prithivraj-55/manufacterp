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
