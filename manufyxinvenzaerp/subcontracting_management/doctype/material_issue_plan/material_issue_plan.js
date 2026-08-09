frappe.ui.form.on("Material Issue Plan", {
	refresh(frm) {
		// Once auto-completed (stock received + every excess row resolved --
		// see _maybe_mark_completed in material_issue_plan.py), lock the whole
		// document: no more edits, and skip adding the transfer/return/final-SE
		// action buttons below. The matching whitelisted endpoints also refuse
		// directly (_ensure_mip_editable), so this is UI convenience on top of
		// a real server-side lock, not the only thing enforcing it.
		if (frm.doc.status === "Completed") {
			frm.disable_form();
			frappe.show_alert({
				message: __("This Material Issue Plan is Completed and locked for further changes."),
				indicator: "green",
			});
			return;
		}

		frm.set_query("subcontracting_order", () => ({
			filters: { custom_production_plan: frm.doc.production_plan || "" },
		}));
		frm.set_query("work_order", () => ({
			filters: { production_plan: frm.doc.production_plan || "" },
		}));
		// Scope every warehouse field to the document's own Company — previously
		// unfiltered, showing every warehouse across every company.
		["source_warehouse", "supplier_warehouse", "cnc_warehouse", "excess_return_warehouse"].forEach((fieldname) => {
			frm.set_query(fieldname, () => ({
				filters: { company: frm.doc.company || "" },
			}));
		});
		_add_view_all_raw_materials_button(frm);
		_add_update_batch_button(frm);
		_add_transfer_buttons(frm);
		_add_pdf_button(frm);
		_render_excess_action_btn(frm);
		_add_final_stock_entry_button(frm);
	},

	load_drawings_btn(frm) {
		_load_mip_drawings(frm);
	},

	refresh_raw_materials_btn(frm) {
		let rows = frm.doc.raw_materials || [];

		function do_refresh() {
			frappe.call({
				method: "manufyxinvenzaerp.subcontracting_management.doctype.material_issue_plan.material_issue_plan.refresh_mip_raw_materials_manual",
				args: { mip_name: frm.doc.name },
				freeze: true,
				freeze_message: __("Refreshing raw materials..."),
				callback() {
					frm.reload_doc();
				},
			});
		}

		function maybe_confirm_then_refresh() {
			// Nothing transferred, but rows already exist -- batch mapping, excess
			// material mapping, cut sheet, or excess return edits may already be on
			// them. Refreshing rebuilds the table from scratch, so confirm first.
			if (rows.length) {
				frappe.confirm(
					__("Batch mapping, Excess Material Mapping, or other changes may already be made on these rows. Refreshing will remove all current rows and rebuild them fresh. Are you sure you want to continue?"),
					do_refresh
				);
			} else {
				do_refresh();
			}
		}

		// Live check against submitted Stock Entries -- deliberately NOT based on
		// raw_materials.transferred_qty on the currently-loaded doc, which only
		// gets (re)computed by a refresh itself and so reads stale (still 0) right
		// after a transfer if nothing has refreshed this table since. Server enforces
		// the same check too (refresh_mip_raw_materials_manual); this pre-flight call
		// is what avoids showing the "are you sure?" confirm before that hard block.
		frappe.call({
			method: "manufyxinvenzaerp.subcontracting_management.doctype.material_issue_plan.material_issue_plan.check_mip_raw_materials_refreshable",
			args: { mip_name: frm.doc.name },
			callback(r) {
				if (r.message && r.message.blocked) {
					frappe.msgprint({
						title: __("Cannot Refresh"),
						indicator: "red",
						message: r.message.message,
					});
					return;
				}
				maybe_confirm_then_refresh();
			},
		});
	},
});

// "Load Drawings" — sits right under the Production Plan field. Saves first if
// needed (a new/dirty doc has nothing to populate_from_production_plan against
// until it has a name), then loads every drawing + raw material.
function _load_mip_drawings(frm) {
	if (!frm.doc.production_plan) {
		frappe.msgprint(__("Select a Production Plan first."));
		return;
	}
	function _load() {
		frappe.call({
			method: "manufyxinvenzaerp.subcontracting_management.doctype.material_issue_plan.material_issue_plan.populate_from_production_plan",
			args: { mip_name: frm.doc.name },
			freeze: true,
			freeze_message: __("Loading drawings from Production Plan..."),
			callback() { frm.reload_doc(); },
		});
	}
	if (frm.is_new() || frm.is_dirty()) {
		frm.save().then(_load);
	} else {
		_load();
	}
}

// "Make Final Stock Entry" — moved here from the Subcontracting Order (client
// change request). Once the linked SCO's operations are all complete, creates a
// draft Manufacture Stock Entry that consumes the supplier-warehouse raw material
// and produces the finished good; the stock-return workflow (Return Excess Entry)
// already lives on this doctype, so the finished-goods entry is created from the
// same place. custom_all_ops_complete lives on the Subcontracting Order, not the
// MIP, so it's read via a lookup rather than a stored/fetched field.
function _add_final_stock_entry_button(frm) {
	if (frm.is_new() || !frm.doc.subcontracting_order) return;

	frappe.db.get_value("Subcontracting Order", frm.doc.subcontracting_order, "custom_all_ops_complete")
		.then((r) => {
			if (!(r.message && r.message.custom_all_ops_complete)) return;

			frm.add_custom_button(__("Make Final Stock Entry"), function () {
				frappe.call({
					method: "manufyxinvenzaerp.subcontracting_management.subcontracting.create_finished_goods_entry",
					args: { sco_name: frm.doc.subcontracting_order },
					freeze: true,
					freeze_message: __("Creating Final Stock Entry…"),
					callback: function (r) {
						if (r.message) {
							let se_name = r.message.name;
							let already = r.message.already_existed;
							frappe.msgprint({
								title: already ? __("Final Stock Entry Already Exists") : __("Final Stock Entry Created"),
								message: (already
										? __("A draft Final Stock Entry already exists for this Subcontracting Order. ")
										: "")
									+ __("Review and submit the stock entry: ") +
									'<a href="/app/stock-entry/' + encodeURIComponent(se_name) + '">' + se_name + "</a>",
								indicator: already ? "orange" : "green"
							});
						}
					},
				});
			});
		});
}

// "View All" — raw_materials can run past 100 rows, well beyond the grid's
// default page size, and the grid also hides several columns (Planned Item/
// Alternate, Batch) at normal width. Show every row and column in one popup,
// mirroring the same pattern used on Material Planning/Sales Order.
function _add_view_all_raw_materials_button(frm) {
	let grid = frm.fields_dict["raw_materials"] && frm.fields_dict["raw_materials"].grid;
	if (!grid || frm.is_new()) return;

	grid.add_custom_button(
		frappe.utils.icon("eye", "xs") + " " + __("View All"),
		() => _show_mip_raw_materials_popup(frm)
	);
}

