frappe.ui.form.on("Drawing", {
	refresh(frm) {
		if (frm.doc.docstatus === 1 && frm.doc.status === "Working") {
			frm.add_custom_button(__("Mark as Final Revision"), function () {
				frappe.confirm(
					__("Mark this drawing as <b>Final Revision</b>? This cannot be undone."),
					function () {
						frappe.call({
							method: "manufyxinvenzaerp.drawing_management.drawing_utils.mark_as_final_revision",
							args: { drawing_name: frm.doc.name },
							freeze: true,
							callback: function () {
								frm.reload_doc();
							},
						});
					}
				);
			});
		}

		if (frm.doc.docstatus === 1 && frm.doc.status === "Final Revision") {
			frm.add_custom_button(__("Create BOM"), function () {
				frappe.confirm(
					__("Create a BOM for <b>" + (frm.doc.fg_item_name || frm.doc.fg_item_code) + "</b>?"),
					function () {
						frappe.call({
							method: "manufyxinvenzaerp.drawing_management.drawing_utils.create_bom_from_drawing",
							args: { drawing_name: frm.doc.name },
							freeze: true,
							callback: function (r) {
								if (r.message) {
									frappe.msgprint({
										title: __("BOM Created"),
										message: __("BOM created") + ': <a href="/app/bom/' +
											encodeURIComponent(r.message) + '" target="_blank">' +
											r.message + "</a>",
										indicator: "green",
									});
									frm.reload_doc();
								}
							},
						});
					}
				);
			}, __("Create"));
		}

		frm.set_query("batch", "items", function (doc, cdt, cdn) {
			var row = locals[cdt][cdn];
			return {
				query: "manufyxinvenzaerp.drawing_management.drawing_utils.get_batches_for_drawing_item",
				filters: { item_code: row.material_code },
			};
		});

		update_totals(frm);
	},

	customer(frm) {
		frm.set_value("customer_no", frm.doc.customer || "");
	},
});

frappe.ui.form.on("Drawing Item", {
	material_code(frm, cdt, cdn) {
		var row = locals[cdt][cdn];
		if (!row.material_code) return;
		frappe.db.get_value(
			"Item",
			row.material_code,
			["item_name", "item_group", "description", "custom_material_spec",
			 "custom_unit_weight", "custom_secondary_uom", "custom_parent_item_group", "stock_uom"],
			function (r) {
				if (!r) return;
				frappe.model.set_value(cdt, cdn, "material_name", r.item_name || "");
				frappe.model.set_value(cdt, cdn, "item_group", r.item_group || "");
				frappe.model.set_value(cdt, cdn, "parent_item_group", r.custom_parent_item_group || "");
				frappe.model.set_value(cdt, cdn, "raw_material_description", r.description || "");
				frappe.model.set_value(cdt, cdn, "material_spec", r.custom_material_spec || "");
				frappe.model.set_value(cdt, cdn, "unit_weight", r.custom_unit_weight || 0);
				frappe.model.set_value(cdt, cdn, "sec_uom", r.custom_secondary_uom || "");
				frappe.model.set_value(cdt, cdn, "uom", r.stock_uom || "");
				setTimeout(function () { drawing_calculate_qty(frm, cdt, cdn); }, 300);
			}
		);
	},

	batch(frm, cdt, cdn) {
		var row = locals[cdt][cdn];
		if (!row.batch) return;
		frappe.db.get_value(
			"Batch",
			row.batch,
			["custom_thickness", "custom_length", "custom_width"],
			function (r) {
				if (!r) return;
				if (r.custom_thickness) frappe.model.set_value(cdt, cdn, "thickness", r.custom_thickness);
				if (r.custom_length) frappe.model.set_value(cdt, cdn, "length", r.custom_length);
				if (r.custom_width) frappe.model.set_value(cdt, cdn, "width", r.custom_width);
				drawing_calculate_qty(frm, cdt, cdn);
			}
		);
	},

	thickness(frm, cdt, cdn) { drawing_calculate_qty(frm, cdt, cdn); },
	length(frm, cdt, cdn) { drawing_calculate_qty(frm, cdt, cdn); },
	width(frm, cdt, cdn) { drawing_calculate_qty(frm, cdt, cdn); },
	sec_qty(frm, cdt, cdn) { drawing_calculate_qty(frm, cdt, cdn); },
	unit_weight(frm, cdt, cdn) { drawing_calculate_qty(frm, cdt, cdn); },

	rate(frm, cdt, cdn) { drawing_calculate_amount(frm, cdt, cdn); },
	qty(frm, cdt, cdn) { drawing_calculate_amount(frm, cdt, cdn); },
});

