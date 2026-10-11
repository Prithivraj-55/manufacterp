// Operation Entry list (client, Oct 2026): the full Job Work Order number, and the
// entry's own Status (Open / In Progress / Completed) as its indicator.
frappe.listview_settings["Supplier Operation Entry"] = {
	add_fields: ["status", "docstatus"],
	has_indicator_for_draft: 1,
	get_indicator(doc) {
		const colour = { Open: "red", "In Progress": "orange", Completed: "green" };
		return [__(doc.status), colour[doc.status] || "gray", "status,=," + doc.status];
	},
	refresh(listview) {
		// A Job Work Order number is ~17 characters and the default column clips it
		// ("SC-ORD-2026-00…"), so that one column is given the room it needs.
		const widen = ($col) => $col.removeClass("ellipsis").css({ flex: "0 0 170px", "white-space": "nowrap" });
		widen(listview.$result.find(".list-row-head .list-row-col").filter(function () {
			return $(this).text().trim() === __("Job Work Order");
		}));
		listview.$result.find(".list-row .list-row-col").each(function () {
			const $col = $(this);
			if ($col.find('[data-filter^="subcontracting_order,"]').length) {
				widen($col);
				$col.find(".ellipsis").removeClass("ellipsis");
			}
		});
	},
};