const _MIP_RAW_MATERIAL_COLS = [
	{ fieldname: "item_code",              label: "Item Code" },
	{ fieldname: "item_name",               label: "Item Name" },
	{ fieldname: "planned_item",             label: "Planned Item (Alternate)" },
	{ fieldname: "batch_no",                label: "Batch" },
	{ fieldname: "duno_mark_no",             label: "DUNO/Mark No" },
	{ fieldname: "customer_drawing_number",   label: "Cust Drawing Number" },
	{ fieldname: "sales_order",              label: "Sales Order" },
	{ fieldname: "material_planning",        label: "Material Planning" },
	{ fieldname: "parent_item_group",        label: "Item Group" },
	{ fieldname: "length",                  label: "Length (mm)" },
	{ fieldname: "width",                   label: "Width (mm)" },
	{ fieldname: "thickness",               label: "Thickness" },
	{ fieldname: "sec_qty",                 label: "Sec Qty" },
	{ fieldname: "qty",                     label: "Weight (Kg)" },
	{ fieldname: "transferred_qty",          label: "Transferred Qty" },
	{ fieldname: "is_reserved",              label: "Reserved" },
	{ fieldname: "is_unavailable",           label: "Unavailable" },
	{ fieldname: "cnc_process",             label: "CNC Process" },
];

function _show_mip_raw_materials_popup(frm) {
	let rows = frm.doc.raw_materials || [];
	if (!rows.length) {
		frappe.msgprint(__("No data to display."));
		return;
	}

	let th_style = "white-space:nowrap;padding:6px 10px;background:#f4f5f7;border-bottom:2px solid #d1d8dd;font-weight:600;font-size:11px;";
	let thead = "<tr>" + _MIP_RAW_MATERIAL_COLS.map(c =>
		`<th style="${th_style}">${__(c.label)}</th>`
	).join("") + "</tr>";

	function _render_tbody(filtered_rows) {
		return filtered_rows.map(function (row, idx) {
			let cells = _MIP_RAW_MATERIAL_COLS.map(function (c) {
				let val = row[c.fieldname];
				if (val === null || val === undefined) val = "";
				return `<td style="padding:5px 10px;white-space:nowrap;border-bottom:1px solid #f0f0f0;">${frappe.utils.escape_html(String(val))}</td>`;
			}).join("");
			let bg = idx % 2 !== 0 ? "background:#fafbfc;" : "";
			return `<tr style="${bg}">${cells}</tr>`;
		}).join("");
	}

	let filter_bar = `<div style="display:flex;gap:8px;margin-bottom:8px;align-items:center;">
		<input id="_mip_vw_duno" type="text" placeholder="${__("Filter DUNO/Mark No…")}"
			style="border:1px solid #d1d8dd;border-radius:4px;padding:4px 8px;font-size:12px;width:180px;">
		<input id="_mip_vw_item" type="text" placeholder="${__("Filter Item Code…")}"
			style="border:1px solid #d1d8dd;border-radius:4px;padding:4px 8px;font-size:12px;width:180px;">
		<span id="_mip_vw_count" style="font-size:12px;color:#6c757d;"></span>
	</div>`;

	let table_html = `<div style="overflow:auto;max-height:65vh;">
		<table style="font-size:12px;border-collapse:collapse;width:100%;" id="_mip_vw_table">
			<thead style="position:sticky;top:0;z-index:1;">${thead}</thead>
			<tbody id="_mip_vw_tbody">${_render_tbody(rows)}</tbody>
		</table>
	</div>`;

	let d = new frappe.ui.Dialog({
		title: __("Raw Materials — {0} item(s)", [rows.length]),
		size: "extra-large",
	});
	d.$body.html(filter_bar + table_html);

	function _apply_filter() {
		let duno_q = (d.$body.find("#_mip_vw_duno").val() || "").toLowerCase();
		let item_q = (d.$body.find("#_mip_vw_item").val() || "").toLowerCase();
		let filtered = rows.filter(function(r) {
			let duno_ok = !duno_q || String(r.duno_mark_no || "").toLowerCase().includes(duno_q);
			let item_ok = !item_q || String(r.item_code || "").toLowerCase().includes(item_q);
			return duno_ok && item_ok;
		});
		d.$body.find("#_mip_vw_tbody").html(_render_tbody(filtered));
		d.$body.find("#_mip_vw_count").text(__("{0} of {1} shown", [filtered.length, rows.length]));
	}
	d.$body.find("#_mip_vw_duno").on("input", _apply_filter);
	d.$body.find("#_mip_vw_item").on("input", _apply_filter);

	d.show();
}

// "Update Batch" — reassign the batch (and optionally dimensions/Sec Qty) already
// selected for a raw-material row. Delegates entirely to Material Planning's own
// reassign_batch, which unreserves, applies the new batch, re-validates mapping
// availability, and re-reserves — this dialog only picks which row and what to change.
function _add_update_batch_button(frm) {
	let grid = frm.fields_dict["raw_materials"] && frm.fields_dict["raw_materials"].grid;
	if (!grid || frm.is_new()) return;

	// "top" (.grid-custom-buttons) rather than the default "bottom"
	// (.grid-buttons, inside .grid-footer) — Frappe hides .grid-footer
	// entirely for a read-only grid once every row fits on one page, which
	// would silently hide this button too if it lived in the bottom toolbar.
	grid.add_custom_button(
		frappe.utils.icon("edit", "xs") + " " + __("Update Batch"),
		() => _show_update_batch_dialog(frm),
		"top"
	);
}

// Per-row "Update Batch" button (Button field on the child doctype) — opens the
// same dialog as the grid toolbar button, pre-filtered/pre-selected onto this row.
// excess_length/width/sec_qty changes get a live Excess Calc Qty preview here
// (client change request Phase 5.3) — the authoritative calc + excess_return_items
// sync happens server-side on save (validate() -> _sync_excess_return_from_raw_materials),
// this is just immediate feedback while the user is still typing.
// use_length/width/sec_qty and balance_length/width/sec_qty get the same kind
// of live W1/W2 Kg preview (client change request Phase 5.2) -- authoritative
// calc + the actual transferred-qty cap / post-submit batch resize both happen
// server-side (material_issue_plan.py's validate(), material_issue_plan_transfer.py,
// production_management/stock_entry.py).
frappe.ui.form.on("Material Issue Plan Raw Material", {
	update_batch_btn(frm, cdt, cdn) {
		_show_update_batch_dialog(frm, locals[cdt][cdn].name);
	},
	excess_length(frm, cdt, cdn) { _recalc_excess_calc_qty(cdt, cdn); },
	excess_width(frm, cdt, cdn) { _recalc_excess_calc_qty(cdt, cdn); },
	excess_sec_qty(frm, cdt, cdn) { _recalc_excess_calc_qty(cdt, cdn); },
	use_length(frm, cdt, cdn) { _recalc_cut_sheet_qty(cdt, cdn, "use"); },
	use_width(frm, cdt, cdn) { _recalc_cut_sheet_qty(cdt, cdn, "use"); },
	use_sec_qty(frm, cdt, cdn) { _recalc_cut_sheet_qty(cdt, cdn, "use"); },
	balance_length(frm, cdt, cdn) { _recalc_cut_sheet_qty(cdt, cdn, "balance"); },
	balance_width(frm, cdt, cdn) { _recalc_cut_sheet_qty(cdt, cdn, "balance"); },
	balance_sec_qty(frm, cdt, cdn) { _recalc_cut_sheet_qty(cdt, cdn, "balance"); },
});

