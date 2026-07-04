frappe.ui.form.on("Material Issue Plan", {
	refresh(frm) {
		frm.set_query("subcontracting_order", () => ({
			filters: { custom_production_plan: frm.doc.production_plan || "" },
		}));
		frm.set_query("work_order", () => ({
			filters: { production_plan: frm.doc.production_plan || "" },
		}));
		_add_update_batch_button(frm);
		_add_transfer_buttons(frm);
		_render_excess_action_btn(frm);
	},

	production_plan(frm) {
		if (frm.is_new() || !frm.doc.production_plan) return;
		frappe.call({
			method: "manufyxinvenzaerp.subcontracting_management.doctype.material_issue_plan.material_issue_plan.populate_from_production_plan",
			args: { mip_name: frm.doc.name },
			freeze: true,
			freeze_message: __("Loading drawings from Production Plan..."),
			callback() {
				frm.reload_doc();
			},
		});
	},

	refresh_raw_materials_btn(frm) {
		frappe.call({
			method: "manufyxinvenzaerp.subcontracting_management.doctype.material_issue_plan.material_issue_plan.refresh_mip_raw_materials",
			args: { mip_name: frm.doc.name },
			freeze: true,
			freeze_message: __("Refreshing raw materials..."),
			callback() {
				frm.reload_doc();
			},
		});
	},
});

// "Update Batch" — reassign the batch (and optionally dimensions/Sec Qty) already
// selected for a raw-material row. Delegates entirely to Material Planning's own
// reassign_batch, which unreserves, applies the new batch, re-validates mapping
// availability, and re-reserves — this dialog only picks which row and what to change.
function _add_update_batch_button(frm) {
	let grid = frm.fields_dict["raw_materials"] && frm.fields_dict["raw_materials"].grid;
	if (!grid || frm.is_new()) return;

	grid.add_custom_button(
		frappe.utils.icon("edit", "xs") + " " + __("Update Batch"),
		() => _show_update_batch_dialog(frm)
	);
}

// ── Transfer / CNC buttons ───────────────────────────────────────────────────

function _add_transfer_buttons(frm) {
	if (frm.is_new() || !frm.doc.source_warehouse) return;
	if (!frm.doc.subcontracting_order && !frm.doc.work_order) return;

	frm.add_custom_button(__("All Pending Material"), function() {
		frappe.confirm(__("Transfer all pending reserved material out of the Source Warehouse. Continue?"), function() {
			frappe.call({
				method: "manufyxinvenzaerp.subcontracting_management.material_issue_plan_transfer.create_mip_transfer_entry",
				args: { mip_name: frm.doc.name },
				freeze: true,
				freeze_message: __("Creating transfer entry…"),
				callback(r) {
					if (r.message) {
						let links = Object.values(r.message).map((n) =>
							'<a href="/app/stock-entry/' + encodeURIComponent(n) + '">' + n + "</a>").join(", ");
						frappe.msgprint({ title: __("Stock Entry Created"), message: links, indicator: "green" });
						frm.reload_doc();
					}
				},
			});
		});
	}, __("Transfer"));

	frm.add_custom_button(__("Select Materials to Transfer"), function() {
		frappe.call({
			method: "manufyxinvenzaerp.subcontracting_management.material_issue_plan_transfer.get_mip_pending_items",
			args: { mip_name: frm.doc.name },
			freeze: true,
			freeze_message: __("Loading pending materials…"),
			callback(r) { _show_mip_transfer_popup(frm, r.message || [], "primary"); },
		});
	}, __("Transfer"));

	if (frm.doc.cnc_warehouse) {
		frm.add_custom_button(__("To CNC Warehouse"), function() {
			frappe.call({
				method: "manufyxinvenzaerp.subcontracting_management.material_issue_plan_transfer.get_mip_pending_items",
				args: { mip_name: frm.doc.name },
				freeze: true,
				freeze_message: __("Loading pending materials…"),
				callback(r) { _show_mip_transfer_popup(frm, r.message || [], "cnc"); },
			});
		}, __("Transfer"));

		frm.add_custom_button(__("CNC to Supplier/WIP"), function() {
			frappe.call({
				method: "manufyxinvenzaerp.subcontracting_management.material_issue_plan_transfer.create_mip_cnc_forward_entry",
				args: { mip_name: frm.doc.name },
				freeze: true,
				freeze_message: __("Forwarding CNC material…"),
				callback(r) {
					if (r.message) {
						frappe.msgprint({ title: __("Stock Entry Created"), message: '<a href="/app/stock-entry/' + encodeURIComponent(r.message) + '">' + r.message + "</a>", indicator: "green" });
						frm.reload_doc();
					}
				},
			});
		}, __("Transfer"));
	}
}

