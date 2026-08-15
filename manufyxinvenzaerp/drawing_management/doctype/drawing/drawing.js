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
            frappe.call({
                method: "manufyxinvenzaerp.drawing_management.doctype.drawing.drawing.check_existing_bom",
                args: {
                    drawing_name: frm.doc.name
                },
                callback: function (r) {
                    if (r.message) {
                        return;
                    }

                    // ✅ Only show button if no BOM exists
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
            });
        }

		if (!frm.is_new()) {
			frm.add_custom_button(__("Update Customer Weight"), function () {
				frappe.prompt(
					[{
						fieldname: "new_weight",
						fieldtype: "Float",
						label: __("New Customer Provided Weight (Kg)"),
						reqd: 1,
						default: frm.doc.customer_provided_wt,
						description: __("Current value: {0} Kg", [frm.doc.customer_provided_wt || 0]),
					}],
					function (values) {
						frappe.call({
							method: "manufyxinvenzaerp.drawing_management.drawing_utils.update_customer_provided_weight",
							args: { drawing_name: frm.doc.name, new_weight: values.new_weight },
							freeze: true,
							freeze_message: __("Updating weight and cascading to linked documents…"),
							callback: function (r) {
								if (!r.message) return;
								var m = r.message;
								frappe.msgprint({
									title: __("Customer Weight Updated"),
									indicator: "green",
									message: __(
										"Weight changed from {0} Kg to {1} Kg.<br>Sales Order updated: {2}<br>" +
										"Production Plan Items updated: {3}<br>Drawing rows (Subcontracting Order / " +
										"Material Issue Plan) updated: {4}<br>Subcontracting Orders re-totalled: {5}<br>" +
										"Material Issue Plans refreshed: {6}<br><br>" +
										"Batch allocation/reservation was <b>not</b> changed automatically — " +
										"reallocate manually if needed.",
										[
											m.old_weight, m.new_weight, m.sales_order_updated ? __("Yes") : __("No"),
											m.production_plan_items_updated, m.drawing_rows_updated,
											m.subcontracting_orders_updated, m.material_issue_plans_updated,
										]
									),
								});
								frm.reload_doc();
							},
						});
					},
					__("Update Customer Provided Weight"),
					__("Update")
				);
			});
		}

		// Filter the picker by Type only when one is chosen. Filtering on an empty
		// Type matched only schedules whose own Type is blank, so an imported drawing
		// -- which arrives with a schedule but no Type -- offered an empty list.
		frm.set_query("rate_schedule", function () {
			return frm.doc.type ? { filters: { type: frm.doc.type } } : {};
		});

		frm.set_query("batch", "items", function (doc, cdt, cdn) {
			var row = locals[cdt][cdn];
			return {
				query: "manufyxinvenzaerp.drawing_management.drawing_utils.get_batches_for_drawing_item",
				filters: { item_code: row.material_code },
			};
		});

		update_totals(frm);

		// Items grid: Download (always) and Upload (draft only) — bottom-right of table
		setTimeout(function () {
			var grid = frm.fields_dict["items"] && frm.fields_dict["items"].grid;
			if (!grid || !grid.wrapper) return;

			var $dl = grid.wrapper.find(".grid-download");
			var $ul = grid.wrapper.find(".grid-upload");

			$dl.off("click.drawing").removeClass("hidden")
				.on("click.drawing", function () { drawing_download_items_csv(frm); return false; });

			$ul.off("click.drawing");
			if (frm.doc.docstatus === 0) {
				$ul.removeClass("hidden")
					.on("click.drawing", function () { drawing_upload_items_dialog(frm); return false; });
			} else {
				$ul.addClass("hidden");
			}
		}, 0);
	},

	customer(frm) {
		frm.set_value("customer_no", frm.doc.customer || "");
	},

	// Type and Rate Schedule describe the same thing from two directions: Type
	// narrows the picker when choosing by hand, and is read back off the schedule
	// when one arrives ready-made from a BOM import. Each only touches the other
	// when they actually disagree, so setting one cannot loop into clearing the other.
	type(frm) {
		if (!frm.doc.rate_schedule) return;
		frappe.db.get_value("Rate Schedule", frm.doc.rate_schedule, "type").then(function (r) {
			var rs_type = (r && r.message && r.message.type) || "";
			// Only drop the schedule if the new Type genuinely excludes it.
			if (frm.doc.type && rs_type && rs_type !== frm.doc.type) {
				frm.set_value("rate_schedule", "");
			}
		});
	},

	rate_schedule(frm) {
		if (!frm.doc.rate_schedule) {
			["rs_job_nature", "rs_details", "rs_work_content", "rs_job_reference", "rs_rate_per_kg"].forEach(function (f) {
				frm.set_value(f, "");
			});
			return;
		}
		// Type belongs to the schedule, so mirror it here rather than expecting the
		// user to have set it first -- an imported drawing never did.
		frappe.db.get_value("Rate Schedule", frm.doc.rate_schedule, "type").then(function (r) {
			var rs_type = (r && r.message && r.message.type) || "";
			if (rs_type && rs_type !== frm.doc.type) frm.set_value("type", rs_type);
		});
	},

	sales_order(frm) {
		if (!frm.doc.sales_order) {
			frm.set_value("project", "");
			return;
		}
		frappe.db.get_value("Sales Order", frm.doc.sales_order, "project", function (r) {
			if (r && r.project) frm.set_value("project", r.project);
		});
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
				setTimeout(function () { drawing_calculate_qty(frm, cdt, cdn); drawing_calculate_totals(frm, cdt, cdn); }, 300);
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
				drawing_calculate_totals(frm, cdt, cdn);
			}
		);
	},

	thickness(frm, cdt, cdn) { drawing_calculate_qty(frm, cdt, cdn); drawing_calculate_totals(frm, cdt, cdn); },
	length(frm, cdt, cdn) { drawing_calculate_qty(frm, cdt, cdn); drawing_calculate_totals(frm, cdt, cdn); },
	width(frm, cdt, cdn) { drawing_calculate_qty(frm, cdt, cdn); drawing_calculate_totals(frm, cdt, cdn); },
	sec_qty(frm, cdt, cdn) { drawing_calculate_qty(frm, cdt, cdn); drawing_calculate_totals(frm, cdt, cdn); },
	unit_weight(frm, cdt, cdn) { drawing_calculate_qty(frm, cdt, cdn); drawing_calculate_totals(frm, cdt, cdn); },

	qty(frm, cdt, cdn) {
		var row = locals[cdt][cdn];
		if ((row.parent_item_group || "") === "Nuts and Bolts" && row.unit_weight) {
			frappe.model.set_value(cdt, cdn, "sec_qty", flt(row.qty * row.unit_weight, 3));
		}
		update_totals(frm);
		drawing_calculate_totals(frm, cdt, cdn);
	},
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
	} else if (group === "Nuts and Bolts") {
		// qty (NOS) is manual; recalculate sec_qty (KG) when unit_weight changes
		if (row.qty && row.unit_weight) {
			frappe.model.set_value(cdt, cdn, "sec_qty", flt(row.qty * row.unit_weight, 3));
			update_totals(frm);
		}
		return;
	}

	if (qty !== null) {
		frappe.model.set_value(cdt, cdn, "qty", flt(qty, 3));
		update_totals(frm);
	}
}