function _recalc_excess_calc_qty(cdt, cdn) {
	let row = locals[cdt][cdn];
	let g = row.parent_item_group;
	let qty = null;
	if (g === "Structurals") {
		if (row.excess_length && row.unit_weight && row.excess_sec_qty) {
			qty = (row.excess_length / 1000) * row.unit_weight * row.excess_sec_qty;
		}
	} else if (g === "Plates") {
		if (row.excess_length && row.excess_width && row.thickness && row.unit_weight && row.excess_sec_qty) {
			qty = (row.excess_length / 1000) * (row.excess_width / 1000) * row.thickness * row.unit_weight * row.excess_sec_qty;
		}
	}
	frappe.model.set_value(cdt, cdn, "excess_calc_qty", qty !== null ? flt(qty, 3) : 0);
}

function _recalc_cut_sheet_qty(cdt, cdn, prefix) {
	let row = locals[cdt][cdn];
	let g = row.parent_item_group;
	let L = row[prefix + "_length"], W = row[prefix + "_width"], S = row[prefix + "_sec_qty"];
	let qty = null;
	if (g === "Structurals") {
		if (L && row.unit_weight && S) qty = (L / 1000) * row.unit_weight * S;
	} else if (g === "Plates") {
		if (L && W && row.thickness && row.unit_weight && S) {
			qty = (L / 1000) * (W / 1000) * row.thickness * row.unit_weight * S;
		}
	}
	frappe.model.set_value(cdt, cdn, prefix + "_calc_qty", qty !== null ? flt(qty, 3) : 0);
}

// ── Transfer readiness pre-flight check ──────────────────────────────────────

function _check_transfer_readiness(frm, on_proceed) {
	frappe.call({
		method: "manufyxinvenzaerp.subcontracting_management.material_issue_plan_transfer.get_mip_readiness_check",
		args: { mip_name: frm.doc.name },
		callback(r) {
			let d = r.message || {};
			if (!d.has_issues) {
				on_proceed();
				return;
			}

			// Build issue table
			function _rows(items, label, batch_col) {
				if (!items || !items.length) return "";
				let hdr = batch_col ? `<th>${__("Batch")}</th>` : "";
				let rows = items.map(function(it) {
					let bc = batch_col ? `<td>${it.batch || "-"}</td>` : "";
					return `<tr>
						<td>${it.material_planning}</td>
						<td>${it.table} / Row ${it.row}</td>
						<td>${it.item_code}</td>
						<td>${it.duno_mark_no || "-"}</td>
						${bc}
						<td>${it.qty} ${it.uom}</td>
					</tr>`;
				}).join("");
				return `<p style="margin:10px 0 4px;font-weight:bold">${label}</p>
					<table class="table table-bordered table-condensed" style="font-size:11px">
						<thead><tr>
							<th>${__("Material Planning")}</th>
							<th>${__("Table / Row")}</th>
							<th>${__("Item Code")}</th>
							<th>${__("DUNO/Mark No")}</th>
							${hdr}
							<th>${__("Qty")}</th>
						</tr></thead>
						<tbody>${rows}</tbody>
					</table>`;
			}

			let html = "";
			if (d.unmapped && d.unmapped.length) {
				html += _rows(d.unmapped, `⚠ ${__("Not Mapped / No Batch Assigned ({0} item(s)) — these will NOT be transferred", [d.unmapped.length])}`, false);
			}
			if (d.unreserved && d.unreserved.length) {
				html += _rows(d.unreserved, `⚠ ${__("Batch Assigned but NOT Reserved ({0} item(s)) — these will NOT be transferred", [d.unreserved.length])}`, true);
			}
			html += `<p style="margin-top:10px;color:#555">
				${__("Ensure stocks are purchased and mapped against Material Planning, or assign batches using the <b>Update Batch</b> option in the Material Issue Plan.")}
			</p>`;

			let dialog = new frappe.ui.Dialog({
				title: __("Transfer Readiness Check — Issues Found"),
				fields: [{ fieldtype: "HTML", fieldname: "body", options: html }],
				primary_action_label: __("Proceed Anyway"),
				primary_action() {
					dialog.hide();
					on_proceed();
				},
				secondary_action_label: __("Cancel"),
				secondary_action() { dialog.hide(); },
			});
			dialog.show();
		},
	});
}

// ── Batch Plan PDF ────────────────────────────────────────────────────────────
// Simple, printable reference for the production/supplier team: for this item,
// this batch (with its Sec Qty) is what's planned, per drawing. The preview
// popup and the downloaded PDF render from the exact same server-built HTML
// (get_mip_batch_plan_html), so what you see is exactly what you download.

function _add_pdf_button(frm) {
	if (frm.is_new()) return;
	frm.add_custom_button(frappe.utils.icon("filetype", "xs") + " " + __("PDF"), function() {
		_show_mip_batch_plan_popup(frm);
	});
}

function _show_mip_batch_plan_popup(frm) {
	frappe.call({
		method: "manufyxinvenzaerp.subcontracting_management.doctype.material_issue_plan.material_issue_plan.get_mip_batch_plan_html",
		args: { mip_name: frm.doc.name },
		freeze: true,
		freeze_message: __("Building batch plan…"),
		callback: function(r) {
			if (!r.message) return;

			var dlg = new frappe.ui.Dialog({
				title: __("Batch Plan — {0}", [frm.doc.name]),
				size: "extra-large",
				fields: [{ fieldtype: "HTML", fieldname: "content" }],
			});
			dlg.fields_dict.content.$wrapper.html(r.message);

			// "Download" in the dialog's top corner (next to the close icon) rather
			// than the usual bottom primary-action button, per how this was asked for.
			var $download = $(
				'<button class="btn btn-primary btn-sm" style="margin-right:8px">' + __("Download") + "</button>"
			);
			$download.on("click", function() {
				window.open(
					"/api/method/manufyxinvenzaerp.subcontracting_management.doctype.material_issue_plan.material_issue_plan.download_mip_batch_plan_pdf?mip_name="
					+ encodeURIComponent(frm.doc.name),
					"_blank"
				);
			});
			dlg.header.find(".modal-actions").prepend($download);

			dlg.show();
		},
	});
}

// ── Transfer / CNC buttons ───────────────────────────────────────────────────