// Popup with three filter modes — Material-wise (free text), DUNO/Mark No-wise,
// Drawing-wise — combined with AND semantics, then transfer only the checked rows.
function _show_mip_transfer_popup(frm, pending_items, transfer_type) {
	var items = pending_items.filter(function(d) { return transfer_type === "cnc" ? d.cnc_process : !d.cnc_process; });
	if (!items.length) {
		frappe.msgprint({
			title: __("No Pending Items"),
			message: transfer_type === "cnc" ? __("No pending CNC items to transfer.") : __("No pending items to transfer."),
			indicator: "orange",
		});
		return;
	}

	var duno_options = Array.from(new Set(items.map((d) => d.duno_mark_no).filter(Boolean))).sort();
	var drawing_options = Array.from(new Set(items.map((d) => d.drawing).filter(Boolean))).sort();

	var $filter = $("<input class='form-control form-control-sm' placeholder='" + __("Material-wise filter…") + "' style='margin-bottom:8px'>");
	var $duno = $("<select class='form-control form-control-sm' style='margin-bottom:8px'><option value=''>" + __("All DUNO/Mark No") + "</option>"
		+ duno_options.map((d) => "<option value='" + d + "'>" + d + "</option>").join("") + "</select>");
	var $drawing = $("<select class='form-control form-control-sm' style='margin-bottom:8px'><option value=''>" + __("All Drawings") + "</option>"
		+ drawing_options.map((d) => "<option value='" + d + "'>" + d + "</option>").join("") + "</select>");
	var $filter_row = $("<div class='row'>").append(
		$("<div class='col-sm-4'>").append($filter),
		$("<div class='col-sm-4'>").append($duno),
		$("<div class='col-sm-4'>").append($drawing)
	);
	var $actions = $("<div style='margin-bottom:8px'>"
		+ "<button class='btn btn-xs btn-default mip-sel-all'>" + __("Select All") + "</button> "
		+ "<button class='btn btn-xs btn-default mip-desel-all'>" + __("Deselect All") + "</button>"
		+ "</div>");
	var $table = $("<table class='table table-bordered table-condensed' style='margin-bottom:0'>"
		+ "<thead><tr>"
		+ "<th style='width:32px'></th>"
		+ "<th>" + __("Item Code") + "</th>"
		+ "<th>" + __("Batch No") + "</th>"
		+ "<th>" + __("DUNO/Mark No") + "</th>"
		+ "<th>" + __("Drawing") + "</th>"
		+ "<th class='text-right'>" + __("Qty (Kg)") + "</th>"
		+ "</tr></thead><tbody></tbody></table>");

	var $tbody = $table.find("tbody");
	items.forEach(function(d, idx) {
		$tbody.append(
			"<tr data-idx='" + idx + "' data-duno='" + (d.duno_mark_no || "") + "' data-drawing='" + (d.drawing || "") + "'>" +
			"<td class='text-center'><input type='checkbox' class='mip-item-chk' checked></td>" +
			"<td>" + frappe.utils.escape_html(d.item_code) + "</td>" +
			"<td>" + frappe.utils.escape_html(d.batch_no || "") + "</td>" +
			"<td>" + frappe.utils.escape_html(d.duno_mark_no || "") + "</td>" +
			"<td>" + frappe.utils.escape_html(d.drawing || "") + "</td>" +
			"<td class='text-right'>" + format_number(flt(d.qty), null, 3) + "</td>" +
			"</tr>"
		);
	});

	function _apply_filters() {
		var q = $filter.val().toLowerCase();
		var duno = $duno.val();
		var drawing = $drawing.val();
		$tbody.find("tr").each(function() {
			var $row = $(this);
			var matches = (!q || $row.text().toLowerCase().indexOf(q) >= 0)
				&& (!duno || $row.data("duno") === duno)
				&& (!drawing || $row.data("drawing") === drawing);
			$row.toggle(matches);
		});
	}
	$filter.on("input", _apply_filters);
	$duno.on("change", _apply_filters);
	$drawing.on("change", _apply_filters);
	$actions.find(".mip-sel-all").on("click", function() { $tbody.find("tr:visible .mip-item-chk").prop("checked", true); });
	$actions.find(".mip-desel-all").on("click", function() { $tbody.find("tr:visible .mip-item-chk").prop("checked", false); });

	var $content = $("<div>").append($filter_row, $actions, $table);

	var dlg = new frappe.ui.Dialog({
		title: transfer_type === "cnc" ? __("Select Materials — To CNC Warehouse") : __("Select Materials to Transfer"),
		size: "extra-large",
		fields: [{ fieldtype: "HTML", fieldname: "content" }],
		primary_action_label: __("Transfer Selected"),
		primary_action: function() {
			var selected = [];
			$tbody.find("tr").each(function() {
				if ($(this).find(".mip-item-chk").prop("checked")) {
					selected.push(items[parseInt($(this).data("idx"), 10)]);
				}
			});
			if (!selected.length) {
				frappe.msgprint(__("Please select at least one item."));
				return;
			}
			dlg.hide();
			frappe.call({
				method: "manufyxinvenzaerp.subcontracting_management.material_issue_plan_transfer.create_mip_partial_transfer",
				args: { mip_name: frm.doc.name, selected_items_json: JSON.stringify(selected), transfer_type: transfer_type },
				freeze: true,
				freeze_message: __("Creating transfer entry…"),
				callback: function(r) {
					if (r.message) {
						frappe.msgprint({ title: __("Stock Entry Created"), message: __("Transfer entry: ") + '<a href="/app/stock-entry/' + encodeURIComponent(r.message) + '">' + r.message + "</a>", indicator: "green" });
						frm.reload_doc();
					}
				},
			});
		},
	});
	dlg.fields_dict.content.$wrapper.html($content);
	dlg.show();
}

