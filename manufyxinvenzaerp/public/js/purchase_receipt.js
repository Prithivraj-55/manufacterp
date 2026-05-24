const FORMULA_GROUPS = ["Structurals", "Plates"];

function calc_total_weight(frm) {
	const total = (frm.doc.items || [])
		.filter(r => FORMULA_GROUPS.includes(r.custom_parent_item_group))
		.reduce((sum, r) => sum + (r.qty || 0), 0);
	frm.set_value("custom_total_weight", total);
}

frappe.ui.form.on("Purchase Receipt Item", {
	qty(frm, cdt, cdn) {
		calc_total_weight(frm);
	},

	custom_parent_item_group(frm, cdt, cdn) {
		calc_total_weight(frm);
	},

	items_remove(frm) {
		calc_total_weight(frm);
	},
});
