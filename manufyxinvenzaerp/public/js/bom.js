frappe.ui.form.on("BOM", {
	refresh(frm) {
		if (frm.doc.custom_drawing) {
			// Drawing-linked BOMs: remove all Create sub-options (including Production Plan)
			frm.page.remove_inner_button(__("Update Cost"));
			frm.page.remove_inner_button(__("Browse BOM"));
			frm.page.remove_inner_button(__("New Version"));
			frm.page.get_inner_group_button(__("Create")) &&
				frm.page.get_inner_group_button(__("Create")).remove();
		}
	},
	onload_post_render(frm) {
		if (frm.is_new()) {
			frm.set_value("with_operations", 1);
			frm.set_value("routing", "Standard Manufacturing Routing");
		}
	},

	// The Rate Schedule belongs to the DRAWING, and this BOM is one of three places
	// showing it. Changing it here changes it everywhere -- so if the drawing
	// already has a different one, ask before overwriting rather than after.
	// The actual propagation is server-side (rate_schedule_sync.on_update_bom);
	// this only decides whether the change is allowed to stand.
	custom_rate_schedule(frm) {
		mfx_confirm_rate_schedule_change({
			drawing: frm.doc.custom_drawing,
			new_schedule: frm.doc.custom_rate_schedule,
			source_doctype: "BOM",
			source_name: frm.doc.name,
			on_decline: (current) => frm.set_value("custom_rate_schedule", current || ""),
		});
	},
});
