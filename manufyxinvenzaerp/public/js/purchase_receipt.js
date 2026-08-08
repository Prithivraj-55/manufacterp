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

// Inspection Call workflow (shared with Job Card / Supplier Operation Entry
// via manufyxinvenzaerp.production_management.inspection) — opt-in per Item
// (`custom_inspection_required`). The call date is captured per round via a
// popup and stored only on the call log row (and its linked Inspection
// Entry) — Purchase Receipt itself does not persist a separate date field.
// Both actions render as Button fields inside the Inspection tab (not the
// page toolbar), right above Inspection Status.
function _pr_inspection_state(frm) {
	const log = frm.doc.custom_inspection_call_log || [];
	const last = log.length ? log[log.length - 1] : null;
	const in_progress = last && last.round_status !== "Completed";
	return { log, last, in_progress };
}

frappe.ui.form.on("Purchase Receipt", {
	refresh(frm) {
		if (frm.is_new()) return;

		const { last, in_progress } = _pr_inspection_state(frm);
		let label = __("Create Inspection");
		if (in_progress && !last.inspection_entry) label = __("Create Inspection Entry");
		else if (in_progress && last.inspection_entry) label = __("View Inspection Entry");
		frm.set_df_property("custom_create_inspection_btn", "label", label);
	},

	custom_create_inspection_btn(frm) {
		const { last, in_progress } = _pr_inspection_state(frm);

		if (in_progress && last.inspection_entry) {
			frappe.set_route("Form", "Inspection Entry", last.inspection_entry);
			return;
		}

		if (in_progress && !last.inspection_entry) {
			frappe.call({
				method: "manufyxinvenzaerp.production_management.inspection.create_inspection_entry",
				args: { source_doctype: "Purchase Receipt", source_name: frm.doc.name },
				freeze: true,
				freeze_message: __("Creating Inspection Entry…"),
				callback(r) {
					if (r.message) {
						frm.reload_doc();
						frappe.set_route("Form", "Inspection Entry", r.message);
					}
				},
			});
			return;
		}

		frappe.prompt(
			[{
				fieldname: "call_date",
				fieldtype: "Date",
				label: __("Inspection Call Date"),
				reqd: 1,
				default: frappe.datetime.get_today(),
			}],
			function (values) {
				frappe.call({
					method: "manufyxinvenzaerp.production_management.inspection.add_inspection_call",
					args: {
						source_doctype: "Purchase Receipt",
						source_name: frm.doc.name,
						call_date: values.call_date,
					},
					freeze: true,
					freeze_message: __("Logging inspection call…"),
					callback() {
						frappe.call({
							method: "manufyxinvenzaerp.production_management.inspection.create_inspection_entry",
							args: { source_doctype: "Purchase Receipt", source_name: frm.doc.name },
							freeze: true,
							freeze_message: __("Creating Inspection Entry…"),
							callback(r) {
								frm.reload_doc();
								if (r.message) {
									frappe.set_route("Form", "Inspection Entry", r.message);
								}
							},
						});
					},
				});
			},
			__("Create Inspection"),
			__("Create")
		);
	},

	custom_update_inspection_call_date_btn(frm) {
		const { last } = _pr_inspection_state(frm);
		if (!last) return;

		frappe.prompt(
			[{
				fieldname: "call_date",
				fieldtype: "Date",
				label: __("Inspection Call Date"),
				reqd: 1,
				default: last.call_date,
			}],
			function (values) {
				frappe.call({
					method: "manufyxinvenzaerp.production_management.inspection.update_inspection_call_date",
					args: {
						source_doctype: "Purchase Receipt",
						source_name: frm.doc.name,
						call_date: values.call_date,
					},
					freeze: true,
					callback() {
						frm.reload_doc();
					},
				});
			},
			__("Update Inspection Call Date"),
			__("Update")
		);
	},
});

// After PR submission: show popup if any batches were auto-allocated to Material Planning
frappe.ui.form.on("Purchase Receipt", {
	after_submit(frm) {
		frappe.call({
			method: "manufyxinvenzaerp.purchase_receipt_management.purchase_receipt.get_pr_mp_allocations",
			args: { pr_name: frm.doc.name },
			callback(r) {
				let allocs = r.message || [];
				if (!allocs.length) return;

				// Group by Material Planning for a clean display
				let by_mp = {};
				allocs.forEach(function(a) {
					if (!by_mp[a.material_planning]) by_mp[a.material_planning] = [];
					by_mp[a.material_planning].push(a);
				});

				// Allocated is NOT the same as reserved -- allocate_pr_stock_to_mp only
				// places the batch into Available Raw Materials / Material Mapping;
				// reserving it is still a separate, manual step on the Material
				// Planning, and nothing transfers via a Material Issue Plan until that
				// happens (_get_mp_reserved_batches only ever offers is_reserved=1 rows
				// for transfer). Say exactly that instead of claiming it's ready.
				let sections = Object.entries(by_mp).map(function([mp, rows]) {
					let mp_safe = frappe.utils.escape_html(mp);
					let mp_link = `<a href="/app/material-planning/${encodeURIComponent(mp)}" target="_blank"><b>${mp_safe}</b></a>`;
					let row_html = rows.map(function(r) {
						return `<tr>
							<td style="padding:3px 6px">${frappe.utils.escape_html(String(r.batch_no == null ? "" : r.batch_no))}</td>
							<td style="padding:3px 6px">${frappe.utils.escape_html(String(r.item_code == null ? "" : r.item_code))}</td>
							<td style="padding:3px 6px;text-align:right">${flt(r.qty, 3)} Kg</td>
							<td style="padding:3px 6px">${r.is_reserved ? __("Reserved") : __("Not Reserved Yet")}</td>
						</tr>`;
					}).join("");
					return `<p style="margin:10px 0 4px">Material Planning: ${mp_link}</p>
						<table class="table table-bordered table-condensed" style="font-size:11px;margin-bottom:4px">
							<thead><tr>
								<th>${__("Batch No")}</th>
								<th>${__("Item Code")}</th>
								<th>${__("Qty")}</th>
								<th>${__("Status")}</th>
							</tr></thead>
							<tbody>${row_html}</tbody>
						</table>`;
				}).join("");

				let any_unreserved = allocs.some(function(a) { return !a.is_reserved; });

				frappe.msgprint({
					title: __("Material Planning — Batches Allocated"),
					indicator: any_unreserved ? "orange" : "green",
					message: `<p>${__("Received batches from this Purchase Receipt have been allocated against the following Material Planning document(s):")}</p>`
						+ sections
						+ (any_unreserved
							? `<p style="margin-top:8px;color:#555">${__("Open the Material Planning and Reserve the batch(es) marked \"Not Reserved Yet\" before they can be used in a Material Issue Plan / transferred — unreserved batches are never offered for transfer.")}</p>`
							: `<p style="margin-top:8px;color:#555">${__("These batches are already reserved and ready for transfer in the linked Material Issue Plan.")}</p>`),
				});
			},
		});
	},
});