// ── Excess Material Return ───────────────────────────────────────────────────

function _render_excess_action_btn(frm) {
	if (frm.is_new() || !frm.doc.excess_return_warehouse) return;
	if (!(frm.doc.excess_return_items || []).length) return;
	if (frm.is_dirty()) return;

	frm.add_custom_button(__("Return Excess Entry"), function() {
		frappe.call({
			method: "manufyxinvenzaerp.subcontracting_management.material_issue_plan_transfer.create_mip_excess_return_entry",
			args: { mip_name: frm.doc.name },
			freeze: true,
			freeze_message: __("Creating return entry…"),
			callback(r) {
				if (r.message) {
					frappe.msgprint({ title: __("Return Excess Entry Created"), message: __("Return Stock Entry: ") + '<a href="/app/stock-entry/' + encodeURIComponent(r.message) + '">' + r.message + "</a>", indicator: "green" });
					frm.reload_doc();
				}
			},
		});
	});
}

// Weight auto-calc for excess_return_items — SCO Excess Material Item is a shared
// child doctype; each parent page (SCO, WO, and now Material Issue Plan) must
// register its own handlers for it to behave interactively on that form.
frappe.ui.form.on("SCO Excess Material Item", {
	item_code(frm, cdt, cdn) {
		if (frm.doctype !== "Material Issue Plan") return;
		var row = locals[cdt][cdn];
		if (row.stock_entry_created) {
			frappe.msgprint(__("This row is locked — Stock Entry already created."));
			return;
		}
		if (!row.item_code) return;
		frappe.db.get_value("Item", row.item_code,
			["custom_parent_item_group", "custom_unit_weight", "custom_secondary_uom", "stock_uom"],
			function(v) {
				if (!v) return;
				frappe.model.set_value(cdt, cdn, "parent_item_group", v.custom_parent_item_group || "");
				frappe.model.set_value(cdt, cdn, "unit_weight", v.custom_unit_weight || 0);
				frappe.model.set_value(cdt, cdn, "sec_uom", v.custom_secondary_uom || "");
				frappe.model.set_value(cdt, cdn, "uom", v.stock_uom || "");
			});
	},
	length(frm, cdt, cdn)    { if (frm.doctype === "Material Issue Plan" && !locals[cdt][cdn].stock_entry_created) _mip_excess_calc(frm, cdt, cdn); },
	width(frm, cdt, cdn)     { if (frm.doctype === "Material Issue Plan" && !locals[cdt][cdn].stock_entry_created) _mip_excess_calc(frm, cdt, cdn); },
	thickness(frm, cdt, cdn) { if (frm.doctype === "Material Issue Plan" && !locals[cdt][cdn].stock_entry_created) _mip_excess_calc(frm, cdt, cdn); },
	sec_qty(frm, cdt, cdn)   { if (frm.doctype === "Material Issue Plan" && !locals[cdt][cdn].stock_entry_created) _mip_excess_calc(frm, cdt, cdn); },
	qty(frm, cdt, cdn) {
		if (frm.doctype !== "Material Issue Plan") return;
		var row = locals[cdt][cdn];
		if (!row.stock_entry_created && row.parent_item_group === "Nuts and Bolts" && row.unit_weight) {
			frappe.model.set_value(cdt, cdn, "sec_qty", flt(row.unit_weight * flt(row.qty), 3));
		}
		_mip_excess_totals(frm);
	},
});

