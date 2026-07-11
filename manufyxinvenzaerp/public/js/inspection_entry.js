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
});
