// Cut Sheet — client script.
//
// Item Code, Item Name, Item Group and Unit Weight all describe the batch being
// cut, so they follow FROM the batch rather than being picked independently — the
// server already refuses a batch/item mismatch (_fetch_batch_dimensions). Item Name
// / Parent Item Group / Unit Weight already cascade automatically once item_code is
// set (fetch_from: item_code.xxx in the doctype); this script's job is only to set
// item_code itself, and to preview the batch's own Length/Width/Thickness/Sec Qty
// immediately rather than leaving that whole section blank until the first Save.

frappe.ui.form.on("Cut Sheet", {
	batch_no(frm) {
		if (!frm.doc.batch_no) {
			frm.set_value("sheet_length", 0);
			frm.set_value("sheet_width", 0);
			frm.set_value("sheet_thickness", 0);
			frm.set_value("sheet_sec_qty", 0);
			return;
		}

		frappe.db.get_value(
			"Batch",
			frm.doc.batch_no,
			["item", "custom_length", "custom_width", "custom_thickness", "custom_sec_qty"],
			(r) => {
				if (!r) return;
				if (r.item) frm.set_value("item_code", r.item);
				// Preview only -- validate() re-fetches these from the batch itself on
				// save regardless, so a stale value here can never actually be saved.
				frm.set_value("sheet_length", flt(r.custom_length));
				frm.set_value("sheet_width", flt(r.custom_width));
				frm.set_value("sheet_thickness", flt(r.custom_thickness));
				frm.set_value("sheet_sec_qty", flt(r.custom_sec_qty));
			}
		);
	},
});