function _mip_excess_calc(frm, cdt, cdn) {
	var row = locals[cdt][cdn];
	var g = row.parent_item_group;
	var qty = null;
	if (g === "Structurals") {
		if (row.length && row.unit_weight && row.sec_qty) qty = (row.length / 1000) * row.unit_weight * row.sec_qty;
	} else if (g === "Plates") {
		if (row.length && row.width && row.thickness && row.unit_weight && row.sec_qty) {
			qty = (row.length / 1000) * (row.width / 1000) * row.thickness * row.unit_weight * row.sec_qty;
		}
	}
	if (qty !== null) frappe.model.set_value(cdt, cdn, "qty", flt(qty, 3));
	_mip_excess_totals(frm);
}

function _mip_excess_totals(frm) {
	var tkg = 0, tnos = 0;
	(frm.doc.excess_return_items || []).forEach(function(r) { tkg += flt(r.qty); tnos += flt(r.sec_qty); });
	frm.set_value("excess_return_total_kg", flt(tkg, 3));
	frm.set_value("excess_return_total_nos", flt(tnos, 3));
}

function _show_update_batch_dialog(frm) {
	let rows = (frm.doc.raw_materials || []).filter((r) => r.source_table !== "Material Planning Unavailable Item");
	if (!rows.length) {
		frappe.msgprint(__("No reservable raw material rows to update. Unavailable items must go through Material Request/Purchase instead."));
		return;
	}

	let row_options = rows.map((r) => ({
		label: `${r.item_code} — ${r.batch_no || __("no batch")} (${r.duno_mark_no || ""})`,
		value: r.name,
	}));

	let dialog = new frappe.ui.Dialog({
		title: __("Update Batch"),
		fields: [
			{
				fieldname: "row_name",
				fieldtype: "Select",
				label: __("Raw Material Row"),
				options: row_options.map((o) => o.label).join("\n"),
				reqd: 1,
			},
			{ fieldtype: "Column Break" },
			{ fieldname: "new_batch_no", fieldtype: "Link", options: "Batch", label: __("New Batch"), reqd: 1 },
			{ fieldtype: "Section Break" },
			{ fieldname: "length", fieldtype: "Float", label: __("Length (mm)") },
			{ fieldname: "width", fieldtype: "Float", label: __("Width (mm)") },
			{ fieldtype: "Column Break" },
			{ fieldname: "thickness", fieldtype: "Float", label: __("Thickness (mm)") },
			{ fieldname: "sec_qty", fieldtype: "Float", label: __("Sec Qty (Nos)") },
			{ fieldname: "reserve_without_dimensions", fieldtype: "Check", label: __("Reserve Without Dimensions") },
		],
		primary_action_label: __("Update"),
		primary_action(values) {
			let picked = row_options.find((o) => o.label === values.row_name);
			let row = rows.find((r) => r.name === picked.value);
			frappe.call({
				method: "manufyxinvenzaerp.production_management.doctype.material_planning.material_planning.reassign_batch",
				args: {
					material_planning_name: row.material_planning,
					source_table: row.source_table,
					row_name: row.source_row,
					new_batch_no: values.new_batch_no,
					dimensions: JSON.stringify({
						length: values.length,
						width: values.width,
						thickness: values.thickness,
					}),
					sec_qty: values.sec_qty,
					reserve_without_dimensions: values.reserve_without_dimensions ? 1 : 0,
				},
				freeze: true,
				freeze_message: __("Reassigning batch..."),
				callback(r) {
					dialog.hide();
					let warnings = (r.message && r.message.warnings) || [];
					if (warnings.length) {
						frappe.msgprint({
							title: __("Shortfall Warning"),
							indicator: "orange",
							message: warnings.map((w) => `${w.item_code} (${w.batch}): ${__("short by")} ${w.shortfall_qty}`).join("<br>"),
						});
					}
					frappe.call({
						method: "manufyxinvenzaerp.subcontracting_management.doctype.material_issue_plan.material_issue_plan.refresh_mip_raw_materials",
						args: { mip_name: frm.doc.name },
						freeze: true,
						callback() { frm.reload_doc(); },
					});
				},
			});
		},
	});
	dialog.show();
}
