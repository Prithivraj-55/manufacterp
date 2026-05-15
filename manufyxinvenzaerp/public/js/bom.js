frappe.ui.form.on("BOM", {
	refresh(frm) {
		// Remove the standard "Create > Production Plan" button — Production Plans
		// are created from the Material Planning doctype instead.
		frm.page.remove_inner_button(__("Production Plan"), __("Create"));
	},
});