function drawing_calculate_qty(frm, cdt, cdn) {
	var row = locals[cdt][cdn];
	var group = row.parent_item_group;
	var qty = null;

	if (group === "Structurals") {
		if (row.length && row.unit_weight && row.sec_qty) {
			qty = (row.length / 1000) * row.unit_weight * row.sec_qty;
		} else {
			drawing_warn_missing_fields(row, group);
		}
	} else if (group === "Plates") {
		if (row.length && row.width && row.thickness && row.unit_weight && row.sec_qty) {
			qty = (row.length / 1000) * (row.width / 1000) * row.thickness * row.unit_weight * row.sec_qty;
		} else {
			drawing_warn_missing_fields(row, group);
		}
	}

	if (qty !== null) {
		frappe.model.set_value(cdt, cdn, "qty", flt(qty, 3));
		drawing_calculate_amount(frm, cdt, cdn);
	}
}

function drawing_calculate_amount(frm, cdt, cdn) {
	var row = locals[cdt][cdn];
	var amount = flt((row.rate || 0) * (row.qty || 0), 2);
	frappe.model.set_value(cdt, cdn, "amount", amount);
	update_totals(frm);
}

function update_totals(frm) {
	var total_cost = 0, total_weight = 0;
	(frm.doc.items || []).forEach(function (row) {
		total_cost += flt(row.amount);
		var uom = (row.uom || "").toLowerCase();
		var sec_uom = (row.sec_uom || "").toLowerCase();
		if (uom === "kg" || uom === "kgs") {
			total_weight += flt(row.qty);
		} else if (sec_uom === "kg" || sec_uom === "kgs") {
			total_weight += flt(row.sec_qty);
		}
	});
	frm.set_value("total_raw_material_cost", flt(total_cost, 2));
	frm.set_value("total_weight", flt(total_weight, 3));
	render_items_summary(frm);
}

function render_items_summary(frm) {
	var wrapper = frm.fields_dict["items_summary_html"] &&
	              frm.fields_dict["items_summary_html"].$wrapper;
	if (!wrapper) return;
	var rows = frm.doc.items || [];
	if (!rows.length) {
		wrapper.html('<p class="text-muted">' + __("No items.") + "</p>");
		return;
	}
	var cols = [
		["Item No", "item_number"], ["Material Code", "material_code"], ["Material Name", "material_name"],
		["Item Group", "item_group"], ["Material Spec", "material_spec"],
		["Thickness", "thickness"], ["Length", "length"], ["Width", "width"],
		["Sec Qty", "sec_qty"], ["Sec UOM", "sec_uom"],
		["Qty ", "qty"], ["UOM", "uom"], ["Rate (₹)", "rate"], ["Amount (₹)", "amount"]
	];
	var html = '<div style="overflow-x:auto;overflow-y:auto;max-height:320px;width:100%;">';
	html += '<table class="table table-bordered table-condensed" style="font-size:12px;white-space:nowrap;min-width:1200px;">';
	html += '<thead style="position:sticky;top:0;background:#f5f5f5;z-index:1;">';
	html += "<tr>" + cols.map(function (c) {
		var minw = (c[1] === "material_code" || c[1] === "material_name") ? ' style="min-width:160px;"' : '';
		return "<th" + minw + ">" + c[0] + "</th>";
	}).join("") + "</tr></thead>";
	html += "<tbody>";
	rows.forEach(function (row) {
		html += "<tr>" + cols.map(function (c) {
			var val = row[c[1]] != null ? row[c[1]] : "";
			if ((c[1] === "rate" || c[1] === "amount") && val !== "") {
				val = "₹ " + flt(val, 2).toFixed(2);
			}
			return "<td>" + val + "</td>";
		}).join("") + "</tr>";
	});
	html += "</tbody></table></div>";
	wrapper.html(html);
}

function drawing_warn_missing_fields(row, group) {
	var missing = [];
	if (group === "Structurals") {
		if (!row.length) missing.push("Length");
		if (!row.unit_weight) missing.push("Unit Weight");
		if (!row.sec_qty) missing.push("Sec Qty");
	} else if (group === "Plates") {
		if (!row.length) missing.push("Length");
		if (!row.width) missing.push("Width");
		if (!row.thickness) missing.push("Thickness");
		if (!row.unit_weight) missing.push("Unit Weight");
		if (!row.sec_qty) missing.push("Sec Qty");
	}
	if (missing.length) {
		frappe.show_alert({
			message: __("Row {0}: Missing for {1} formula: {2}", [row.idx, group, missing.join(", ")]),
			indicator: "orange",
		});
	}
}
