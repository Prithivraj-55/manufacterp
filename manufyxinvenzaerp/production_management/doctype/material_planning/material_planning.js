frappe.ui.form.on("Material Planning", {

	refresh(frm) {
		// "Get Raw Materials" — always visible in draft
		if (frm.doc.docstatus === 0) {
			frm.add_custom_button(__("Get Raw Materials"), function () {
				if (!frm.doc.bom_items || !frm.doc.bom_items.length) {
					frappe.msgprint(__("Add at least one BOM in the 'Selected BOMs' tab first."));
					return;
				}
				if (!frm.doc.company) {
					frappe.msgprint(__("Set Company before fetching raw materials."));
					return;
				}
				frappe.call({
					method: "manufyxinvenzaerp.production_management.doctype.material_planning.material_planning.get_raw_materials",
					args: { doc: frm.doc },
					freeze: true,
					freeze_message: __("Exploding BOMs…"),
					callback(r) {
						if (!r.message) return;
						frm.clear_table("raw_materials");
						(r.message || []).forEach(function (row) {
							let child = frm.add_child("raw_materials");
							Object.keys(row).forEach(function (k) {
								if (k !== "name") child[k] = row[k];
							});
						});
						frm.refresh_field("raw_materials");
						frappe.show_alert({
							message: __("{0} raw material row(s) loaded.", [r.message.length]),
							indicator: "green",
						}, 5);
					},
				});
			});
		}

		// "Check Stock Availability" — visible when raw_materials table has rows
		if (frm.doc.docstatus === 0 && (frm.doc.raw_materials || []).length) {
			frm.add_custom_button(__("Check Stock Availability"), function () {
				if (!frm.doc.for_warehouse) {
					frappe.msgprint(__("Set 'Raw Materials Warehouse' in Production Settings first."));
					return;
				}
				frappe.call({
					method: "manufyxinvenzaerp.production_management.doctype.material_planning.material_planning.check_stock_availability",
					args: { doc: frm.doc },
					freeze: true,
					freeze_message: __("Checking stock…"),
					callback(r) {
						if (!r.message) return;
						frm.clear_table("raw_materials");
						(r.message || []).forEach(function (row) {
							let child = frm.add_child("raw_materials");
							Object.keys(row).forEach(function (k) {
								if (k !== "name") child[k] = row[k];
							});
						});
						frm.refresh_field("raw_materials");
						frappe.show_alert({
							message: __("Stock availability updated."),
							indicator: "green",
						}, 4);
					},
				});
			});
		}

		// "Create → Production Plan" — available in draft and submitted states
		if (frm.doc.docstatus !== 2) {
			frm.add_custom_button(__("Production Plan"), function () {
				if (!frm.doc.bom_items || !frm.doc.bom_items.length) {
					frappe.msgprint(__("Add at least one BOM in the 'Selected BOMs' tab first."));
					return;
				}
				if (frm.doc.__islocal) {
					frappe.msgprint(__("Save the document before creating a Production Plan."));
					return;
				}

				function _do_create() {
					frappe.call({
						method: "manufyxinvenzaerp.production_management.doctype.material_planning.material_planning.make_production_plan",
						args: { material_planning_name: frm.doc.name },
						freeze: true,
						freeze_message: __("Creating Production Plan…"),
						callback(r) {
							if (r.message) {
								frappe.show_alert({
									message: __("Production Plan {0} created.", [r.message]),
									indicator: "green",
								}, 5);
								frappe.set_route("Form", "Production Plan", r.message);
							}
						},
					});
				}

				frappe.confirm(
					__("Create a Production Plan from this Material Planning?"),
					function () {
						// Draft docs: save unsaved changes before reading from DB on server
						if (frm.doc.docstatus === 0 && frm.is_dirty()) {
							frappe.call({
								method: "frappe.client.save",
								args: { doc: frm.doc },
								freeze: true,
								freeze_message: __("Saving…"),
								callback(r) {
									if (r.message) {
										frappe.model.sync(r.message);
										frm.refresh();
									}
									_do_create();
								},
							});
						} else {
							_do_create();
						}
					}
				);
			}, __("Create"));
		}
	},
});

// Auto-fill BOM row details from the linked Drawing when bom_no is set
frappe.ui.form.on("Material Planning BOM Item", {
	bom_no(frm, cdt, cdn) {
		let row = locals[cdt][cdn];
		if (!row.bom_no) return;
		frappe.call({
			method: "manufyxinvenzaerp.production_management.doctype.material_planning.material_planning.get_bom_info",
			args: { bom_no: row.bom_no },
			callback(r) {
				if (!r.message) return;
				let d = r.message;
				frappe.model.set_value(cdt, cdn, "item_code",          d.item_code || "");
				frappe.model.set_value(cdt, cdn, "item_name",          d.item_name || "");
				frappe.model.set_value(cdt, cdn, "drawing",            d.drawing || "");
				frappe.model.set_value(cdt, cdn, "duno_mark_no",       d.duno_mark_no || 0);
				frappe.model.set_value(cdt, cdn, "sales_order",        d.sales_order || "");
				frappe.model.set_value(cdt, cdn, "customer",           d.customer || "");
				frappe.model.set_value(cdt, cdn, "qty_to_manufacture", d.qty_to_manufacture || 0);
				frappe.model.set_value(cdt, cdn, "uom",                d.uom || "");
			},
		});
	},
});
