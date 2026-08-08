function recalc_rework_qty(frm) {
	const rework = flt(frm.doc.total_checked_qty) - flt(frm.doc.cleared_qty);
	frm.set_value("rework_qty", rework > 0 ? rework : 0);
}

frappe.ui.form.on("Inspection Entry", {
	refresh(frm) {
		frm.__insp_prev_status = frm.doc.status;
	},

	total_checked_qty(frm) {
		recalc_rework_qty(frm);
	},

	cleared_qty(frm) {
		recalc_rework_qty(frm);
	},

	// Marking Status as Completed is the one action that finalizes an Inspection
	// Entry — there is no separate manual Submit step. Feedback must already be
	// entered (revert + tell the user otherwise); only then confirm and
	// save-and-submit in one shot. Declining the confirm also reverts Status.
	status(frm) {
		if (frm.doc.docstatus !== 0) return;

		if (frm.doc.status === "Completed") {
			if (!frm.doc.feedback) {
				frappe.msgprint(__("Enter Feedback to complete it."));
				frm.set_value("status", frm.__insp_prev_status || "Working");
				return;
			}
			frappe.confirm(
				__("Mark this Inspection as Complete and Submit? Once submitted, it cannot be edited."),
				function () {
					frm.save("Submit");
				},
				function () {
					frm.set_value("status", frm.__insp_prev_status || "Working");
				}
			);
		} else {
			frm.__insp_prev_status = frm.doc.status;
		}
	},
});

function recalc_item_reject_qty(frm, cdt, cdn) {
	const row = locals[cdt][cdn];
	const reject = flt(row.qty) - flt(row.accept_qty);
	frappe.model.set_value(cdt, cdn, "reject_qty", reject > 0 ? reject : 0);
}

frappe.ui.form.on("Inspection Entry Item", {
	accept_qty(frm, cdt, cdn) {
		recalc_item_reject_qty(frm, cdt, cdn);
	},
	qty(frm, cdt, cdn) {
		recalc_item_reject_qty(frm, cdt, cdn);
	},
});

function recalc_soe_item_reject_qty(frm, cdt, cdn) {
	const row = locals[cdt][cdn];
	const reject = flt(row.qty_nos) - flt(row.accept_qty);
	frappe.model.set_value(cdt, cdn, "reject_qty", reject > 0 ? reject : 0);
}

frappe.ui.form.on("SOE Inspection Item", {
	accept_qty(frm, cdt, cdn) {
		recalc_soe_item_reject_qty(frm, cdt, cdn);
	},
	qty_nos(frm, cdt, cdn) {
		recalc_soe_item_reject_qty(frm, cdt, cdn);
	},
});
