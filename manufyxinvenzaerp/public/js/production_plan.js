frappe.ui.form.on('Production Plan', {
    refresh(frm) {
        if (
            frm.doc.mr_items?.length &&
            !["Material Requested", "Closed"].includes(frm.doc.status) && frm.doc.docstatus == 1
        ) {
            // Remove default button
            frm.page.remove_inner_button("Material Request", "Create");

            // Add custom button
            frm.add_custom_button("Material Requests", () => {
                frappe.confirm(
                    "Do you want to submit the material request?",
                    () => create_material_request(frm, 1),
                    () => create_material_request(frm, 0)
                );
            }, "Create");
        }
    },
    custom_get_raw_materials_for_purchase(frm) {
        if (!frm.doc.for_warehouse) {
            frm.trigger("toggle_for_warehouse");
            frappe.throw(__("Select the Warehouse"));
        }

        frm.events.get_items_for_material_requests(frm, [
            {
                warehouse: frm.doc.for_warehouse,
            },
        ]);
    },
    get_items_for_material_requests(frm, warehouses) {
        frappe.call({
            method: "manufyxinvenzaerp.production_plan_management.production_plan.get_items_for_material_requests",
            freeze: true,
            args: {
                doc: frm.doc,
                warehouses: warehouses || [],
            },
            callback: function (r) {
                if (r.message) {
                    frm.set_value("mr_items", []);
                    r.message.forEach((row) => {
                        let d = frm.add_child("mr_items");
                        for (let field in row) {
                            if (field !== "name") {
                                d[field] = row[field];
                            }
                        }
                    });
                }
                refresh_field("mr_items");
            },
        });
    },
});

function create_material_request(frm, submit) {
    frappe.call({
        method: "manufyxinvenzaerp.production_plan_management.production_plan.make_material_request",
        args: {
            doc: frm.doc.name,
            submit: submit
        },
        freeze: true,
        callback: () => frm.reload_doc()
    });
}