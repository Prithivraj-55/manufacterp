frappe.ui.form.on("Supplier Operation Entry", {
	refresh(frm) {
		if (frm.is_new() || !frm.doc.custom_inspection_mandatory) return;

		const log = frm.doc.custom_inspection_call_log || [];
		const pending = log.find(r => r.round_status === "Pending");

		if (!pending) {
			frm.add_custom_button(__("Add Inspection Call"), function () {
				if (!frm.doc.custom_inspection_call_date) {
					frappe.msgprint(__("Set an Inspection Call Date first."));
					return;
				}
				frappe.call({
					method: "manufyxinvenzaerp.production_management.inspection.add_inspection_call",
					args: { source_doctype: "Supplier Operation Entry", source_name: frm.doc.name },
					freeze: true,
					freeze_message: __("Logging inspection call…"),
					callback() {
						frm.reload_doc();
					},
				});
			}, __("Inspection"));
		} else if (!pending.inspection_entry) {
			frm.add_custom_button(__("Create Inspection Entry"), function () {
				frappe.call({
					method: "manufyxinvenzaerp.production_management.inspection.create_inspection_entry",
					args: { source_doctype: "Supplier Operation Entry", source_name: frm.doc.name },
					freeze: true,
					freeze_message: __("Creating Inspection Entry…"),
					callback(r) {
						if (r.message) {
							frm.reload_doc();
							frappe.set_route("Form", "Inspection Entry", r.message);
						}
					},
				});
			}, __("Inspection"));
		} else {
			frm.add_custom_button(__("View Inspection Entry"), function () {
				frappe.set_route("Form", "Inspection Entry", pending.inspection_entry);
			}, __("Inspection"));
		}
	},
});
