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
		// unfiltered, showing every warehouse across every company. Group
		// warehouses are excluded too: they are only tree nodes (e.g. "All
		// Warehouses"), stock can never sit in one, so picking one here would set
		// a warehouse no transfer could ever move material into or out of.
		["source_warehouse", "supplier_warehouse", "cnc_warehouse", "excess_return_warehouse"].forEach((fieldname) => {
			frm.set_query(fieldname, () => ({
				filters: { company: frm.doc.company || "", is_group: 0 },
			}));
		});
		_add_view_all_raw_materials_button(frm);
		_add_update_batch_button(frm);
		// The Manual button is removed at the client's request in favour of one
		// doctype-wise ERP Manual page (production_management/page/erp_manual),
		// added to a Workspace separately rather than linked from here. The
		// per-doctype material-issue-plan-manual page it used to open has since
		// been deleted outright -- all manual content now lives in ERP Manual.
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
	// Only To Use drives the numbers. Balance Calc Qty is whatever the sheet has left
	// once To Use comes off it, so editing the Balance dimensions no longer changes it
	// -- they describe the SHAPE of the off-cut, which is checked against that weight
	// server-side on save (_warn_cut_sheet_mismatch).
	use_length(frm, cdt, cdn) { _recalc_cut_sheet_qty(cdt, cdn); },
	use_width(frm, cdt, cdn) { _recalc_cut_sheet_qty(cdt, cdn); },
	use_sec_qty(frm, cdt, cdn) { _recalc_cut_sheet_qty(cdt, cdn); },
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

// Weight from dimensions -- the client-side twin of utils/dimension_formula.calculate_qty.
function _cut_sheet_weight(row, L, W, S) {
	let g = row.parent_item_group;
	if (g === "Structurals") {
		if (L && row.unit_weight && S) return (L / 1000) * row.unit_weight * S;
	} else if (g === "Plates") {
		if (L && W && row.thickness && row.unit_weight && S) {
			return (L / 1000) * (W / 1000) * row.thickness * row.unit_weight * S;
		}
	}
	return null;
}

// Live W1/W2 preview while typing. Authoritative calc is server-side on save
// (_sync_cut_sheet_calc); the transferred-qty cap and post-submit batch resize are in
// material_issue_plan_transfer.py / production_management/stock_entry.py.
function _recalc_cut_sheet_qty(cdt, cdn) {
	let row = locals[cdt][cdn];

	let w1 = _cut_sheet_weight(row, row.use_length, row.use_width, row.use_sec_qty);
	frappe.model.set_value(cdt, cdn, "use_calc_qty", w1 !== null ? flt(w1, 3) : 0);

	// The whole sheet before cutting: its pre-cut size once one is recorded, otherwise
	// the batch dimensions carried on the row. Same order as the server -- after a
	// transfer has resized the batch to its Balance, the row's own dimensions describe
	// the remnant rather than the sheet.
	let sheet = (row.precut_length || row.precut_width)
		? _cut_sheet_weight(row, row.precut_length, row.precut_width, row.precut_sec_qty)
		: _cut_sheet_weight(row, row.length, row.width, row.sec_qty);

	let w2 = (sheet !== null && w1 !== null) ? Math.max(sheet - w1, 0) : 0;
	frappe.model.set_value(cdt, cdn, "balance_calc_qty", flt(w2, 3));
}

// ── Transfer readiness pre-flight check ──────────────────────────────────────

