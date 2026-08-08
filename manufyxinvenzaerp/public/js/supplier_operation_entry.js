frappe.ui.form.on("Supplier Operation Entry", {
	refresh(frm) {
		if (frm.is_new() || !frm.doc.custom_inspection_mandatory) return;

		const log = frm.doc.custom_inspection_call_log || [];
		const pending = log.find(r => r.round_status === "Pending");

		if (!pending || !pending.inspection_entry) {
			frm.add_custom_button(__("Create Inspection"), function () {
				_soe_create_inspection(frm, pending);
			}, __("Inspection"));
		} else {
			frm.add_custom_button(__("View Inspection Entry"), function () {
				frappe.set_route("Form", "Inspection Entry", pending.inspection_entry);
			}, __("Inspection"));
		}
	},
});

// One button drives the whole hand-off to QC: logs an Inspection Call (if one
// isn't already pending) using whatever is currently sitting in the Inspection
// Items table, then creates the Inspection Entry from it automatically -- no
// separate manual "Add Inspection Call" step.
function _soe_create_inspection(frm, pending) {
	if (!pending && !frm.doc.custom_inspection_call_date) {
		frappe.msgprint(__("Set an Inspection Call Date first."));
		return;
	}

	const create_entry = function () {
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
	};

	if (pending) {
		// A round is already logged (just no Inspection Entry yet) -- go straight to creating it.
		create_entry();
		return;
	}

	frappe.call({
		method: "manufyxinvenzaerp.production_management.inspection.add_inspection_call",
		args: { source_doctype: "Supplier Operation Entry", source_name: frm.doc.name },
		freeze: true,
		freeze_message: __("Logging inspection call…"),
		callback() {
			create_entry();
		},
	});
}
