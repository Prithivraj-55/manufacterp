// Copyright (c) 2026, Manufyxinvenza and Contributors
// License: GNU General Public License v3. See license.txt

frappe.query_reports["Cut Sheet Report"] = {
	filters: [
		{
			// Phrased as what still needs attention rather than mirroring the
			// doctype's Status field. "W2 Not Written" is the one worth chasing:
			// pieces have been cut but the plate's remaining size was never written
			// back, so the rack and the system disagree.
			fieldname: "status",
			label: __("Show"),
			fieldtype: "Select",
			options: "Active\nHas Free Pieces\nFully Allocated\nW2 Not Written\nConsumed\nAll",
			default: "Active",
		},
		{
			fieldname: "company",
			label: __("Company"),
			fieldtype: "Link",
			options: "Company",
		},
		{
			fieldname: "item_code",
			label: __("Item Code"),
			fieldtype: "Link",
			options: "Item",
		},
		{
			fieldname: "batch_no",
			label: __("Batch"),
			fieldtype: "Link",
			options: "Batch",
		},
		{
			fieldname: "warehouse",
			label: __("Warehouse"),
			fieldtype: "Link",
			options: "Warehouse",
		},
		{
			// Which sheets a given job is drawing from — the reverse lookup, since
			// one Material Planning can take pieces off several plates.
			fieldname: "material_planning",
			label: __("Allocated To Material Planning"),
			fieldtype: "Link",
			options: "Material Planning",
		},
		{
			fieldname: "from_date",
			label: __("Created From"),
			fieldtype: "Date",
			default: frappe.datetime.add_months(frappe.datetime.get_today(), -3),
		},
		{
			fieldname: "to_date",
			label: __("Created To"),
			fieldtype: "Date",
			default: frappe.datetime.get_today(),
		},
	],
	formatter(value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);
		if (!data) return value;

		// Free pieces in green: these plates can still take work.
		if (column.fieldname === "available_sec_qty" && flt(data.available_sec_qty) > 0) {
			value = `<span style="color:#2f9e44;font-weight:600;">${value}</span>`;
		}
		// Cut but never reconciled — the plate in the rack is smaller than the batch
		// claims. Amber past a week, since it only matters once it has been left.
		if (column.fieldname === "w2_applied" && !data.w2_applied && flt(data.allocated_sec_qty) > 0) {
			value = `<span style="color:#e8590c;font-weight:600;">${__("Not written")}</span>`;
		}
		if (column.fieldname === "material_plannings" && data.holder_count) {
			value = `<span style="color:#1971c2;">${value}</span>`;
		}
		if (column.fieldname === "age_days" && flt(data.age_days) > 30 && flt(data.available_sec_qty) > 0) {
			value = `<span style="color:#e03131;font-weight:600;">${value}</span>`;
		}
		return value;
	},
};