function _check_transfer_readiness(frm, on_proceed) {
	frappe.call({
		method: "manufyxinvenzaerp.subcontracting_management.material_issue_plan_transfer.get_mip_readiness_check",
		args: { mip_name: frm.doc.name },
		callback(r) {
			let d = r.message || {};
			// Off-cuts claimed through Excess Material Mapping that are still at the
			// supplier never reach the transfer list (there is no batch in the source
			// warehouse to move). Stashed on the form so the transfer popup can say so
			// outright, instead of the user hunting for a row that will never appear.
			// Not an "issue" -- it is a correct, finished state -- so it must be picked
			// up here, before the has_issues early return.
			frm.__mip_at_supplier = d.at_supplier || [];
			frm.__mip_supplier_warehouse = d.supplier_warehouse || "";
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

			// CNC Process is a routing instruction, not a preference -- flagged material
			// must go to CNC before the supplier. With no CNC Warehouse there is nowhere
			// valid to send it, so this BLOCKS the transfer outright rather than offering
			// a "proceed anyway" that would physically move stock past the CNC step.
			let cnc = d.cnc_without_warehouse || [];
			if (cnc.length) {
				html += `<div style="border:1px solid #b91c1c;background:#fef2f2;border-radius:6px;padding:12px;margin-bottom:12px;">
					<p style="margin:0 0 6px;font-weight:bold;color:#b91c1c;font-size:13px;">
						🚫 ${__("Transfer blocked — CNC Warehouse is not set ({0} CNC item(s))", [cnc.length])}
					</p>
					<p style="margin:0 0 8px;color:#7f1d1d;">
						${__("These rows are marked <b>CNC Process</b>, so they must go to the <b>CNC Warehouse first</b>, and only then on to {0}. This Material Issue Plan has no CNC Warehouse, so there is nowhere valid to send them.", [frappe.utils.escape_html(frm.doc.supplier_warehouse || __("the supplier/WIP warehouse"))])}
					</p>
					<p style="margin:0;color:#7f1d1d;">
						${__("Fix it in one of two ways: set <b>CNC Warehouse</b> in the Warehouses section, or untick <b>CNC Process</b> on those rows in the Material Planning if the CNC step is not required.")}
					</p>
					${_rows(cnc, __("CNC rows affected"), true)}
				</div>`;
			}

			if (d.unmapped && d.unmapped.length) {
				html += _rows(d.unmapped, `⚠ ${__("Not Mapped / No Batch Assigned ({0} item(s)) — these will NOT be transferred", [d.unmapped.length])}`, false);
			}
			if (d.unreserved && d.unreserved.length) {
				// Reserving is a separate deliberate step on the Material Planning, and
				// unreserved stock is simply never offered for transfer -- with nothing
				// here to explain the gap. Name the plan and the weight so it is obvious
				// where to go and what is at stake.
				let per_mp = (d.unreserved_summary || []).map((s) =>
					`<li><a href="/app/material-planning/${encodeURIComponent(s.material_planning)}" target="_blank"><b>${frappe.utils.escape_html(s.material_planning)}</b></a> — ${s.rows} ${__("row(s)")}, ${format_number(s.qty, null, 3)} Kg</li>`
				).join("");
				html += `<div style="border:1px solid #f59e0b;background:#fffbeb;border-radius:6px;padding:12px;margin-bottom:12px;">
					<p style="margin:0 0 6px;font-weight:bold;color:#92400e;font-size:13px;">
						⚠ ${__("Stock is mapped in Material Planning but NOT reserved ({0} item(s))", [d.unreserved.length])}
					</p>
					<p style="margin:0 0 8px;color:#78350f;">
						${__("These batches are assigned but never reserved, so they will <b>not</b> be transferred and no Stock Entry will be made for them. Open the Material Planning below and run <b>Reserve Batches</b>, then transfer.")}
					</p>
					<ul style="margin:0 0 8px 18px;color:#78350f;">${per_mp}</ul>
					${_rows(d.unreserved, __("Rows awaiting reservation"), true)}
				</div>`;
			}
			if (d.unmapped && d.unmapped.length || d.unreserved && d.unreserved.length) {
				html += `<p style="margin-top:10px;color:#555">
					${__("Ensure stocks are purchased and mapped against Material Planning, or assign batches using the <b>Update Batch</b> option in the Material Issue Plan.")}
				</p>`;
			}

			// A missing CNC Warehouse is a hard stop -- no primary action at all, so the
			// only way on is to fix the routing. The other two issues merely skip rows,
			// which is a judgement call, so those keep "Proceed Anyway".
			let dialog = new frappe.ui.Dialog({
				title: cnc.length
					? __("Transfer Blocked — CNC Warehouse Required")
					: __("Transfer Readiness Check — Issues Found"),
				size: "large",
				fields: [{ fieldtype: "HTML", fieldname: "body", options: html }],
				primary_action_label: cnc.length ? __("Close") : __("Proceed Anyway"),
				primary_action() {
					dialog.hide();
					if (!cnc.length) on_proceed();
				},
			});
			if (!cnc.length) {
				dialog.set_secondary_action_label(__("Cancel"));
				dialog.set_secondary_action(() => dialog.hide());
			}
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

	// Reference view of what this plan will hand over, per item + batch, before
	// any Stock Entry exists — the same Kg/Sec Nos figures the transfer popup
	// will show, with fractional totals called out.
	frm.add_custom_button(__("Validate Stock"), function() {
		frappe.call({
			method: "manufyxinvenzaerp.subcontracting_management.material_issue_plan_transfer.get_mip_pending_items",
			args: { mip_name: frm.doc.name },
			freeze: true,
			freeze_message: __("Checking planned stock…"),
			callback(r) { _show_mip_stock_validation(r.message || []); },
		});
	}, __("Transfer"));

	if (frm.doc.cnc_warehouse) {
		// One call answers both buttons. "To CNC Warehouse" is shown only while CNC
		// rows are still waiting to move there -- it used to appear whenever a CNC
		// warehouse was merely set, so it lingered after everything had gone and could
		// only open an empty popup.
		frappe.call({
			method: "manufyxinvenzaerp.subcontracting_management.material_issue_plan_transfer.get_mip_cnc_button_state",
			args: { mip_name: frm.doc.name },
			callback(r) {
				var state = r.message || {};

				if (state.show_to_cnc) {
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
				}

				if (state.show_cnc_forward) {
					// Second leg, and a separate Stock Entry by design: only material
					// that has physically arrived at CNC can be forwarded, and it can
					// be released in stages as machining finishes, so this opens the
					// same selection popup rather than moving everything at once.
					frm.add_custom_button(__("CNC to Supplier/WIP"), function() {
						frappe.call({
							method: "manufyxinvenzaerp.subcontracting_management.material_issue_plan_transfer.get_mip_cnc_pending_items",
							args: { mip_name: frm.doc.name },
							freeze: true,
							freeze_message: __("Loading CNC material…"),
							callback(r) {
								let rows = r.message || [];
								if (!rows.length) {
									frappe.msgprint({
										title: __("Nothing at CNC"),
										message: __("No machined material is waiting at {0} to forward. Transfer material to CNC first, and make sure that Stock Entry is submitted.", [frappe.utils.escape_html(frm.doc.cnc_warehouse || "CNC")]),
										indicator: "orange",
									});
									return;
								}
								_show_mip_transfer_popup(frm, rows, "cnc_forward");
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
// Read-only summary of the pending transfer rows: Kg and Sec Nos per item+batch.
// A fractional Sec Nos means one batch is shared across several drawings, so the
// whole-piece decision is still open — it is taken row by row in the transfer
// popup, not here.
function _show_mip_stock_validation(rows) {
	if (!rows.length) {
		frappe.msgprint({
			title: __("Validate Stock"),
			message: __("Nothing is pending transfer on this plan."),
			indicator: "orange",
		});
		return;
	}

	// Full width, no horizontal scrollbar: only the text columns wrap, numeric
	// columns stay nowrap + right-aligned so everything fits the wide dialog.
	let num = "text-align:right;white-space:nowrap;";
	let html = '<table class="table table-bordered table-condensed" style="font-size:12px;width:100%;table-layout:auto;margin-bottom:0;">';
	html += "<thead><tr>" + [
		[__("Item"), ""], [__("Batch"), ""], [__("DUNO/Mark No"), ""],
		[__("Planned Kg"), num], [__("Planned Sec Nos"), num],
	].map(([h, st]) => '<th style="' + st + '">' + h + "</th>").join("") + "</tr></thead><tbody>";

	let fractional = 0;
	rows.forEach(function (d) {
		let sec = flt(d.custom_sec_qty, 3);
		let is_frac = Math.abs(sec - Math.round(sec)) > 0.001;
		if (is_frac) fractional++;
		html += "<tr>" +
			'<td style="white-space:nowrap;">' + frappe.utils.escape_html(d.item_code) + "</td>" +
			'<td style="word-break:break-all;">' + frappe.utils.escape_html(d.batch_no || "—") + "</td>" +
			'<td style="white-space:nowrap;">' + frappe.utils.escape_html(d.duno_mark_no || "—") + "</td>" +
			'<td style="' + num + '">' + flt(d.qty, 3) + "</td>" +
			'<td style="' + num + '">' + (is_frac
				? '<span style="color:#b45309;font-weight:600;">' + sec + "</span> " +
				  "<span class='text-muted'>(" + __("or {0} whole", [Math.ceil(sec - 0.001)]) + ")</span>"
				: sec) +
			"</td></tr>";
	});
	html += "</tbody></table>";

	if (fractional) {
		html += '<p class="text-muted" style="margin-top:10px;">' +
			__("{0} row(s) have a fractional Sec Nos — one batch shared across several drawings. You can raise it to a whole number in the transfer popup; the extra weight is then recorded as excess to return.", [fractional]) +
			"</p>";
	}

	// A plain msgprint caps its own width and forces the table to scroll
	// sideways; an extra-large Dialog fits every column on screen.
	let dlg = new frappe.ui.Dialog({
		title: __("Validate Stock"),
		size: "extra-large",
		fields: [{ fieldtype: "HTML", fieldname: "content" }],
	});
	dlg.fields_dict.content.$wrapper.html(html);
	dlg.show();
}

// Weight of an off-cut from what was measured -- client-side twin of
// utils/dimension_formula.calculate_qty, same as the Cut Sheet preview uses.
function _excess_weight(d, L, W, S) {
	var g = d.custom_parent_item_group;
	var t = flt(d.custom_thickness), uw = flt(d.custom_unit_weight);
	if (g === "Structurals") {
		if (L && uw && S) return (L / 1000) * uw * S;
	} else if (g === "Plates") {
		if (L && W && t && uw && S) return (L / 1000) * (W / 1000) * t * uw * S;
	}
	return null;
}

function _show_mip_transfer_popup(frm, pending_items, transfer_type) {
	var is_cnc_fwd = transfer_type === "cnc_forward";
	var items = is_cnc_fwd
		? pending_items
		: pending_items.filter(function(d) { return transfer_type === "cnc" ? d.cnc_process : !d.cnc_process; });
	if (!items.length) {
		frappe.msgprint({
			title: __("No Pending Items"),
			message: is_cnc_fwd ? __("Nothing is waiting at CNC to forward.")
				: transfer_type === "cnc" ? __("No pending CNC items to transfer.") : __("No pending items to transfer."),
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
	var $table = $("<table class='table table-bordered table-condensed' style='margin-bottom:0;font-size:12px'>"
		+ "<thead><tr>"
		+ "<th style='width:32px'></th>"
		+ "<th>" + __("Item") + "</th>"
		+ "<th>" + __("Batch") + "</th>"
		+ "<th class='text-right' style='white-space:nowrap'>" + __("Planned") + "</th>"
		+ "<th class='text-right' style='white-space:nowrap'>" + __("Transferred") + "</th>"
		+ "<th class='text-right' style='white-space:nowrap'>" + __("In Stock") + "</th>"
		+ "<th class='text-right' style='white-space:nowrap'>" + __("Sec Nos")
			+ "<div class='text-muted' style='font-weight:normal;font-size:10px'>" + __("edit to transfer part") + "</div></th>"
		+ "<th class='text-right' style='white-space:nowrap'>" + __("Transfer Qty (Kg)")
			+ "<div class='text-muted' style='font-weight:normal;font-size:10px'>" + __("from Sec Nos") + "</div></th>"
		+ "</tr></thead><tbody></tbody></table>");

	var $tbody = $table.find("tbody");

	// Anything parked by a previous "Save and Close" comes back onto the rows it was
	// entered against. Fetched after the table is built, so it can simply replay the
	// same handlers a user would have triggered by typing.
	frappe.call({
		method: "manufyxinvenzaerp.subcontracting_management.doctype.material_issue_plan.material_issue_plan.get_transfer_draft",
		args: { mip_name: frm.doc.name },
		callback: function(r) {
			var draft = r.message || {};
			if (!Object.keys(draft).length) return;
			var restored = 0;
			$tbody.find("tr").each(function() {
				var $tr = $(this);
				var d = items[parseInt($tr.data("idx"), 10)];
				if (!d) return;
				var saved = draft[d.item_code + "|" + (d.batch_no || "") + "|" + (d.cnc_process ? 1 : 0)];
				if (!saved) return;
				restored++;
				if (flt(saved.draft_sec_qty)) {
					// Fire the normal change handler rather than writing the figure
					// directly: it is what recalculates Kg and the surplus. Duplicating
					// that here would be a second copy to keep in step.
					$tr.find(".mip-sec-qty").val(flt(saved.draft_sec_qty, 3)).trigger("change");
				}
			});
			if (restored) {
				frappe.show_alert({
					message: __("Restored a saved draft for {0} row(s).", [restored]),
					indicator: "blue",
				}, 6);
			}
		},
	});
	// Sec Nos is THE control, and Kg is derived from it -- steel moves in pieces and
	// the weight is a consequence of the piece count, so lowering Sec Nos is how a
	// partial transfer is made. Kg is therefore read-only: editing it directly would
	// ship a Stock Entry whose Sec Qty and weight disagree, and Supplier Operation
	// Entry consumption and the excess-return figures are both derived from Sec Qty.
	//
	// The exception is a row with no usable Kg-per-piece (dimensions missing, so Sec
	// Nos is 0 and editing it changes nothing). There Kg is the only way to transfer
	// part of a row, so it stays editable.
	items.forEach(function(d, idx) {
		d._planned_sec_qty = flt(d.custom_sec_qty);
		d._planned_qty = flt(d.qty);
		var is_frac = Math.abs(d._planned_sec_qty - Math.round(d._planned_sec_qty)) > 0.001;
		var done = flt(d.transferred_qty);
		var avail = flt(d.available_qty);
		var short = avail + 0.001 < flt(d.qty);
		// Sec Nos can only drive the weight when both are non-zero.
		var sec_drives_qty = d._planned_sec_qty > 0 && d._planned_qty > 0;

		$tbody.append(
			"<tr data-idx='" + idx + "' data-item='" + frappe.utils.escape_html(d.item_code || "") + "'>" +
			"<td class='text-center'><input type='checkbox' class='mip-item-chk'" + (short ? "" : " checked") + "></td>" +
			"<td>" + frappe.utils.escape_html(d.item_code) +
				(d.duno_mark_no ? "<div class='text-muted' style='font-size:11px'>" +
					frappe.utils.escape_html(d.duno_mark_no) + "</div>" : "") + "</td>" +
			"<td style='word-break:break-all'>" + frappe.utils.escape_html(d.batch_no || "—") + "</td>" +
			"<td class='text-right' style='white-space:nowrap'>" + format_number(flt(d.planned_qty), null, 3) + "</td>" +
			"<td class='text-right' style='white-space:nowrap'>" +
				(done > 0 ? "<span style='color:#15803d'>" + format_number(done, null, 3) + "</span>" : "—") + "</td>" +
			"<td class='text-right' style='white-space:nowrap'>" +
				(short ? "<span style='color:#b91c1c;font-weight:600'>" + format_number(avail, null, 3) + "</span>"
				       : format_number(avail, null, 3)) + "</td>" +
			"<td class='text-right'>" +
				(sec_drives_qty
					? "<input type='number' step='0.001' min='0' class='form-control input-xs text-right mip-sec-qty' " +
					  "style='width:100px;display:inline-block" + (is_frac ? ";border-color:#f59e0b" : "") + "' " +
					  "value='" + flt(d._planned_sec_qty, 3) + "'>" +
					  // Always name the planned figure -- once the box has been typed
					  // into there is otherwise nothing left on screen saying what the
					  // plan actually called for.
					  "<div class='text-muted' style='font-size:11px'>" +
						flt(d._planned_sec_qty, 3) + " " + __("(Plan)") +
						(is_frac ? " · " + __("or {0} whole", [Math.ceil(d._planned_sec_qty - 0.001)]) : "") +
					  "</div>"
					: "<span class='text-muted'>—</span>") +
			"</td>" +
			"<td class='text-right'>" +
				(sec_drives_qty
					? "<span class='mip-qty-text'>" + format_number(flt(d.qty), null, 3) + "</span>" +
					  "<input type='hidden' class='mip-qty' value='" + flt(d.qty, 3) + "'>"
					: "<input type='number' step='0.001' min='0' class='form-control input-xs text-right mip-qty' " +
					  "style='width:120px;display:inline-block' value='" + flt(d.qty, 3) + "'>") +
				"<div class='text-muted mip-qty-note' style='font-size:11px'>" +
					__("pending {0}", [format_number(flt(d.qty), null, 3)]) + "</div>" +
			"</td>" +
			"</tr>"
		);
	});

	// Only reachable on rows where Sec Nos cannot drive the weight (see above), so
	// this is the sole way to transfer part of such a row. Obvious limits only --
	// the authoritative check runs server-side at transfer.
	$tbody.on("change", "input.mip-qty", function() {
		var $input = $(this);
		var $row = $input.closest("tr");
		var d = items[parseInt($row.data("idx"), 10)];
		var v = flt($input.val());
		var max = Math.min(flt(d.qty), flt(d.available_qty));

		if (v <= 0) {
			frappe.show_alert({ message: __("Transfer qty must be greater than zero."), indicator: "red" }, 5);
			$input.val(flt(d.qty, 3));
			return;
		}
		if (v > max + 0.001) {
			frappe.show_alert({
				message: __("Only {0} can be transferred now (pending {1}, in stock {2}).",
					[format_number(max, null, 3), format_number(flt(d.qty), null, 3), format_number(flt(d.available_qty), null, 3)]),
				indicator: "red",
			}, 7);
			$input.val(flt(max, 3));
			v = max;
		}
		d._transfer_qty = v;
		$row.find(".mip-qty-note").text(
			v + 0.001 < flt(d.qty)
				? __("partial · {0} will stay pending", [format_number(flt(d.qty) - v, null, 3)])
				: __("pending {0}", [format_number(flt(d.qty), null, 3)])
		);
	});

	// Re-derive Kg + excess from an edited Sec Nos, refusing anything the batch
	// cannot physically cover.
	$tbody.on("change", ".mip-sec-qty", function() {
		var $input = $(this);
		var $row = $input.closest("tr");
		var d = items[parseInt($row.data("idx"), 10)];
		var new_sec = flt($input.val());

		if (new_sec <= 0) {
			frappe.show_alert({ message: __("Sec Nos must be greater than zero."), indicator: "red" }, 5);
			$input.val(flt(d.custom_sec_qty, 3));
			return;
		}
		frappe.call({
			method: "manufyxinvenzaerp.subcontracting_management.material_issue_plan_transfer.update_transfer_sec_qty",
			args: {
				mip_name: frm.doc.name,
				item_code: d.item_code,
				batch_no: d.batch_no || "",
				planned_sec_qty: d._planned_sec_qty,
				planned_qty: d._planned_qty,
				new_sec_qty: new_sec,
			},
			callback: function(r) {
				if (!r.message) return;
				var m = r.message;
				if (m.blocked) {
					frappe.msgprint({ title: __("Not Enough Stock"), message: m.message, indicator: "red" });
					$input.val(flt(d.custom_sec_qty, 3));
					return;
				}
				d.custom_sec_qty = m.custom_sec_qty;
				d.qty = m.qty;
				d.round_up_excess_kg = m.round_up_excess_kg;
				d.round_up_excess_pieces = m.round_up_excess_pieces;
				// Sec Nos drives the weight, so push the recalculated Kg into both the
				// hidden field that gets submitted and the figure on screen.
				d._transfer_qty = flt(m.qty);
				$row.find(".mip-qty").val(flt(m.qty, 3));
				$row.find(".mip-qty-text").text(format_number(flt(m.qty), null, 3));
				$row.find(".mip-qty-note").text(
					flt(m.qty) + 0.001 < flt(d._planned_qty)
						? __("partial · {0} will stay pending", [format_number(flt(d._planned_qty) - flt(m.qty), null, 3)])
						: __("pending {0}", [format_number(flt(m.qty), null, 3)])
				);
				if (m.round_up_excess_kg > 0) {
					frappe.show_alert({
						message: __("{0} Kg extra will be issued and recorded as excess to return.", [flt(m.round_up_excess_kg, 3)]),
						indicator: "orange",
					}, 6);
				}
				// The numbers on screen are no longer the ones this popup opened
				// with, so the button says what actually happens next: stock is
				// re-checked server-side before any Stock Entry is created.
				_mark_sec_nos_edited();
			},
		});
	});

	function _apply_filters() {
		var item_q = item_search.getValue().toLowerCase();
		$tbody.find("tr").each(function() {
			var $row = $(this);
			$row.toggle(!item_q || String($row.data("item") || "").toLowerCase().includes(item_q));
		});
	}
	item_search.$el.on("mip:filter", _apply_filters);
	$actions.find(".mip-sel-all").on("click", function() { $tbody.find("tr:visible .mip-item-chk").prop("checked", true); });
	$actions.find(".mip-desel-all").on("click", function() { $tbody.find("tr:visible .mip-item-chk").prop("checked", false); });

	// Header strip: where this transfer stands overall, and anything that would
	// quietly reduce what actually moves -- stock not yet received, or reserved
	// material sitting on a Material Planning that nobody has reserved yet.
	var tot_planned = items.reduce(function(a, d) { return a + flt(d.planned_qty); }, 0);
	var tot_done    = items.reduce(function(a, d) { return a + flt(d.transferred_qty); }, 0);
	var tot_pending = items.reduce(function(a, d) { return a + flt(d.qty); }, 0);
	var short_rows  = items.filter(function(d) { return flt(d.available_qty) + 0.001 < flt(d.qty); });

	var summary = "<div style='background:#f8fafc;border:1px solid #e2e8f0;border-radius:6px;padding:10px 12px;margin-bottom:10px;font-size:12px'>"
		+ "<b>" + __("Planned") + ":</b> " + format_number(tot_planned, null, 3) + " Kg"
		+ " &nbsp;·&nbsp; <b>" + __("Already transferred") + ":</b> <span style='color:#15803d'>"
		+ format_number(tot_done, null, 3) + " Kg</span>"
		+ " &nbsp;·&nbsp; <b>" + __("Pending now") + ":</b> " + format_number(tot_pending, null, 3) + " Kg"
		+ " &nbsp;·&nbsp; " + __("to") + " <b>" + frappe.utils.escape_html(
			transfer_type === "cnc" ? (frm.doc.cnc_warehouse || "-") : (frm.doc.supplier_warehouse || "-")) + "</b>"
		+ (is_cnc_fwd ? " &nbsp;·&nbsp; " + __("from") + " <b>" + frappe.utils.escape_html(frm.doc.cnc_warehouse || "-") + "</b>" : "")
		+ "</div>";

	if (short_rows.length) {
		summary += "<div style='background:#fef2f2;border:1px solid #fecaca;border-radius:6px;padding:10px 12px;margin-bottom:10px;font-size:12px;color:#7f1d1d'>"
			+ "⚠ <b>" + __("{0} item(s) do not have enough stock in {1} yet", [short_rows.length, frappe.utils.escape_html(frm.doc.source_warehouse || "-")]) + "</b><br>"
			+ __("Their <b>In Stock</b> figure is below what is pending — usually the Purchase Receipt has not been made yet. These rows are left unticked; transfer the rest now and come back for them.")
			+ "</div>";
	}

	// Material already sitting at the supplier: an off-cut this plan claimed through
	// Excess Material Mapping while it was still at their end. There is nothing to
	// move -- it is already where the transfer would have sent it -- so the row is
	// absent from the list below by design, and this says so rather than leaving a
	// silent gap between what was planned and what is on offer.
	// Only on the legs that leave the source warehouse. The CNC-to-supplier leg does
	// not run the readiness check at all, so its stash would be whatever the last
	// transfer dialog left behind — and material already at the supplier says nothing
	// about what is waiting at CNC anyway.
	var at_supplier = is_cnc_fwd ? [] : (frm.__mip_at_supplier || []);
	if (at_supplier.length) {
		var at_rows = at_supplier.map(function(s) {
			return "<li>" + frappe.utils.escape_html(s.item_code)
				+ (s.duno_mark_no ? " · " + frappe.utils.escape_html(s.duno_mark_no) : "")
				+ " — " + format_number(flt(s.qty), null, 3) + " " + frappe.utils.escape_html(s.uom || "Kg")
				+ (s.source_mip ? " (" + __("from") + " " + frappe.utils.escape_html(s.source_mip) + ")" : "")
				+ "</li>";
		}).join("");
		summary += "<div style='background:#eff6ff;border:1px solid #bfdbfe;border-radius:6px;padding:10px 12px;margin-bottom:10px;font-size:12px;color:#1e3a8a'>"
			+ "ℹ <b>" + __("{0} item(s) are already at {1} — no transfer needed", [
				at_supplier.length,
				frappe.utils.escape_html(frm.__mip_supplier_warehouse || frm.doc.supplier_warehouse || __("the supplier"))]) + "</b><br>"
			+ __("These are excess off-cuts this plan claimed through <b>Excess Material Mapping</b> while they were still at the supplier. They are not listed below because there is no stock in {0} to move.", [
				frappe.utils.escape_html(frm.doc.source_warehouse || __("the source warehouse"))])
			+ "<ul style='margin:6px 0 0 18px'>" + at_rows + "</ul>"
			+ "</div>";
	}

	// Two tabs. The first is the transfer itself, per batch; the second plans the
	// excess return for the same material CONSOLIDATED by item, because that is how
	// an off-cut is actually handled -- one item comes back as one shape, however
	// many batches it was drawn from. Asking per batch made the same item's excess
	// be entered two and three times over.
	var $tab_nav = $(
		"<ul class='nav nav-tabs' style='margin-bottom:12px'>" +
			"<li class='active'><a href='#' data-pane='transfer' style='cursor:pointer'>" +
				__("Raw material to transfer") + "</a></li>" +
			"<li><a href='#' data-pane='excess' style='cursor:pointer'>" +
				__("Consolidate item for excess return plan") + "</a></li>" +
		"</ul>"
	);
	var $pane_transfer = $("<div class='mip-pane' data-pane='transfer'>")
		.append($(summary), $filter_row, $actions, $table);
	var $pane_excess = $("<div class='mip-pane' data-pane='excess' style='display:none'>");
	var $content = $("<div>").append($tab_nav, $pane_transfer, $pane_excess);

	$tab_nav.on("click", "a", function(e) {
		e.preventDefault();
		var pane = $(this).data("pane");
		$tab_nav.find("li").removeClass("active");
		$(this).closest("li").addClass("active");
		$content.find(".mip-pane").hide().filter("[data-pane='" + pane + "']").show();
		// Rebuilt on entry rather than kept in step continuously: it reads the
		// transfer tab's live figures, and those change with every tick and every
		// Sec Nos edit.
		if (pane === "excess") _render_excess_plan();
	});

	// ── Consolidated excess plan ──────────────────────────────────────────────
	//
	//   Excess Kg (system)  = Planned transfer weight - Planned drawing weight
	//   Difference          = Excess Kg (entered) - Excess Kg (system)
	//
	// Positive means more is coming back than the transfer created; negative means
	// part of the excess is unaccounted for. Neither blocks the transfer -- the
	// figure is there to be judged, not enforced.
	function _collect_excess_plan_state() {
		var by_item = {};
		$tbody.find("tr").each(function() {
			var $tr = $(this);
			if (!$tr.find(".mip-item-chk").prop("checked")) return;
			var d = items[parseInt($tr.data("idx"), 10)];
			if (!d) return;
			var e = by_item[d.item_code];
			if (!e) {
				e = by_item[d.item_code] = {
					item_code: d.item_code,
					item_name: d.item_name || d.item_code,
					group: d.custom_parent_item_group || "",
					thickness: flt(d.custom_thickness),
					unit_weight: flt(d.custom_unit_weight),
					drawing_kg: 0,
					transfer_kg: 0,
					batches: 0,
				};
			}
			e.drawing_kg += flt(d.drawing_planned_weight);
			e.transfer_kg += flt($tr.find(".mip-qty").val()) || flt(d.qty);
			e.batches += 1;
		});
		return by_item;
	}

	function _render_excess_plan() {
		var by_item = _collect_excess_plan_state();
		var codes = Object.keys(by_item).sort();
		if (!codes.length) {
			$pane_excess.html("<div class='text-muted' style='padding:20px 4px'>" +
				__("Tick the materials to transfer on the first tab. Whatever is selected there is consolidated here, one line per item.") +
				"</div>");
			return;
		}

		var th = "white-space:nowrap;padding:6px 8px;background:#f4f5f7;border-bottom:2px solid #d1d8dd;font-weight:600;font-size:11px;";
		var html = "<div style='font-size:12px;color:#475569;margin-bottom:10px'>" +
			__("One line per item, with no batch reference: an off-cut comes back as one shape however many batches it was drawn from.") +
			"<br><b>" + __("Excess Kg (system)") + "</b> = " + __("Planned transfer weight − Planned drawing weight") +
			" &nbsp;·&nbsp; <b>" + __("Difference") + "</b> = " + __("Excess Kg (entered) − Excess Kg (system)") +
			" &nbsp;(" + __("positive = extra, negative = missing") + ")</div>" +
			"<div style='overflow-x:auto'><table class='table table-bordered table-condensed' style='margin-bottom:0;font-size:12px'>" +
			"<thead><tr>" +
				"<th style='" + th + "'>" + __("Item") + "</th>" +
				"<th style='" + th + "text-align:right'>" + __("Planned Drawing Wt") + "</th>" +
				"<th style='" + th + "text-align:right'>" + __("Planned Transfer Wt") + "</th>" +
				"<th style='" + th + "text-align:right'>" + __("Excess Kg") +
					"<div class='text-muted' style='font-weight:normal;font-size:10px'>" + __("system") + "</div></th>" +
				"<th style='" + th + "'>" + __("Length (mm)") + "</th>" +
				"<th style='" + th + "'>" + __("Width (mm)") + "</th>" +
				"<th style='" + th + "'>" + __("Sec Qty") + "</th>" +
				"<th style='" + th + "text-align:right'>" + __("Excess Kg") +
					"<div class='text-muted' style='font-weight:normal;font-size:10px'>" + __("entered") + "</div></th>" +
				"<th style='" + th + "text-align:right'>" + __("Difference") + "</th>" +
			"</tr></thead><tbody>";

		codes.forEach(function(code) {
			var e = by_item[code];
			var sys = flt(e.transfer_kg - e.drawing_kg, 3);
			var saved = (dlg._excess_plan || {})[code] || {};
			var num = "<input type='number' step='0.001' min='0' class='form-control input-xs text-right ";
			html += "<tr data-item='" + frappe.utils.escape_html(code) + "'>" +
				"<td>" + frappe.utils.escape_html(code) +
					"<div class='text-muted' style='font-size:11px'>" +
						__("{0} batch row(s)", [e.batches]) + "</div></td>" +
				"<td class='text-right' style='white-space:nowrap'>" + format_number(e.drawing_kg, null, 3) + "</td>" +
				"<td class='text-right' style='white-space:nowrap'>" + format_number(e.transfer_kg, null, 3) + "</td>" +
				"<td class='text-right mip-xs-sys' style='white-space:nowrap;font-weight:600'>" +
					format_number(sys, null, 3) + "</td>" +
				"<td>" + num + "mip-xs-length' style='width:100px' value='" + (flt(saved.length) || "") + "'></td>" +
				"<td>" + num + "mip-xs-width' style='width:100px' value='" + (flt(saved.width) || "") + "'></td>" +
				"<td>" + num + "mip-xs-sec' style='width:90px' value='" + (flt(saved.sec_qty) || "") + "'></td>" +
				"<td class='text-right mip-xs-kg' style='white-space:nowrap;font-weight:600'>—</td>" +
				"<td class='text-right mip-xs-diff' style='white-space:nowrap;font-weight:600'>—</td>" +
			"</tr>";
		});
		html += "</tbody></table></div>";
		$pane_excess.html(html);
		$pane_excess.find("tr[data-item]").each(function() { _recalc_excess_row($(this), by_item); });
		$pane_excess.off("input.xs").on("input.xs", ".mip-xs-length, .mip-xs-width, .mip-xs-sec", function() {
			_recalc_excess_row($(this).closest("tr"), by_item);
		});
	}

	function _recalc_excess_row($row, by_item) {
		var e = by_item[$row.data("item")];
		if (!e) return;
		var L = flt($row.find(".mip-xs-length").val());
		var W = flt($row.find(".mip-xs-width").val());
		var S = flt($row.find(".mip-xs-sec").val());
		var entered = _excess_weight({
			custom_parent_item_group: e.group,
			custom_thickness: e.thickness,
			custom_unit_weight: e.unit_weight,
		}, L, W, S);
		var sys = flt(e.transfer_kg - e.drawing_kg, 3);

		// Remembered on the dialog, not only in the DOM: switching back to the
		// transfer tab re-renders this one from scratch.
		dlg._excess_plan = dlg._excess_plan || {};
		if (L || W || S) {
			dlg._excess_plan[e.item_code] = { length: L, width: W, sec_qty: S };
		} else {
			delete dlg._excess_plan[e.item_code];
		}

		if (entered === null) {
			$row.find(".mip-xs-kg").text("—");
			$row.find(".mip-xs-diff").text("—").css("color", "");
			return;
		}
		var diff = flt(entered - sys, 3);
		$row.find(".mip-xs-kg").text(format_number(entered, null, 3));
		$row.find(".mip-xs-diff")
			.text((diff > 0 ? "+" : "") + format_number(diff, null, 3))
			.attr("title", diff > 0 ? __("extra beyond the transfer") : diff < 0 ? __("missing") : "")
			.css("color", Math.abs(diff) < 0.001 ? "#15803d" : diff > 0 ? "#1d4ed8" : "#b91c1c");
	}

	var dlg = new frappe.ui.Dialog({
		title: is_cnc_fwd ? __("Select Materials — CNC to Supplier/WIP")
			: transfer_type === "cnc" ? __("Select Materials — To CNC Warehouse") : __("Select Materials to Transfer"),
		size: "extra-large",
		fields: [{ fieldtype: "HTML", fieldname: "content" }],
		primary_action_label: __("Transfer Selected"),
		secondary_action_label: __("Save and Close"),
		// Parks whatever has been typed and closes, without validating any of it --
		// the point is to step away mid-decision. Everything is re-checked server-side
		// when Transfer is pressed.
		secondary_action: function() {
			var draft = [];
			$tbody.find("tr").each(function() {
				var $tr = $(this);
				var d = items[parseInt($tr.data("idx"), 10)];
				if (!d) return;
				draft.push({
					item_code: d.item_code,
					batch_no: d.batch_no || "",
					cnc_process: d.cnc_process ? 1 : 0,
					custom_sec_qty: flt($tr.find(".mip-sec-qty").val()) || flt(d.custom_sec_qty),
				});
			});
			frappe.call({
				method: "manufyxinvenzaerp.subcontracting_management.doctype.material_issue_plan.material_issue_plan.save_transfer_draft",
				args: { mip_name: frm.doc.name, rows_json: JSON.stringify(draft) },
				freeze: true,
				freeze_message: __("Saving draft…"),
				callback: function(r) {
					dlg.hide();
					frappe.show_alert({
						message: __("Draft saved for {0} row(s). Reopen this popup to carry on.",
							[(r.message || {}).saved || 0]),
						indicator: "blue",
					}, 6);
					frm.reload_doc();
				},
			});
		},
		primary_action: function() {
			var selected = [];
			$tbody.find("tr").each(function() {
				var $tr = $(this);
				if (!$tr.find(".mip-item-chk").prop("checked")) return;
				var d = items[parseInt($tr.data("idx"), 10)];
				// Send whatever is in the Qty box, not the full pending figure --
				// that box IS the partial-transfer control.
				var qty = flt($tr.find(".mip-qty").val());
				selected.push($.extend({}, d, {
					qty: qty > 0 ? qty : flt(d.qty),
				}));
			});
			if (!selected.length) {
				frappe.msgprint(__("Please select at least one item."));
				return;
			}

			// Rounding Sec Nos up to whole pieces is expected -- it is the whole
			// point of this popup -- but it means issuing MORE than the plan
			// reserved, and that surplus comes back as excess. Say so plainly and
			// get a confirmation, rather than letting extra steel leave the rack on
			// the strength of a number the user may have typed without realising
			// what it implied.
			var over = selected.filter(function(s) {
				return flt(s.qty) > flt(s.planned_qty) + 0.001;
			});
			if (!over.length) {
				_do_transfer(selected);
				return;
			}

			var total_extra = 0;
			var rows = over.map(function(s) {
				var extra = flt(s.qty) - flt(s.planned_qty);
				total_extra += extra;
				return "<tr>"
					+ "<td style='padding:4px 10px 4px 0'>" + frappe.utils.escape_html(s.item_code) + "</td>"
					+ "<td style='padding:4px 10px 4px 0;color:#888'>" + frappe.utils.escape_html(s.batch_no || "-") + "</td>"
					+ "<td style='padding:4px 10px 4px 0;text-align:right'>" + format_number(flt(s.planned_qty), null, 3) + "</td>"
					+ "<td style='padding:4px 10px 4px 0;text-align:right'>" + format_number(flt(s.qty), null, 3) + "</td>"
					+ "<td style='padding:4px 0;text-align:right;color:#e8590c;font-weight:600'>+"
					+ format_number(extra, null, 3) + "</td></tr>";
			}).join("");

			frappe.confirm(
				__("These lines are being issued above what Material Planning reserved:")
				+ "<div style='overflow-x:auto;margin:10px 0'><table style='font-size:12px;border-collapse:collapse'>"
				+ "<thead><tr style='border-bottom:1px solid #ddd'>"
				+ "<th style='text-align:left;padding:4px 10px 4px 0'>" + __("Item") + "</th>"
				+ "<th style='text-align:left;padding:4px 10px 4px 0'>" + __("Batch") + "</th>"
				+ "<th style='text-align:right;padding:4px 10px 4px 0'>" + __("Planned") + "</th>"
				+ "<th style='text-align:right;padding:4px 10px 4px 0'>" + __("Transferring") + "</th>"
				+ "<th style='text-align:right;padding:4px 0'>" + __("Difference") + "</th>"
				+ "</tr></thead><tbody>" + rows + "</tbody></table></div>"
				+ __("The <b>{0} Kg</b> difference is recorded as <b>excess to return</b> on the Excess Material Items table, so it can be brought back once the job has cut what it needs. Stock is re-checked before anything moves.",
					[format_number(total_extra, null, 3)]),
				function() { _do_transfer(selected); }
			);
		},
	});

	function _do_transfer(selected) {
		{
			dlg.hide();
			// The CNC leg draws from the CNC warehouse, not the source warehouse, so
			// it has its own endpoint and its own pending/validation basis.
			frappe.call({
				method: is_cnc_fwd
					? "manufyxinvenzaerp.subcontracting_management.material_issue_plan_transfer.create_mip_cnc_partial_forward"
					: "manufyxinvenzaerp.subcontracting_management.material_issue_plan_transfer.create_mip_partial_transfer",
				args: is_cnc_fwd
					? { mip_name: frm.doc.name, selected_items_json: JSON.stringify(selected) }
					: {
						mip_name: frm.doc.name,
						selected_items_json: JSON.stringify(selected),
						transfer_type: transfer_type,
						// One measured off-cut per item, from the second tab. Empty
						// when nothing was entered, and the server falls back to its
						// own placeholder shape exactly as before.
						excess_plan_json: JSON.stringify(dlg._excess_plan || {}),
					},
				freeze: true,
				freeze_message: __("Creating transfer entry…"),
				callback: function(r) {
					if (r.message) {
						frappe.msgprint({ title: __("Stock Entry Created"), message: __("Transfer entry: ") + '<a href="/app/stock-entry/' + encodeURIComponent(r.message) + '">' + r.message + "</a>", indicator: "green" });
						frm.reload_doc();
					}
				},
			});
		}
	}

	function _mark_sec_nos_edited() {
		if (dlg._sec_edited) return;
		dlg._sec_edited = true;
		dlg.set_primary_action(__("Verify and Transfer"), dlg.primary_action);
	}

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
	// The way out of the "already reserved" block: release the claim, correct the
	// dimensions, then map the off-cut again from the Material Planning. Confirmed
	// first because releasing it puts the off-cut back in front of every other job's
	// picker, so the claiming plan can lose it to someone else.
	unlink_claim_btn(frm, cdt, cdn) {
		if (frm.doctype !== "Material Issue Plan") return;
		var row = locals[cdt][cdn];
		if (!row.mapped_material_planning) {
			frappe.msgprint(__("This excess item is not claimed by any Material Planning."));
			return;
		}
		frappe.confirm(
			__("Release <b>{0}</b> from Material Planning <b>{1}</b>?<br><br>Its reservation there will be dropped and the off-cut becomes available for any job to claim again.",
				[frappe.utils.escape_html(row.item_code || ""), frappe.utils.escape_html(row.mapped_material_planning)]),
			function() {
				frappe.call({
					method: "manufyxinvenzaerp.subcontracting_management.doctype.material_issue_plan.material_issue_plan.unlink_excess_claim",
					args: { mip_name: frm.doc.name, excess_row_name: row.name },
					freeze: true,
					freeze_message: __("Releasing claim…"),
					callback(r) {
						if (!r.message) return;
						frappe.show_alert({
							message: __("Claim released from {0}. Dimensions can now be edited.", [r.message.released_from]),
							indicator: "green",
						});
						frm.reload_doc();
					},
				});
			}
		);
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
	"reserve_without_dimensions",
];
const _MIP_NEW_ALLOC_FIELDS = [
	"new_batch_no", "length", "width", "thickness", "sec_qty", "calculated_qty",
	"reserve_without_dimensions",
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
	// Sec Qty is no longer typed in — the row reserves its exact Required Qty in Kg and
	// Sec Nos is derived from it server-side (_apply_rwd_fractional_nos), left fractional
	// until someone rounds it to whole pieces at transfer time.
	function _toggle_rwd(checked) {
		dialog.fields_dict.sec_qty.df.read_only = checked ? 1 : 0;
		dialog.fields_dict.sec_qty.refresh();
		if (checked) dialog.set_value("sec_qty", 0);
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
