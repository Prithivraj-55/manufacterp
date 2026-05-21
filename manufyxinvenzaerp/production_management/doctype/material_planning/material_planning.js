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

frappe.ui.form.on("Material Planning", {

	refresh(frm) {
		// Always keep the Stock Analysis tab visible regardless of table data
		frm.set_df_property("tab_stock_analysis", "hidden", 0); // fieldname stays, label changed to "Stock Details"
		frm.set_df_property("section_raw_materials", "hidden", 0);
		frm.set_df_property("section_available_raw_materials", "hidden", 0);
		frm.set_df_property("section_material_mapping", "hidden", 0);
		frm.set_df_property("section_unavailable_items", "hidden", 0);

		// Filter batch dropdown to the item in that row
		frm.set_query("batch", "material_mapping", function(doc, cdt, cdn) {
			let row = locals[cdt][cdn];
			return { filters: { item: row.item_code }, description_field: "item" };
		});

		let has_raw = !!(frm.doc.raw_materials || []).length;
		let has_mapping = !!(frm.doc.material_mapping || []).length;
		let has_unavail = !!(frm.doc.unavailable_items || []).length;

		// Button visibility
		frm.set_df_property("get_raw_materials_btn",  "hidden", 0);
		frm.set_df_property("check_stock_btn",         "hidden", has_raw     ? 0 : 1);
		frm.set_df_property("update_exact_match_btn",  "hidden", has_unavail ? 0 : 1);
		frm.set_df_property("finalize_mapping_btn",    "hidden", has_mapping ? 0 : 1);

		// Add icons to inline form buttons (no color override)
		function _style_btn(fieldname, icon, label) {
			let $btn = frm.fields_dict[fieldname] && frm.fields_dict[fieldname].$input;
			if (!$btn || !$btn.length) return;
			$btn.html(frappe.utils.icon(icon, "sm") + "&nbsp;" + __(label));
		}
		setTimeout(function () {
			_style_btn("get_raw_materials_btn",  "refresh", "Get Raw Materials");
			_style_btn("check_stock_btn",        "search",  "Check Stock Availability");
			_style_btn("update_exact_match_btn", "tick",    "Update Exact Match");
			_style_btn("finalize_mapping_btn",   "move",    "Move to Unavailable Items");
		}, 50);

		// Disable add/delete rows on all auto-populated tables
		["raw_materials", "available_raw_materials", "material_mapping", "unavailable_items"].forEach(function (tbl) {
			let g = frm.fields_dict[tbl] && frm.fields_dict[tbl].grid;
			if (!g) return;
			g.cannot_add_rows = true;
			g.df.cannot_delete_rows = true;
			g.refresh();
		});

		// Grid toolbar buttons — guard against duplicates on re-render
		if (!frm._grid_btns_added) {
			frm._grid_btns_added = true;

			// Upload/Download on all four tables
			["raw_materials", "available_raw_materials", "material_mapping", "unavailable_items"].forEach(function (tbl) {
				_add_io_buttons(frm, tbl);
			});

			// Reserve / Unreserve on Material Mapping
			_add_reservation_buttons(frm);

			// Action buttons on Unavailable Items
			let $map_btn = frm.fields_dict["unavailable_items"].grid.add_custom_button(
				frappe.utils.icon("move", "xs") + " " + __("Add to Mapping"),
				function () {
					let all_items = frm.doc.unavailable_items || [];
					if (!all_items.length) {
						frappe.msgprint(__("No unavailable items to map."));
						return;
					}
					_show_add_to_mapping_dialog(frm, all_items);
				}
			);
			let $mr_btn = frm.fields_dict["unavailable_items"].grid.add_custom_button(
				frappe.utils.icon("buying", "xs") + " " + __("Create Material Request"),
				function () { _show_material_request_dialog(frm); }
			);
		}

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

					frm.set_df_property("finalize_mapping_btn",   "hidden", mapping  ? 0 : 1);
					frm.set_df_property("update_exact_match_btn", "hidden", unavail  ? 0 : 1);

					frappe.show_alert({
						message: __("Stock checked: {0} matched, {1} to map, {2} unavailable.", [avail, mapping, unavail]),
						indicator: "green",
					}, 6);
				},
			});
		};

		let has_work = (frm.doc.material_mapping || []).length || (frm.doc.unavailable_items || []).length;
		let has_reserved = (frm.doc.material_mapping || []).some(r => r.is_reserved);
		if (has_work) {
			let warn = has_reserved
				? __("Re-checking stock will clear all mapping work including RESERVED rows. Unreserve first if you want to keep them. Continue?")
				: __("Re-checking stock will clear all current mapping work. Continue?");
			frappe.confirm(warn, _run);
		} else {
			_run();
		}
	},

	finalize_mapping_btn(frm) {
		if (!(frm.doc.material_mapping || []).length) {
			frappe.msgprint(__("No items in Material Mapping to finalize."));
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
				});
				frm.refresh_field("material_mapping");

				// Merge newly-unmapped rows with any existing unavailable items
				let existing = (frm.doc.unavailable_items || []).filter(r => r.item_code);
				frm.clear_table("unavailable_items");
				existing.concat(result.unavailable_items || []).forEach(function(row) {
					let child = frm.add_child("unavailable_items");
					Object.keys(row).forEach(function(k) { if (k !== "name" && k !== "idx") child[k] = row[k]; });
				});
				frm.refresh_field("unavailable_items");

				let mapped  = (result.material_mapping || []).length;
				let unavail = (frm.doc.unavailable_items || []).length;

				frm.set_df_property("finalize_mapping_btn",   "hidden", mapped  ? 0 : 1);
				frm.set_df_property("update_exact_match_btn", "hidden", unavail ? 0 : 1);

				frappe.show_alert({
					message: __("{0} mapped, {1} moved to Unavailable Items.", [mapped, unavail]),
					indicator: "blue",
				}, 5);
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
		frappe.call({
			method: "manufyxinvenzaerp.production_management.doctype.material_planning.material_planning.move_to_exact_match",
			args: {
				doc: frm.doc,
				item_codes: JSON.stringify(all_items.map(r => r.item_code).filter(Boolean)),
			},
			freeze: true,
			freeze_message: __("Checking exact match…"),
			callback(r) {
				if (!r.message) return;
				let { matched, failed } = r.message;

				if (!matched.length) {
					frappe.msgprint(__("No exact dimension match found for: {0}", [failed.join(", ")]));
					return;
				}

				let matched_codes = new Set(matched.map(m => m.item_code));

				matched.forEach(function(row) {
					let child = frm.add_child("available_raw_materials");
					Object.keys(row).forEach(k => { if (k !== "name" && k !== "idx") child[k] = row[k]; });
				});
				frm.refresh_field("available_raw_materials");

				let remaining = (frm.doc.unavailable_items || []).filter(r => !matched_codes.has(r.item_code));
				frm.clear_table("unavailable_items");
				remaining.forEach(function(row) {
					let child = frm.add_child("unavailable_items");
					Object.keys(row).forEach(k => { if (k !== "name" && k !== "idx") child[k] = row[k]; });
				});
				frm.refresh_field("unavailable_items");

				frm.set_df_property("update_exact_match_btn", "hidden",
					!(frm.doc.unavailable_items || []).length ? 1 : 0
				);

				let msg = __("{0} item(s) moved to Exact Match.", [matched_codes.size]);
				if (failed.length) msg += " " + __("No match for: {0}.", [failed.join(", ")]);
				frappe.show_alert({ message: msg, indicator: "green" }, 6);
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
					frm.set_df_property("check_stock_btn", "hidden", 0);
					frappe.show_alert({
						message: __("{0} raw material row(s) loaded.", [r.message.length]),
						indicator: "green",
					}, 5);
				},
			});
		};

		if ((frm.doc.raw_materials || []).length) {
			frappe.confirm(
				__("This will replace the existing raw materials list. Continue?"),
				_fetch
			);
		} else {
			_fetch();
		}
	},
});

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
				frappe.model.set_value(cdt, cdn, "item_code",          d.item_code || "");
				frappe.model.set_value(cdt, cdn, "item_name",          d.item_name || "");
				frappe.model.set_value(cdt, cdn, "drawing",            d.drawing || "");
				frappe.model.set_value(cdt, cdn, "duno_mark_no",       d.duno_mark_no || 0);
				frappe.model.set_value(cdt, cdn, "sales_order",        d.sales_order || "");
				frappe.model.set_value(cdt, cdn, "customer",           d.customer || "");
				frappe.model.set_value(cdt, cdn, "qty_to_manufacture", d.qty_to_manufacture || 0);
				frappe.model.set_value(cdt, cdn, "uom",                d.uom || "");
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
			get_query: (function(item_code) {
				return function() { return { filters: { item: item_code } }; };
			})(row.item_code),
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
	// Save first so the server reads current unavailable_items state
	frm.save().then(function() { _build_material_request_dialog(frm, items); });
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
		fields.push({
			fieldname: "item_" + idx,
			fieldtype: "Check",
			label: `${row.item_code} — ${row.item_name || ""} | Qty: ${row.qty} ${row.uom || ""}`,
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

frappe.ui.form.on("Material Planning Unavailable Item", {
	alternate_item(frm, cdt, cdn) {
		let row = locals[cdt][cdn];
		if (!row.alternate_item) {
			// Hide all alternate dimension fields when cleared
			frappe.model.set_value(cdt, cdn, "alternate_length", 0);
			frappe.model.set_value(cdt, cdn, "alternate_width", 0);
			frappe.model.set_value(cdt, cdn, "alternate_thickness", 0);
			frappe.meta.get_docfield("Material Planning Unavailable Item", "alternate_length", frm.doc.name).hidden = 1;
			frappe.meta.get_docfield("Material Planning Unavailable Item", "alternate_width", frm.doc.name).hidden = 1;
			frappe.meta.get_docfield("Material Planning Unavailable Item", "alternate_thickness", frm.doc.name).hidden = 1;
			return;
		}
		// Read the 3 mandatory checkboxes from the alternate Item and show only relevant dimension fields
		frappe.db.get_value(
			"Item",
			row.alternate_item,
			["custom_mandatory_length", "custom_mandatory_width", "custom_mandatory_thickness"],
			function (d) {
				if (!d) return;
				let show_l = d.custom_mandatory_length  ? 1 : 0;
				let show_w = d.custom_mandatory_width   ? 1 : 0;
				let show_t = d.custom_mandatory_thickness ? 1 : 0;

				frappe.meta.get_docfield("Material Planning Unavailable Item", "alternate_length",    frm.doc.name).hidden = show_l ? 0 : 1;
				frappe.meta.get_docfield("Material Planning Unavailable Item", "alternate_width",     frm.doc.name).hidden = show_w ? 0 : 1;
				frappe.meta.get_docfield("Material Planning Unavailable Item", "alternate_thickness", frm.doc.name).hidden = show_t ? 0 : 1;
				frm.refresh_field("unavailable_items");
			}
		);
	},
});

// Table 3: batch field events on Material Mapping rows
frappe.ui.form.on("Material Planning Material Mapping", {
	batch(frm, cdt, cdn) {
		let row = locals[cdt][cdn];

		// Block batch change on reserved rows — revert to DB value and show error
		if (row.is_reserved) {
			frappe.msgprint(__("This row is reserved. Unreserve it before changing the batch."));
			// Fetch the committed batch value from DB and revert
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
			return;
		}
		frappe.call({
			method: "manufyxinvenzaerp.production_management.doctype.material_planning.material_planning.get_batch_item",
			args: { batch_no: row.batch },
			callback(r) {
				if (r.message) {
					frappe.model.set_value(cdt, cdn, "planned_item", r.message);
				}
			},
		});
	},
});

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
			frappe.confirm(__("Reserve all batches assigned in Material Mapping?"), function () {
				// Save any unsaved batch assignments first, then call reserve
				let do_reserve = function() {
					frappe.call({
						method: "manufyxinvenzaerp.production_management.doctype.material_planning.material_planning.reserve_batches",
						args: { material_planning_name: frm.doc.name },
						freeze: true,
						freeze_message: __("Reserving batches…"),
						callback(r) {
							if (!r.message) return;
							frm.reload_doc();
							let partial = r.message.partial || [];
							if (partial.length) {
								let lines = partial.map(function(p) {
									return `<tr>
										<td>${p.item_code}</td>
										<td>${p.batch}</td>
										<td>${p.required_qty} ${p.uom}</td>
										<td>${p.reserved_qty} ${p.uom}</td>
										<td style="color:red">${p.shortfall_qty} ${p.uom}</td>
									</tr>`;
								}).join("");
								frappe.msgprint({
									title: __("Partial Reservation — Stock Shortfall"),
									indicator: "orange",
									message: `<p>${__("Some batches had insufficient stock. Partial quantities were reserved:")}</p>
										<table class="table table-bordered table-condensed" style="font-size:12px">
											<thead><tr>
												<th>${__("Item")}</th><th>${__("Batch")}</th>
												<th>${__("Required")}</th><th>${__("Reserved")}</th>
												<th>${__("Shortfall")}</th>
											</tr></thead>
											<tbody>${lines}</tbody>
										</table>`,
								});
							} else {
								frappe.show_alert({ message: __("Batches reserved."), indicator: "green" }, 4);
							}
						},
					});
				};
				if (frm.is_dirty()) {
					frm.save().then(do_reserve).catch(do_reserve);
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
			// Show checklist of reserved rows
			let fields = [
				{
					fieldtype: "Section Break",
					label: __("Select rows to unreserve"),
				},
			];
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
					if (!targets.length) {
						frappe.msgprint(__("Select at least one row."));
						return;
					}
					frappe.call({
						method: "manufyxinvenzaerp.production_management.doctype.material_planning.material_planning.unreserve_batches",
						args: {
							material_planning_name: frm.doc.name,
							row_names: JSON.stringify(targets),
						},
						freeze: true,
						freeze_message: __("Unreserving…"),
						callback(r) {
							d.hide();
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