function _add_transfer_buttons(frm) {
	if (frm.is_new() || !frm.doc.source_warehouse) return;
	if (!frm.doc.subcontracting_order && !frm.doc.work_order) return;

	frm.add_custom_button(__("All Pending Material"), function() {
		_check_transfer_readiness(frm, function() {
			// Check pending count before showing confirm — avoid confusing dialog when nothing is left
			frappe.call({
				method: "manufyxinvenzaerp.subcontracting_management.material_issue_plan_transfer.get_mip_pending_items",
				args: { mip_name: frm.doc.name },
				freeze: true,
				freeze_message: __("Checking pending items…"),
				callback(r) {
					let primary_pending = (r.message || []).filter(function(p) { return !p.cnc_process; });
					if (!primary_pending.length) {
						frappe.msgprint({
							title: __("Nothing to Transfer"),
							message: __("All reserved materials have already been transferred to the Supplier / WIP Warehouse."),
							indicator: "blue",
						});
						return;
					}
					frappe.confirm(
						__("Transfer {0} item(s) to the Supplier / WIP Warehouse. Continue?", [primary_pending.length]),
						function() {
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
						}
					);
				},
			});
		});
	}, __("Transfer"));

	frm.add_custom_button(__("Select Materials to Transfer"), function() {
		_check_transfer_readiness(frm, function() {
			frappe.call({
				method: "manufyxinvenzaerp.subcontracting_management.material_issue_plan_transfer.get_mip_pending_items",
				args: { mip_name: frm.doc.name },
				freeze: true,
				freeze_message: __("Loading pending materials…"),
				callback(r) { _show_mip_transfer_popup(frm, r.message || [], "primary"); },
			});
		});
	}, __("Transfer"));

	if (frm.doc.cnc_warehouse) {
		frm.add_custom_button(__("To CNC Warehouse"), function() {
			_check_transfer_readiness(frm, function() {
				frappe.call({
					method: "manufyxinvenzaerp.subcontracting_management.material_issue_plan_transfer.get_mip_pending_items",
					args: { mip_name: frm.doc.name },
					freeze: true,
					freeze_message: __("Loading pending materials…"),
					callback(r) { _show_mip_transfer_popup(frm, r.message || [], "cnc"); },
				});
			});
		}, __("Transfer"));

		frappe.call({
			method: "manufyxinvenzaerp.subcontracting_management.material_issue_plan_transfer.has_cnc_stock",
			args: { mip_name: frm.doc.name },
			callback(r) {
				if (r.message) {
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
			},
		});
	}
}

// Item Code filter only. DUNO/Mark No, Drawing, Sales Order and Customer Drawing No
// are deliberately NOT shown/filterable here: a row in this table is one reserved
// BATCH, and a single consolidated batch (bought once, allocated across many
// drawings' requirements -- see Consolidate Item / allocate_pr_stock_to_mp) can
// legitimately serve several DUNO/drawings at once, so no single value could be
// shown here without being misleading. A batch with no drawing tag at all (e.g. a
// purchase never traced back to one specific drawing) is still a perfectly valid
// row and is never excluded from this list on that basis.
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

	var item_code_options = Array.from(new Set(items.map((d) => d.item_code).filter(Boolean))).sort();

	// Searchable dropdown list — text input that opens a filtered option list on focus/type.
	// Returns { $el, getValue(), reset() }. Triggers a custom "mip:filter" event on $el
	// whenever the selected value changes (so callers bind a single event).
	function _make_search_list(options, placeholder) {
		var current_val = "";
		var uid = "mip_sl_" + Math.random().toString(36).slice(2);
		var $wrap = $('<div>').css({ position: "relative", marginBottom: "8px" });
		var $input = $('<input type="text" class="form-control form-control-sm" autocomplete="off">')
			.attr("placeholder", placeholder);
		var $drop = $('<div>').css({
			position: "absolute", top: "100%", left: 0, right: 0, zIndex: 9999,
			background: "#fff", border: "1px solid #d1d8dd", borderRadius: "4px",
			maxHeight: "200px", overflowY: "auto", display: "none",
			boxShadow: "0 4px 12px rgba(0,0,0,0.15)",
		});
		$wrap.append($input, $drop);

		function _render(q) {
			var filtered = q ? options.filter(function(o) { return o.toLowerCase().includes(q.toLowerCase()); }) : options;
			$drop.empty();
			var $all = $('<div>').css({ padding: "6px 10px", cursor: "pointer", fontSize: "12px",
				color: "#6c757d", borderBottom: "1px solid #f0f0f0" }).text(__("All"));
			$all.on("mouseenter", function() { $(this).css("background", "#f0f4f7"); })
				.on("mouseleave", function() { $(this).css("background", ""); })
				.on("mousedown", function(e) {
					e.preventDefault();
					current_val = ""; $input.val(""); $drop.hide(); $wrap.trigger("mip:filter");
				});
			$drop.append($all);
			filtered.forEach(function(opt) {
				var $opt = $('<div>').css({ padding: "6px 10px", cursor: "pointer", fontSize: "12px" }).text(opt);
				$opt.on("mouseenter", function() { $(this).css("background", "#f0f4f7"); })
					.on("mouseleave", function() { $(this).css("background", ""); })
					.on("mousedown", function(e) {
						e.preventDefault();
						current_val = opt; $input.val(opt); $drop.hide(); $wrap.trigger("mip:filter");
					});
				$drop.append($opt);
			});
			if (filtered.length || !q) $drop.show(); else $drop.hide();
		}

		$input.on("focus", function() { _render($input.val()); });
		$input.on("blur",  function() { $drop.hide(); });
		$input.on("input", function() { current_val = ""; _render($input.val()); $wrap.trigger("mip:filter"); });

		return {
			$el: $wrap,
			getValue() { return current_val || $input.val() || ""; },
			reset() { current_val = ""; $input.val(""); $drop.hide(); },
		};
	}

	var item_search = _make_search_list(item_code_options, __("Search item code…"));

	var $filter_row = $("<div>").append(
		$("<div class='row'>").append(
			$("<div class='col-sm-4'>").append(item_search.$el)
		)
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
		+ "<th class='text-right'>" + __("Sec Nos") + "</th>"
		+ "<th class='text-right'>" + __("Qty (Kg)") + "</th>"
		+ "</tr></thead><tbody></tbody></table>");

	var $tbody = $table.find("tbody");
	items.forEach(function(d, idx) {
		$tbody.append(
			"<tr data-idx='" + idx + "' data-item='" + frappe.utils.escape_html(d.item_code || "") + "'>" +
			"<td class='text-center'><input type='checkbox' class='mip-item-chk' checked></td>" +
			"<td>" + frappe.utils.escape_html(d.item_code) + "</td>" +
			"<td>" + frappe.utils.escape_html(d.batch_no || "") + "</td>" +
			"<td class='text-right'>" + format_number(flt(d.custom_sec_qty), null, 3)
				+ (d.custom_sec_uom ? " " + frappe.utils.escape_html(d.custom_sec_uom) : "") + "</td>" +
			"<td class='text-right'>" + format_number(flt(d.qty), null, 3) + "</td>" +
			"</tr>"
		);
	});

	function _apply_filters() {
		var item_q = item_search.getValue().toLowerCase();
		$tbody.find("tr").each(function() {
			var $row = $(this);
			var matches = !item_q || $row.data("item").toLowerCase().includes(item_q);
			$row.toggle(matches);
		});
	}
	item_search.$el.on("mip:filter", _apply_filters);
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
		_show_return_excess_dialog(frm);
	});
}

