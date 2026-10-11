// Storage Location pickers on the stock forms (server: stock_management/storage_location.py).
//
// Going IN to a warehouse the picker lists where the item may be put: the item's own
// Storage Locations for that warehouse, or every location of the warehouse when the
// item lists none. Going OUT it lists only the locations holding the item -- or the
// row's batch -- with the quantity in each. An inward row is filled with the item's
// default as soon as item and warehouse are known.
//
// The server fills what it can on save and refuses submit while a location is missing
// in a warehouse whose type needs one, so these are conveniences, not the rule.

function inward_query(item_code, warehouse) {
	return { query: "manufyxinvenzaerp.stock_management.storage_location.inward_location_query", filters: { item_code, warehouse } };
}

function outward_query(item_code, warehouse, batch_no) {
	return { query: "manufyxinvenzaerp.stock_management.storage_location.outward_location_query", filters: { item_code, warehouse, batch_no } };
}

function fill_default(cdt, cdn, field, warehouse) {
	const row = locals[cdt][cdn];
	if (!row.item_code || !warehouse || row[field]) return;
	frappe.call({
		method: "manufyxinvenzaerp.stock_management.storage_location.get_default_location",
		args: { item_code: row.item_code, warehouse },
		callback(r) {
			if (r.message && !locals[cdt][cdn][field]) {
				frappe.model.set_value(cdt, cdn, field, r.message);
			}
		},
	});
}

// ── Stock Entry: storage_location = source, to_storage_location = target ─────────

frappe.ui.form.on("Stock Entry", {
	onload(frm) {
		frm.set_query("storage_location", "items", (doc, cdt, cdn) => {
			const row = locals[cdt][cdn];
			return outward_query(row.item_code, row.s_warehouse, row.batch_no);
		});
		frm.set_query("to_storage_location", "items", (doc, cdt, cdn) => {
			const row = locals[cdt][cdn];
			return inward_query(row.item_code, row.t_warehouse);
		});
	},
});

frappe.ui.form.on("Stock Entry Detail", {
	item_code(frm, cdt, cdn) {
		fill_default(cdt, cdn, "to_storage_location", locals[cdt][cdn].t_warehouse);
	},
	t_warehouse(frm, cdt, cdn) {
		frappe.model.set_value(cdt, cdn, "to_storage_location", null);
		fill_default(cdt, cdn, "to_storage_location", locals[cdt][cdn].t_warehouse);
	},
	s_warehouse(frm, cdt, cdn) {
		frappe.model.set_value(cdt, cdn, "storage_location", null);
	},
});

// ── Purchase Receipt: storage_location (and rejected_storage_location) ───────────

frappe.ui.form.on("Purchase Receipt", {
	onload(frm) {
		frm.set_query("storage_location", "items", (doc, cdt, cdn) => {
			const row = locals[cdt][cdn];
			return doc.is_return
				? outward_query(row.item_code, row.warehouse, row.batch_no)
				: inward_query(row.item_code, row.warehouse);
		});
		frm.set_query("rejected_storage_location", "items", (doc, cdt, cdn) => {
			const row = locals[cdt][cdn];
			return inward_query(row.item_code, row.rejected_warehouse);
		});
	},
});

frappe.ui.form.on("Purchase Receipt Item", {
	item_code(frm, cdt, cdn) {
		if (!frm.doc.is_return) fill_default(cdt, cdn, "storage_location", locals[cdt][cdn].warehouse);
	},
	warehouse(frm, cdt, cdn) {
		if (frm.doc.is_return) return;
		frappe.model.set_value(cdt, cdn, "storage_location", null);
		fill_default(cdt, cdn, "storage_location", locals[cdt][cdn].warehouse);
	},
});

// ── Delivery Note: storage_location is where the goods leave from ───────────────

frappe.ui.form.on("Delivery Note", {
	onload(frm) {
		frm.set_query("storage_location", "items", (doc, cdt, cdn) => {
			const row = locals[cdt][cdn];
			return doc.is_return
				? inward_query(row.item_code, row.warehouse)
				: outward_query(row.item_code, row.warehouse, row.batch_no);
		});
	},
});

// ── Item: its Storage Locations table lists each warehouse's own locations ───────

frappe.ui.form.on("Item", {
	onload(frm) {
		frm.set_query("storage_location", "custom_storage_locations", (doc, cdt, cdn) => ({
			filters: { warehouse: locals[cdt][cdn].warehouse || "" },
		}));
	},
});

frappe.ui.form.on("Item Storage Location", {
	warehouse(frm, cdt, cdn) {
		frappe.model.set_value(cdt, cdn, "storage_location", null);
	},
	is_default(frm, cdt, cdn) {
		// One default per warehouse: ticking one clears the others of that warehouse.
		const row = locals[cdt][cdn];
		if (!row.is_default) return;
		(frm.doc.custom_storage_locations || []).forEach((other) => {
			if (other.name !== row.name && other.warehouse === row.warehouse && other.is_default) {
				frappe.model.set_value(other.doctype, other.name, "is_default", 0);
			}
		});
	},
});