function drawing_calculate_totals(frm, cdt, cdn) {
	var row = locals[cdt][cdn];
	var no_of_qty = flt(frm.doc.no_of_qty_to_manufacture);
	var group = row.parent_item_group || "";

	if (group === "Nuts and Bolts") {
		var nab_total_qty = flt(row.qty * no_of_qty, 3);
		frappe.model.set_value(cdt, cdn, "total_qty", nab_total_qty);
		frappe.model.set_value(cdt, cdn, "total_sec_qty", flt(nab_total_qty * row.unit_weight, 3));
		return;
	}

	var total_sec_qty = flt(flt(row.sec_qty) * no_of_qty, 3);
	frappe.model.set_value(cdt, cdn, "total_sec_qty", total_sec_qty);

	var total_qty = 0;
	if (group === "Structurals") {
		if (row.length && row.unit_weight && total_sec_qty) {
			total_qty = flt((row.length / 1000) * row.unit_weight * total_sec_qty, 3);
		}
	} else if (group === "Plates") {
		if (row.length && row.width && row.thickness && row.unit_weight && total_sec_qty) {
			total_qty = flt((row.length / 1000) * (row.width / 1000) * row.thickness * row.unit_weight * total_sec_qty, 3);
		}
	}
	frappe.model.set_value(cdt, cdn, "total_qty", total_qty);
}