// "Return Excess Entry" -- review/edit the planned Qty and record a mandatory
// Reason for every row before the actual Material Receipt Stock Entry is
// created (client change request Phase 5.6). Structurals/Plates rows edit
// Length/Width/Sec Qty (Qty is always DERIVED for these groups -- Stock
// Entry's own validate_stock_entry hook recalculates Qty from dimensions on
// Material Receipt, so a directly-typed Qty would be silently discarded);
// every other group (e.g. Nuts and Bolts) edits Qty directly, matching how
// this same row already behaves everywhere else in this app (_mip_excess_calc
// below). Qty/dimensions + Reason entered here are saved back onto the
// excess_return_items row itself server-side, so re-opening this dialog
// later (or the grid) shows whatever was last entered.
function _show_return_excess_dialog(frm) {
	let rows = (frm.doc.excess_return_items || []).filter((r) => !r.stock_entry_created && flt(r.qty) > 0);
	if (!rows.length) {
		frappe.msgprint(__("No pending excess return rows to process. All rows already have a Stock Entry created, or no rows with Weight (Kg) > 0 exist."));
		return;
	}

	function _is_dim_driven(g) { return g === "Structurals" || g === "Plates"; }

	let rows_html = rows.map(function(r) {
		let g = r.parent_item_group;
		let dims_html;
		if (_is_dim_driven(g)) {
			dims_html = `<input type="number" step="any" class="form-control form-control-sm _rex_length" placeholder="${__("Length (mm)")}" value="${flt(r.length)}" style="margin-bottom:4px;">`
				+ (g === "Plates" ? `<input type="number" step="any" class="form-control form-control-sm _rex_width" placeholder="${__("Width (mm)")}" value="${flt(r.width)}" style="margin-bottom:4px;">` : "")
				+ `<input type="number" step="any" class="form-control form-control-sm _rex_sec_qty" placeholder="${__("Sec Qty")}" value="${flt(r.sec_qty)}">`;
		} else {
			dims_html = `<span style="color:#adb5bd;font-size:11px;">${__("n/a")}</span>`;
		}
		let qty_html = _is_dim_driven(g)
			? `<span class="_rex_qty_preview">${format_number(flt(r.qty), null, 3)}</span>`
			: `<input type="number" step="any" class="form-control form-control-sm _rex_qty" value="${flt(r.qty)}">`;
		return `<tr data-name="${frappe.utils.escape_html(r.name)}" data-group="${frappe.utils.escape_html(g || "")}"
			data-thickness="${flt(r.thickness)}" data-unit-weight="${flt(r.unit_weight)}">
			<td style="padding:6px 8px;vertical-align:top;">${frappe.utils.escape_html(r.item_code || "")}</td>
			<td style="padding:6px 8px;">${dims_html}</td>
			<td style="padding:6px 8px;vertical-align:top;text-align:right;">${qty_html}</td>
			<td style="padding:6px 8px;">
				<input type="text" class="form-control form-control-sm _rex_reason" placeholder="${__("Reason (required)…")}" value="${frappe.utils.escape_html(r.return_reason || "")}">
			</td>
		</tr>`;
	}).join("");

	let table_html = `<table class="table table-bordered table-condensed" style="margin-bottom:0;">
		<thead><tr>
			<th style="padding:6px 8px;">${__("Item Code")}</th>
			<th style="padding:6px 8px;width:170px;">${__("Length / Width / Sec Qty")}</th>
			<th style="padding:6px 8px;width:100px;">${__("Qty (Kg)")}</th>
			<th style="padding:6px 8px;">${__("Return Reason")}</th>
		</tr></thead>
		<tbody>${rows_html}</tbody>
	</table>`;

	let dialog = new frappe.ui.Dialog({
		title: __("Return Excess Entry — Review Qty & Reason"),
		size: "extra-large",
		fields: [{ fieldtype: "HTML", fieldname: "rows_html", options: table_html }],
		primary_action_label: __("Create Return Entry"),
		primary_action() {
			let payload = [];
			let missing_reason = false;
			dialog.$wrapper.find("tbody tr").each(function() {
				let $tr = $(this);
				let reason = ($tr.find("._rex_reason").val() || "").trim();
				let g = $tr.data("group");
				let entry = { name: $tr.data("name"), return_reason: reason };
				if (_is_dim_driven(g)) {
					entry.length = flt($tr.find("._rex_length").val());
					if (g === "Plates") entry.width = flt($tr.find("._rex_width").val());
					entry.sec_qty = flt($tr.find("._rex_sec_qty").val());
				} else {
					entry.qty = flt($tr.find("._rex_qty").val());
				}
				if (!reason) missing_reason = true;
				payload.push(entry);
			});
			if (missing_reason) {
				frappe.msgprint({
					title: __("Reason Required"),
					message: __("Please enter a Return Reason for every row before continuing."),
					indicator: "orange",
				});
				return;
			}
			frappe.confirm(
				__("This material will be received into the Finished Goods Warehouse ({0}). Continue?", [frappe.utils.escape_html(frm.doc.excess_return_warehouse)]),
				function () {
					dialog.hide();
					frappe.call({
						method: "manufyxinvenzaerp.subcontracting_management.material_issue_plan_transfer.create_mip_excess_return_entry",
						args: { mip_name: frm.doc.name, rows_json: JSON.stringify(payload) },
						freeze: true,
						freeze_message: __("Creating return entry…"),
						callback(r) {
							if (r.message) {
								frappe.msgprint({ title: __("Return Excess Entry Created"), message: __("Return Stock Entry: ") + '<a href="/app/stock-entry/' + encodeURIComponent(r.message) + '">' + r.message + "</a>", indicator: "green" });
								frm.reload_doc();
							}
						},
					});
				}
			);
		},
	});

	// Live Qty preview as the user edits Length/Width/Sec Qty on a dimension-driven row.
	dialog.$wrapper.find("tbody tr").each(function() {
		let $tr = $(this);
		let g = $tr.data("group");
		if (!_is_dim_driven(g)) return;
		function _refresh() {
			let L = flt($tr.find("._rex_length").val());
			let W = flt($tr.find("._rex_width").val());
			let S = flt($tr.find("._rex_sec_qty").val());
			let uw = flt($tr.data("unit-weight"));
			let T = flt($tr.data("thickness"));
			let qty = null;
			if (g === "Structurals" && L && uw && S) qty = (L / 1000) * uw * S;
			else if (g === "Plates" && L && W && T && uw && S) qty = (L / 1000) * (W / 1000) * T * uw * S;
			$tr.find("._rex_qty_preview").text(qty !== null ? format_number(flt(qty, 3), null, 3) : "—");
		}
		$tr.find("._rex_length, ._rex_width, ._rex_sec_qty").on("input", _refresh);
	});

	dialog.show();
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

// Rows matching the free-text Customer Drawing No / DUNO-Mark No / Sales Order
// filters (AND semantics, substring match; a blank filter matches everything) —
// same filter semantics as Production Plan's drawing picker (public/js/production_plan.js).
function _mip_row_matches_filters(r, f) {
	return (!f.cdn || String(r.customer_drawing_number || "").toLowerCase().includes(f.cdn))
		&& (!f.duno || String(r.duno_mark_no || "").toLowerCase().includes(f.duno))
		&& (!f.so || String(r.sales_order || "").toLowerCase().includes(f.so));
}

// Batch/purchase-reference cell — reservable rows show their batch (or "no batch"),
// unavailable/purchased rows show a link to the Purchase Receipt that fulfilled them.
function _mip_batch_cell_html(r) {
	if (r.batch_no) return frappe.utils.escape_html(r.batch_no);
	if (r.purchase_receipt) {
		return __("Purchased via {0}", [
			`<a href="/app/purchase-receipt/${encodeURIComponent(r.purchase_receipt)}" target="_blank">`
			+ `${frappe.utils.escape_html(r.purchase_receipt)}</a>`,
		]);
	}
	return r.is_unavailable
		? `<span style="color:#adb5bd;">${__("Pending Purchase")}</span>`
		: `<span style="color:#adb5bd;">${__("no batch")}</span>`;
}

// Builds the filter bar + results table ONCE into the dialog's "picker_html" field
// and returns a controller so the caller can update the highlighted row (on every
// click) and pre-fill filters (on preselect) without tearing down and rebuilding the
// filter inputs each time — rebuilding on every click would otherwise wipe out
// whatever the user had already typed into the filter boxes.
// Reservable rows (Material Mapping / Available Raw Material) are clickable and
// call `on_select`; Unavailable Item rows are shown dimmed for context only —
// they can't be reallocated here (must go through Material Request/Purchase).
function _mip_build_picker(dialog, all_rows, on_select) {
	let $wrap = dialog.fields_dict.picker_html.$wrapper;
	let selected_row_name = null;

	let filter_bar = `
		<div style="display:flex;gap:8px;flex-wrap:wrap;align-items:flex-end;margin-bottom:10px;padding:8px 10px;background:#f8f9fa;border:1px solid #e9ecef;border-radius:4px;">
			<div style="display:flex;flex-direction:column;gap:3px;flex:1;min-width:140px;">
				<label style="font-size:10px;font-weight:600;color:#6c757d;margin:0;">${__("Customer Drawing No")}</label>
				<input id="_mip_ub_cdn" type="text" placeholder="${__("Filter…")}"
					style="border:1px solid #d1d8dd;border-radius:4px;padding:4px 8px;font-size:12px;width:100%;">
			</div>
			<div style="display:flex;flex-direction:column;gap:3px;min-width:100px;">
				<label style="font-size:10px;font-weight:600;color:#6c757d;margin:0;">${__("DUNO / Mark No")}</label>
				<input id="_mip_ub_duno" type="text" placeholder="${__("Filter…")}"
					style="border:1px solid #d1d8dd;border-radius:4px;padding:4px 8px;font-size:12px;width:100%;">
			</div>
			<div style="display:flex;flex-direction:column;gap:3px;min-width:120px;">
				<label style="font-size:10px;font-weight:600;color:#6c757d;margin:0;">${__("Sales Order")}</label>
				<input id="_mip_ub_so" type="text" placeholder="${__("Filter…")}"
					style="border:1px solid #d1d8dd;border-radius:4px;padding:4px 8px;font-size:12px;width:100%;">
			</div>
			<div style="display:flex;flex-direction:column;gap:3px;align-items:flex-start;justify-content:flex-end;padding-bottom:1px;">
				<label style="font-size:10px;font-weight:600;color:#6c757d;margin:0;">&nbsp;</label>
				<div style="display:flex;gap:6px;align-items:center;flex-wrap:wrap;">
					<button class="btn btn-xs" id="_mip_ub_clear"
						style="background:#c62828;color:#fff;border-color:#c62828;">${__("Clear Filters")}</button>
					<span id="_mip_ub_count" style="font-size:12px;color:#6c757d;white-space:nowrap;"></span>
				</div>
			</div>
		</div>`;

	let th_style = "white-space:nowrap;padding:6px 10px;background:#f4f5f7;border-bottom:2px solid #d1d8dd;font-weight:600;font-size:11px;";
	let cols = [
		["item_code", __("Item Code")],
		["duno_mark_no", __("DUNO/Mark No")],
		["customer_drawing_number", __("Cust Drawing No")],
		["sales_order", __("Sales Order")],
		["_batch", __("Batch / Purchase Ref")],
		["sec_qty", __("Sec Qty")],
		["reqd_kg", __("Reqd Kg")],
		["qty", __("Qty (Kg)")],
	];
	let thead = "<tr>" + cols.map((c) => `<th style="${th_style}">${c[1]}</th>`).join("") + "</tr>";

	let table_html = `<div style="overflow-x:auto;">
		<table style="font-size:12px;border-collapse:collapse;width:100%;min-width:700px;">
			<thead style="position:sticky;top:0;z-index:1;">${thead}</thead>
			<tbody id="_mip_ub_tbody"></tbody>
		</table>
	</div>`;

	$wrap.html(filter_bar + `<div style="max-height:32vh;overflow-y:auto;border:1px solid #e9ecef;border-radius:4px;">${table_html}</div>`);

	function _render_rows(rows) {
		let $tbody = $wrap.find("#_mip_ub_tbody");
		$tbody.html(rows.map((r) => {
			let reservable = r.source_table !== "Material Planning Unavailable Item";
			let is_selected = r.name === selected_row_name;
			let row_style = reservable
				? `cursor:pointer;${is_selected ? "background:#e3f2fd;" : ""}`
				: "cursor:not-allowed;color:#adb5bd;background:#fafbfc;";
			let cells = [
				frappe.utils.escape_html(r.item_code || ""),
				frappe.utils.escape_html(r.duno_mark_no || ""),
				frappe.utils.escape_html(r.customer_drawing_number || ""),
				frappe.utils.escape_html(r.sales_order || ""),
				_mip_batch_cell_html(r),
				format_number(flt(r.sec_qty), null, 3),
				format_number(flt(r.reqd_kg), null, 3),
				format_number(flt(r.qty), null, 3),
			];
			return `<tr data-name="${frappe.utils.escape_html(r.name)}" data-reservable="${reservable ? 1 : 0}" style="${row_style}">`
				+ cells.map((c) => `<td style="padding:5px 10px;white-space:nowrap;border-bottom:1px solid #f0f0f0;">${c}</td>`).join("")
				+ "</tr>";
		}).join(""));
		$wrap.find("#_mip_ub_count").text(__("{0} shown", [rows.length]));

		$tbody.find("tr[data-reservable='1']").on("click", function() {
			let row = all_rows.find((r) => r.name === $(this).data("name"));
			if (row) on_select(row);
		});
	}

	function _get_filters() {
		return {
			cdn: (($wrap.find("#_mip_ub_cdn").val()) || "").toLowerCase().trim(),
			duno: (($wrap.find("#_mip_ub_duno").val()) || "").toLowerCase().trim(),
			so: (($wrap.find("#_mip_ub_so").val()) || "").toLowerCase().trim(),
		};
	}

	function _apply_filter() {
		let f = _get_filters();
		_render_rows(all_rows.filter((r) => _mip_row_matches_filters(r, f)));
	}

	$wrap.find("#_mip_ub_cdn, #_mip_ub_duno, #_mip_ub_so").on("input", _apply_filter);
	$wrap.find("#_mip_ub_clear").on("click", function() {
		$wrap.find("#_mip_ub_cdn, #_mip_ub_duno, #_mip_ub_so").val("");
		_apply_filter();
	});

	_render_rows(all_rows);

	return {
		// Highlight `row_name` as selected and re-render with whatever filters are
		// currently typed (does NOT reset the filter inputs).
		markSelected(row_name) {
			selected_row_name = row_name;
			_apply_filter();
		},
		// Pre-fill the filter inputs (used when opening via the per-row grid button)
		// and apply them immediately.
		setFilters(cdn, duno, so) {
			$wrap.find("#_mip_ub_cdn").val(cdn || "");
			$wrap.find("#_mip_ub_duno").val(duno || "");
			$wrap.find("#_mip_ub_so").val(so || "");
			_apply_filter();
		},
	};
}

const _MIP_ALLOC_FIELDS = [
	"current_batch", "current_sec_qty", "current_qty",
	"new_batch_no", "length", "width", "thickness", "sec_qty", "calculated_qty",
	"reserve_without_dimensions", "allocate_based_on_sec_qty",
];
const _MIP_NEW_ALLOC_FIELDS = [
	"new_batch_no", "length", "width", "thickness", "sec_qty", "calculated_qty",
	"reserve_without_dimensions", "allocate_based_on_sec_qty",
];

// "Update Batch" dialog — search/filter across every raw material row (reservable and
// purchased/unavailable, for context), pick one reservable row, review its current
// allocation (read-only) alongside an editable new-allocation panel, then reassign.
// `preselect_row_name` (optional) is the raw_materials row to open straight onto,
// used by the per-row grid button; the toolbar button opens it with nothing selected.
function _show_update_batch_dialog(frm, preselect_row_name) {
	let all_rows = frm.doc.raw_materials || [];
	if (!all_rows.length) {
		frappe.msgprint(__("No raw materials found. Use \"Refresh Raw Materials\" first."));
		return;
	}

	let selected_row = null;

	let dialog = new frappe.ui.Dialog({
		title: __("Update Batch"),
		size: "extra-large",
		fields: [
			{ fieldtype: "HTML", fieldname: "picker_html" },
			{ fieldtype: "HTML", fieldname: "no_selection_html" },
			{ fieldtype: "Section Break", label: __("Current Allocation") },
			{ fieldname: "current_batch", fieldtype: "Data", label: __("Current Batch / Purchase Ref"), read_only: 1 },
			{ fieldname: "current_sec_qty", fieldtype: "Float", label: __("Current Sec Qty (Nos)"), read_only: 1 },
			{ fieldtype: "Column Break" },
			{ fieldname: "current_qty", fieldtype: "Float", label: __("Current Qty (Kg)"), read_only: 1 },
			{ fieldname: "reqd_kg", fieldtype: "Float", label: __("Reqd Kg"), read_only: 1,
				description: __("The drawing's own planned/required weight -- fixed, does not change no matter which batch/Sec Qty is picked below.") },
			{ fieldtype: "HTML", fieldname: "transferred_notice_html" },
			{ fieldtype: "Section Break", label: __("New Allocation"), fieldname: "new_alloc_section" },
			{ fieldname: "new_batch_no", fieldtype: "Link", options: "Batch", label: __("New Batch"), reqd: 1,
				description: __("Length/Width/Thickness are fetched from the batch automatically.") },
			{ fieldname: "length", fieldtype: "Float", label: __("Length (mm)"), read_only: 1 },
			{ fieldtype: "Column Break" },
			{ fieldname: "width", fieldtype: "Float", label: __("Width (mm)"), read_only: 1 },
			{ fieldname: "thickness", fieldtype: "Float", label: __("Thickness (mm)"), read_only: 1 },
			{ fieldname: "sec_qty", fieldtype: "Float", label: __("Sec Qty (Nos)") },
			{ fieldname: "calculated_qty", fieldtype: "Float", label: __("Calculated Qty (Kg)"), read_only: 1 },
			{ fieldname: "reserve_without_dimensions", fieldtype: "Check", label: __("Reserve Without Dimensions") },
			{ fieldname: "allocate_based_on_sec_qty", fieldtype: "Check", label: __("Allocate based on Sec Nos"), default: "1" },
		],
		primary_action_label: __("Reassign Batch"),
		primary_action(values) {
			if (!selected_row) {
				frappe.msgprint(__("Select a raw material row first."));
				return;
			}
			if (flt(selected_row.transferred_qty) > 0) {
				frappe.msgprint(__("This batch has already been transferred. Reassignment is not allowed."));
				return;
			}
			if (!values.new_batch_no) {
				frappe.msgprint(__("Select a New Batch."));
				return;
			}
			// Material Mapping: length/width/thickness are the row's REQUIRED (demand)
			// dimensions, a separate concept from the batch's own physical dimensions —
			// reassign_batch already fetches the batch's dims from the Batch record
			// directly for that table, so leave required dims untouched here.
			// Available Raw Material: there's no such split — length/width/thickness
			// there ARE the assigned batch's own dimensions, so send what we fetched.
			let dimensions = selected_row.source_table === "Material Planning Material Mapping"
				? {}
				: { length: values.length, width: values.width, thickness: values.thickness };
			frappe.call({
				method: "manufyxinvenzaerp.production_management.doctype.material_planning.material_planning.reassign_batch",
				args: {
					material_planning_name: selected_row.material_planning,
					source_table: selected_row.source_table,
					row_name: selected_row.source_row,
					new_batch_no: values.new_batch_no,
					dimensions: JSON.stringify(dimensions),
					sec_qty: values.sec_qty,
					reserve_without_dimensions: values.reserve_without_dimensions ? 1 : 0,
					allocate_based_on_sec_qty: values.allocate_based_on_sec_qty ? 1 : 0,
					material_issue_plan: frm.doc.name,
				},
				freeze: true,
				freeze_message: __("Reassigning batch..."),
				callback(r) {
					// Dialog stays open — the user reassigns several rows in one sitting;
					// they close it themselves (X / click-outside) when done.
					let warnings = (r.message && r.message.warnings) || [];
					if (warnings.length) {
						frappe.msgprint({
							title: __("Reallocation Warnings"),
							indicator: "orange",
							message: warnings.map((w) =>
								w.reason || `${w.item_code} (${w.batch}): ${__("short by")} ${w.shortfall_qty}`
							).join("<br>"),
						});
					}
					// refresh_mip_raw_materials rebuilds the raw_materials snapshot from
					// scratch, so every row gets a brand-new `.name` — re-locate the row via
					// its stable source_table/source_row reference (the underlying Material
					// Planning child row), not the MIP snapshot's own transient name.
					let reassigned_source_table = selected_row.source_table;
					let reassigned_source_row = selected_row.source_row;
					frappe.call({
						method: "manufyxinvenzaerp.subcontracting_management.doctype.material_issue_plan.material_issue_plan.refresh_mip_raw_materials",
						args: { mip_name: frm.doc.name },
						freeze: true,
						freeze_message: __("Refreshing raw materials..."),
						callback() {
							frm.reload_doc().then(() => {
								// Mutate all_rows IN PLACE — _mip_build_picker/_select_row above
								// already closed over this same array, so this refreshes both
								// the picker table and this dialog's row lookups without
								// needing to rebuild the picker or reopen the dialog.
								all_rows.splice(0, all_rows.length, ...(frm.doc.raw_materials || []));
								let updated_row = all_rows.find((r) =>
									r.source_table === reassigned_source_table && r.source_row === reassigned_source_row
								);
								if (updated_row) {
									// Re-selecting shows the just-updated Current Allocation and
									// resets New Allocation inputs, ready for the next row.
									_select_row(updated_row);
								} else {
									picker.markSelected(null);
								}
							});
						},
					});
				},
			});
		},
	});

	dialog.fields_dict.no_selection_html.$wrapper.html(
		`<div style="color:#8d99a6;padding:8px 4px;font-size:12px;">`
		+ __("Select a reservable row above to review its current allocation and reassign a new batch.")
		+ `</div>`
	);
	dialog.fields_dict.transferred_notice_html.$wrapper.html("");

	function _toggle_allocation_fields(show, is_transferred) {
		_MIP_ALLOC_FIELDS.forEach((f) => dialog.fields_dict[f].toggle(show));
		dialog.fields_dict.no_selection_html.toggle(!show);
		// Hide "New Allocation" section and its fields if already transferred
		let block_edit = show && is_transferred;
		_MIP_NEW_ALLOC_FIELDS.forEach((f) => dialog.fields_dict[f].toggle(!block_edit));
		dialog.fields_dict.new_alloc_section && dialog.fields_dict.new_alloc_section.toggle && dialog.fields_dict.new_alloc_section.toggle(!block_edit);
		dialog.fields_dict.transferred_notice_html.toggle(block_edit);
		if (block_edit) {
			dialog.fields_dict.transferred_notice_html.$wrapper.html(
				`<div style="background:#fff3cd;border:1px solid #ffc107;border-radius:4px;padding:10px 14px;margin:8px 0;color:#856404;">`
				+ `<b>${__("Already Transferred")}</b> — `
				+ __("This batch has been transferred to the Supplier / WIP Warehouse. Batch reassignment is not allowed after transfer.")
				+ `</div>`
			);
		} else {
			dialog.fields_dict.transferred_notice_html.$wrapper.html("");
		}
		// Show/hide the Reassign Batch button accordingly
		if (dialog.get_primary_btn) {
			dialog.get_primary_btn().toggle(!block_edit);
		}
	}

	// Length/Width/Thickness always come from the Batch record itself (custom_length/
	// custom_width/custom_thickness) — same as Material Planning's own Material Mapping
	// grid — never typed in by hand.
	function _fetch_batch_dims(batch_no) {
		if (!batch_no) {
			dialog.set_value("length", 0);
			dialog.set_value("width", 0);
			dialog.set_value("thickness", 0);
			dialog.set_value("calculated_qty", 0);
			return;
		}
		frappe.db.get_value("Batch", batch_no, ["custom_length", "custom_width", "custom_thickness"]).then((r) => {
			let d = r.message || {};
			dialog.set_value("length", flt(d.custom_length));
			dialog.set_value("width", flt(d.custom_width));
			dialog.set_value("thickness", flt(d.custom_thickness));
			_calc_new_qty();
		});
	}
	dialog.fields_dict.new_batch_no.df.onchange = () => _fetch_batch_dims(dialog.get_value("new_batch_no"));

	function _calc_new_qty() {
		if (!selected_row) return;
		let g = selected_row.parent_item_group;
		let uw = flt(selected_row.unit_weight);
		let l = flt(dialog.get_value("length"));
		let w = flt(dialog.get_value("width"));
		let t = flt(dialog.get_value("thickness"));
		let sec = flt(dialog.get_value("sec_qty"));
		let qty = 0;
		if (g === "Structurals" && l && uw && sec) {
			qty = (l / 1000) * uw * sec;
		} else if (g === "Plates" && l && w && t && uw && sec) {
			qty = (l / 1000) * (w / 1000) * t * uw * sec;
		}
		dialog.set_value("calculated_qty", flt(qty, 3));
	}
	dialog.fields_dict.sec_qty.df.onchange = () => _calc_new_qty();
	dialog.fields_dict.sec_qty.$input && dialog.fields_dict.sec_qty.$input.on("input", _calc_new_qty);

	// "Reserve Without Dimensions" mirrors Material Mapping's own toggle: when checked,
	// Sec Qty is no longer typed in — it's computed server-side (grouped Sec-Qty rounding
	// across every row sharing this batch, same as reserve_batches/_calc_group_rwd_allocations)
	// — and "Allocate based on Sec Nos" appears to control that computation.
	function _toggle_rwd(checked) {
		dialog.fields_dict.allocate_based_on_sec_qty.toggle(!!checked);
		dialog.fields_dict.sec_qty.df.read_only = checked ? 1 : 0;
		dialog.fields_dict.sec_qty.refresh();
		if (checked) {
			dialog.set_value("allocate_based_on_sec_qty", 1);
			dialog.set_value("sec_qty", 0);
		}
	}
	dialog.fields_dict.reserve_without_dimensions.df.onchange = () =>
		_toggle_rwd(dialog.get_value("reserve_without_dimensions"));

	function _select_row(row) {
		selected_row = row;
		let is_transferred = flt(row.transferred_qty) > 0;
		dialog.set_value("current_batch", row.batch_no || (row.purchase_receipt ? __("Purchased via {0}", [row.purchase_receipt]) : __("(none)")));
		dialog.set_value("current_sec_qty", flt(row.sec_qty));
		dialog.set_value("current_qty", flt(row.qty));
		dialog.set_value("reqd_kg", flt(row.reqd_kg));
		dialog.set_value("new_batch_no", "");
		dialog.set_value("length", 0);
		dialog.set_value("width", 0);
		dialog.set_value("thickness", 0);
		dialog.set_value("sec_qty", 0);
		dialog.set_value("calculated_qty", 0);
		dialog.set_value("reserve_without_dimensions", 0);
		dialog.set_value("allocate_based_on_sec_qty", 1);
		_toggle_allocation_fields(true, is_transferred);
		_toggle_rwd(0);
		picker.markSelected(row.name);
	}

	_toggle_allocation_fields(false, false);
	let picker = _mip_build_picker(dialog, all_rows, _select_row);

	// "Refresh Raw Materials" button inside the dialog header
	dialog.$wrapper.find(".modal-header .modal-title").after(
		`<button class="btn btn-xs btn-default mip-dlg-refresh" style="margin-left:12px;vertical-align:middle;">`
		+ frappe.utils.icon("refresh", "xs") + " " + __("Refresh Raw Materials")
		+ `</button>`
	);
	dialog.$wrapper.find(".mip-dlg-refresh").on("click", function() {
		frappe.call({
			method: "manufyxinvenzaerp.subcontracting_management.doctype.material_issue_plan.material_issue_plan.refresh_mip_raw_materials",
			args: { mip_name: frm.doc.name },
			freeze: true,
			freeze_message: __("Refreshing raw materials..."),
			callback() {
				frm.reload_doc().then(() => {
					all_rows.splice(0, all_rows.length, ...(frm.doc.raw_materials || []));
					// Re-select the current row with updated data if one was selected
					if (selected_row) {
						let updated = all_rows.find((r) =>
							r.source_table === selected_row.source_table && r.source_row === selected_row.source_row
						);
						if (updated) _select_row(updated);
						else _toggle_allocation_fields(false, false);
					}
					frappe.show_alert({ message: __("Raw materials refreshed"), indicator: "green" });
				});
			},
		});
	});

	if (preselect_row_name) {
		let row = all_rows.find((r) => r.name === preselect_row_name);
		if (row) {
			picker.setFilters(row.customer_drawing_number, row.duno_mark_no, row.sales_order);
			_select_row(row);
		}
	}

	dialog.show();
}
