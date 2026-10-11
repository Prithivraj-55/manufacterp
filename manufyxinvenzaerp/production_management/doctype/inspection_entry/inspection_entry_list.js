frappe.listview_settings["Inspection Entry"] = {
	add_fields: ["status", "docstatus"],
	has_indicator_for_draft: 1,
	get_indicator(doc) {
		const colour = {
			Open: "red",
			Working: "orange",
			"Partly Completed": "yellow",
			Completed: "green",
		};
		return [__(doc.status), colour[doc.status] || "gray", "status,=," + doc.status];
	},
};
