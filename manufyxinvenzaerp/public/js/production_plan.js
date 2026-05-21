frappe.ui.form.on("Production Plan", {
	refresh(frm) {
		// Hide standard sections/fields now managed via Material Planning
		frm.toggle_display([
			// "Get Items From" field and "Get Finished Goods for Manufacture" button
			"get_items_from",
			"get_items",
			// "Preview Required Materials" section
			"download_materials_request_plan_section_section",
			"download_materials_required",
			// "Material Request Planning" section
			"material_request_planning",
			"include_non_stock_items",
			"include_subcontracted_items",
			"consider_minimum_order_qty",
			"include_safety_stock",
			"ignore_existing_ordered_qty",
			"column_break_25",
			"for_warehouse",
			"get_items_for_mr",
			"transfer_materials",
			// "Raw Materials" section (mr_items)
			"section_break_27",
			"mr_items",
			// "Other Details" section
			"other_details",
			"total_planned_qty",
			"total_produced_qty",
			"column_break_32",
			"status",
			"warehouses",
		], false);

	},
});
