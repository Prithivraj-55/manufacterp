// `var`, not `const`: doctype_js files are eval'd into the SAME global script
// scope, so navigating Purchase Order -> Purchase Receipt in one session parses
// both files, and a repeated top-level `const` is a SyntaxError that kills the
// whole second file (none of its handlers register). `var` may be redeclared.
var FORMULA_GROUPS = ["Structurals", "Plates"];

function calc_total_weight(frm) {
	const total = (frm.doc.items || [])
		.filter(r => FORMULA_GROUPS.includes(r.custom_parent_item_group))
		.reduce((sum, r) => sum + (r.qty || 0), 0);
	frm.set_value("custom_total_weight", total);
}

function recalc_nuts_and_bolts(frm, cdt, cdn) {
	const row = locals[cdt][cdn];
	if (row.custom_parent_item_group !== "Nuts and Bolts") return;
	if (row.custom_unit_weight && row.qty) {
		frappe.model.set_value(cdt, cdn, "custom_sec_qty", row.custom_unit_weight * row.qty);
	}
}

frappe.ui.form.on("Purchase Order Item", {
	qty(frm, cdt, cdn) {
		recalc_nuts_and_bolts(frm, cdt, cdn);
		calc_total_weight(frm);
	},

	custom_unit_weight(frm, cdt, cdn) {
		recalc_nuts_and_bolts(frm, cdt, cdn);
	},

	custom_parent_item_group(frm, cdt, cdn) {
		recalc_nuts_and_bolts(frm, cdt, cdn);
		calc_total_weight(frm);
	},

	items_remove(frm) {
		calc_total_weight(frm);
	},
});
