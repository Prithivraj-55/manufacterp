const FORMULA_GROUPS = ["Structurals", "Plates"];

function set_calculation_type(frm) {
	const group = frm.doc.custom_parent_item_group;
	if (FORMULA_GROUPS.includes(group)) {
		frm.set_value("custom_item_calculation_type", "Formula Weight Calculation");
	} else if (group) {
		frm.set_value("custom_item_calculation_type", "Normal Weight Calculation");
	}
}

function lock_item_group_filter(frm) {
	const field = frm.fields_dict["item_group"];

	// Null out df.link_filters so Frappe's apply_link_field_filters()
	// never fires and never resets our get_query when the dropdown opens
	field.df.link_filters = null;

	// Use a getter so ERPNext's set_query("item_group", ...) calls in
	// refresh handlers are silently swallowed and cannot override us
	Object.defineProperty(field, "get_query", {
		get() {
			return function () {
				const filters = [["Item Group", "is_group", "=", 0]];
				if (frm.doc.custom_parent_item_group) {
					filters.push([
						"Item Group",
						"parent_item_group",
						"=",
						frm.doc.custom_parent_item_group,
					]);
				}
				return { filters };
			};
		},
		set() {},
		configurable: true,
		enumerable: true,
	});
}

frappe.ui.form.on("Item", {
	refresh(frm) {
		frm.set_df_property("custom_item_calculation_type", "read_only", 1);
		frm.set_query("custom_parent_item_group", () => ({ filters: { is_group: 1 } }));
		lock_item_group_filter(frm);
	},

	custom_parent_item_group(frm) {
		set_calculation_type(frm);
		frm.set_value("item_group", "");
	},
});
