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
});
