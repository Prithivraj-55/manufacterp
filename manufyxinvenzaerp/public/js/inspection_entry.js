function recalc_rework_qty(frm) {
	const rework = flt(frm.doc.total_checked_qty) - flt(frm.doc.cleared_qty);
	frm.set_value("rework_qty", rework > 0 ? rework : 0);
}

frappe.ui.form.on("Inspection Entry", {
	total_checked_qty(frm) {
		recalc_rework_qty(frm);
	},
	cleared_qty(frm) {
		recalc_rework_qty(frm);
	},
	status(frm) {
		if (frm.doc.status === "Completed" && !frm.doc.inspection_complete_date) {
			frm.set_value("inspection_complete_date", frappe.datetime.get_today());
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
