frappe.ui.form.on("Batch", {
	refresh(frm) {
		if (frm.is_new()) return;
		_render_reservations(frm);
	},
});

function _render_reservations(frm) {
	let $wrapper = $(frm.fields_dict.custom_reservations_html.wrapper);
	$wrapper.html(
		`<p class="text-muted" style="margin:8px 0;">${__("Loading reservations…")}</p>`
	);

	frappe.call({
		method: "manufyxinvenzaerp.production_management.doctype.material_planning.material_planning.get_batch_reservation_summary",
		args: { batch_no: frm.doc.name },
		callback(r) {
			let rows = r.message || [];

			if (!rows.length) {
				$wrapper.html(
					`<p class="text-muted" style="margin:8px 0;font-style:italic;">${__("No active reservations for this batch.")}</p>`
				);
				return;
			}

			let total_reserved = rows.reduce(function(sum, row) {
				return sum + flt(row.reserved_qty);
			}, 0);

			let th = function(label) {
				return `<th style="padding:6px 10px;background:#f4f5f7;white-space:nowrap;font-size:12px;border-bottom:2px solid #d1d8dd;">${__(label)}</th>`;
			};
			let td = function(val, style) {
				return `<td style="padding:5px 10px;white-space:nowrap;font-size:12px;border-bottom:1px solid #f0f0f0;${style || ""}">${frappe.utils.escape_html(String(val == null ? "" : val))}</td>`;
			};

			let tbody = rows.map(function(row, idx) {
				let bg = idx % 2 !== 0 ? "background:#fafbfc;" : "";
				return `<tr style="${bg}">
					${td(row.mp_name)}
					${td(row.item_code)}
					${td(row.item_name)}
					${td(row.sales_order)}
					${td(row.customer)}
					${td(flt(row.reserved_qty, 3), "font-weight:600;")}
				</tr>`;
			}).join("");

			let html = `
				<div style="margin:8px 0;">
					<div style="overflow:auto;">
						<table style="border-collapse:collapse;width:100%;font-size:12px;">
							<thead>
								<tr>
									${th("Material Planning")}
									${th("Item Code")}
									${th("Item Name")}
									${th("Sales Order")}
									${th("Customer")}
									${th("Reserved Qty")}
								</tr>
							</thead>
							<tbody>${tbody}</tbody>
							<tfoot>
								<tr>
									<td colspan="5" style="padding:6px 10px;font-size:12px;font-weight:600;background:#f4f5f7;border-top:2px solid #d1d8dd;text-align:right;">
										${__("Total Reserved")}
									</td>
									<td style="padding:6px 10px;font-size:12px;font-weight:700;background:#f4f5f7;border-top:2px solid #d1d8dd;color:#d44;">
										${flt(total_reserved, 3)}
									</td>
								</tr>
							</tfoot>
						</table>
					</div>
				</div>`;

			$wrapper.html(html);
		},
	});
}
