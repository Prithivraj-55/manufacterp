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

				let sections = Object.entries(by_mp).map(function([mp, rows]) {
					let mp_safe = frappe.utils.escape_html(mp);
					let mp_link = `<a href="/app/material-planning/${encodeURIComponent(mp)}" target="_blank"><b>${mp_safe}</b></a>`;
					let row_html = rows.map(function(r) {
						return `<tr>
							<td style="padding:3px 6px">${frappe.utils.escape_html(String(r.batch_no == null ? "" : r.batch_no))}</td>
							<td style="padding:3px 6px">${frappe.utils.escape_html(String(r.item_code == null ? "" : r.item_code))}</td>
							<td style="padding:3px 6px;text-align:right">${flt(r.reserved_qty, 3)} Kg</td>
						</tr>`;
					}).join("");
					return `<p style="margin:10px 0 4px">Material Planning: ${mp_link}</p>
						<table class="table table-bordered table-condensed" style="font-size:11px;margin-bottom:4px">
							<thead><tr>
								<th>${__("Batch No")}</th>
								<th>${__("Item Code")}</th>
								<th>${__("Reserved Qty")}</th>
							</tr></thead>
							<tbody>${row_html}</tbody>
						</table>`;
				}).join("");

				frappe.msgprint({
					title: __("Material Planning — Batch Reserved"),
					indicator: "green",
					message: `<p>${__("The batches from this Purchase Receipt have been automatically allocated and reserved against the following Material Planning document(s):")}</p>`
						+ sections
						+ `<p style="margin-top:8px;color:#555">${__("These batches are now ready for transfer in the linked Material Issue Plan.")}</p>`,
				});
			},
		});
	},
});
