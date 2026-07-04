// ── Upload / Download helper for child table toolbars ──────────────────────
function _add_io_buttons(frm, fieldname) {
	var grid = frm.fields_dict[fieldname] && frm.fields_dict[fieldname].grid;
	if (!grid) return;

	// Download — export current rows as CSV
	var $dl = grid.add_custom_button(
		__("Download"),
		function () {
			var rows = frm.doc[fieldname] || [];
			if (!rows.length) { frappe.msgprint(__("No data to download.")); return; }
			var cols = (grid.docfields || []).filter(function (f) {
				return f.fieldtype !== "Column Break" && f.fieldtype !== "Section Break"
					&& f.fieldtype !== "Button" && f.in_list_view;
			});
			if (!cols.length) {
				cols = (grid.docfields || []).filter(function (f) {
					return f.fieldtype !== "Column Break" && f.fieldtype !== "Section Break" && f.fieldtype !== "Button";
				});
			}
			var headers = cols.map(function (f) { return f.label || f.fieldname; });
			var lines = [headers.join(",")];
			rows.forEach(function (row) {
				var vals = cols.map(function (f) {
					var v = String(row[f.fieldname] === null || row[f.fieldname] === undefined ? "" : row[f.fieldname]);
					if (v.indexOf(",") >= 0 || v.indexOf("\n") >= 0 || v.indexOf('"') >= 0) {
						v = '"' + v.replace(/"/g, '""') + '"';
					}
					return v;
				});
				lines.push(vals.join(","));
			});
			var blob = new Blob([lines.join("\n")], { type: "text/csv;charset=utf-8;" });
			var url = URL.createObjectURL(blob);
			var a = document.createElement("a");
			a.href = url; a.download = fieldname + ".csv";
			document.body.appendChild(a); a.click();
			document.body.removeChild(a); URL.revokeObjectURL(url);
		}
	);
	// default button style (no color override)

	// Upload — commented out (not yet active)
	// var $ul = grid.add_custom_button(
	// 	__("Upload"),
	// 	function () {
	// 		var $input = $('<input type="file" accept=".csv" style="display:none">');
	// 		$input.on("change", function () {
	// 			var file = this.files[0];
	// 			if (!file) return;
	// 			var reader = new FileReader();
	// 			reader.onload = function (e) {
	// 				var text = e.target.result;
	// 				var lines = text.split(/\r?\n/).filter(function (l) { return l.trim(); });
	// 				if (lines.length < 2) {
	// 					frappe.msgprint(__("CSV must have a header row and at least one data row."));
	// 					return;
	// 				}
	// 				var headers = lines[0].split(",").map(function (h) { return h.trim().toLowerCase().replace(/ /g, "_"); });
	// 				var cols = grid.docfields || [];
	// 				var header_map = {};
	// 				headers.forEach(function (h, i) {
	// 					var match = cols.find(function (f) {
	// 						return f.fieldname === h || (f.label || "").toLowerCase().replace(/ /g, "_") === h;
	// 					});
	// 					if (match) header_map[i] = match.fieldname;
	// 				});
	// 				var added = 0;
	// 				for (var r = 1; r < lines.length; r++) {
	// 					var vals = lines[r].split(",");
	// 					var child = frm.add_child(fieldname);
	// 					vals.forEach(function (v, i) { if (header_map[i]) child[header_map[i]] = v.trim(); });
	// 					added++;
	// 				}
	// 				frm.refresh_field(fieldname);
	// 				frappe.show_alert({ message: __("{0} row(s) added.", [added]), indicator: "green" }, 4);
	// 			};
	// 			reader.readAsText(file);
	// 		});
	// 		$input.trigger("click");
	// 	}
	// );
}

function _update_weight_summary(frm) {
	let total_raw = 0;
	(frm.doc.raw_materials || []).forEach(r => {
		let g = r.parent_item_group || "";
		if (g === "Structurals" || g === "Plates") total_raw += flt(r.qty);
	});

	let total_exact = 0;
	(frm.doc.available_raw_materials || []).forEach(r => { total_exact += flt(r.required_qty); });

	let expected_mapping = 0;
	let cross_mapped = 0;
	let mapping_rows = frm.doc.material_mapping || [];
	mapping_rows.forEach(r => {
		expected_mapping += flt(r.qty);
		cross_mapped    += flt(r.batch_calc_qty);
	});

	// Diff: only consider rows that have been mapped
	let mapped_expected = 0;
	let mapped_cross    = 0;
	mapping_rows.forEach(r => {
		if (r.batch_mapped === "Mapped") {
			mapped_expected += flt(r.qty);
			mapped_cross    += flt(r.batch_calc_qty);
		}
	});

	let diff = mapped_cross - mapped_expected;

	frm.set_value("total_weight_plates_structurals", flt(total_raw, 3));
	frm.set_value("weight_exact_raw_material",       flt(total_exact, 3));
	frm.set_value("expected_weight_material_mapping", flt(expected_mapping, 3));
	frm.set_value("weight_cross_item_mapped",         flt(cross_mapped, 3));

	// Render the coloured difference HTML
	let $wrap = frm.fields_dict["diff_weight_html"] && frm.fields_dict["diff_weight_html"].$wrapper;
	if (!$wrap) return;

	let html = "";

	// Show difference as soon as at least one Material Mapping row is mapped
	let any_mapped = mapping_rows.some(r => r.batch_mapped === "Mapped");

	if (!any_mapped) {
		$wrap.html("");
		return;
	}

	if (!mapped_expected && !mapped_cross) {
		$wrap.html("");
		return;
	}

	let sign    = diff >= 0 ? "+" : "";
	let color   = diff >= 0 ? "#2e7d32" : "#c62828";
	let val_str = sign + flt(diff, 3).toFixed(3) + " Kg";

	let mapped_count = mapping_rows.filter(r => r.batch_mapped === "Mapped").length;
	let total_count  = mapping_rows.length;
	html = `<div style="margin-top:6px;">
		<label class="control-label" style="font-size:11px;color:#8d99a6;">
			Difference in Kg — Batch Mapped Items
			<span style="font-weight:400;color:#aaa;">(${mapped_count} of ${total_count} mapped)</span>
		</label>
		<div style="font-size:15px;font-weight:700;color:${color};margin-top:2px;">${val_str}</div>`;

	if (diff > 0) {
		html += `<div style="margin-top:8px;padding:8px 12px;background:#f1f8e9;border-left:3px solid #66bb6a;border-radius:3px;font-size:12px;color:#33691e;">
			<b>Excess material:</b> If this material is transferred to the supplier, ensure they return the excess quantity.
		</div>`;
	}
	html += "</div>";
	$wrap.html(html);
}

frappe.ui.form.on("Material Planning", {

	update_so_diff_btn(frm) {
		if (frm.is_dirty()) {
			frappe.msgprint(__("Please save the document before updating the Sales Order."));
			return;
		}
		frappe.call({
			method: "manufyxinvenzaerp.production_management.doctype.material_planning.material_planning.update_so_difference_kg",
			args: { mp_name: frm.doc.name },
			freeze: true,
			freeze_message: __("Updating Difference Kg in Sales Order…"),
			callback(r) {
				if (r.message) {
					frappe.show_alert({
						message: __("{0} Sales Order Drawing row(s) updated.", [r.message.updated]),
						indicator: "green",
					}, 5);
				}
			},
		});
	},

	refresh(frm) {
		// Always keep the Stock Analysis tab visible regardless of table data
		frm.set_df_property("tab_stock_analysis", "hidden", 0); // fieldname stays, label changed to "Stock Details"
		frm.set_df_property("section_raw_materials", "hidden", 0);
		frm.set_df_property("section_available_raw_materials", "hidden", 0);
		frm.set_df_property("section_material_mapping", "hidden", 0);
		frm.set_df_property("section_unavailable_items", "hidden", 0);

		// BOM search: supports name, item, item_name, and DUNO/Mark No
		frm.set_query("bom_no", "bom_items", function() {
			return {
				query: "manufyxinvenzaerp.production_management.doctype.material_planning.material_planning.search_bom",
			};
		});

		frm.set_query("batch", "material_mapping", function() {
			return {};
		});

		let has_raw = !!(frm.doc.raw_materials || []).length;
		let has_avail = !!(frm.doc.available_raw_materials || []).length;
		let has_mapping = !!(frm.doc.material_mapping || []).length;
		let has_unavail = !!(frm.doc.unavailable_items || []).length;

		// Button visibility
		frm.set_df_property("get_raw_materials_btn",  "hidden", 0);
		frm.set_df_property("check_stock_btn",         "hidden", has_raw     ? 0 : 1);
		frm.set_df_property("update_exact_match_btn",  "hidden", has_unavail ? 0 : 1);
		frm.set_df_property("verify_material_mapping_btn", "hidden", has_mapping ? 0 : 1);
		frm.set_df_property("finalize_mapping_btn",    "hidden", has_mapping ? 0 : 1);

		// Lock the SO picker and Show Drawings button once stock has been checked
		// (raw materials fetched + at least one stock analysis table populated)
		let so_locked = has_raw && (has_avail || has_mapping || has_unavail);
		frm.set_df_property("so_bom_import",     "read_only", so_locked ? 1 : 0);
		frm.set_df_property("show_drawings_btn", "hidden",    so_locked ? 1 : 0);

		// Add icons to inline form buttons (no color override)
		function _style_btn(fieldname, icon, label) {
			let $btn = frm.fields_dict[fieldname] && frm.fields_dict[fieldname].$input;
			if (!$btn || !$btn.length) return;
			$btn.html(frappe.utils.icon(icon, "sm") + "&nbsp;" + __(label));
		}
		setTimeout(function () {
			_style_btn("get_raw_materials_btn",  "refresh", "Get Raw Materials");
			_style_btn("check_stock_btn",        "search",  "Check Stock Availability");
			_style_btn("update_exact_match_btn", "tick",    "Update & Map Exact Matches");
			_style_btn("verify_material_mapping_btn", "check", "Verify Raw Materials");
			_style_btn("finalize_mapping_btn",   "move",    "Move to Unavailable Items");

			// "View All" injected next to each section's action button
			function _inject_view_all($anchor_input, css_class, fieldname) {
				if (!$anchor_input || !$anchor_input.length) return;
				$anchor_input.closest(".frappe-control").find("." + css_class).remove();
				let $va = $('<button class="btn btn-default btn-sm ' + css_class + '" style="margin-left:8px;"></button>');
				$va.html(frappe.utils.icon("eye", "sm") + "&nbsp;" + __("View All"));
				$va.on("click", function () { _show_table_popup(frm, fieldname); });
				$anchor_input.after($va);
			}

			let $raw_btn  = frm.fields_dict["get_raw_materials_btn"]  && frm.fields_dict["get_raw_materials_btn"].$input;
			let $chk_btn  = frm.fields_dict["check_stock_btn"]        && frm.fields_dict["check_stock_btn"].$input;
			let $fin_btn  = frm.fields_dict["finalize_mapping_btn"]   && frm.fields_dict["finalize_mapping_btn"].$input;
			let $upd_btn  = frm.fields_dict["update_exact_match_btn"] && frm.fields_dict["update_exact_match_btn"].$input;

			_inject_view_all($raw_btn,  "view-all-raw-btn", "raw_materials");
			_inject_view_all($chk_btn,  "view-all-arm-btn", "available_raw_materials");
			_inject_view_all($fin_btn,  "view-all-mm-btn",  "material_mapping");
			_inject_view_all($upd_btn,  "view-all-ui-btn",  "unavailable_items");
		}, 50);

		// Colour-coded Status badge on Material Mapping rows
		let _mm_meta = frappe.get_meta("Material Planning Material Mapping");
		if (_mm_meta && _mm_meta.fields) {
			let _status_df = _mm_meta.fields.find(function(f) { return f.fieldname === "batch_mapped"; });
			if (_status_df) {
				_status_df.formatter = function(value) {
					if (value === "Mapped") {
						return `<span class="indicator-pill green" style="display:inline-block;font-size:11px;padding:2px 8px">${__("Mapped")}</span>`;
					}
					if (value) {
						return `<span class="indicator-pill red" style="display:inline-block;font-size:11px;padding:2px 8px">${__("Not Mapped")}</span>`;
					}
					return "";
				};
			}
		}

		// Disable add/delete rows on all auto-populated tables
		["raw_materials", "available_raw_materials", "material_mapping", "unavailable_items"].forEach(function (tbl) {
			let g = frm.fields_dict[tbl] && frm.fields_dict[tbl].grid;
			if (!g) return;
			g.cannot_add_rows = true;
			g.df.cannot_delete_rows = true;
			g.refresh();
		});

		// Lock BOM Items once a Production Plan exists OR any stock is reserved
		let has_any_reserved = (frm.doc.available_raw_materials || []).some(r => r.is_reserved)
			|| (frm.doc.material_mapping || []).some(r => r.is_reserved);

		if (frm.doc.production_plan || has_any_reserved) {
			frm.set_df_property("bom_items", "read_only", 1);
			let bom_grid = frm.fields_dict["bom_items"] && frm.fields_dict["bom_items"].grid;
			if (bom_grid) {
				bom_grid.df.read_only = 1;
				bom_grid.cannot_add_rows = true;
				bom_grid.df.cannot_delete_rows = true;
				bom_grid.refresh();
			}
			if (has_any_reserved && !frm.doc.production_plan) {
				frm.set_df_property("bom_items", "description",
					"⚠ BOM Items are locked because stock is already reserved. Unreserve all batches before modifying BOMs.");
			}
		}

		// Grid toolbar buttons — guard against duplicates on re-render
		if (!frm._grid_btns_added) {
			frm._grid_btns_added = true;

			// Upload/Download on all four tables
			["raw_materials", "available_raw_materials", "material_mapping", "unavailable_items"].forEach(function (tbl) {
				_add_io_buttons(frm, tbl);
			});



			// Reserve / Unreserve on Material Mapping (Alternate Stock)
			_add_reservation_buttons(frm);

			// Reserve / Unreserve on Available Raw Materials (Exact Match)
			_add_exact_match_reservation_buttons(frm);

			// Action buttons on Unavailable Items
			let $mr_btn = frm.fields_dict["unavailable_items"].grid.add_custom_button(
				frappe.utils.icon("buying", "xs") + " " + __("Create Material Request"),
				function () { _show_material_request_dialog(frm); }
			);

			// Auto Purchase section — visible only when Manufyxinvenza Settings enables it
			frappe.db.get_single_value("Manufyxinvenza Settings", "auto_purchase_from_material_planning")
				.then(function(enabled) {
					if (!enabled) return;
					frm.set_df_property("custom_auto_purchase_section",  "hidden", 0);
					frm.set_df_property("custom_auto_purchase_supplier", "hidden", 0);
					frm.refresh_fields(["custom_auto_purchase_section", "custom_auto_purchase_supplier", "custom_auto_purchase_btn"]);
				});
		}

		_update_weight_summary(frm);

		// "Create → Production Plan" — available in draft and submitted states
		if (frm.doc.docstatus !== 2) {
			frm.add_custom_button(__("Production Plan"), function () {
				if (!frm.doc.bom_items || !frm.doc.bom_items.length) {
					frappe.msgprint(__("Add at least one BOM in the 'Selected BOMs' tab first."));
					return;
				}
				if (frm.doc.__islocal) {
					frappe.msgprint(__("Save the document before creating a Production Plan."));
					return;
				}

				function _do_create() {
					frappe.call({
						method: "manufyxinvenzaerp.production_management.doctype.material_planning.material_planning.make_production_plan",
						args: { material_planning_name: frm.doc.name },
						freeze: true,
						freeze_message: __("Creating Production Plan…"),
						callback(r) {
							if (r.message) {
								frappe.show_alert({
									message: __("Production Plan {0} created.", [r.message]),
									indicator: "green",
								}, 5);
								frappe.set_route("Form", "Production Plan", r.message);
							}
						},
					});
				}

				frappe.confirm(
					__("Create a Production Plan from this Material Planning?"),
					function () {
						if (frm.doc.docstatus === 0 && frm.is_dirty()) {
							frappe.call({
								method: "frappe.client.save",
								args: { doc: frm.doc },
								freeze: true,
								freeze_message: __("Saving…"),
								callback(r) {
									if (r.message) {
										frappe.model.sync(r.message);
										frm.refresh();
									}
									_do_create();
								},
							});
						} else {
							_do_create();
						}
					}
				);
			}, __("Create"));
		}
	},
});

// Batch availability warning popup shown before save
function _show_batch_warning_popup(warnings) {
	let lines = warnings.map(function(w) {
		return `<tr>
			<td>${w.idx || ""}</td>
			<td>${w.item_code}</td>
			<td>${w.item_name || ""}</td>
			<td>${w.batch}</td>
			<td>${w.required_qty} ${w.uom}</td>
			<td>${w.batch_stock} ${w.uom}</td>
			<td>${w.available_to_reserve} ${w.uom}</td>
			<td style="color:red;font-weight:bold">${w.shortfall_qty} ${w.uom}</td>
		</tr>`;
	}).join("");
	frappe.msgprint({
		title: __("Batch Stock Warning — Insufficient Stock"),
		indicator: "orange",
		message: `<p>${__("The following Material Mapping rows have insufficient batch stock for full reservation:")}</p>
			<table class="table table-bordered table-condensed" style="font-size:12px">
				<thead><tr>
					<th>${__("Row")}</th>
					<th>${__("Item Code")}</th>
					<th>${__("Item Name")}</th>
					<th>${__("Batch")}</th>
					<th>${__("Required")}</th>
					<th>${__("Batch Stock")}</th>
					<th>${__("Available to Reserve")}</th>
					<th>${__("Shortfall")}</th>
				</tr></thead>
				<tbody>${lines}</tbody>
			</table>
			<p class="text-muted" style="margin-top:8px">
				<b>${__("Action required:")}</b>
				${__("Assign a different batch with sufficient stock, or click")}
				<b>${__("Move to Unavailable Items")}</b>
				${__("to handle the shortfall separately.")}
			</p>`,
	});
}

frappe.ui.form.on("Material Planning", {
	after_save(frm) {
		// Show "Check Stock Availability" summary popup
		if (frm._check_stock_summary) {
			let s = frm._check_stock_summary;
			frm._check_stock_summary = null;

			let rows_html = `
				<table class="table table-bordered" style="font-size:13px;margin-top:8px;">
					<tbody>
						<tr style="background:#f6fff6;">
							<td style="padding:8px 12px;width:80%;">
								${__("Exact match found — added to <b>Available Raw Materials (Exact Match)</b>")}
							</td>
							<td style="padding:8px 12px;font-weight:700;text-align:center;color:green;">${s.avail}</td>
						</tr>
						<tr style="background:${s.mapping ? "#fffbf0" : ""};">
							<td style="padding:8px 12px;">
								${__("Added to <b>Material Mapping (Alternate Stock)</b>")}
								${s.mapping ? `<br><span class="text-muted" style="font-size:11px;">
									${s.shortfall_mapping ? `<span style="color:#e65100;">&#9888; ${s.shortfall_mapping} row(s) from partial stock — NOS/Kg not fully available</span><br>` : ""}
									${__("Assign a batch manually to cover each row")}
								</span>` : ""}
							</td>
							<td style="padding:8px 12px;font-weight:700;text-align:center;color:${s.mapping ? "orange" : "green"};">${s.mapping}</td>
						</tr>
						<tr style="background:${s.unavail ? "#fff5f5" : ""};">
							<td style="padding:8px 12px;">
								${__("Added to <b>Unavailable Items (No Stock — Needs Purchase)</b>")}
							</td>
							<td style="padding:8px 12px;font-weight:700;text-align:center;color:${s.unavail ? "red" : "green"};">${s.unavail}</td>
						</tr>
					</tbody>
				</table>
				${s.avail ? `<div style="margin-top:10px;padding:8px 12px;background:#e8f4fd;border-left:4px solid #2490ef;border-radius:3px;font-size:12px;">
					<b>${__("Next step:")}</b> ${__("Reserve stock against <b>Available Raw Materials (Exact Match)</b> before proceeding, to lock the matched batches and avoid duplication across other Material Plans.")}
				</div>` : ""}`;

			frappe.msgprint({
				title: __("Check Stock Availability — Summary"),
				indicator: s.avail ? "green" : (s.mapping ? "orange" : "red"),
				message: rows_html,
			});
			return;
		}

		// Show "Move to Unavailable Items" summary popup
		if (frm._finalize_mapping_summary) {
			let s = frm._finalize_mapping_summary;
			frm._finalize_mapping_summary = null;

			let reservation_detail = "";
			if (s.mapped) {
				reservation_detail = `
					<div style="margin-top:6px;display:flex;gap:12px;flex-wrap:wrap;">
						<span style="font-size:11px;background:#e8f5e9;color:#2e7d32;padding:3px 8px;border-radius:10px;font-weight:600;">
							&#10003; ${s.reserved} Reserved
						</span>
						<span style="font-size:11px;background:${s.not_reserved ? "#fff8e1" : "#e8f5e9"};color:${s.not_reserved ? "#e65100" : "#2e7d32"};padding:3px 8px;border-radius:10px;font-weight:600;">
							&#9675; ${s.not_reserved} Not Reserved
						</span>
					</div>
					${s.not_reserved ? `<div style="margin-top:6px;font-size:11px;color:#e65100;padding:4px 0;">
						&#9888; Reserve the unresolved batches to avoid duplication mapping across other Material Plans.
					</div>` : ""}`;
			}

			let rows_html = `
				<table class="table table-bordered" style="font-size:13px;margin-top:8px;">
					<tbody>
						<tr style="background:${s.mapped ? "#f6fff6" : ""};">
							<td style="padding:8px 12px;width:80%;">
								${__("Rows remaining in <b>Material Mapping (Alternate Stock)</b>")}
								<br><span class="text-muted" style="font-size:11px;">${s.mapped} batch${s.mapped !== 1 ? "es" : ""} assigned</span>
								${reservation_detail}
							</td>
							<td style="padding:8px 12px;font-weight:700;text-align:center;color:${s.mapped ? "green" : ""};">${s.mapped}</td>
						</tr>
						<tr style="background:${s.unavail ? "#fff5f5" : ""};">
							<td style="padding:8px 12px;">
								${__("Moved to <b>Unavailable Items (No Stock — Needs Purchase)</b>")}
								${s.unavail ? `<br><span class="text-muted" style="font-size:11px;">${__("No batch assigned — create a Material Request to purchase")}</span>` : ""}
							</td>
							<td style="padding:8px 12px;font-weight:700;text-align:center;color:${s.unavail ? "red" : "green"};">${s.unavail}</td>
						</tr>
					</tbody>
				</table>`;

			frappe.msgprint({
				title: __("Move to Unavailable Items — Summary"),
				indicator: s.unavail ? "orange" : "green",
				message: rows_html,
			});
			return;
		}

		// Show "Update Exact Match" summary popup if stashed by the button handler
		if (frm._update_exact_summary) {
			let s = frm._update_exact_summary;
			frm._update_exact_summary = null;

			let arm_added = s.arm_rows_added;
			let row_range = "";
			if (arm_added === 1) {
				row_range = __("{0} row added to Exact Match table", [arm_added]);
			} else if (arm_added > 1) {
				row_range = __("{0} rows added to Exact Match table", [arm_added]);
			}

			let rows_html = `
				<table class="table table-bordered" style="font-size:13px;margin-top:8px;">
					<tbody>
						<tr>
							<td style="padding:8px 12px;width:80%;">
								${__("Total items checked from <b>Unavailable Items</b>")}
							</td>
							<td style="padding:8px 12px;font-weight:700;text-align:center;">${s.unavail_total}</td>
						</tr>
						<tr style="background:#f6fff6;">
							<td style="padding:8px 12px;">
								${__("Exact match found — added to <b>Available Raw Materials (Exact Match)</b>")}
								${row_range ? `<br><span class="text-muted" style="font-size:11px;">(${row_range})</span>` : ""}
							</td>
							<td style="padding:8px 12px;font-weight:700;text-align:center;color:green;">${s.matched_count}</td>
						</tr>
						<tr style="background:${s.mapping_added ? "#fffbf0" : ""};">
							<td style="padding:8px 12px;">
								${__("Added to <b>Material Mapping (Alternate Stock)</b>")}
								${s.mapping_added ? `<br><span class="text-muted" style="font-size:11px;">${__("Batch items with no exact match — assign a batch manually")}</span>` : ""}
							</td>
							<td style="padding:8px 12px;font-weight:700;text-align:center;color:${s.mapping_added ? "orange" : "green"};">${s.mapping_added}</td>
						</tr>
						<tr style="background:${s.still_unavail ? "#fff5f5" : ""};">
							<td style="padding:8px 12px;">
								${__("Kept in <b>Unavailable Items (No Stock — Needs Purchase)</b>")}
								${s.still_unavail ? `<br><span class="text-muted" style="font-size:11px;">${__("Non-batch items with insufficient stock — create a Material Request")}</span>` : ""}
							</td>
							<td style="padding:8px 12px;font-weight:700;text-align:center;color:${s.still_unavail ? "red" : "green"};">${s.still_unavail}</td>
						</tr>
					</tbody>
				</table>`;

			frappe.msgprint({
				title: __("Update Exact Match — Summary"),
				indicator: s.matched_count ? "green" : (s.still_unavail ? "red" : "orange"),
				message: rows_html,
			});
			return; // skip batch warning check this save cycle
		}

		// Batch stock warning after any other save that has mapping rows
		if (!frm.doc.for_warehouse) return;
		let has_unresolved = (frm.doc.material_mapping || []).some(r => r.batch);
		if (!has_unresolved) return;

		frappe.call({
			method: "manufyxinvenzaerp.production_management.doctype.material_planning.material_planning.check_mapping_batch_availability",
			args: { doc: frm.doc },
			callback(r) {
				let warnings = (r && r.message) || [];
				if (warnings.length) {
					_show_batch_warning_popup(warnings);
				}
			},
		});
	},
});

frappe.ui.form.on("Material Planning", {
	check_stock_btn(frm) {
		if (!frm.doc.for_warehouse) {
			frappe.msgprint(__("Set 'Raw Materials Warehouse' before checking stock."));
			return;
		}
		if (!(frm.doc.raw_materials || []).length) {
			frappe.msgprint(__("Get Raw Materials first before checking stock."));
			return;
		}

		let _run = function() {
			frappe.call({
				method: "manufyxinvenzaerp.production_management.doctype.material_planning.material_planning.check_stock_availability",
				args: { doc: frm.doc },
				freeze: true,
				freeze_message: __("Checking stock…"),
				callback(r) {
					if (!r.message) return;
					let result = r.message;

					frm.clear_table("raw_materials");
					(result.raw_materials || []).forEach(function(row) {
						let child = frm.add_child("raw_materials");
						Object.keys(row).forEach(function(k) { if (k !== "name" && k !== "idx") child[k] = row[k]; });
					});
					frm.refresh_field("raw_materials");

					frm.clear_table("available_raw_materials");
					(result.available_raw_materials || []).forEach(function(row) {
						let child = frm.add_child("available_raw_materials");
						Object.keys(row).forEach(function(k) { if (k !== "name" && k !== "idx") child[k] = row[k]; });
					});
					frm.refresh_field("available_raw_materials");

					frm.clear_table("material_mapping");
					(result.material_mapping || []).forEach(function(row) {
						let child = frm.add_child("material_mapping");
						Object.keys(row).forEach(function(k) { if (k !== "name" && k !== "idx") child[k] = row[k]; });
						if (!child.batch_mapped) child.batch_mapped = child.batch ? "Mapped" : "Not Mapped";
					});
					frm.refresh_field("material_mapping");

					frm.clear_table("unavailable_items");
					(result.unavailable_items || []).forEach(function(row) {
						let child = frm.add_child("unavailable_items");
						Object.keys(row).forEach(function(k) { if (k !== "name" && k !== "idx") child[k] = row[k]; });
					});
					frm.refresh_field("unavailable_items");

					let mapping = (result.material_mapping || []).length;
					let unavail = (result.unavailable_items || []).length;
					let avail   = (result.available_raw_materials || []).length;
					let shortfall_mapping = result.shortfall_mapping_count || 0;

					frm.set_df_property("finalize_mapping_btn",   "hidden", mapping  ? 0 : 1);
					frm.set_df_property("update_exact_match_btn", "hidden", unavail  ? 0 : 1);

					_update_weight_summary(frm);

					// Stash summary for after_save popup
					frm._check_stock_summary = { avail, mapping, unavail, shortfall_mapping };
					frm.save();
				},
			});
		};

		let has_exact_reserved   = (frm.doc.available_raw_materials || []).some(r => r.is_reserved);
		let has_mapping_reserved = (frm.doc.material_mapping || []).some(r => r.is_reserved);
		if (has_exact_reserved || has_mapping_reserved) {
			let which = [];
			if (has_exact_reserved)   which.push(__("<b>Available Raw Materials (Exact Match)</b>"));
			if (has_mapping_reserved) which.push(__("<b>Material Mapping (Alternate Stock)</b>"));
			frappe.msgprint({
				title: __("Cannot Re-check Stock"),
				indicator: "red",
				message: __("Stocks are already reserved in: {0}. Unreserve all reservations before re-checking.", [which.join(", ")]),
			});
			return;
		}

		// Evaluate all conditions up front and show ONE combined confirm
		let has_exact_batch = (frm.doc.available_raw_materials || []).some(r => r.batch_no);
		let has_work        = (frm.doc.material_mapping || []).length || (frm.doc.unavailable_items || []).length;
		let has_reserved    = (frm.doc.material_mapping || []).some(r => r.is_reserved);

		if (!has_exact_batch && !has_work) {
			_run();
			return;
		}

		let points = [];
		if (has_exact_batch) {
			points.push(__("Batches already mapped in <b>Available Raw Materials (Exact Match)</b> will be updated."));
		}
		if (has_work && has_reserved) {
			points.push(__("All mapping work in <b>Material Mapping</b> including <b>RESERVED rows</b> will be cleared — unreserve first if you want to keep them."));
		} else if (has_work) {
			points.push(__("All current mapping work in <b>Material Mapping</b> and <b>Unavailable Items</b> will be cleared."));
		}

		let msg = "<p>" + __("Re-checking stock will do the following:") + "</p><ul style='margin:6px 0 0 16px;'>"
			+ points.map(p => `<li style="margin-bottom:4px;">${p}</li>`).join("")
			+ "</ul><p style='margin-top:8px;'>" + __("Continue?") + "</p>";

		frappe.confirm(msg, _run);
	},

	verify_material_mapping_btn(frm) {
		if (!(frm.doc.material_mapping || []).length) {
			frappe.msgprint(__("No items in Material Mapping to verify."));
			return;
		}
		frappe.call({
			method: "manufyxinvenzaerp.production_management.doctype.material_planning.material_planning.verify_material_mapping",
			args: { doc: frm.doc },
			freeze: true,
			freeze_message: __("Verifying Nos vs Qty…"),
			callback(r) {
				if (!r.message) return;
				let { checked, issues } = r.message;

				if (!issues.length) {
					frappe.show_alert({ message: __("All {0} row(s) verified — Nos and Qty match.", [checked]), indicator: "green" }, 5);
					return;
				}

				let rows_html = issues.map(function(row) {
					let formula_cell = row.formula_ok
						? `<span style="color:#888;">—</span>`
						: `<span style="color:#c0392b;font-weight:600;">${__("Expected")} ${row.checked_field === "sec_qty" ? "Sec Qty" : "Qty"} = ${row.formula_expected}</span>`;
					let so_cell = row.so_expected_sec_qty === null
						? `<span style="color:#888;">—</span>`
						: (row.so_ok
							? `<span style="color:#2e7d32;">${__("OK")}</span>`
							: `<span style="color:#c0392b;font-weight:600;">${__("SO requires Sec Qty")} = ${row.so_expected_sec_qty}</span>`);
					return `<tr>
						<td style="padding:5px 10px;border-bottom:1px solid #f0f0f0;">${row.idx}</td>
						<td style="padding:5px 10px;border-bottom:1px solid #f0f0f0;">${frappe.utils.escape_html(row.item_number)}</td>
						<td style="padding:5px 10px;border-bottom:1px solid #f0f0f0;">${frappe.utils.escape_html(row.item_code || "")}</td>
						<td style="padding:5px 10px;border-bottom:1px solid #f0f0f0;">${frappe.utils.escape_html(row.customer_drawing_number)}</td>
						<td style="padding:5px 10px;border-bottom:1px solid #f0f0f0;">${row.sec_qty}</td>
						<td style="padding:5px 10px;border-bottom:1px solid #f0f0f0;">${row.qty}</td>
						<td style="padding:5px 10px;border-bottom:1px solid #f0f0f0;">${formula_cell}</td>
						<td style="padding:5px 10px;border-bottom:1px solid #f0f0f0;">${so_cell}</td>
					</tr>`;
				}).join("");

				let html = `<div style="overflow:auto;max-height:60vh;">
					<table style="font-size:12px;border-collapse:collapse;width:100%;">
						<thead><tr style="background:#f4f5f7;">
							<th style="padding:6px 10px;text-align:left;">${__("Row")}</th>
							<th style="padding:6px 10px;text-align:left;">${__("Item No")}</th>
							<th style="padding:6px 10px;text-align:left;">${__("Material Code")}</th>
							<th style="padding:6px 10px;text-align:left;">${__("Drawing")}</th>
							<th style="padding:6px 10px;text-align:left;">${__("Sec Qty (Nos)")}</th>
							<th style="padding:6px 10px;text-align:left;">${__("Qty (Kg)")}</th>
							<th style="padding:6px 10px;text-align:left;">${__("Formula Check")}</th>
							<th style="padding:6px 10px;text-align:left;">${__("Sales Order Check")}</th>
						</tr></thead>
						<tbody>${rows_html}</tbody>
					</table>
				</div>`;

				let d = new frappe.ui.Dialog({
					title: __("{0} of {1} row(s) need attention", [issues.length, checked]),
					size: "extra-large",
				});
				d.$body.html(html);
				d.show();
			},
		});
	},

	finalize_mapping_btn(frm) {
		if (frm.is_dirty()) {
			frappe.msgprint(__("There is unsaved changes, save it to move items to unavailable item table."));
			return;
		}
		if (!(frm.doc.material_mapping || []).length) {
			frappe.msgprint(__("No items in Material Mapping to finalize."));
			return;
		}
		let unmapped = (frm.doc.material_mapping || []).filter(r => !r.batch);
		if (!unmapped.length) {
			frappe.msgprint(__("No items to move to purchase table, all are mapped."));
			return;
		}
		frappe.call({
			method: "manufyxinvenzaerp.production_management.doctype.material_planning.material_planning.finalize_mapping",
			args: { doc: frm.doc },
			freeze: true,
			freeze_message: __("Moving unmapped items to Unavailable…"),
			callback(r) {
				if (!r.message) return;
				let result = r.message;

				frm.clear_table("material_mapping");
				(result.material_mapping || []).forEach(function(row) {
					let child = frm.add_child("material_mapping");
					Object.keys(row).forEach(function(k) { if (k !== "name" && k !== "idx") child[k] = row[k]; });
					if (!child.batch_mapped) child.batch_mapped = child.batch ? "Mapped" : "Not Mapped";
				});
				frm.refresh_field("material_mapping");

				// Merge newly-unmapped rows with existing unavailable items (de-duplicate by item_code+bom_no)
				let existing = (frm.doc.unavailable_items || []).filter(r => r.item_code);
				let existing_keys = new Set(existing.map(r => `${r.item_code}|${r.bom_no || ""}`));
				let new_rows = (result.unavailable_items || []).filter(r => !existing_keys.has(`${r.item_code}|${r.bom_no || ""}`));
				frm.clear_table("unavailable_items");
				existing.concat(new_rows).forEach(function(row) {
					let child = frm.add_child("unavailable_items");
					Object.keys(row).forEach(function(k) { if (k !== "name" && k !== "idx") child[k] = row[k]; });
				});
				frm.refresh_field("unavailable_items");

				let mapped       = (result.material_mapping || []).length;
				let reserved     = (result.material_mapping || []).filter(r => r.is_reserved).length;
				let not_reserved = mapped - reserved;
				let unavail      = (frm.doc.unavailable_items || []).length;

				frm.set_df_property("finalize_mapping_btn",   "hidden", mapped  ? 0 : 1);
				frm.set_df_property("update_exact_match_btn", "hidden", unavail ? 0 : 1);

				_update_weight_summary(frm);

				frm._finalize_mapping_summary = { mapped, reserved, not_reserved, unavail };
				frm.save();
			},
		});
	},

	update_exact_match_btn(frm) {
		let all_items = frm.doc.unavailable_items || [];
		if (!all_items.length) {
			frappe.msgprint(__("No unavailable items to check."));
			return;
		}
		if (!frm.doc.for_warehouse) {
			frappe.msgprint(__("Set 'Raw Materials Warehouse' before checking stock."));
			return;
		}

		// Capture row count before adding so we can report which rows were appended
		let arm_before    = (frm.doc.available_raw_materials || []).length;
		let unavail_total = all_items.length;

		frappe.call({
			method: "manufyxinvenzaerp.production_management.doctype.material_planning.material_planning.move_to_exact_match",
			args: {
				doc: frm.doc,
				item_codes: JSON.stringify(all_items.map(r => r.item_code).filter(Boolean)),
			},
			freeze: true,
			freeze_message: __("Checking stock for unavailable items…"),
			callback(r) {
				if (!r.message) return;
				let { matched, failed, still_unavailable } = r.message;

				const SKIP_KEYS = new Set([
					"name", "idx", "doctype", "parent", "parenttype", "parentfield",
					"__islocal", "__dirty", "__run_link_triggers", "__unsaved",
				]);

				// Matched → add to Available Raw Materials (Exact Match)
				let matched_codes = new Set(matched.map(m => m.item_code));
				matched.forEach(function(row) {
					let child = frm.add_child("available_raw_materials");
					Object.keys(row).forEach(k => { if (k !== "name" && k !== "idx") child[k] = row[k]; });
				});
				frm.refresh_field("available_raw_materials");

				// Failed (batch items with no matching stock) → Material Mapping, assign batch manually
				let failed_set = new Set(failed || []);
				let failed_rows = all_items.filter(r => failed_set.has(r.item_code));
				failed_rows.forEach(function(row) {
					let child = frm.add_child("material_mapping");
					Object.keys(row).forEach(function(k) {
						if (!SKIP_KEYS.has(k)) child[k] = row[k];
					});
					child.batch_mapped = "Not Mapped";
					child.batch = "";
					child.planned_item = "";
				});
				frm.refresh_field("material_mapping");

				// Still unavailable (non-batch items with no plain stock) → stay in Unavailable Items
				let still_set = new Set(still_unavailable || []);
				let still_rows = all_items.filter(r => still_set.has(r.item_code));
				frm.clear_table("unavailable_items");
				still_rows.forEach(function(row) {
					let child = frm.add_child("unavailable_items");
					Object.keys(row).forEach(function(k) {
						if (!SKIP_KEYS.has(k)) child[k] = row[k];
					});
				});
				frm.refresh_field("unavailable_items");

				frm.set_df_property("update_exact_match_btn", "hidden", still_rows.length ? 0 : 1);
				frm.set_df_property("finalize_mapping_btn", "hidden",
					(frm.doc.material_mapping || []).length ? 0 : 1);

				_update_weight_summary(frm);

				// Stash summary so after_save can show the popup once the form is stable
				frm._update_exact_summary = {
					unavail_total:    unavail_total,
					matched_count:    all_items.filter(function(r) { return matched_codes.has(r.item_code); }).length,
					arm_rows_added:   matched.length,
					arm_before:       arm_before,
					mapping_added:    failed_rows.length,
					still_unavail:    still_rows.length,
				};

				frm.save();
			},
		});
	},

	get_raw_materials_btn(frm) {
		if (!frm.doc.bom_items || !frm.doc.bom_items.length) {
			frappe.msgprint(__("Add at least one BOM in the 'Selected BOMs' tab first."));
			return;
		}
		if (!frm.doc.company) {
			frappe.msgprint(__("Set Company before fetching raw materials."));
			return;
		}

		// Block immediately if any stock is reserved in either table
		let has_exact_reserved   = (frm.doc.available_raw_materials || []).some(r => r.is_reserved);
		let has_mapping_reserved = (frm.doc.material_mapping || []).some(r => r.is_reserved);
		if (has_exact_reserved || has_mapping_reserved) {
			let tables = [];
			if (has_exact_reserved)   tables.push(__("Available Raw Materials (Exact Match)"));
			if (has_mapping_reserved) tables.push(__("Material Mapping (Alternate Stock)"));
			frappe.msgprint({
				title: __("Cannot Refetch Raw Materials"),
				indicator: "red",
				message: __("Stock is already reserved in: <b>{0}</b>.<br>Unreserve it first before refetching raw materials.", [tables.join(", ")]),
			});
			return;
		}

		let _fetch = function() {
			frappe.call({
				method: "manufyxinvenzaerp.production_management.doctype.material_planning.material_planning.get_raw_materials",
				args: { doc: frm.doc },
				freeze: true,
				freeze_message: __("Exploding BOMs…"),
				callback(r) {
					if (!r.message) return;
					if (!r.message.length) {
						frappe.msgprint(__("No raw materials found. Check that the BOMs have sub-items."));
						return;
					}
					frm.clear_table("raw_materials");
					r.message.forEach(function(row) {
						let child = frm.add_child("raw_materials");
						Object.keys(row).forEach(function(k) {
							if (k !== "name" && k !== "idx") child[k] = row[k];
						});
					});
					frm.refresh_field("raw_materials");

					// Clear all stock-analysis tables — user must re-run Check Stock
					frm.clear_table("available_raw_materials");
					frm.refresh_field("available_raw_materials");
					frm.clear_table("material_mapping");
					frm.refresh_field("material_mapping");
					frm.clear_table("unavailable_items");
					frm.refresh_field("unavailable_items");

					frm.set_df_property("check_stock_btn",        "hidden", 0);
					frm.set_df_property("finalize_mapping_btn",   "hidden", 1);
					frm.set_df_property("update_exact_match_btn", "hidden", 1);

					_update_weight_summary(frm);

					frappe.show_alert({
						message: __("{0} raw material row(s) loaded.", [r.message.length]),
						indicator: "green",
					}, 5);
					frm.save();
				},
			});
		};

		let has_any_data = (frm.doc.raw_materials || []).length
			|| (frm.doc.available_raw_materials || []).length
			|| (frm.doc.material_mapping || []).length
			|| (frm.doc.unavailable_items || []).length;

		if (!has_any_data) {
			_fetch();
			return;
		}

		// Check for an active Material Request linked to this plan before confirming
		let has_unavail = (frm.doc.unavailable_items || []).length;
		let _check_mr_then_confirm = function() {
			if (!has_unavail || frm.doc.__islocal) {
				_show_confirm();
				return;
			}
			frappe.db.get_value(
				"Material Request",
				{ custom_material_planning: frm.doc.name, docstatus: ["!=", 2] },
				"name",
				function(r) {
					if (r && r.name) {
						frappe.msgprint({
							title: __("Cannot Refetch Raw Materials"),
							indicator: "red",
							message: __("Material Request <b>{0}</b> is already created against Unavailable Items.<br>Cancel it first before refetching raw materials.", [r.name]),
						});
						return;
					}
					_show_confirm();
				}
			);
		};

		let _show_confirm = function() {
			frappe.confirm(
				__("This will replace the existing raw materials list.<br><br>"
					+ "Rows in <b>Available Raw Materials (Exact Match)</b>, "
					+ "<b>Material Mapping (Alternate Stock)</b>, and "
					+ "<b>Unavailable Items (No Stock — Needs Purchase)</b> "
					+ "will also be removed. Continue?"),
				_fetch
			);
		};

		_check_mr_then_confirm();
	},
});

// ── SO Drawing picker — "Show Drawings" button ───────────────────────────────

frappe.ui.form.on("Material Planning", {
	show_drawings_btn(frm) {
		let so = frm.doc.so_bom_import;
		if (!so) {
			frappe.msgprint(__("Select a Sales Order first."));
			return;
		}
		frappe.call({
			method: "manufyxinvenzaerp.production_management.doctype.material_planning.material_planning.get_so_drawings_for_bom_picker",
			args: { so_name: so, mp_name: frm.doc.name || "" },
			freeze: true,
			freeze_message: __("Loading drawings…"),
			callback(r) {
				let drawings = r.message || [];
				if (!drawings.length) {
					frappe.msgprint(__("No submitted BOMs found for Sales Order {0}.", [so]));
					return;
				}
				_show_drawings_picker_dialog(frm, so, drawings);
			},
		});
	},
});

function _show_drawings_picker_dialog(frm, so_name, drawings) {

	// Split into selectable (free) and already-mapped (used in another MP)
	var free_drawings = drawings.filter(function(d) { return !d.already_used_in; });
	var used_drawings = drawings.filter(function(d) { return !!d.already_used_in; });

	// Stamp _orig_idx only on free drawings (used in Insert action)
	free_drawings.forEach(function(d, i) { d._orig_idx = i; });

	function _free_rows_html(rows) {
		if (!rows.length) {
			return '<div style="color:#6c757d;padding:12px 8px;">' + __("No drawings match.") + "</div>";
		}
		return rows.map(function(d) {
			let cdn  = frappe.utils.escape_html(d.customer_drawing_number || "—");
			let duno = frappe.utils.escape_html(String(d.duno_mark_no || "—"));
			let bom  = frappe.utils.escape_html(d.bom_no || "");
			let item = frappe.utils.escape_html(d.item_name || d.item_code || "");
			return `<label style="display:flex;align-items:center;gap:10px;padding:6px 4px;cursor:pointer;border-bottom:1px solid #f0f0f0;user-select:none;">
				<input type="checkbox" class="mp-dchk" data-bom="${bom}" data-orig="${d._orig_idx}"
				       style="width:15px;height:15px;flex-shrink:0;cursor:pointer;" checked>
				<span style="flex:0 0 260px;font-size:12px;font-weight:500;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">${cdn}</span>
				<span style="flex:0 0 120px;font-size:12px;color:#495057;">${duno}</span>
				<span style="flex:0 0 130px;font-size:11px;color:#6c757d;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">${item}</span>
				<span style="flex:1;font-size:11px;color:#aaa;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">${bom}</span>
			</label>`;
		}).join("");
	}

	function _used_rows_html(rows) {
		return rows.map(function(d) {
			let cdn     = frappe.utils.escape_html(d.customer_drawing_number || "—");
			let duno    = frappe.utils.escape_html(String(d.duno_mark_no || "—"));
			let bom     = frappe.utils.escape_html(d.bom_no || "");
			let item    = frappe.utils.escape_html(d.item_name || d.item_code || "");
			let used_in = frappe.utils.escape_html(d.already_used_in || "");
			return `<div style="display:flex;align-items:center;gap:10px;padding:6px 4px;border-bottom:1px solid #f0f0f0;background:#fafafa;">
				<input type="checkbox" disabled
				       style="width:15px;height:15px;flex-shrink:0;cursor:not-allowed;opacity:0.4;">
				<span style="flex:0 0 260px;font-size:12px;font-weight:500;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;color:#bbb;">${cdn}</span>
				<span style="flex:0 0 120px;font-size:12px;color:#bbb;">${duno}</span>
				<span style="flex:0 0 130px;font-size:11px;color:#bbb;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">${item}</span>
				<span style="flex:1;font-size:11px;color:#ccc;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">${bom}</span>
				<span style="flex:0 0 160px;font-size:11px;color:#e65100;font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;"
				      title="${used_in}">${used_in}</span>
			</div>`;
		}).join("");
	}

	let has_used = used_drawings.length > 0;
	let free_height = has_used ? "35vh" : "55vh";

	let header_html = `
		<div style="display:flex;gap:8px;align-items:center;margin-bottom:8px;flex-wrap:wrap;">
			<input id="_mpd_search" type="text" placeholder="${__("Search Customer Drawing ID or DUNO/Mark No…")}"
				style="flex:1;min-width:200px;border:1px solid #d1d8dd;border-radius:4px;padding:5px 10px;font-size:12px;">
			<button class="btn btn-xs btn-default" id="_mpd_sel_all">${__("Select All")}</button>
			<button class="btn btn-xs btn-default" id="_mpd_unsel_all">${__("Unselect All")}</button>
			<span id="_mpd_count" style="font-size:12px;color:#6c757d;"></span>
		</div>
		<div style="display:flex;gap:10px;padding:5px 4px;background:#f4f5f7;border-radius:4px;margin-bottom:4px;font-size:11px;font-weight:600;color:#6c757d;">
			<span style="flex:0 0 15px;"></span>
			<span style="flex:0 0 260px;">${__("Customer Drawing ID")}</span>
			<span style="flex:0 0 120px;">${__("DUNO / Mark No")}</span>
			<span style="flex:0 0 130px;">${__("Item Name")}</span>
			<span style="flex:1;">${__("BOM No")}</span>
		</div>`;

	let free_section_html = `<div id="_mpd_list"
		style="max-height:${free_height};overflow-y:auto;border:1px solid #e9ecef;border-radius:4px;padding:4px 8px;">
		${_free_rows_html(free_drawings)}
	</div>`;

	let used_section_html = "";
	if (has_used) {
		used_section_html = `
			<div style="margin-top:14px;">
				<div style="font-size:12px;font-weight:600;color:#e65100;padding:6px 4px 4px;display:flex;align-items:center;gap:6px;">
					<span>&#9888;</span>
					${__("{0} drawing(s) already mapped in another Material Planning — cannot be selected", [used_drawings.length])}
				</div>
				<div style="display:flex;gap:10px;padding:5px 4px;background:#fff3e0;border-radius:4px 4px 0 0;border:1px solid #ffe0b2;font-size:11px;font-weight:600;color:#6c757d;">
					<span style="flex:0 0 15px;"></span>
					<span style="flex:0 0 260px;">${__("Customer Drawing ID")}</span>
					<span style="flex:0 0 120px;">${__("DUNO / Mark No")}</span>
					<span style="flex:0 0 130px;">${__("Item Name")}</span>
					<span style="flex:1;">${__("BOM No")}</span>
					<span style="flex:0 0 160px;color:#e65100;">${__("Used In MP")}</span>
				</div>
				<div style="max-height:20vh;overflow-y:auto;border:1px solid #ffe0b2;border-top:none;border-radius:0 0 4px 4px;padding:4px 8px;">
					${_used_rows_html(used_drawings)}
				</div>
			</div>`;
	}

	let d = new frappe.ui.Dialog({
		title: __("Select Drawings — {0}", [so_name]),
		size: "extra-large",
		primary_action_label: __("Insert"),
		primary_action() {
			let selected = [];
			d.$body.find(".mp-dchk:checked").each(function() {
				let orig = parseInt($(this).data("orig"));
				if (!isNaN(orig)) selected.push(free_drawings[orig]);
			});

			if (!selected.length) {
				frappe.msgprint(__("Select at least one drawing."));
				return;
			}

			// Skip BOMs already in the table
			let existing = new Set((frm.doc.bom_items || []).map(r => r.bom_no));
			let to_add  = selected.filter(s => !existing.has(s.bom_no));
			let skipped = selected.length - to_add.length;

			to_add.forEach(function(s) {
				let child = frm.add_child("bom_items");
				child.bom_no                  = s.bom_no;
				child.item_code               = s.item_code  || "";
				child.item_name               = s.item_name  || "";
				child.drawing                 = s.drawing    || "";
				child.duno_mark_no            = s.duno_mark_no            || "";
				child.customer_drawing_number = s.customer_drawing_number || "";
				child.sales_order             = s.sales_order || "";
				child.customer                = s.customer   || "";
				child.qty_to_manufacture      = s.qty_to_manufacture || 1;
				child.uom                     = s.uom        || "";
			});
			frm.refresh_field("bom_items");

			d.hide();
			let msg = __("{0} BOM(s) added.", [to_add.length]);
			if (skipped) msg += "  " + __("{0} already in table — skipped.", [skipped]);
			frappe.show_alert({ message: msg, indicator: "green" }, 5);
		},
	});

	d.$body.html(header_html + free_section_html + used_section_html);

	function _update_count() {
		let total   = d.$body.find(".mp-dchk").length;
		let checked = d.$body.find(".mp-dchk:checked").length;
		d.$body.find("#_mpd_count").text(checked + " / " + total + " " + __("selected"));
	}

	function _apply_filter() {
		let q = (d.$body.find("#_mpd_search").val() || "").toLowerCase();
		let visible = q
			? free_drawings.filter(function(dd) {
				return String(dd.customer_drawing_number || "").toLowerCase().includes(q)
					|| String(dd.duno_mark_no || "").toLowerCase().includes(q)
					|| String(dd.bom_no || "").toLowerCase().includes(q)
					|| String(dd.item_name || "").toLowerCase().includes(q);
			})
			: free_drawings.slice();
		d.$body.find("#_mpd_list").html(_free_rows_html(visible));
		_update_count();
	}

	d.$body.on("input",  "#_mpd_search",  _apply_filter);
	d.$body.on("change", ".mp-dchk",      _update_count);
	d.$body.on("click",  "#_mpd_sel_all", function() {
		d.$body.find(".mp-dchk").prop("checked", true);
		_update_count();
	});
	d.$body.on("click", "#_mpd_unsel_all", function() {
		d.$body.find(".mp-dchk").prop("checked", false);
		_update_count();
	});

	_update_count();
	d.show();
}

// Auto-fill BOM row details from the linked Drawing when bom_no is set
frappe.ui.form.on("Material Planning BOM Item", {
	bom_no(frm, cdt, cdn) {
		let row = locals[cdt][cdn];
		if (!row.bom_no) return;
		frappe.call({
			method: "manufyxinvenzaerp.production_management.doctype.material_planning.material_planning.get_bom_info",
			args: { bom_no: row.bom_no },
			callback(r) {
				if (!r.message) return;
				let d = r.message;
				frappe.model.set_value(cdt, cdn, "item_code",               d.item_code || "");
				frappe.model.set_value(cdt, cdn, "item_name",               d.item_name || "");
				frappe.model.set_value(cdt, cdn, "drawing",                 d.drawing || "");
				frappe.model.set_value(cdt, cdn, "duno_mark_no",            d.duno_mark_no || 0);
				frappe.model.set_value(cdt, cdn, "customer_drawing_number", d.customer_drawing_number || "");
				frappe.model.set_value(cdt, cdn, "sales_order",             d.sales_order || "");
				frappe.model.set_value(cdt, cdn, "customer",                d.customer || "");
				frappe.model.set_value(cdt, cdn, "qty_to_manufacture",      d.qty_to_manufacture || 0);
				frappe.model.set_value(cdt, cdn, "uom",                     d.uom || "");
			},
		});
	},
});

// Add to Mapping dialog — user assigns a batch per unavailable item
function _show_add_to_mapping_dialog(frm, selected_rows) {
	let fields = [];

	selected_rows.forEach(function (row, idx) {
		fields.push({
			fieldtype: "Section Break",
			label: `${row.item_code} — ${row.item_name || ""}`,
		});
		fields.push({
			fieldname: `batch_${idx}`,
			fieldtype: "Link",
			label: __("Assign Batch"),
			options: "Batch",
		});
	});

	let d = new frappe.ui.Dialog({
		title: __("Add to Material Mapping"),
		fields: fields,
		primary_action_label: __("Add"),
		primary_action(values) {
			let to_map = [];
			selected_rows.forEach(function (row, idx) {
				let batch = values[`batch_${idx}`];
				if (batch) to_map.push({ row: row, batch: batch });
			});

			if (!to_map.length) {
				frappe.msgprint(__("Assign at least one batch to proceed."));
				return;
			}

			let mapped_codes = new Set(to_map.map(m => m.row.item_code));

			// Add rows to material_mapping; use frappe.model.set_value for batch
			// so the existing "batch" field handler auto-fills planned_item
			const SKIP_KEYS = new Set([
				"name", "idx", "doctype", "parent", "parenttype", "parentfield",
				"__islocal", "__dirty", "__run_link_triggers", "__unsaved",
			]);
			to_map.forEach(function (m) {
				let child = frm.add_child("material_mapping");
				Object.keys(m.row).forEach(function (k) {
					if (!SKIP_KEYS.has(k)) child[k] = m.row[k];
				});
				// set_value triggers the batch → planned_item handler
				frappe.model.set_value(child.doctype, child.name, "batch", m.batch);
			});
			frm.refresh_field("material_mapping");

			// Remove mapped items from unavailable_items
			let remaining = (frm.doc.unavailable_items || []).filter(r => !mapped_codes.has(r.item_code));
			frm.clear_table("unavailable_items");
			remaining.forEach(function (row) {
				let child = frm.add_child("unavailable_items");
				Object.keys(row).forEach(function (k) {
					if (k !== "name" && k !== "idx") child[k] = row[k];
				});
			});
			frm.refresh_field("unavailable_items");

			// Update button visibility to match new table state
			let has_mapping  = !!(frm.doc.material_mapping   || []).length;
			let has_unavail  = !!(frm.doc.unavailable_items   || []).length;
			frm.set_df_property("finalize_mapping_btn",   "hidden", has_mapping  ? 0 : 1);
			frm.set_df_property("update_exact_match_btn", "hidden", has_unavail  ? 0 : 1);
			setTimeout(function () {
				let $fin = frm.fields_dict["finalize_mapping_btn"] && frm.fields_dict["finalize_mapping_btn"].$input;
				if ($fin && $fin.length) {
					$fin.html(frappe.utils.icon("move", "sm") + "&nbsp;" + __("Move to Unavailable Items"));
				}
			}, 50);

			d.hide();
			frappe.show_alert({
				message: __("{0} item(s) moved to Material Mapping.", [mapped_codes.size]),
				indicator: "blue",
			}, 5);
		},
	});

	d.show();
}

// Material Request creation dialog
function _show_material_request_dialog(frm) {
	let items = (frm.doc.unavailable_items || []).filter(r => r.item_code);
	if (!items.length) {
		frappe.msgprint(__("No unavailable items to request."));
		return;
	}
	if (frm.is_dirty()) {
		frm.save()
			.then(function() { _build_material_request_dialog(frm, items); })
			.catch(function() { frappe.msgprint(__("Please save the document successfully before creating a Material Request.")); });
	} else {
		_build_material_request_dialog(frm, items);
	}
}

function _build_material_request_dialog(frm, items) {

	let fields = [
		{
			fieldname: "items_section",
			fieldtype: "Section Break",
			label: __("Select Items to Request"),
			description: __("Tick the items you want to include in the Material Request."),
		},
	];

	items.forEach(function (row, idx) {
		let display_item = row.alternate_item ? row.alternate_item : `${row.item_code} — ${row.item_name || ""}`;
		let display_qty  = row.alternate_item && row.alternate_quantity
			? `${flt(row.alternate_quantity).toFixed(3)} Kg`
			: `${row.qty} ${row.uom || ""}`;
		let alt_suffix   = row.alternate_item ? ` (Alt for ${row.item_code})` : "";
		fields.push({
			fieldname: "item_" + idx,
			fieldtype: "Check",
			label: `${display_item} | Qty: ${display_qty}${alt_suffix}`,
			default: 1,
		});
	});

	let d = new frappe.ui.Dialog({
		title: __("Create Material Request"),
		fields: fields,
		primary_action_label: __("Create"),
		primary_action(values) {
			let selected = [];
			items.forEach(function (row, idx) {
				if (values["item_" + idx]) {
					selected.push(row.item_code);
				}
			});

			if (!selected.length) {
				frappe.msgprint(__("Select at least one item."));
				return;
			}

			frappe.call({
				method: "manufyxinvenzaerp.production_management.doctype.material_planning.material_planning.make_material_request",
				args: {
					material_planning_name: frm.doc.name,
					selected_items: JSON.stringify(selected),
				},
				freeze: true,
				freeze_message: __("Creating Material Request…"),
				callback(r) {
					if (r.message) {
						d.hide();
						frappe.show_alert({
							message: __("Material Request {0} created.", [r.message]),
							indicator: "green",
						}, 5);
						frappe.set_route("Form", "Material Request", r.message);
					}
				},
			});
		},
	});

	d.show();
}

// ── Alternate dimension UI helpers ───────────────────────────────────────────

function _apply_alternate_dim_ui(frm, cdt, cdn, group) {
	let get_df = function(fn) {
		return frappe.meta.get_docfield("Material Planning Unavailable Item", fn, frm.doc.name);
	};

	// Defaults: hide all, not required
	let cfg = {
		alternate_length:    { hidden: 1, reqd: 0 },
		alternate_width:     { hidden: 1, reqd: 0 },
		alternate_thickness: { hidden: 1, reqd: 0 },
		alternate_sec_qty:   { hidden: 1, reqd: 0 },
	};

	if (group === "Structurals") {
		cfg.alternate_length.hidden  = 0; cfg.alternate_length.reqd  = 1;
		cfg.alternate_sec_qty.hidden = 0; cfg.alternate_sec_qty.reqd = 1;
	} else if (group === "Plates") {
		cfg.alternate_length.hidden    = 0; cfg.alternate_length.reqd    = 1;
		cfg.alternate_width.hidden     = 0; cfg.alternate_width.reqd     = 1;
		cfg.alternate_thickness.hidden = 0; cfg.alternate_thickness.reqd = 1;
		cfg.alternate_sec_qty.hidden   = 0; cfg.alternate_sec_qty.reqd   = 1;
	}

	Object.keys(cfg).forEach(function(fn) {
		let df = get_df(fn);
		if (df) { df.hidden = cfg[fn].hidden; df.reqd = cfg[fn].reqd; }
	});

	frm.refresh_field("unavailable_items");
}

function _recalc_alternate_quantity(frm, cdt, cdn) {
	let row = locals[cdt][cdn];
	let group = row.alternate_parent_item_group || "";
	let L  = flt(row.alternate_length);
	let W  = flt(row.alternate_width);
	let T  = flt(row.alternate_thickness);
	let S  = flt(row.alternate_sec_qty);
	let UW = flt(row.alternate_unit_weight);

	let qty = 0;
	if (group === "Structurals" && L && UW && S) {
		qty = (L / 1000) * UW * S;
	} else if (group === "Plates" && L && W && T && UW && S) {
		qty = (L / 1000) * (W / 1000) * T * UW * S;
	}
	frappe.model.set_value(cdt, cdn, "alternate_quantity", qty);
}

frappe.ui.form.on("Material Planning Unavailable Item", {
	form_render(frm, cdt, cdn) {
		// Restore field visibility when an existing row is expanded
		let row = locals[cdt][cdn];
		_apply_alternate_dim_ui(frm, cdt, cdn, row.alternate_parent_item_group || null);
	},

	alternate_item(frm, cdt, cdn) {
		let row = locals[cdt][cdn];
		if (!row.alternate_item) {
			frappe.model.set_value(cdt, cdn, "alternate_length",            0);
			frappe.model.set_value(cdt, cdn, "alternate_width",             0);
			frappe.model.set_value(cdt, cdn, "alternate_thickness",         0);
			frappe.model.set_value(cdt, cdn, "alternate_sec_qty",           0);
			frappe.model.set_value(cdt, cdn, "alternate_unit_weight",       0);
			frappe.model.set_value(cdt, cdn, "alternate_quantity",          0);
			frappe.model.set_value(cdt, cdn, "alternate_parent_item_group", "");
			_apply_alternate_dim_ui(frm, cdt, cdn, null);
			return;
		}
		frappe.db.get_value(
			"Item",
			row.alternate_item,
			["custom_parent_item_group", "custom_unit_weight"],
			function(d) {
				if (!d) return;
				let group = d.custom_parent_item_group || "";
				frappe.model.set_value(cdt, cdn, "alternate_parent_item_group", group);
				frappe.model.set_value(cdt, cdn, "alternate_unit_weight", flt(d.custom_unit_weight));
				_apply_alternate_dim_ui(frm, cdt, cdn, group);
				_recalc_alternate_quantity(frm, cdt, cdn);
			}
		);
	},

	alternate_length(frm, cdt, cdn)    { _recalc_alternate_quantity(frm, cdt, cdn); },
	alternate_width(frm, cdt, cdn)     { _recalc_alternate_quantity(frm, cdt, cdn); },
	alternate_thickness(frm, cdt, cdn) { _recalc_alternate_quantity(frm, cdt, cdn); },
	alternate_sec_qty(frm, cdt, cdn)   { _recalc_alternate_quantity(frm, cdt, cdn); },
	alternate_unit_weight(frm, cdt, cdn) { _recalc_alternate_quantity(frm, cdt, cdn); },
});

// Recalculate Calc Qty (Kg) from assigned batch dimensions × sec qty
function _recalc_batch_qty(frm, cdt, cdn) {
	let row = locals[cdt][cdn];
	let group = row.batch_parent_item_group || "";
	let L  = flt(row.batch_length);
	let W  = flt(row.batch_width);
	let T  = flt(row.batch_thickness);
	let S  = flt(row.batch_sec_qty);
	let UW = flt(row.batch_unit_weight);

	let qty = 0;
	if (group === "Structurals" && L && UW && S) {
		qty = (L / 1000) * UW * S;
	} else if (group === "Plates" && L && W && T && UW && S) {
		qty = (L / 1000) * (W / 1000) * T * UW * S;
	} else if (group === "Nuts and Bolts" && S && UW) {
		qty = flt(S * UW, 3);
	}
	frappe.model.set_value(cdt, cdn, "batch_calc_qty", flt(qty, 3));
}

function _kg_per_nos(group, L, W, T, UW) {
	L = flt(L); W = flt(W); T = flt(T); UW = flt(UW);
	if (group === "Structurals" && L && UW) return (L / 1000) * UW;
	if (group === "Plates" && L && W && T && UW) return (L / 1000) * (W / 1000) * T * UW;
	if (group === "Nuts and Bolts" && UW) return UW;
	return 0;
}

// Preview how much Kg must actually be reserved for rows under "Reserve stock
// without dimensions" + "Allocate based on Sec Nos". Stock can only be
// physically transferred in whole Sec Qty (Nos) pieces, so every row sharing
// the SAME batch is grouped, their required Kg summed, rounded UP to the
// nearest whole piece as a GROUP, then split back across the rows
// proportional to each row's own required-Kg share — mirrors the server-side
// _calc_group_rwd_allocations (rounding per row independently would
// over-reserve an extra sheet per row instead of one extra sheet per group).
// Recalculates every row in the group, not just the one that changed, since
// the group total depends on all of them.
function _calc_rwd_preview(frm, cdt, cdn) {
	let row = locals[cdt][cdn];
	if (!row.reserve_without_dimensions || !row.batch) return;

	if (!row.allocate_based_on_sec_qty) {
		frappe.model.set_value(cdt, cdn, "batch_sec_qty", 0);
		frappe.model.set_value(cdt, cdn, "batch_calc_qty", 0);
		return;
	}

	let group_rows = (frm.doc.material_mapping || []).filter(function(r) {
		return r.batch === row.batch && !r.is_reserved
			&& r.reserve_without_dimensions && r.allocate_based_on_sec_qty
			&& (r.batch_parent_item_group === "Structurals" || r.batch_parent_item_group === "Plates");
	});
	if (!group_rows.length) return;

	let kg_per_nos = _kg_per_nos(row.batch_parent_item_group, row.batch_length, row.batch_width, row.batch_thickness, row.batch_unit_weight);
	let group_required = group_rows.reduce(function(sum, r) { return sum + flt(r.qty); }, 0);

	if (!kg_per_nos || !group_required) {
		group_rows.forEach(function(r) {
			frappe.model.set_value(r.doctype, r.name, "batch_sec_qty", 0);
			frappe.model.set_value(r.doctype, r.name, "batch_calc_qty", flt(r.qty, 3));
		});
		return;
	}

	let sec_qty_needed = Math.ceil(flt(group_required / kg_per_nos, 9));
	let group_kg_to_reserve = flt(sec_qty_needed * kg_per_nos, 3);

	group_rows.forEach(function(r) {
		let share = flt(r.qty) / group_required;
		let row_kg = flt(share * group_kg_to_reserve, 3);
		let row_sec = flt(row_kg / kg_per_nos, 3);
		frappe.model.set_value(r.doctype, r.name, "batch_sec_qty", row_sec);
		frappe.model.set_value(r.doctype, r.name, "batch_calc_qty", row_kg);
	});
}

// Fetch and populate batch stock summary (total / reserved / free) for a mapping row
function _fetch_batch_stock_summary(frm, cdt, cdn) {
	let row = locals[cdt][cdn];
	if (!row.batch || !frm.doc.for_warehouse) return;
	frappe.call({
		method: "manufyxinvenzaerp.production_management.doctype.material_planning.material_planning.get_batch_stock_summary",
		args: {
			batch_no: row.batch,
			warehouse: frm.doc.for_warehouse,
			mp_name: frm.doc.name || "",
		},
		callback(r) {
			if (!r.message) return;
			let d = r.message;
			frappe.model.set_value(cdt, cdn, "batch_total_qty",    flt(d.total_qty,    3));
			frappe.model.set_value(cdt, cdn, "batch_reserved_qty", flt(d.reserved_qty, 3));
			frappe.model.set_value(cdt, cdn, "batch_free_qty",     flt(d.free_qty,     3));
		},
	});
}

// Table 3: batch field events on Material Mapping rows
frappe.ui.form.on("Material Planning Material Mapping", {
	form_render(frm, cdt, cdn) {
		// Refresh stock summary whenever a row is expanded
		let row = locals[cdt][cdn];
		if (row.batch) {
			_fetch_batch_stock_summary(frm, cdt, cdn);
		}
	},

	batch(frm, cdt, cdn) {
		let row = locals[cdt][cdn];

		// Block batch change on reserved rows — revert to DB value and show error
		if (row.is_reserved) {
			frappe.msgprint(__("This row is reserved. Unreserve it before changing the batch."));
			if (row.name && !String(row.name).startsWith("new-")) {
				frappe.db.get_value(
					"Material Planning Material Mapping",
					row.name,
					"batch",
					function (d) {
						frappe.model.set_value(cdt, cdn, "batch", (d && d.batch) || "");
						frappe.model.set_value(cdt, cdn, "planned_item", "");
					}
				);
			} else {
				frappe.model.set_value(cdt, cdn, "batch", "");
				frappe.model.set_value(cdt, cdn, "planned_item", "");
			}
			return;
		}

		if (!row.batch) {
			frappe.model.set_value(cdt, cdn, "planned_item", "");
			frappe.model.set_value(cdt, cdn, "batch_length", 0);
			frappe.model.set_value(cdt, cdn, "batch_width", 0);
			frappe.model.set_value(cdt, cdn, "batch_thickness", 0);
			frappe.model.set_value(cdt, cdn, "batch_unit_weight", 0);
			frappe.model.set_value(cdt, cdn, "batch_parent_item_group", "");
			frappe.model.set_value(cdt, cdn, "batch_sec_qty", 0);
			frappe.model.set_value(cdt, cdn, "batch_calc_qty", 0);
			frappe.model.set_value(cdt, cdn, "batch_total_qty", 0);
			frappe.model.set_value(cdt, cdn, "batch_reserved_qty", 0);
			frappe.model.set_value(cdt, cdn, "batch_free_qty", 0);
			frappe.model.set_value(cdt, cdn, "batch_mapped", "Not Mapped");
			return;
		}

		// Batch is being assigned — mark as Mapped and fetch stock summary
		frappe.model.set_value(cdt, cdn, "batch_mapped", "Mapped");
		_fetch_batch_stock_summary(frm, cdt, cdn);

		// Fetch batch dimensions (length, width, thickness)
		frappe.db.get_value(
			"Batch",
			row.batch,
			["custom_length", "custom_width", "custom_thickness"],
			function(d) {
				if (!d) return;
				frappe.model.set_value(cdt, cdn, "batch_length",    flt(d.custom_length));
				frappe.model.set_value(cdt, cdn, "batch_width",     flt(d.custom_width));
				frappe.model.set_value(cdt, cdn, "batch_thickness", flt(d.custom_thickness));
				_recalc_batch_qty(frm, cdt, cdn);
			}
		);

		// Fetch planned item → then fetch unit_weight and item group from that item
		frappe.call({
			method: "manufyxinvenzaerp.production_management.doctype.material_planning.material_planning.get_batch_item",
			args: { batch_no: row.batch },
			callback(r) {
				if (!r.message) return;
				let item_code = r.message;
				frappe.model.set_value(cdt, cdn, "planned_item", item_code);

				frappe.db.get_value(
					"Item",
					item_code,
					["custom_unit_weight", "custom_parent_item_group"],
					function(d) {
						if (!d) return;
						frappe.model.set_value(cdt, cdn, "batch_unit_weight",        flt(d.custom_unit_weight));
						frappe.model.set_value(cdt, cdn, "batch_parent_item_group",  d.custom_parent_item_group || "");
						_recalc_batch_qty(frm, cdt, cdn);
						// Alert user to enter Sec Qty for dimensional items
						let group = d.custom_parent_item_group || "";
						if (group === "Structurals" || group === "Plates") {
							frappe.show_alert({
								message: __("Batch selected — enter <b>Sec Qty (NOS)</b> to calculate the required weight."),
								indicator: "blue",
							}, 6);
						}
					}
				);
			},
		});
	},

	batch_sec_qty(frm, cdt, cdn) {
		_recalc_batch_qty(frm, cdt, cdn);
		_update_weight_summary(frm);
	},

	reserve_without_dimensions(frm, cdt, cdn) {
		let row = locals[cdt][cdn];
		if (row.reserve_without_dimensions) {
			frappe.model.set_value(cdt, cdn, "allocate_based_on_sec_qty", 1);
			// set_value above won't re-fire its own handler if the value was
			// already 1 (e.g. row default) — calculate directly too.
			_calc_rwd_preview(frm, cdt, cdn);
		} else {
			frappe.model.set_value(cdt, cdn, "batch_sec_qty", 0);
			frappe.model.set_value(cdt, cdn, "batch_calc_qty", 0);
		}
		frm.fields_dict["material_mapping"].grid.refresh_row(cdn);
	},

	allocate_based_on_sec_qty(frm, cdt, cdn) {
		_calc_rwd_preview(frm, cdt, cdn);
		frm.fields_dict["material_mapping"].grid.refresh_row(cdn);
	},
});

// Shared helper: build the partial-reservation warning table HTML
function _partial_reservation_html(partial) {
	let lines = partial.map(function(p) {
		let batch_cell = p.batch || __("(non-batch)");
		let reserved_by = flt(p.reserved_by_others);
		let reserved_by_cell = reserved_by > 0
			? `<span style="color:orange;font-weight:bold">${reserved_by} ${p.uom}</span>`
			: `0 ${p.uom}`;
		return `<tr>
			<td>${p.item_code}</td>
			<td>${p.item_name || ""}</td>
			<td>${batch_cell}</td>
			<td>${p.required_qty} ${p.uom}</td>
			<td>${flt(p.batch_stock)} ${p.uom}</td>
			<td>${reserved_by_cell}</td>
			<td>${p.reserved_qty} ${p.uom}</td>
			<td style="color:red;font-weight:bold">${p.shortfall_qty} ${p.uom}</td>
		</tr>`;
	}).join("");
	return `<p>${__("Some items had insufficient free stock. Partial quantities were reserved:")}</p>
		<table class="table table-bordered table-condensed" style="font-size:12px">
			<thead><tr>
				<th>${__("Item Code")}</th><th>${__("Item Name")}</th><th>${__("Batch")}</th>
				<th>${__("Required")}</th><th>${__("Total Stock")}</th>
				<th>${__("Reserved by Others")}</th>
				<th>${__("Reserved")}</th><th>${__("Shortfall")}</th>
			</tr></thead>
			<tbody>${lines}</tbody>
		</table>`;
}

// Reserve / Unreserve toolbar buttons on the Material Mapping grid
function _add_reservation_buttons(frm) {
	let grid = frm.fields_dict["material_mapping"] && frm.fields_dict["material_mapping"].grid;
	if (!grid) return;

	grid.add_custom_button(
		frappe.utils.icon("lock", "xs") + " " + __("Reserve"),
		function () {
			let has_batch = (frm.doc.material_mapping || []).some(r => r.batch && !r.is_reserved);
			if (!has_batch) {
				frappe.msgprint(__("No un-reserved rows with a batch to reserve."));
				return;
			}

			// Validate: all dimensional batch rows must have Sec Qty entered —
			// unless the row is flagged to reserve stock without dimensions.
			let missing_sec = (frm.doc.material_mapping || []).filter(function(r) {
				let group = r.batch_parent_item_group || "";
				return r.batch && !r.is_reserved && !r.reserve_without_dimensions
					&& (group === "Structurals" || group === "Plates")
					&& !flt(r.batch_sec_qty);
			});
			if (missing_sec.length) {
				let items = missing_sec.map(r => `Row ${r.idx}: ${r.item_code} (Batch: ${r.batch})`).join("<br>");
				frappe.msgprint({
					title: __("Sec Qty Required"),
					indicator: "red",
					message: __("Enter <b>Sec Qty (NOS)</b> for the following rows before reserving:<br><br>{0}", [items]),
				});
				return;
			}

			frappe.confirm(__("Reserve all batches assigned in Material Mapping?"), function () {
				let do_reserve = function() {
					frappe.call({
						method: "manufyxinvenzaerp.production_management.doctype.material_planning.material_planning.reserve_batches",
						args: { material_planning_name: frm.doc.name },
						freeze: true,
						freeze_message: __("Reserving batches…"),
						callback(r) {
							if (!r.message) return;
							frm._grid_btns_added = false;
							frm.reload_doc();
							let partial = r.message.partial || [];
							if (partial.length) {
								frappe.msgprint({
									title: __("Partial Reservation — Stock Shortfall"),
									indicator: "orange",
									message: _partial_reservation_html(partial),
								});
							} else {
								frappe.show_alert({ message: __("Batches reserved."), indicator: "green" }, 4);
							}
						},
					});
				};
				if (frm.is_dirty()) {
					frm.save().then(do_reserve).catch(function() {
						frappe.msgprint(__("Save failed. Fix any errors before reserving."));
					});
				} else {
					do_reserve();
				}
			});
		}
	);

	grid.add_custom_button(
		frappe.utils.icon("unlock", "xs") + " " + __("Unreserve"),
		function () {
			let reserved = (frm.doc.material_mapping || []).filter(r => r.is_reserved);
			if (!reserved.length) {
				frappe.msgprint(__("No reserved rows to unreserve."));
				return;
			}
			let fields = [{ fieldtype: "Section Break", label: __("Select rows to unreserve") }];
			reserved.forEach(function (row, idx) {
				fields.push({
					fieldname: "row_" + idx,
					fieldtype: "Check",
					label: `${row.item_code} — Batch: ${row.batch || ""}`,
					default: 1,
				});
			});

			let d = new frappe.ui.Dialog({
				title: __("Unreserve Batches"),
				fields: fields,
				primary_action_label: __("Unreserve"),
				primary_action(values) {
					let targets = [];
					reserved.forEach(function (row, idx) {
						if (values["row_" + idx]) targets.push(row.name);
					});
					if (!targets.length) { frappe.msgprint(__("Select at least one row.")); return; }
					frappe.call({
						method: "manufyxinvenzaerp.production_management.doctype.material_planning.material_planning.unreserve_batches",
						args: { material_planning_name: frm.doc.name, row_names: JSON.stringify(targets) },
						freeze: true,
						freeze_message: __("Unreserving…"),
						callback(r) {
							d.hide();
							frm._grid_btns_added = false;
							frm.reload_doc();
							frappe.show_alert({ message: __("Batches unreserved."), indicator: "orange" }, 4);
						},
					});
				},
			});
			d.show();
		}
	);
}

// Column definitions for each table's View All popup
const _TABLE_VIEW_CONFIG = {
	raw_materials: {
		title: "Raw Materials",
		cols: [
			{ fieldname: "item_number",       label: "Item No" },
			{ fieldname: "sales_order",       label: "Sales Order" },
			{ fieldname: "item_code",         label: "Item Code" },
			{ fieldname: "item_name",         label: "Item Name" },
			{ fieldname: "bom_no",                    label: "Source BOM" },
			{ fieldname: "duno_mark_no",              label: "DUNO/Mark No" },
			{ fieldname: "customer_drawing_number",   label: "Cust Drawing Number" },
			{ fieldname: "parent_item_group",         label: "Item Group" },
			{ fieldname: "length",            label: "Length (mm)" },
			{ fieldname: "width",             label: "Width (mm)" },
			{ fieldname: "thickness",         label: "Thickness" },
			{ fieldname: "sec_qty",           label: "Sec Qty" },
			{ fieldname: "sec_uom",           label: "Sec UOM" },
			{ fieldname: "qty",               label: "Required Qty" },
			{ fieldname: "uom",               label: "UOM" },
			{ fieldname: "available_qty",     label: "Available Qty" },
			{ fieldname: "shortage_qty",      label: "Shortage Qty" },
			{ fieldname: "unit_weight",       label: "Unit Weight" },
			{ fieldname: "material_spec",     label: "Material Spec" },
			{ fieldname: "warehouse",         label: "Warehouse" },
			{ fieldname: "store_location",    label: "Store Location" },
		],
	},
	available_raw_materials: {
		title: "Available Raw Materials (Exact Match)",
		cols: [
			{ fieldname: "item_number",       label: "Item No" },
			{ fieldname: "sales_order",       label: "Sales Order" },
			{ fieldname: "item_code",         label: "Item Code" },
			{ fieldname: "item_name",         label: "Item Name" },
			{ fieldname: "batch_no",          label: "Batch No" },
			{ fieldname: "parent_item_group", label: "Item Group" },
			{ fieldname: "length",            label: "Length (mm)" },
			{ fieldname: "width",             label: "Width (mm)" },
			{ fieldname: "thickness",         label: "Thickness" },
			{ fieldname: "sec_qty",           label: "Sec Qty" },
			{ fieldname: "sec_uom",           label: "Sec UOM" },
			{ fieldname: "required_qty",      label: "Required Qty" },
			{ fieldname: "available_qty",     label: "Available Qty" },
			{ fieldname: "uom",               label: "UOM" },
			{ fieldname: "is_reserved",       label: "Reserved" },
			{ fieldname: "reserved_qty",      label: "Reserved Qty" },
			{ fieldname: "shortfall_qty",     label: "Shortfall Qty" },
			{ fieldname: "warehouse",         label: "Warehouse" },
		],
	},
	material_mapping: {
		title: "Material Mapping (Alternate Stock)",
		cols: [
			{ fieldname: "item_number",       label: "Item No" },
			{ fieldname: "sales_order",       label: "Sales Order" },
			{ fieldname: "item_code",         label: "Item Code" },
			{ fieldname: "item_name",         label: "Item Name" },
			{ fieldname: "qty",               label: "Req Qty" },
			{ fieldname: "uom",               label: "UOM" },
			{ fieldname: "parent_item_group", label: "Item Group" },
			{ fieldname: "length",            label: "Length (mm)" },
			{ fieldname: "width",             label: "Width (mm)" },
			{ fieldname: "thickness",         label: "Thickness" },
			{ fieldname: "sec_qty",           label: "Required Sec Qty" },
			{ fieldname: "batch",             label: "Batch" },
			{ fieldname: "batch_mapped",      label: "Status" },
			{ fieldname: "batch_length",      label: "Batch Length" },
			{ fieldname: "reserve_without_dimensions", label: "Reserve w/o Dimensions" },
			{ fieldname: "allocate_based_on_sec_qty",  label: "Allocate by Sec Nos" },
			{ fieldname: "batch_sec_qty",     label: "Batch Sec Qty" },
			{ fieldname: "batch_calc_qty",    label: "Calc Qty (Kg)" },
			{ fieldname: "is_reserved",       label: "Reserved" },
			{ fieldname: "reserved_qty",      label: "Reserved Qty" },
		],
	},
	unavailable_items: {
		title: "Unavailable Items (No Stock — Needs Purchase)",
		cols: [
			{ fieldname: "item_number",        label: "Item No" },
			{ fieldname: "sales_order",        label: "Sales Order" },
			{ fieldname: "item_code",          label: "Item Code" },
			{ fieldname: "item_name",          label: "Item Name" },
			{ fieldname: "qty",                label: "Required Qty" },
			{ fieldname: "uom",                label: "UOM" },
			{ fieldname: "parent_item_group",  label: "Item Group" },
			{ fieldname: "length",             label: "Length (mm)" },
			{ fieldname: "width",              label: "Width (mm)" },
			{ fieldname: "thickness",          label: "Thickness" },
			{ fieldname: "sec_qty",            label: "Sec Qty" },
			{ fieldname: "sec_uom",            label: "Sec UOM" },
			{ fieldname: "unit_weight",        label: "Unit Weight" },
			{ fieldname: "alternate_item",     label: "Alt Item" },
			{ fieldname: "alternate_quantity", label: "Alt Qty (Kg)" },
		],
	},
};

// Generic View All popup — read-only, all configured columns, scrollable
function _show_table_popup(frm, fieldname) {
	let cfg  = _TABLE_VIEW_CONFIG[fieldname];
	if (!cfg) return;
	let rows = frm.doc[fieldname] || [];
	if (!rows.length) {
		frappe.msgprint(__("No data to display."));
		return;
	}

	let th_style = "white-space:nowrap;padding:6px 10px;background:#f4f5f7;border-bottom:2px solid #d1d8dd;font-weight:600;font-size:11px;";
	let thead = "<tr>" + cfg.cols.map(c =>
		`<th style="${th_style}">${__(c.label)}</th>`
	).join("") + "</tr>";

	function _render_tbody(filtered_rows) {
		return filtered_rows.map(function (row, idx) {
			let cells = cfg.cols.map(function (c) {
				let val = row[c.fieldname];
				if (val === null || val === undefined) val = "";
				return `<td style="padding:5px 10px;white-space:nowrap;border-bottom:1px solid #f0f0f0;">${frappe.utils.escape_html(String(val))}</td>`;
			}).join("");
			let bg = idx % 2 !== 0 ? "background:#fafbfc;" : "";
			return `<tr style="${bg}">${cells}</tr>`;
		}).join("");
	}

	let filter_bar = `<div style="display:flex;gap:8px;margin-bottom:8px;align-items:center;">
		<input id="_vw_duno" type="text" placeholder="${__("Filter DUNO/Mark No…")}"
			style="border:1px solid #d1d8dd;border-radius:4px;padding:4px 8px;font-size:12px;width:180px;">
		<input id="_vw_cdn" type="text" placeholder="${__("Filter Cust Drawing Number…")}"
			style="border:1px solid #d1d8dd;border-radius:4px;padding:4px 8px;font-size:12px;width:200px;">
		<span id="_vw_count" style="font-size:12px;color:#6c757d;"></span>
	</div>`;

	let table_html = `<div style="overflow:auto;max-height:65vh;">
		<table style="font-size:12px;border-collapse:collapse;width:100%;" id="_vw_table">
			<thead style="position:sticky;top:0;z-index:1;">${thead}</thead>
			<tbody id="_vw_tbody">${_render_tbody(rows)}</tbody>
		</table>
	</div>`;

	let d = new frappe.ui.Dialog({
		title: __(cfg.title + " — {0} item(s)", [rows.length]),
		size: "extra-large",
	});
	d.$body.html(filter_bar + table_html);

	function _apply_filter() {
		let duno_q = (d.$body.find("#_vw_duno").val() || "").toLowerCase();
		let cdn_q  = (d.$body.find("#_vw_cdn").val() || "").toLowerCase();
		let filtered = rows.filter(function(r) {
			let duno_ok = !duno_q || String(r.duno_mark_no || "").toLowerCase().includes(duno_q);
			let cdn_ok  = !cdn_q  || String(r.customer_drawing_number || "").toLowerCase().includes(cdn_q);
			return duno_ok && cdn_ok;
		});
		d.$body.find("#_vw_tbody").html(_render_tbody(filtered));
		d.$body.find("#_vw_count").text(filtered.length + " / " + rows.length + " " + __("rows"));
	}
	d.$body.find("#_vw_duno, #_vw_cdn").on("input", _apply_filter);
	_apply_filter();
	d.show();
}

// ── Available Raw Material child table events ────────────────────────────────
frappe.ui.form.on("Material Planning Available Raw Material", {
	form_render(frm, cdt, cdn) {
		let row = locals[cdt][cdn];
		// Make skip checkbox read-only for reserved rows in the expanded row view
		let df = frappe.meta.get_docfield("Material Planning Available Raw Material", "skip_auto_suggest_batch", cdn);
		if (df) df.read_only = row.is_reserved ? 1 : 0;
		frm.fields_dict["available_raw_materials"].grid.refresh_row(cdn);
	},

	skip_auto_suggest_batch(frm, cdt, cdn) {
		let row = locals[cdt][cdn];
		if (row.is_reserved && row.skip_auto_suggest_batch) {
			frappe.model.set_value(cdt, cdn, "skip_auto_suggest_batch", 0);
			frappe.show_alert({
				message: __("Cannot skip a reserved batch. Unreserve it first."),
				indicator: "orange",
			}, 4);
		}
	},
});

// Reserve / Unreserve toolbar buttons on the Available Raw Materials (Exact Match) grid
function _add_exact_match_reservation_buttons(frm) {
	let grid = frm.fields_dict["available_raw_materials"] && frm.fields_dict["available_raw_materials"].grid;
	if (!grid) return;

	grid.add_custom_button(
		frappe.utils.icon("lock", "xs") + " " + __("Reserve"),
		function () {
			let has_unreserved = (frm.doc.available_raw_materials || []).some(r => !r.is_reserved);
			if (!has_unreserved) {
				frappe.msgprint(__("No un-reserved rows to reserve."));
				return;
			}
			frappe.confirm(__("Reserve all batches in Available Raw Materials (Exact Match)?"), function () {
				let do_reserve = function() {
					frappe.call({
						method: "manufyxinvenzaerp.production_management.doctype.material_planning.material_planning.reserve_exact_match_batches",
						args: { material_planning_name: frm.doc.name },
						freeze: true,
						freeze_message: __("Reserving batches…"),
						callback(r) {
							if (!r.message) return;
							frm._grid_btns_added = false;
							frm.reload_doc();
							let partial = r.message.partial || [];
							if (partial.length) {
								let partial_codes = new Set(partial.map(p => p.item_code));
								let already_in_mapping = (frm.doc.material_mapping || []).some(row => partial_codes.has(row.item_code));
								let note = already_in_mapping
									? `<div style="margin-top:10px;padding:8px 12px;background:#e8f4fd;border-left:4px solid #2490ef;border-radius:3px;font-size:12px;">
											<b>${__("Next step:")}</b> ${__("Shortfall rows are already in <b>Material Mapping (Alternate Stock)</b>. Assign a batch to each row to cover the gap, then reserve.")}
										</div>`
									: `<div style="margin-top:10px;padding:8px 12px;background:#fff8e1;border-left:4px solid #f9a825;border-radius:3px;font-size:12px;">
											<b>${__("Tip:")}</b> ${__("Re-run <b>Check Stock Availability</b> to automatically add shortfall rows to Material Mapping.")}
										</div>`;
								frappe.msgprint({
									title: __("Partial Reservation — Stock Shortfall"),
									indicator: "orange",
									message: _partial_reservation_html(partial) + note,
								});
							} else {
								frappe.show_alert({ message: __("Batches reserved."), indicator: "green" }, 4);
							}
						},
					});
				};
				if (frm.is_dirty()) {
					frm.save().then(do_reserve).catch(function() {
						frappe.msgprint(__("Save failed. Fix any errors before reserving."));
					});
				} else {
					do_reserve();
				}
			});
		}
	);

	grid.add_custom_button(
		frappe.utils.icon("unlock", "xs") + " " + __("Unreserve"),
		function () {
			let reserved = (frm.doc.available_raw_materials || []).filter(r => r.is_reserved);
			if (!reserved.length) {
				frappe.msgprint(__("No reserved rows to unreserve."));
				return;
			}
			let fields = [{ fieldtype: "Section Break", label: __("Select rows to unreserve") }];
			reserved.forEach(function (row, idx) {
				fields.push({
					fieldname: "row_" + idx,
					fieldtype: "Check",
					label: `${row.item_code} — Batch: ${row.batch_no || ""}`,
					default: 1,
				});
			});

			let d = new frappe.ui.Dialog({
				title: __("Unreserve Exact Match Batches"),
				fields: fields,
				primary_action_label: __("Unreserve"),
				primary_action(values) {
					let targets = [];
					reserved.forEach(function (row, idx) {
						if (values["row_" + idx]) targets.push(row.name);
					});
					if (!targets.length) { frappe.msgprint(__("Select at least one row.")); return; }
					frappe.call({
						method: "manufyxinvenzaerp.production_management.doctype.material_planning.material_planning.unreserve_exact_match_batches",
						args: { material_planning_name: frm.doc.name, row_names: JSON.stringify(targets) },
						freeze: true,
						freeze_message: __("Unreserving…"),
						callback(r) {
							d.hide();
							frm._grid_btns_added = false;
							frm.reload_doc();
							frappe.show_alert({ message: __("Batches unreserved."), indicator: "orange" }, 4);
						},
					});
				},
			});
			d.show();
		}
	);
}


// ── Auto Purchase (Manufyxinvenza Settings) ──────────────────────────────
frappe.ui.form.on("Material Planning", {
	custom_auto_purchase_btn(frm) {
		_run_auto_purchase(frm);
	},
});

function _run_auto_purchase(frm) {
	if (!frm.doc.custom_auto_purchase_supplier) {
		frappe.msgprint({ title: __("Supplier Required"), message: __("Please set the Supplier field before running Auto Purchase."), indicator: "orange" });
		return;
	}
	if (!frm.doc.for_warehouse) {
		frappe.msgprint({ title: __("Warehouse Required"), message: __("Please set the Raw Materials Warehouse before running Auto Purchase."), indicator: "orange" });
		return;
	}
	if (!(frm.doc.unavailable_items || []).length) {
		frappe.msgprint({ title: __("No Items"), message: __("No unavailable items to purchase."), indicator: "orange" });
		return;
	}
	frappe.confirm(
		__("This will automatically create and submit a Material Request, Purchase Order, and Purchase Receipt for ALL unavailable items. Continue?"),
		function() {
			if (frm.is_dirty()) {
				frappe.call({
					method: "frappe.client.save",
					args: { doc: frm.doc },
					freeze: true, freeze_message: __("Saving…"),
					callback(r) {
						if (r.message) { frappe.model.sync(r.message); frm.refresh(); }
						_do_auto_purchase(frm);
					},
				});
			} else {
				_do_auto_purchase(frm);
			}
		}
	);
}

function _do_auto_purchase(frm) {
	frappe.call({
		method: "manufyxinvenzaerp.production_management.doctype.material_planning.material_planning.auto_purchase_from_mp",
		args: { material_planning_name: frm.doc.name },
		freeze: true,
		freeze_message: __("Creating MR → PO → PR…"),
		callback(r) {
			if (r.message) {
				var m = r.message;
				frappe.msgprint({
					title: __("Auto Purchase Complete"),
					message:
						__("Material Request: ") + '<a href="/app/material-request/' + encodeURIComponent(m.mr) + '">' + m.mr + '</a><br>' +
						__("Purchase Order: ")   + '<a href="/app/purchase-order/'   + encodeURIComponent(m.po) + '">' + m.po + '</a><br>' +
						__("Purchase Receipt: ") + '<a href="/app/purchase-receipt/' + encodeURIComponent(m.pr) + '">' + m.pr + '</a>',
					indicator: "green",
				});
				frm._grid_btns_added = false;
				frm.reload_doc();
			}
		},
	});
}