function update_totals(frm) {
	var total_weight = 0;
	(frm.doc.items || []).forEach(function (row) {
		var uom = (row.uom || "").toLowerCase();
		var sec_uom = (row.sec_uom || "").toLowerCase();
		if (uom === "kg" || uom === "kgs") {
			total_weight += flt(row.qty);
		} else if (sec_uom === "kg" || sec_uom === "kgs") {
			total_weight += flt(row.sec_qty);
		}
	});
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
		["Qty ", "qty"], ["UOM", "uom"]
	];
	var html = '<div style="overflow-x:auto;overflow-y:auto;max-height:320px;width:100%;">';
	html += '<table class="table table-bordered table-condensed" style="font-size:12px;white-space:nowrap;min-width:1200px;">';
	html += '<thead style="position:sticky;top:0;background:#f5f5f5;z-index:1;">';
	html += "<tr>" + cols.map(function (c) {
		var minw = (c[1] === "material_code" || c[1] === "material_name") ? ' style="min-width:160px;"' : '';
		return "<th" + minw + ">" + frappe.utils.escape_html(c[0]) + "</th>";
	}).join("") + "</tr></thead>";
	html += "<tbody>";
	rows.forEach(function (row) {
		html += "<tr>" + cols.map(function (c) {
			var val = row[c[1]] != null ? row[c[1]] : "";
			return "<td>" + frappe.utils.escape_html(String(val)) + "</td>";
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

// ─────────────────────────────────────────────────────────────────────────────
// CSV Upload / Download helpers
// ─────────────────────────────────────────────────────────────────────────────

/**
 * Download a blank Drawing Items CSV template with three sample rows.
 * Columns: item_number, material_code, sec_qty, thickness, length, width
 */
function drawing_download_csv_template() {
	var HEADERS = ["item_number", "material_code", "sec_qty", "thickness", "length", "width"];
	var LABELS  = ["Item Number", "Item Code",     "Sec Qty", "Thickness (mm)", "Length (mm)", "Width (mm)"];
	var SAMPLES = [
		["1", "ISMBX250X125", "2", "",   "1500", ""],
		["2", "PLATE12",      "1", "12", "1500", "2000"],
		["3", "BOLTM24",      "2", "",   "",     ""],
	];

	var lines = [
		HEADERS.join(","),
		"# " + LABELS.join(",") + "  ← (labels for reference — do not include this row in your upload)"
	];
	SAMPLES.forEach(function(r) { lines.push(r.join(",")); });

	_drawing_trigger_csv_download(lines.join("\n"), "drawing_items_template.csv");
}

/**
 * Download the current items table as a CSV file.
 */
function drawing_download_items_csv(frm) {
	var items = frm.doc.items || [];
	if (!items.length) {
		frappe.msgprint(__("No items to download."));
		return;
	}

	var COLS = [
		["item_number",    "item_number"],
		["material_code",  "material_code"],
		["material_name",  "material_name"],
		["parent_item_group", "parent_item_group"],
		["sec_qty",        "sec_qty"],
		["sec_uom",        "sec_uom"],
		["thickness",      "thickness"],
		["length",         "length"],
		["width",          "width"],
		["unit_weight",    "unit_weight"],
		["qty",            "qty"],
		["uom",            "uom"],
	];

	var lines = [COLS.map(function(c) { return c[0]; }).join(",")];
	items.forEach(function(row) {
		var cells = COLS.map(function(c) {
			var v = row[c[1]];
			if (v == null) v = "";
			// Wrap in quotes if the value contains a comma or quote
			var s = String(v);
			if (s.indexOf(",") !== -1 || s.indexOf('"') !== -1) {
				s = '"' + s.replace(/"/g, '""') + '"';
			}
			return s;
		});
		lines.push(cells.join(","));
	});

	var doc_id = frm.doc.name || "drawing";
	_drawing_trigger_csv_download(lines.join("\n"), doc_id + "_items.csv");
}

function drawing_upload_items_dialog(frm) {
	new frappe.ui.FileUploader({
		as_dataurl: true,
		allow_multiple: false,
		restrictions: { allowed_file_types: [".csv"] },
		on_success: function (file) {
			var csv_content = frappe.utils.get_decoded_string(file.dataurl);
			frappe.call({
				method: "manufyxinvenzaerp.drawing_management.drawing_utils.parse_drawing_items_csv",
				args: { csv_content: csv_content },
				freeze: true,
				freeze_message: __("Processing CSV…"),
				callback: function (r) {
					if (!r.message || !r.message.length) return;
					frm.clear_table("items");
					r.message.forEach(function (row_data) {
						var child = frm.add_child("items");
						$.extend(locals[child.doctype][child.name], row_data);
					});
					frm.refresh_field("items");
					update_totals(frm);
					frappe.show_alert({
						message: __("{0} item(s) loaded from CSV.", [r.message.length]),
						indicator: "green",
					}, 5);
				},
			});
		},
	});
}

/** Trigger a browser CSV download from a plain-text string. */
function _drawing_trigger_csv_download(csv_text, filename) {
	var blob = new Blob([csv_text], { type: "text/csv;charset=utf-8;" });
	var url  = URL.createObjectURL(blob);
	var a    = document.createElement("a");
	a.href     = url;
	a.download = filename;
	document.body.appendChild(a);
	a.click();
	setTimeout(function () {
		document.body.removeChild(a);
		URL.revokeObjectURL(url);
	}, 100);
}
