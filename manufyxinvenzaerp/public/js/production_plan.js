frappe.ui.form.on("Production Plan", {
	refresh(frm) {
		// Hide standard sections/fields now managed via Material Planning
		frm.toggle_display([
			// "Get Items From" field
			"get_items_from",
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

		// "Get Raw Materials" — re-explodes po_items BOMs and refills BOM Raw Material List
		frm.add_custom_button(__("Get Raw Materials"), function () {
			if (!frm.doc.po_items || !frm.doc.po_items.length) {
				frappe.msgprint(__("No items to manufacture found. Add FG items first."));
				return;
			}
			if (!frm.doc.company) {
				frappe.msgprint(__("Set Company first."));
				return;
			}
			frappe.call({
				method: "manufyxinvenzaerp.production_plan_management.production_plan.get_bom_raw_materials_for_pp",
				args: { doc: frm.doc },
				freeze: true,
				freeze_message: __("Exploding BOMs…"),
				callback(r) {
					if (!r.message) return;
					frm.clear_table("custom_bom_raw_materials");
					(r.message || []).forEach(function (row) {
						let child = frm.add_child("custom_bom_raw_materials");
						Object.keys(row).forEach(function (k) {
							if (k !== "name") child[k] = row[k];
						});
					});
					frm.refresh_field("custom_bom_raw_materials");
					frappe.show_alert({
						message: __("{0} raw material row(s) loaded.", [r.message.length]),
						indicator: "green",
					}, 5);
				},
			});
		});
	},
});

// Auto-fill Planned Item from the selected Batch's item field
frappe.ui.form.on("Production Plan BOM Raw Material", {
	batch(frm, cdt, cdn) {
		let row = locals[cdt][cdn];
		if (!row.batch) {
			frappe.model.set_value(cdt, cdn, "planned_item", "");
			return;
		}
		frappe.db.get_value("Batch", row.batch, "item", function (r) {
			if (r && r.item) {
				frappe.model.set_value(cdt, cdn, "planned_item", r.item);
			}
		});
	},
});
