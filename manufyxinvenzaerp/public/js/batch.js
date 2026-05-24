frappe.ui.form.on("Batch", {
	refresh(frm) {
		if (frm.is_new()) return;

		frm.add_custom_button(__("View Reservations"), function () {
			frappe.call({
				method: "manufyxinvenzaerp.production_management.doctype.material_planning.material_planning.get_batch_reservation_summary",
				args: { batch_no: frm.doc.name },
				freeze: true,
				freeze_message: __("Loading reservations…"),
				callback(r) {
					let rows = r.message || [];
					if (!rows.length) {
						frappe.msgprint({
							title: __("Reservations"),
							indicator: "green",
							message: __("No active reservations for this batch."),
						});
						return;
					}

					let total_reserved = rows.reduce(function (sum, row) {
						return sum + (flt(row.reserved_qty) || 0);
					}, 0);

					let th = function (label) {
						return `<th style="padding:6px 10px;background:#f4f5f7;white-space:nowrap;">${__(label)}</th>`;
					};
					let td = function (val) {
						return `<td style="padding:5px 10px;white-space:nowrap;">${frappe.utils.escape_html(String(val || ""))}</td>`;
					};

					let tbody = rows.map(function (row) {
						return `<tr>
							${td(row.mp_name)}
							${td(row.sales_order)}
							${td(row.customer)}
							${td(row.project)}
							${td(flt(row.reserved_qty, 3))}
						</tr>`;
					}).join("");

					let html = `
						<p style="margin-bottom:8px;">
							<b>${__("Total Reserved Qty:")} ${flt(total_reserved, 3)}</b>
						</p>
						<div style="overflow:auto;max-height:60vh;">
							<table class="table table-bordered table-condensed" style="font-size:12px;margin:0;">
								<thead>
									<tr>
										${th("Material Planning")}
										${th("Sales Order")}
										${th("Customer")}
										${th("Project")}
										${th("Reserved Qty")}
									</tr>
								</thead>
								<tbody>${tbody}</tbody>
							</table>
						</div>`;

					frappe.msgprint({
						title: __("Reservations — {0}", [frm.doc.name]),
						indicator: "orange",
						message: html,
					});
				},
			});
		}, __("Stock"));
	},
});
