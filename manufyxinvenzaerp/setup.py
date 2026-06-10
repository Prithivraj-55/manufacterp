import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

CLIENT_SCRIPT_NAME = "Item-parent-item-group-filter"
PO_CLIENT_SCRIPT_NAME = "Purchase Order-custom-po-item-logic"
PR_CLIENT_SCRIPT_NAME = "Purchase Receipt-custom-pr-item-logic"
MR_CLIENT_SCRIPT_NAME = "Material Request-custom-mr-item-logic"
RFQ_CLIENT_SCRIPT_NAME = "Request for Quotation-custom-rfq-item-logic"
SQ_CLIENT_SCRIPT_NAME = "Supplier Quotation-custom-sq-item-logic"
SO_CLIENT_SCRIPT_NAME = "Sales Order-create-drawing-button"

BOM_CLIENT_SCRIPT_NAME = "BOM-create-production-plan-button"
PRODUCTION_PLAN_CLIENT_SCRIPT_NAME = "Production Plan-subcontracting-plan-logic"
JOB_CARD_CLIENT_SCRIPT_NAME = "Job Card-raw-material-consumption-logic"
STOCK_ENTRY_CLIENT_SCRIPT_NAME = "Stock Entry-dimensional-weight-logic"
SCO_CLIENT_SCRIPT_NAME = "Subcontracting Order-soe-buttons"
SOE_CLIENT_SCRIPT_NAME = "Supplier Operation Entry-consumption-logic"

BOM_CLIENT_SCRIPT = """
frappe.ui.form.on("BOM", {
\trefresh(frm) {
\t\tif (frm.doc.docstatus === 1 && frm.doc.custom_drawing) {
\t\t\tfrm.remove_custom_button(__("Work Order"), __("Create"));
\t\t\tfrm.add_custom_button(__("Production Plan"), function () {
\t\t\t\tfrappe.confirm(
\t\t\t\t\t__("Create a Production Plan for <b>" + (frm.doc.item_name || frm.doc.item) + "</b>?"),
\t\t\t\t\tfunction () {
\t\t\t\t\t\tfrappe.call({
\t\t\t\t\t\t\tmethod: "manufyxinvenzaerp.drawing_management.drawing_utils.create_production_plan_from_bom",
\t\t\t\t\t\t\targs: { bom_name: frm.doc.name },
\t\t\t\t\t\t\tfreeze: true,
\t\t\t\t\t\t\tcallback: function (r) {
\t\t\t\t\t\t\t\tif (r.message) {
\t\t\t\t\t\t\t\t\tfrappe.msgprint({
\t\t\t\t\t\t\t\t\t\ttitle: __("Production Plan Created"),
\t\t\t\t\t\t\t\t\t\tmessage: __("Production Plan created") + ': <a href="/app/production-plan/' + encodeURIComponent(r.message) + '" target="_blank">' + r.message + '</a>',
\t\t\t\t\t\t\t\t\t\tindicator: "green",
\t\t\t\t\t\t\t\t\t});
\t\t\t\t\t\t\t\t}
\t\t\t\t\t\t\t},
\t\t\t\t\t\t});
\t\t\t\t\t}
\t\t\t\t);
\t\t\t}, __("Create"));
\t\t}
\t},
});
""".strip()

CLIENT_SCRIPT = """
frappe.ui.form.on("Item", {
\trefresh(frm) {
\t\t// Null link_filters so apply_link_field_filters() is skipped on dropdown open
\t\tfrm.fields_dict.item_group.df.link_filters = null;
\t\tfrm.set_query("item_group", function() {
\t\t\tvar filters = [["Item Group", "is_group", "=", 0]];
\t\t\tif (frm.doc.custom_parent_item_group) {
\t\t\t\tfilters.push(["Item Group", "parent_item_group", "=", frm.doc.custom_parent_item_group]);
\t\t\t}
\t\t\treturn { filters: filters };
\t\t});
\t\tfrm.set_query("custom_parent_item_group", function() {
\t\t\treturn { filters: { is_group: 1 } };
\t\t});
\t\tfrm.set_df_property("custom_item_calculation_type", "read_only", 1);
\t},
\tcustom_parent_item_group(frm) {
\t\tvar group = frm.doc.custom_parent_item_group;
\t\tif (["Structurals", "Plates"].includes(group)) {
\t\t\tfrm.set_value("custom_item_calculation_type", "Formula Weight Calculation");
\t\t} else if (group) {
\t\t\tfrm.set_value("custom_item_calculation_type", "Normal Weight Calculation");
\t\t}
\t\tfrm.set_value("item_group", "");
\t}
});
""".strip()

PO_CLIENT_SCRIPT = """
frappe.ui.form.on("Purchase Order", {
\trefresh(frm) {
\t\tfrm.set_query("uom", "items", function(doc, cdt, cdn) {
\t\t\tvar row = locals[cdt][cdn];
\t\t\treturn {
\t\t\t\tquery: "manufyxinvenzaerp.purchase_order_management.purchase_order.get_po_item_uom",
\t\t\t\tfilters: { item_code: row.item_code }
\t\t\t};
\t\t});
\t}
});

frappe.ui.form.on("Purchase Order Item", {
\titem_code(frm, cdt, cdn) {
\t\tsetTimeout(function() {
\t\t\tcalculate_qty(frm, cdt, cdn);
\t\t\tpo_toggle_dims(frm, cdt, cdn);
\t\t}, 600);
\t},
\tqty(frm, cdt, cdn) {
\t\tvar row = locals[cdt][cdn];
\t\tif (row.custom_parent_item_group === "Nuts and Bolts") {
\t\t\tcalculate_qty(frm, cdt, cdn);
\t\t}
\t},
\tcustom_length(frm, cdt, cdn) { calculate_qty(frm, cdt, cdn); },
\tcustom_width(frm, cdt, cdn) { calculate_qty(frm, cdt, cdn); },
\tcustom_thickness(frm, cdt, cdn) { calculate_qty(frm, cdt, cdn); },
\tcustom_sec_qty(frm, cdt, cdn) { calculate_qty(frm, cdt, cdn); },
\tcustom_unit_weight(frm, cdt, cdn) { calculate_qty(frm, cdt, cdn); },
\tform_render(frm, cdt, cdn) { po_toggle_dims(frm, cdt, cdn); },
\tuom(frm, cdt, cdn) {
\t\tvar row = locals[cdt][cdn];
\t\tif (row.uom && row.stock_uom && row.uom !== row.stock_uom) {
\t\t\tfrappe.msgprint({
\t\t\t\tmessage: "Weight is entered for Stock UOM, Kindly update UOM Weight in item master for correct calculation",
\t\t\t\tindicator: "orange",
\t\t\t\ttitle: "UOM Warning"
\t\t\t});
\t\t}
\t}
});

function po_toggle_dims(frm, cdt, cdn) {
\tvar row = locals[cdt][cdn];
\tvar group = row.custom_parent_item_group;
\tvar show_len   = group === "Structurals" || group === "Plates";
\tvar show_thick = group === "Plates";
\t$.each(frm.fields_dict["items"].grid.grid_rows, function(i, gr) {
\t\tif (gr.doc && gr.doc.name === cdn && gr.grid_form) {
\t\t\tgr.grid_form.toggle_display("custom_length",    show_len);
\t\t\tgr.grid_form.toggle_display("custom_thickness", show_thick);
\t\t\tgr.grid_form.toggle_display("custom_width",     show_thick);
\t\t}
\t});
}

function calculate_qty(frm, cdt, cdn) {
\tvar row = locals[cdt][cdn];
\tvar group = row.custom_parent_item_group;

\tif (group === "Structurals") {
\t\tif (row.custom_length && row.custom_unit_weight && row.custom_sec_qty) {
\t\t\tfrappe.model.set_value(cdt, cdn, "qty", flt((row.custom_length / 1000) * row.custom_unit_weight * row.custom_sec_qty, 3));
\t\t} else {
\t\t\twarn_missing_fields(row, group);
\t\t}
\t} else if (group === "Plates") {
\t\tif (row.custom_length && row.custom_width && row.custom_thickness && row.custom_unit_weight && row.custom_sec_qty) {
\t\t\tfrappe.model.set_value(cdt, cdn, "qty", flt((row.custom_length / 1000) * (row.custom_width / 1000) * row.custom_thickness * row.custom_unit_weight * row.custom_sec_qty, 3));
\t\t} else {
\t\t\twarn_missing_fields(row, group);
\t\t}
\t} else if (group === "Nuts and Bolts") {
\t\tif (row.qty && row.custom_unit_weight) {
\t\t\tvar new_sec = flt(row.qty * row.custom_unit_weight, 3);
\t\t\tif (flt(row.custom_sec_qty, 3) !== new_sec) {
\t\t\t\tfrappe.model.set_value(cdt, cdn, "custom_sec_qty", new_sec);
\t\t\t}
\t\t}
\t}
}

function warn_missing_fields(row, group) {
\tvar missing = [];
\tif (group === "Structurals") {
\t\tif (!row.custom_length) missing.push("Length");
\t\tif (!row.custom_unit_weight) missing.push("Unit Weight");
\t\tif (!row.custom_sec_qty) missing.push("Sec Qty");
\t} else if (group === "Plates") {
\t\tif (!row.custom_length) missing.push("Length");
\t\tif (!row.custom_width) missing.push("Width");
\t\tif (!row.custom_thickness) missing.push("Thickness");
\t\tif (!row.custom_unit_weight) missing.push("Unit Weight");
\t\tif (!row.custom_sec_qty) missing.push("Sec Qty");
\t}
\tif (missing.length) {
\t\tfrappe.show_alert({
\t\t\tmessage: "Row " + row.idx + ": Missing for " + group + " formula: " + missing.join(", "),
\t\t\tindicator: "orange"
\t\t});
\t}
}
""".strip()

PR_CLIENT_SCRIPT = """
frappe.ui.form.on("Purchase Receipt", {
\trefresh(frm) {
\t\tfrm.set_query("uom", "items", function(doc, cdt, cdn) {
\t\t\tvar row = locals[cdt][cdn];
\t\t\treturn {
\t\t\t\tquery: "manufyxinvenzaerp.purchase_receipt_management.purchase_receipt.get_pr_item_uom",
\t\t\t\tfilters: { item_code: row.item_code }
\t\t\t};
\t\t});
\t}
});

frappe.ui.form.on("Purchase Receipt Item", {
\titem_code(frm, cdt, cdn) {
\t\tsetTimeout(function() {
\t\t\tpr_calculate_qty(frm, cdt, cdn);
\t\t\tpr_toggle_dims(frm, cdt, cdn);
\t\t}, 600);
\t},
\tqty(frm, cdt, cdn) {
\t\tvar row = locals[cdt][cdn];
\t\tif (row.custom_parent_item_group === "Nuts and Bolts") {
\t\t\tpr_calculate_qty(frm, cdt, cdn);
\t\t}
\t},
\tcustom_length(frm, cdt, cdn) { pr_calculate_qty(frm, cdt, cdn); },
\tcustom_width(frm, cdt, cdn) { pr_calculate_qty(frm, cdt, cdn); },
\tcustom_thickness(frm, cdt, cdn) { pr_calculate_qty(frm, cdt, cdn); },
\tcustom_sec_qty(frm, cdt, cdn) { pr_calculate_qty(frm, cdt, cdn); },
\tcustom_unit_weight(frm, cdt, cdn) { pr_calculate_qty(frm, cdt, cdn); },
\tform_render(frm, cdt, cdn) { pr_toggle_dims(frm, cdt, cdn); },
\tuom(frm, cdt, cdn) {
\t\tvar row = locals[cdt][cdn];
\t\tif (row.uom && row.stock_uom && row.uom !== row.stock_uom) {
\t\t\tfrappe.msgprint({
\t\t\t\tmessage: "Weight is entered for Stock UOM, Kindly update UOM Weight in item master for correct calculation",
\t\t\t\tindicator: "orange",
\t\t\t\ttitle: "UOM Warning"
\t\t\t});
\t\t}
\t}
});

function pr_toggle_dims(frm, cdt, cdn) {
\tvar row = locals[cdt][cdn];
\tvar group = row.custom_parent_item_group;
\tvar show_len   = group === "Structurals" || group === "Plates";
\tvar show_thick = group === "Plates";
\t$.each(frm.fields_dict["items"].grid.grid_rows, function(i, gr) {
\t\tif (gr.doc && gr.doc.name === cdn && gr.grid_form) {
\t\t\tgr.grid_form.toggle_display("custom_length",    show_len);
\t\t\tgr.grid_form.toggle_display("custom_thickness", show_thick);
\t\t\tgr.grid_form.toggle_display("custom_width",     show_thick);
\t\t}
\t});
}

function pr_calculate_qty(frm, cdt, cdn) {
\tvar row = locals[cdt][cdn];
\tvar group = row.custom_parent_item_group;

\tif (group === "Structurals") {
\t\tif (row.custom_length && row.custom_unit_weight && row.custom_sec_qty) {
\t\t\tfrappe.model.set_value(cdt, cdn, "qty", flt((row.custom_length / 1000) * row.custom_unit_weight * row.custom_sec_qty, 3));
\t\t} else {
\t\t\tpr_warn_missing_fields(row, group);
\t\t}
\t} else if (group === "Plates") {
\t\tif (row.custom_length && row.custom_width && row.custom_thickness && row.custom_unit_weight && row.custom_sec_qty) {
\t\t\tfrappe.model.set_value(cdt, cdn, "qty", flt((row.custom_length / 1000) * (row.custom_width / 1000) * row.custom_thickness * row.custom_unit_weight * row.custom_sec_qty, 3));
\t\t} else {
\t\t\tpr_warn_missing_fields(row, group);
\t\t}
\t} else if (group === "Nuts and Bolts") {
\t\tif (row.qty && row.custom_unit_weight) {
\t\t\tvar new_sec = flt(row.qty * row.custom_unit_weight, 3);
\t\t\tif (flt(row.custom_sec_qty, 3) !== new_sec) {
\t\t\t\tfrappe.model.set_value(cdt, cdn, "custom_sec_qty", new_sec);
\t\t\t}
\t\t}
\t}
}

function pr_warn_missing_fields(row, group) {
\tvar missing = [];
\tif (group === "Structurals") {
\t\tif (!row.custom_length) missing.push("Length");
\t\tif (!row.custom_unit_weight) missing.push("Unit Weight");
\t\tif (!row.custom_sec_qty) missing.push("Sec Qty");
\t} else if (group === "Plates") {
\t\tif (!row.custom_length) missing.push("Length");
\t\tif (!row.custom_width) missing.push("Width");
\t\tif (!row.custom_thickness) missing.push("Thickness");
\t\tif (!row.custom_unit_weight) missing.push("Unit Weight");
\t\tif (!row.custom_sec_qty) missing.push("Sec Qty");
\t}
\tif (missing.length) {
\t\tfrappe.show_alert({
\t\t\tmessage: "Row " + row.idx + ": Missing for " + group + " formula: " + missing.join(", "),
\t\t\tindicator: "orange"
\t\t});
\t}
}
""".strip()

MR_CLIENT_SCRIPT = """
frappe.ui.form.on("Material Request", {
\trefresh(frm) {
\t\tfrm.set_query("uom", "items", function(doc, cdt, cdn) {
\t\t\tvar row = locals[cdt][cdn];
\t\t\treturn {
\t\t\t\tquery: "manufyxinvenzaerp.material_request_management.material_request.get_mr_item_uom",
\t\t\t\tfilters: { item_code: row.item_code }
\t\t\t};
\t\t});

\t\t// Skip the "Enter Supplier" prompt — go straight to Purchase Order
\t\tfrm.events.make_purchase_order = function(frm) {
\t\t\tfrappe.model.open_mapped_doc({
\t\t\t\tmethod: "erpnext.stock.doctype.material_request.material_request.make_purchase_order",
\t\t\t\tfrm: frm,
\t\t\t\targs: { default_supplier: "" },
\t\t\t\trun_link_triggers: true,
\t\t\t});
\t\t};
\t}
});

frappe.ui.form.on("Material Request Item", {
\titem_code(frm, cdt, cdn) {
\t\tsetTimeout(function() {
\t\t\tmr_calculate_qty(frm, cdt, cdn);
\t\t\tmr_toggle_dims(frm, cdt, cdn);
\t\t}, 600);
\t},
\tqty(frm, cdt, cdn) {
\t\tvar row = locals[cdt][cdn];
\t\tif (row.custom_parent_item_group === "Nuts and Bolts") {
\t\t\tmr_calculate_qty(frm, cdt, cdn);
\t\t}
\t},
\tcustom_length(frm, cdt, cdn) { mr_calculate_qty(frm, cdt, cdn); },
\tcustom_width(frm, cdt, cdn) { mr_calculate_qty(frm, cdt, cdn); },
\tcustom_thickness(frm, cdt, cdn) { mr_calculate_qty(frm, cdt, cdn); },
\tcustom_sec_qty(frm, cdt, cdn) { mr_calculate_qty(frm, cdt, cdn); },
\tcustom_unit_weight(frm, cdt, cdn) { mr_calculate_qty(frm, cdt, cdn); },
\tform_render(frm, cdt, cdn) { mr_toggle_dims(frm, cdt, cdn); },
\tuom(frm, cdt, cdn) {
\t\tvar row = locals[cdt][cdn];
\t\tif (row.uom && row.stock_uom && row.uom !== row.stock_uom) {
\t\t\tfrappe.msgprint({
\t\t\t\tmessage: "Weight is entered for Stock UOM, Kindly update UOM Weight in item master for correct calculation",
\t\t\t\tindicator: "orange",
\t\t\t\ttitle: "UOM Warning"
\t\t\t});
\t\t}
\t}
});

function mr_toggle_dims(frm, cdt, cdn) {
\tvar row = locals[cdt][cdn];
\tvar group = row.custom_parent_item_group;
\tvar show_len   = group === "Structurals" || group === "Plates";
\tvar show_thick = group === "Plates";
\t$.each(frm.fields_dict["items"].grid.grid_rows, function(i, gr) {
\t\tif (gr.doc && gr.doc.name === cdn && gr.grid_form) {
\t\t\tgr.grid_form.toggle_display("custom_length",    show_len);
\t\t\tgr.grid_form.toggle_display("custom_thickness", show_thick);
\t\t\tgr.grid_form.toggle_display("custom_width",     show_thick);
\t\t}
\t});
}

function mr_calculate_qty(frm, cdt, cdn) {
\tvar row = locals[cdt][cdn];
\tvar group = row.custom_parent_item_group;

\tif (group === "Structurals") {
\t\tif (row.custom_length && row.custom_unit_weight && row.custom_sec_qty) {
\t\t\tfrappe.model.set_value(cdt, cdn, "qty", flt((row.custom_length / 1000) * row.custom_unit_weight * row.custom_sec_qty, 3));
\t\t} else {
\t\t\tmr_warn_missing_fields(row, group);
\t\t}
\t} else if (group === "Plates") {
\t\tif (row.custom_length && row.custom_width && row.custom_thickness && row.custom_unit_weight && row.custom_sec_qty) {
\t\t\tfrappe.model.set_value(cdt, cdn, "qty", flt((row.custom_length / 1000) * (row.custom_width / 1000) * row.custom_thickness * row.custom_unit_weight * row.custom_sec_qty, 3));
\t\t} else {
\t\t\tmr_warn_missing_fields(row, group);
\t\t}
\t} else if (group === "Nuts and Bolts") {
\t\tif (row.qty && row.custom_unit_weight) {
\t\t\tvar new_sec = flt(row.qty * row.custom_unit_weight, 3);
\t\t\tif (flt(row.custom_sec_qty, 3) !== new_sec) {
\t\t\t\tfrappe.model.set_value(cdt, cdn, "custom_sec_qty", new_sec);
\t\t\t}
\t\t}
\t}
}

function mr_warn_missing_fields(row, group) {
\tvar missing = [];
\tif (group === "Structurals") {
\t\tif (!row.custom_length) missing.push("Length");
\t\tif (!row.custom_unit_weight) missing.push("Unit Weight");
\t\tif (!row.custom_sec_qty) missing.push("Sec Qty");
\t} else if (group === "Plates") {
\t\tif (!row.custom_length) missing.push("Length");
\t\tif (!row.custom_width) missing.push("Width");
\t\tif (!row.custom_thickness) missing.push("Thickness");
\t\tif (!row.custom_unit_weight) missing.push("Unit Weight");
\t\tif (!row.custom_sec_qty) missing.push("Sec Qty");
\t}
\tif (missing.length) {
\t\tfrappe.show_alert({
\t\t\tmessage: "Row " + row.idx + ": Missing for " + group + " formula: " + missing.join(", "),
\t\t\tindicator: "orange"
\t\t});
\t}
}
""".strip()

RFQ_CLIENT_SCRIPT = """
frappe.ui.form.on("Request for Quotation", {
\trefresh(frm) {
\t\tfrm.set_query("uom", "items", function(doc, cdt, cdn) {
\t\t\tvar row = locals[cdt][cdn];
\t\t\treturn {
\t\t\t\tquery: "manufyxinvenzaerp.sq_management.supplier_quotation.get_sq_item_uom",
\t\t\t\tfilters: { item_code: row.item_code }
\t\t\t};
\t\t});
\t}
});

frappe.ui.form.on("Request for Quotation Item", {
\tform_render(frm, cdt, cdn) { rfq_toggle_dims(frm, cdt, cdn); }
});

function rfq_toggle_dims(frm, cdt, cdn) {
\tvar row = locals[cdt][cdn];
\tvar group = row.custom_parent_item_group;
\tvar show_len   = group === "Structurals" || group === "Plates";
\tvar show_thick = group === "Plates";
\t$.each(frm.fields_dict["items"].grid.grid_rows, function(i, gr) {
\t\tif (gr.doc && gr.doc.name === cdn && gr.grid_form) {
\t\t\tgr.grid_form.toggle_display("custom_length",    show_len);
\t\t\tgr.grid_form.toggle_display("custom_thickness", show_thick);
\t\t\tgr.grid_form.toggle_display("custom_width",     show_thick);
\t\t}
\t});
}
""".strip()

SQ_CLIENT_SCRIPT = """
frappe.ui.form.on("Supplier Quotation", {
\trefresh(frm) {
\t\tfrm.set_query("uom", "items", function(doc, cdt, cdn) {
\t\t\tvar row = locals[cdt][cdn];
\t\t\treturn {
\t\t\t\tquery: "manufyxinvenzaerp.sq_management.supplier_quotation.get_sq_item_uom",
\t\t\t\tfilters: { item_code: row.item_code }
\t\t\t};
\t\t});
\t}
});

frappe.ui.form.on("Supplier Quotation Item", {
\titem_code(frm, cdt, cdn) {
\t\tsetTimeout(function() {
\t\t\tsq_calculate_qty(frm, cdt, cdn);
\t\t\tsq_toggle_dims(frm, cdt, cdn);
\t\t}, 600);
\t},
\tqty(frm, cdt, cdn) {
\t\tvar row = locals[cdt][cdn];
\t\tif (row.custom_parent_item_group === "Nuts and Bolts") {
\t\t\tsq_calculate_qty(frm, cdt, cdn);
\t\t}
\t},
\tcustom_length(frm, cdt, cdn) { sq_calculate_qty(frm, cdt, cdn); },
\tcustom_width(frm, cdt, cdn) { sq_calculate_qty(frm, cdt, cdn); },
\tcustom_thickness(frm, cdt, cdn) { sq_calculate_qty(frm, cdt, cdn); },
\tcustom_sec_qty(frm, cdt, cdn) { sq_calculate_qty(frm, cdt, cdn); },
\tcustom_unit_weight(frm, cdt, cdn) { sq_calculate_qty(frm, cdt, cdn); },
\tform_render(frm, cdt, cdn) { sq_toggle_dims(frm, cdt, cdn); },
\tuom(frm, cdt, cdn) {
\t\tvar row = locals[cdt][cdn];
\t\tif (row.uom && row.stock_uom && row.uom !== row.stock_uom) {
\t\t\tfrappe.msgprint({
\t\t\t\tmessage: "Weight is entered for Stock UOM, Kindly update UOM Weight in item master for correct calculation",
\t\t\t\tindicator: "orange",
\t\t\t\ttitle: "UOM Warning"
\t\t\t});
\t\t}
\t}
});

function sq_toggle_dims(frm, cdt, cdn) {
\tvar row = locals[cdt][cdn];
\tvar group = row.custom_parent_item_group;
\tvar show_len   = group === "Structurals" || group === "Plates";
\tvar show_thick = group === "Plates";
\t$.each(frm.fields_dict["items"].grid.grid_rows, function(i, gr) {
\t\tif (gr.doc && gr.doc.name === cdn && gr.grid_form) {
\t\t\tgr.grid_form.toggle_display("custom_length",    show_len);
\t\t\tgr.grid_form.toggle_display("custom_thickness", show_thick);
\t\t\tgr.grid_form.toggle_display("custom_width",     show_thick);
\t\t}
\t});
}

function sq_calculate_qty(frm, cdt, cdn) {
\tvar row = locals[cdt][cdn];
\tvar group = row.custom_parent_item_group;

\tif (group === "Structurals") {
\t\tif (row.custom_length && row.custom_unit_weight && row.custom_sec_qty) {
\t\t\tfrappe.model.set_value(cdt, cdn, "qty", flt((row.custom_length / 1000) * row.custom_unit_weight * row.custom_sec_qty, 3));
\t\t} else {
\t\t\tsq_warn_missing_fields(row, group);
\t\t}
\t} else if (group === "Plates") {
\t\tif (row.custom_length && row.custom_width && row.custom_thickness && row.custom_unit_weight && row.custom_sec_qty) {
\t\t\tfrappe.model.set_value(cdt, cdn, "qty", flt((row.custom_length / 1000) * (row.custom_width / 1000) * row.custom_thickness * row.custom_unit_weight * row.custom_sec_qty, 3));
\t\t} else {
\t\t\tsq_warn_missing_fields(row, group);
\t\t}
\t} else if (group === "Nuts and Bolts") {
\t\tif (row.qty && row.custom_unit_weight) {
\t\t\tvar new_sec = flt(row.qty * row.custom_unit_weight, 3);
\t\t\tif (flt(row.custom_sec_qty, 3) !== new_sec) {
\t\t\t\tfrappe.model.set_value(cdt, cdn, "custom_sec_qty", new_sec);
\t\t\t}
\t\t}
\t}
}

function sq_warn_missing_fields(row, group) {
\tvar missing = [];
\tif (group === "Structurals") {
\t\tif (!row.custom_length) missing.push("Length");
\t\tif (!row.custom_unit_weight) missing.push("Unit Weight");
\t\tif (!row.custom_sec_qty) missing.push("Sec Qty");
\t} else if (group === "Plates") {
\t\tif (!row.custom_length) missing.push("Length");
\t\tif (!row.custom_width) missing.push("Width");
\t\tif (!row.custom_thickness) missing.push("Thickness");
\t\tif (!row.custom_unit_weight) missing.push("Unit Weight");
\t\tif (!row.custom_sec_qty) missing.push("Sec Qty");
\t}
\tif (missing.length) {
\t\tfrappe.show_alert({
\t\t\tmessage: "Row " + row.idx + ": Missing for " + group + " formula: " + missing.join(", "),
\t\t\tindicator: "orange"
\t\t});
\t}
}
""".strip()

SO_CLIENT_SCRIPT = """
// ── Sales Order: Drawing Import ────────────────────────────────────────────

frappe.ui.form.on("Sales Order", {
	refresh(frm) {
		_so_render_file_buttons(frm);
		_so_render_rm_verify_btn(frm);
		_so_render_drawing_buttons(frm);
	},
	custom_bom_excel_file(frm) {
		_so_render_file_buttons(frm);
	}
});

// ── Qty calculation in Raw Materials child table ───────────────────────────

frappe.ui.form.on("Sales Order Drawing Raw Material", {
	material_code(frm, cdt, cdn) {
		var row = locals[cdt][cdn];
		if (row.is_locked || !row.material_code) return;
		_so_reset_verification(frm);
		frappe.db.get_value("Item", row.material_code,
			["custom_unit_weight", "custom_parent_item_group"],
			function(v) {
				if (v) {
					frappe.model.set_value(cdt, cdn, "unit_weight", v.custom_unit_weight || 0);
					frappe.model.set_value(cdt, cdn, "parent_item_group", v.custom_parent_item_group || "");
				}
				_so_calc_rm_qty(frm, cdt, cdn);
			}
		);
	},
	sec_qty(frm, cdt, cdn)   { _so_reset_verification(frm); _so_calc_rm_qty(frm, cdt, cdn); },
	thickness(frm, cdt, cdn) { _so_reset_verification(frm); _so_calc_rm_qty(frm, cdt, cdn); },
	width(frm, cdt, cdn)     { _so_reset_verification(frm); _so_calc_rm_qty(frm, cdt, cdn); },
	length(frm, cdt, cdn)    { _so_reset_verification(frm); _so_calc_rm_qty(frm, cdt, cdn); }
});

function _so_calc_rm_qty(frm, cdt, cdn) {
	var row = locals[cdt][cdn];
	if (row.is_locked) return;
	var pig = row.parent_item_group || "";
	var uw = flt(row.unit_weight), L = flt(row.length),
	    W = flt(row.width), T = flt(row.thickness), sq = flt(row.sec_qty);

	// Look up total_quantity from the Drawing List for this drawing number
	var tq = 1;
	var cdn_val = row.customer_drawing_number;
	if (cdn_val && frm.doc.custom_duno_items) {
		var dr = frm.doc.custom_duno_items.find(function(r) { return r.drawing_number === cdn_val; });
		if (dr && dr.total_quantity) tq = flt(dr.total_quantity);
	}

	var qty = 0;
	if (pig === "Structurals") {
		if (L && uw && sq) qty = (L / 1000) * uw * sq;
	} else if (pig === "Plates") {
		if (L && W && T && uw && sq) qty = (L / 1000) * (W / 1000) * T * uw * sq;
	} else {
		qty = sq;
	}
	frappe.model.set_value(cdt, cdn, "qty", flt(qty, 3));
	frappe.model.set_value(cdt, cdn, "total_sec_qty", flt(sq * tq, 3));
	frappe.model.set_value(cdt, cdn, "total_weight", flt(qty * tq, 3));
}

// ── Verify Raw Materials button above the RM table ────────────────────────

function _so_render_rm_verify_btn(frm) {
	var fd = frm.fields_dict["custom_rm_verify_btn"];
	if (!fd) return;
	var $w = fd.$wrapper;
	$w.empty();
	if (frm.doc.__islocal || frm.doc.docstatus === 2) return;

	var has_unlocked = (frm.doc.custom_so_raw_materials || []).some(function(r) { return !r.is_locked; });
	if (!has_unlocked) return;

	var verified = !!frm.doc.custom_raw_materials_verified;
	var $row = $('<div style="display:flex;align-items:center;gap:10px;padding:4px 0 8px">').appendTo($w);

	$('<button class="btn btn-sm btn-default">')
		.text(__("Verify Raw Materials"))
		.on("click", function() { _so_verify_rm(frm); })
		.appendTo($row);

	if (verified) {
		$('<span style="color:green;font-weight:bold;font-size:13px;">').html("&#10003; " + __("Verified")).appendTo($row);
	} else {
		$('<span style="color:orange;font-size:12px;">').text(__("Not verified — required before creating drawings")).appendTo($row);
	}
}

function _so_reset_verification(frm) {
	if (frm.doc.custom_raw_materials_verified) {
		frm.doc.custom_raw_materials_verified = 0;
		_so_render_rm_verify_btn(frm);
	}
}

function _so_verify_rm(frm) {
	function _do_verify() {
		frappe.call({
			method: "manufyxinvenzaerp.drawing_management.so_drawing_import.verify_raw_materials",
			args: { so_name: frm.doc.name },
			freeze: true,
			freeze_message: __("Verifying raw materials…"),
			callback: function(r) {
				if (!r.message) return;
				var res = r.message;
				// Sync modified timestamp so subsequent saves don't get conflict errors
				if (res.modified) { frm.doc.modified = res.modified; }
				frm.doc.custom_raw_materials_verified = res.verified ? 1 : 0;
				_so_render_rm_verify_btn(frm);
				if (res.verified) {
					frappe.show_alert({ message: __("All raw materials verified!"), indicator: "green" }, 5);
				} else {
					var msg = "<b>" + res.issues.length + " " + __("issue(s) found:") + "</b><br><br>" +
						res.issues.map(function(i) { return "• " + i; }).join("<br>");
					frappe.msgprint({ title: __("Raw Material Issues"), message: msg, indicator: "orange" });
				}
			}
		});
	}
	if (frm.is_dirty()) {
		frm.save(undefined, function() { _do_verify(); });
	} else {
		_do_verify();
	}
}

// ── Inline Load / Clear buttons next to the attach field ──────────────────

function _so_render_file_buttons(frm) {
	var fd = frm.fields_dict["custom_bom_action_btns"];
	if (!fd) return;
	var $w = fd.$wrapper;
	$w.empty();
	if (frm.doc.__islocal || frm.doc.docstatus === 2) return;

	var has_file = !!frm.doc.custom_bom_excel_file;
	var has_drawing_created = (frm.doc.custom_duno_items || []).some(function(r) { return !!r.drawing; });

	// Lock the attach field once any drawing has been created
	frm.set_df_property("custom_bom_excel_file", "read_only", has_drawing_created ? 1 : 0);
	frm.refresh_field("custom_bom_excel_file");

	var $row = $('<div style="display:flex;gap:8px;padding:4px 0 8px">').appendTo($w);

	if (!has_file) {
		// No file yet — show Download Template only
		$('<button class="btn btn-sm btn-default">')
			.text(__("Download Template"))
			.on("click", function() {
				window.open(frappe.urllib.get_full_url(
					"/api/method/manufyxinvenzaerp.drawing_management.so_drawing_import.download_bom_template"
				));
			})
			.appendTo($row);
	} else {
		// File attached — show Load Items and Clear Items
		var $load = $('<button class="btn btn-sm btn-primary">')
			.text(__("Load Items"))
			.appendTo($row);
		if (has_drawing_created) {
			$load.prop("disabled", true)
				.attr("title", __("Drawings have been created — load is disabled"));
		} else {
			$load.on("click", function() { _so_load_excel(frm); });
		}

		var $clear = $('<button class="btn btn-sm btn-default">')
			.text(__("Clear Items"))
			.appendTo($row);
		if (has_drawing_created) {
			$clear.prop("disabled", true)
				.attr("title", __("Drawings have been created — clear is disabled"));
		} else {
			$clear.on("click", function() { _so_clear_import(frm); });
		}
	}
}

// ── Drawing group buttons (top bar) ───────────────────────────────────────

function _so_render_drawing_buttons(frm) {
	if (frm.doc.__islocal || frm.doc.docstatus === 2) return;

	var items = frm.doc.custom_duno_items || [];

	// Create Drawing — synchronous: no drawing exists yet
	var has_pending = items.some(function(r) { return r.create_drawing && !r.drawing; });
	if (has_pending) {
		frm.add_custom_button(__("Create Drawing"), function() {
			_so_create_drawings(frm);
		}, __("Drawing"));
	}

	// Remaining 3 buttons depend on live drawing docstatus — fetch async
	var drawing_names = items.filter(function(r) { return !!r.drawing; }).map(function(r) { return r.drawing; });
	if (!drawing_names.length) return;

	frappe.db.get_list("Drawing", {
		filters: [["name", "in", drawing_names]],
		fields: ["name", "docstatus", "status"],
		limit: drawing_names.length
	}).then(function(drawings) {
		var drafts   = new Set(drawings.filter(function(d) { return d.docstatus === 0; }).map(function(d) { return d.name; }));
		var subm_nf  = new Set(drawings.filter(function(d) { return d.docstatus === 1 && d.status !== "Final Revision"; }).map(function(d) { return d.name; }));
		var final    = new Set(drawings.filter(function(d) { return d.status === "Final Revision"; }).map(function(d) { return d.name; }));

		// Submit Drawing — only if drafts exist with checkbox on
		var submit_count = items.filter(function(r) { return r.submit_drawing && drafts.has(r.drawing); }).length;
		if (submit_count) {
			frm.add_custom_button(__("Submit Drawing"), function() {
				_so_run_step(frm, "submit", __("Submit Drawing"), __("Submitting Drawings…"), submit_count, __("Submit"));
			}, __("Drawing"));
		}

		// Mark as Final Revision — only if submitted (non-final) drawings with checkbox on
		var final_count = items.filter(function(r) { return r.mark_final_revision && subm_nf.has(r.drawing); }).length;
		if (final_count) {
			frm.add_custom_button(__("Mark as Final Revision"), function() {
				if (frm.doc.docstatus !== 1) {
					frappe.msgprint({
						title: __("Sales Order Not Submitted"),
						message: __("Please submit the Sales Order before marking drawings as Final Revision."),
						indicator: "orange",
					});
					return;
				}
				_so_run_step(frm, "final_revision", __("Mark as Final Revision"), __("Marking Final Revision…"), final_count, __("Final Revision"));
			}, __("Drawing"));
		}

		// Create BOM options — only if final revision drawings with checkbox on
		var bom_candidates = items.filter(function(r) { return r.create_bom && final.has(r.drawing); });
		var bom_count = bom_candidates.length;
		if (bom_count) {
			var bom_drawing_names = bom_candidates.map(function(r) { return r.drawing; });

			// Check upfront if all candidate drawings already have a submitted BOM.
			// If so, show an info message instead of running the step.
			function _run_if_not_all_done(step, title, freeze_msg) {
				frappe.db.get_list("BOM", {
					filters: [["custom_drawing", "in", bom_drawing_names], ["docstatus", "=", 1]],
					fields: ["name"],
					limit: bom_drawing_names.length + 1,
				}).then(function(existing) {
					if (existing.length >= bom_drawing_names.length) {
						frappe.msgprint({
							title: __("BOMs Already Created"),
							message: __("All BOMs are already created and submitted — nothing to create.")
								+ "<br><br>"
								+ __("You can now proceed to <b>Material Planning</b> to start production planning."),
							indicator: "blue",
						});
						return;
					}
					_so_run_step(frm, step, title, freeze_msg, bom_count, __("Create BOM"));
				});
			}

			frm.add_custom_button(__("Create and Submit BOM"), function() {
				_run_if_not_all_done("create_and_submit_bom", __("Create and Submit BOM"), __("Creating and Submitting BOMs…"));
			}, __("Drawing"));

			frm.add_custom_button(__("Create BOM"), function() {
				_run_if_not_all_done("create_bom", __("Create BOM"), __("Creating BOMs…"));
			}, __("Drawing"));
		}

		// Submit BOM — only if draft BOMs already exist
		frappe.db.get_list("BOM", {
			filters: [["custom_drawing", "in", drawing_names], ["docstatus", "=", 0]],
			fields: ["name", "custom_drawing"],
			limit: drawing_names.length
		}).then(function(draft_boms) {
			if (draft_boms.length) {
				frm.add_custom_button(__("Submit BOM"), function() {
					_so_run_step(frm, "submit_bom", __("Submit BOM"), __("Submitting BOMs…"), draft_boms.length, null);
				}, __("Drawing"));
			}
		});
	});
}

// ── Action implementations ─────────────────────────────────────────────────

function _so_load_excel(frm) {
	var has_locked = (frm.doc.custom_duno_items || []).some(function(r) { return !!r.drawing; });
	var do_load = function() {
		frappe.call({
			method: "manufyxinvenzaerp.drawing_management.so_drawing_import.parse_bom_excel",
			args: { so_name: frm.doc.name },
			freeze: true,
			freeze_message: __("Parsing Excel file…"),
			callback: function(r) {
				if (!r.message) return;
				var res = r.message;
				var msg = __("{0} drawing(s) and {1} raw material row(s) loaded.", [res.drawing_count, res.item_count]);
				if (res.warnings && res.warnings.length) {
					frappe.msgprint({ title: __("Loaded with Warnings"),
						message: msg + "<br><br><b>" + __("Warnings:") + "</b><br>" + res.warnings.join("<br>"),
						indicator: "orange" });
				} else {
					frappe.show_alert({ message: msg, indicator: "green" }, 5);
				}
				frm.reload_doc();
			}
		});
	};
	if (has_locked) {
		frappe.confirm(__("Some drawings are already created. Only rows without a drawing will be reloaded. Continue?"), do_load);
	} else {
		do_load();
	}
}

function _so_create_drawings(frm) {
	if (!frm.doc.custom_raw_materials_verified) {
		frappe.msgprint({
			title: __("Verification Required"),
			message: __("Please click <b>Verify Raw Materials</b> above the Raw Materials table and resolve all issues before creating drawings."),
			indicator: "orange"
		});
		return;
	}
	var items = frm.doc.custom_duno_items || [];
	var count = items.filter(function(r) { return r.create_drawing && !r.drawing; }).length;
	var confirm_msg = __("{0} drawing(s) will be created.", [count]) + "<br><br>" +
		__("To skip any drawing, uncheck <b>Create Drawing</b> in the Drawing List row.");
	frappe.confirm(confirm_msg, function() {
		_so_run_batched(frm, {
			method: "manufyxinvenzaerp.drawing_management.so_drawing_import.create_drawings_from_import",
			title: __("Create Drawing"),
			args: { so_name: frm.doc.name },
			count: count,
		});
	});
}

function _so_run_step(frm, step, label, freeze_msg, count, checkbox_label) {
	var confirm_msg = __("{0} drawing(s) will be processed: <b>{1}</b>.", [count || "", label]);
	if (checkbox_label) {
		confirm_msg += "<br><br>" + __("To skip any drawing, uncheck <b>{0}</b> in the Drawing List row.", [checkbox_label]);
	}
	frappe.confirm(confirm_msg, function() {
		_so_run_batched(frm, {
			method: "manufyxinvenzaerp.drawing_management.so_drawing_import.process_drawings",
			title: label,
			args: { so_name: frm.doc.name, step: step },
			count: count,
		});
	});
}

// ── Batched runner — processes in chunks of 30, shows live progress ───────────

function _so_run_batched(frm, opts) {
	var BATCH_SIZE = 30;
	var all_results = [];
	var batch_start = 0;

	// Create dialog with a pre-wired Close button (hidden until done)
	var d = new frappe.ui.Dialog({
		title: opts.title,
		size: "small",
		primary_action_label: __("Close & Reload"),
		primary_action: function() { d.hide(); frm.reload_doc(); }
	});
	// Hide Close button and X while running
	d.get_primary_btn().hide();
	d.$wrapper.find(".modal-header .close").hide();
	d.$body.html(_so_progress_html(0, opts.count || 1, [], false));
	d.show();

	function _next() {
		var args = Object.assign({}, opts.args, {
			batch_start: batch_start,
			batch_size: BATCH_SIZE
		});
		frappe.call({
			method: opts.method,
			args: args,
			callback: function(r) {
				var res = (r && r.message) || {};
				var batch_results = res.results || [];
				all_results = all_results.concat(batch_results);
				var processed = res.processed != null ? res.processed : (batch_start + batch_results.length);
				var total = res.total || processed;
				var done = (res.next_start === null || res.next_start === undefined || processed >= total);

				d.$body.html(_so_progress_html(processed, total, all_results, done));

				if (!done) {
					batch_start = res.next_start;
					_next();
				} else {
					// Show Close button and X — do NOT reload yet; let the user read the results
					d.get_primary_btn().show();
					d.$wrapper.find(".modal-header .close").show();
				}
			},
			error: function() {
				d.hide();
				frappe.msgprint(__("A server error occurred — check the error log for details."));
				frm.reload_doc();
			}
		});
	}
	_next();
}

function _so_progress_html(processed, total, results, done) {
	var pct  = total ? Math.min(100, Math.round((processed / total) * 100)) : 0;
	var ok   = results.filter(function(x) { return x.status === "success"; }).length;
	var err  = results.filter(function(x) { return x.status === "error"; }).length;
	var skip = results.filter(function(x) {
		return x.status === "skipped" || x.status === "unchecked" || x.status === "already_done";
	}).length;

	var has_err = err > 0;
	var clr_main = has_err ? "#e53e3e" : (done ? "#38a169" : "#5a67d8");

	// Inject keyframe CSS once into the page
	if (!document.getElementById("_so_pg_css")) {
		var _s = document.createElement("style");
		_s.id = "_so_pg_css";
		_s.textContent = "@keyframes _so_shine{0%{background-position:-400px 0}100%{background-position:400px 0}}"
			+ "@keyframes _so_spin{to{transform:rotate(360deg)}}";
		document.head.appendChild(_s);
	}

	// Progress bar style — animated shimmer while running, solid gradient when done
	var bar_style;
	if (done) {
		bar_style = "background:" + (has_err
			? "linear-gradient(90deg,#fc8181,#e53e3e)"
			: "linear-gradient(90deg,#68d391,#38a169)") + ";";
	} else {
		bar_style = "background-image:linear-gradient(90deg,#5a67d8 0%,#9f7aea 50%,#5a67d8 100%);"
			+ "background-size:800px 100%;animation:_so_shine 1.8s linear infinite;";
	}

	// Status icon — spinner while running, circle-check/warn when done
	var icon_html;
	if (done && !has_err) {
		icon_html = '<span style="display:inline-flex;align-items:center;justify-content:center;'
			+ 'width:34px;height:34px;border-radius:50%;background:#c6f6d5;color:#276749;font-size:18px;font-weight:700;">&#10003;</span>';
	} else if (done && has_err) {
		icon_html = '<span style="display:inline-flex;align-items:center;justify-content:center;'
			+ 'width:34px;height:34px;border-radius:50%;background:#fed7d7;color:#c53030;font-size:18px;">&#9888;</span>';
	} else {
		icon_html = '<span style="display:inline-flex;align-items:center;justify-content:center;'
			+ 'width:34px;height:34px;border-radius:50%;background:#ebf4ff;">'
			+ '<span style="width:18px;height:18px;border:3px solid #c3dafe;border-top-color:#5a67d8;'
			+ 'border-radius:50%;animation:_so_spin 0.8s linear infinite;display:inline-block;"></span></span>';
	}

	var lbl = done
		? (has_err ? __("Completed with errors") : __("Complete"))
		: __("Processing…");

	var html = '<div style="padding:20px 16px 14px;">';

	// Header: icon + label on left, large % on right
	html += '<div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:18px;">';
	html += '<div style="display:flex;align-items:center;gap:12px;">' + icon_html;
	html += '<div><div style="font-size:14px;font-weight:700;color:#1a202c;line-height:1.2;">' + lbl + '</div>';
	html += '<div style="font-size:11px;color:#a0aec0;margin-top:2px;">' + processed + ' / ' + total + ' ' + __("processed") + '</div></div>';
	html += '</div>';
	html += '<span style="font-size:36px;font-weight:800;color:' + clr_main + ';line-height:1;letter-spacing:-1px;">'
		+ pct + '<span style="font-size:16px;font-weight:500;color:#a0aec0;">%</span></span>';
	html += '</div>';

	// Progress bar track
	html += '<div style="background:#e2e8f0;border-radius:999px;height:10px;overflow:hidden;'
		+ 'margin-bottom:16px;box-shadow:inset 0 1px 3px rgba(0,0,0,0.08);">';
	html += '<div style="' + bar_style + 'width:' + pct + '%;height:100%;border-radius:999px;transition:width 0.35s ease;"></div>';
	html += '</div>';

	// Stats pills
	if (results.length) {
		html += '<div style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:' + (err ? "12" : "0") + 'px;">';
		if (ok)
			html += '<span style="display:inline-flex;align-items:center;gap:5px;background:#f0fff4;color:#276749;'
				+ 'border:1px solid #9ae6b4;border-radius:999px;padding:5px 14px;font-size:12px;font-weight:600;">'
				+ '&#10003;&nbsp;' + ok + '&nbsp;' + __("succeeded") + '</span>';
		if (err)
			html += '<span style="display:inline-flex;align-items:center;gap:5px;background:#fff5f5;color:#c53030;'
				+ 'border:1px solid #fed7d7;border-radius:999px;padding:5px 14px;font-size:12px;font-weight:600;">'
				+ '&#10007;&nbsp;' + err + '&nbsp;' + __("failed") + '</span>';
		if (skip)
			html += '<span style="display:inline-flex;align-items:center;gap:5px;background:#fffaf0;color:#c05621;'
				+ 'border:1px solid #fbd38d;border-radius:999px;padding:5px 14px;font-size:12px;font-weight:600;">'
				+ '&#8677;&nbsp;' + skip + '&nbsp;' + __("skipped") + '</span>';
		html += '</div>';

		// Error detail list
		if (err) {
			var errors = results.filter(function(x) { return x.status === "error"; });
			html += '<div style="max-height:130px;overflow-y:auto;font-size:11px;background:#fff5f5;'
				+ 'border:1px solid #fed7d7;border-radius:8px;padding:10px 12px;margin-top:4px;">';
			errors.forEach(function(e) {
				html += '<div style="display:flex;gap:6px;margin-bottom:5px;align-items:flex-start;">'
					+ '<span style="color:#e53e3e;font-weight:700;flex-shrink:0;margin-top:1px;">&#10007;</span>'
					+ '<span><b style="color:#c53030;">' + frappe.utils.escape_html(e.drawing_number || e.drawing || "") + '</b>'
					+ '<span style="color:#742a2a;">: ' + frappe.utils.escape_html(e.error || "") + '</span></span>'
					+ '</div>';
			});
			html += '</div>';
		}
	}

	html += '</div>';
	return html;
}

function _so_clear_import(frm) {
	var has_locked = (frm.doc.custom_duno_items || []).some(function(r) { return !!r.drawing; });
	var msg = has_locked
		? __("Remove the attached file and all import rows without a created Drawing? Rows with Drawings will be kept.")
		: __("Remove the attached file and all import rows?");
	frappe.confirm(msg, function() {
		frappe.call({
			method: "manufyxinvenzaerp.drawing_management.so_drawing_import.clear_drawing_import",
			args: { so_name: frm.doc.name },
			freeze: true,
			freeze_message: __("Clearing…"),
			callback: function(r) {
				if (!r.message) return;
				var res = r.message;
				frappe.show_alert({ message: __("{0} drawing row(s) and {1} item row(s) cleared.",
					[res.deleted_drawings, res.deleted_items]), indicator: "blue" }, 5);
				frm.reload_doc();
			}
		});
	});
}
""".strip()


def after_install():
    create_item_custom_fields()
    create_item_client_script()
    create_purchase_order_custom_fields()
    hide_purchase_order_weight_fields()
    create_purchase_order_client_script()
    create_purchase_receipt_custom_fields()
    create_batch_custom_fields()
    create_purchase_receipt_client_script()
    create_material_request_custom_fields()
    create_material_request_client_script()
    create_rfq_custom_fields()
    create_rfq_client_script()
    create_sq_custom_fields()
    create_sq_client_script()
    create_so_custom_fields()
    create_so_client_script()
    create_bom_custom_fields()
    create_bom_client_script()
    create_production_plan_custom_fields()
    create_production_plan_client_script()
    create_job_card_custom_fields()
    create_job_card_client_script()
    create_stock_entry_custom_fields()
    create_stock_entry_client_script()
    remove_sco_purchase_order_mandatory()
    create_sco_custom_fields()
    create_sco_client_script()
    create_soe_client_script()
    from manufyxinvenzaerp.production_management.production_utils import (
        create_operations_workstations_routing,
    )
    create_operations_workstations_routing()


def after_migrate():
    create_item_custom_fields()
    create_item_client_script()
    create_purchase_order_custom_fields()
    hide_purchase_order_weight_fields()
    create_purchase_order_client_script()
    create_purchase_receipt_custom_fields()
    create_batch_custom_fields()
    create_purchase_receipt_client_script()
    create_material_request_custom_fields()
    create_material_request_client_script()
    create_rfq_custom_fields()
    create_rfq_client_script()
    create_sq_custom_fields()
    create_sq_client_script()
    create_so_custom_fields()
    create_so_client_script()
    create_bom_custom_fields()
    create_bom_client_script()
    create_production_plan_custom_fields()
    create_production_plan_client_script()
    create_job_card_custom_fields()
    create_job_card_client_script()
    create_stock_entry_custom_fields()
    create_stock_entry_client_script()
    remove_sco_purchase_order_mandatory()
    create_sco_custom_fields()
    create_sco_client_script()
    create_soe_client_script()
    from manufyxinvenzaerp.production_management.production_utils import (
        create_operations_workstations_routing,
    )
    create_operations_workstations_routing()
    setup_storage_location()


def setup_storage_location():
    """Create Storage Location records A-1 and A-2, then register as an Inventory Dimension."""
    # 1. Seed master records
    for loc in ["A-1", "A-2"]:
        if not frappe.db.exists("Storage Location", loc):
            frappe.get_doc({
                "doctype": "Storage Location",
                "name": loc,
            }).insert(ignore_permissions=True)

    # 2. Register as an Inventory Dimension (creates custom fields on all stock doctypes)
    if not frappe.db.exists("Inventory Dimension", "Storage Location"):
        frappe.get_doc({
            "doctype": "Inventory Dimension",
            "reference_document": "Storage Location",
            "dimension_name": "Storage Location",
            "apply_to_all_doctypes": 1,
        }).insert(ignore_permissions=True)

    frappe.db.commit()


def create_item_client_script():
    if frappe.db.exists("Client Script", CLIENT_SCRIPT_NAME):
        frappe.db.set_value("Client Script", CLIENT_SCRIPT_NAME, "script", CLIENT_SCRIPT)
        frappe.db.set_value("Client Script", CLIENT_SCRIPT_NAME, "enabled", 1)
    else:
        frappe.get_doc({
            "doctype": "Client Script",
            "name": CLIENT_SCRIPT_NAME,
            "dt": "Item",
            "view": "Form",
            "enabled": 1,
            "script": CLIENT_SCRIPT,
        }).insert(ignore_permissions=True)
    frappe.db.commit()


def create_item_custom_fields():
    custom_fields = {
        "Item": [
            {
                "fieldname": "custom_material_spec",
                "label": "Material Spec",
                "fieldtype": "Data",
                "insert_after": "item_name",
                "description": "Material specification for the item",
            },
            {
                "fieldname": "custom_parent_item_group",
                "label": "Parent Item Group",
                "fieldtype": "Link",
                "options": "Item Group",
                "insert_after": "custom_material_spec",
                "reqd": 1,
                "description": "Primary category determining calculation method",
            },
            {
                "fieldname": "custom_unit_weight",
                "label": "Unit Weight",
                "fieldtype": "Float",
                "insert_after": "stock_uom",
                "description": "Default UOM Weight - kg/meter for Structurals, density factor for Plates",
            },
            {
                "fieldname": "custom_secondary_uom",
                "label": "Secondary UOM",
                "fieldtype": "Link",
                "options": "UOM",
                "insert_after": "custom_unit_weight",
                "description": "NOS for Structurals/Plates, KG for Nuts and Bolts",
            },
            {
                "fieldname": "custom_item_calculation_type",
                "label": "Item Calculation Type",
                "fieldtype": "Select",
                "options": "\nNormal Weight Calculation\nFormula Weight Calculation",
                "insert_after": "custom_secondary_uom",
                "read_only": 1,
                "description": "Auto-set based on Parent Item Group",
            },
            {
                "fieldname": "custom_batch_prefix",
                "label": "Custom Batch Abbreviation",
                "fieldtype": "Data",
                "insert_after": "has_batch_no",
                "depends_on": "eval:doc.has_batch_no",
                "description": "Batch prefix for custom naming (e.g., ISMB150)",
            },
        ],
        "Item Group": [
            {
                "fieldname": "custom_mandatory_thickness",
                "label": "Mandatory Thickness",
                "fieldtype": "Check",
                "depends_on": "eval:doc.is_group==1",
            },
            {
                "fieldname": "custom_mandatory_length",
                "label": "Mandatory Length Value",
                "fieldtype": "Check",
                "depends_on": "eval:doc.is_group==1",
            },
            {
                "fieldname": "custom_mandatory_width",
                "label": "Mandatory Width Value",
                "fieldtype": "Check",
                "depends_on": "eval:doc.is_group==1",
            },
        ],
    }
    create_custom_fields(custom_fields, update=True)


def create_purchase_order_custom_fields():
    custom_fields = {
        "Purchase Order Item": [
            {
                "fieldname": "custom_parent_item_group",
                "label": "Parent Item Group",
                "fieldtype": "Data",
                "fetch_from": "item_code.custom_parent_item_group",
                "read_only": 1,
                "insert_after": "item_name",
                "in_list_view": 0,
            },
            {
                "fieldname": "custom_item_calculation_type",
                "label": "Item Calculation Type",
                "fieldtype": "Data",
                "fetch_from": "item_code.custom_item_calculation_type",
                "read_only": 1,
                "insert_after": "custom_parent_item_group",
                "in_list_view": 0,
            },
            {
                "fieldname": "custom_sec_qty",
                "label": "Sec Qty",
                "fieldtype": "Float",
                "insert_after": "uom",
                "in_list_view": 1,
            },
            {
                "fieldname": "custom_sec_uom",
                "label": "Sec UOM",
                "fieldtype": "Link",
                "options": "UOM",
                "fetch_from": "item_code.custom_secondary_uom",
                "read_only": 1,
                "insert_after": "custom_sec_qty",
                "in_list_view": 1,
            },
            {
                "fieldname": "custom_unit_weight",
                "label": "Unit Weight",
                "fieldtype": "Float",
                "fetch_from": "item_code.custom_unit_weight",
                "read_only": 1,
                "insert_after": "custom_sec_uom",
                "in_list_view": 1,
            },
            {
                "fieldname": "custom_thickness",
                "label": "Thickness",
                "fieldtype": "Float",
                "depends_on": "eval:doc.custom_parent_item_group === 'Plates'",
                "insert_after": "custom_unit_weight",
                "in_list_view": 1,
            },
            {
                "fieldname": "custom_length",
                "label": "Length",
                "fieldtype": "Float",
                "depends_on": "eval:['Structurals','Plates'].includes(doc.custom_parent_item_group)",
                "insert_after": "custom_thickness",
                "in_list_view": 1,
            },
            {
                "fieldname": "custom_width",
                "label": "Width",
                "fieldtype": "Float",
                "depends_on": "eval:doc.custom_parent_item_group === 'Plates'",
                "insert_after": "custom_length",
                "in_list_view": 1,
            },
        ],
    }
    create_custom_fields(custom_fields, update=True)


def hide_purchase_order_weight_fields():
    for fieldname in ["item_weight_details", "weight_per_unit", "total_weight", "weight_uom"]:
        frappe.make_property_setter(
            {
                "doctype": "Purchase Order Item",
                "fieldname": fieldname,
                "property": "hidden",
                "value": 1,
                "property_type": "Check",
            }
        )
    frappe.db.commit()


def create_purchase_order_client_script():
    if frappe.db.exists("Client Script", PO_CLIENT_SCRIPT_NAME):
        frappe.db.set_value("Client Script", PO_CLIENT_SCRIPT_NAME, "script", PO_CLIENT_SCRIPT)
        frappe.db.set_value("Client Script", PO_CLIENT_SCRIPT_NAME, "enabled", 1)
    else:
        frappe.get_doc({
            "doctype": "Client Script",
            "name": PO_CLIENT_SCRIPT_NAME,
            "dt": "Purchase Order",
            "view": "Form",
            "enabled": 1,
            "script": PO_CLIENT_SCRIPT,
        }).insert(ignore_permissions=True)
    frappe.db.commit()


def create_purchase_receipt_custom_fields():
    custom_fields = {
        "Purchase Receipt Item": [
            {
                "fieldname": "custom_parent_item_group",
                "label": "Parent Item Group",
                "fieldtype": "Data",
                "fetch_from": "item_code.custom_parent_item_group",
                "read_only": 1,
                "insert_after": "item_name",
                "in_list_view": 0,
            },
            {
                "fieldname": "custom_item_calculation_type",
                "label": "Item Calculation Type",
                "fieldtype": "Data",
                "fetch_from": "item_code.custom_item_calculation_type",
                "read_only": 1,
                "insert_after": "custom_parent_item_group",
                "in_list_view": 0,
            },
            {
                "fieldname": "custom_sec_qty",
                "label": "Sec Qty",
                "fieldtype": "Float",
                "insert_after": "uom",
                "in_list_view": 1,
            },
            {
                "fieldname": "custom_sec_uom",
                "label": "Sec UOM",
                "fieldtype": "Link",
                "options": "UOM",
                "fetch_from": "item_code.custom_secondary_uom",
                "read_only": 1,
                "insert_after": "custom_sec_qty",
                "in_list_view": 1,
            },
            {
                "fieldname": "custom_unit_weight",
                "label": "Unit Weight",
                "fieldtype": "Float",
                "fetch_from": "item_code.custom_unit_weight",
                "read_only": 1,
                "insert_after": "custom_sec_uom",
                "in_list_view": 1,
            },
            {
                "fieldname": "custom_thickness",
                "label": "Thickness",
                "fieldtype": "Float",
                "mandatory_depends_on": "eval:doc.custom_parent_item_group==='Plates'",
                "depends_on": "eval:doc.custom_parent_item_group === 'Plates'",
                "insert_after": "custom_unit_weight",
                "in_list_view": 1,
            },
            {
                "fieldname": "custom_length",
                "label": "Length",
                "fieldtype": "Float",
                "mandatory_depends_on": "eval:['Structurals','Plates'].includes(doc.custom_parent_item_group)",
                "depends_on": "eval:['Structurals','Plates'].includes(doc.custom_parent_item_group)",
                "insert_after": "custom_thickness",
                "in_list_view": 1,
            },
            {
                "fieldname": "custom_width",
                "label": "Width",
                "fieldtype": "Float",
                "mandatory_depends_on": "eval:doc.custom_parent_item_group==='Plates'",
                "depends_on": "eval:doc.custom_parent_item_group === 'Plates'",
                "insert_after": "custom_length",
                "in_list_view": 1,
            },
        ],
    }
    create_custom_fields(custom_fields, update=True)


def create_batch_custom_fields():
    custom_fields = {
        "Batch": [
            {
                "fieldname": "custom_thickness",
                "label": "Thickness",
                "fieldtype": "Float",
                "read_only": 1,
                "insert_after": "description",
            },
            {
                "fieldname": "custom_length",
                "label": "Length",
                "fieldtype": "Float",
                "read_only": 1,
                "insert_after": "custom_thickness",
            },
            {
                "fieldname": "custom_width",
                "label": "Width",
                "fieldtype": "Float",
                "read_only": 1,
                "insert_after": "custom_length",
            },
            {
                "fieldname": "custom_sec_qty",
                "label": "Sec Qty",
                "fieldtype": "Float",
                "read_only": 1,
                "insert_after": "custom_width",
            },
            {
                "fieldname": "custom_sec_uom",
                "label": "Sec UOM",
                "fieldtype": "Link",
                "options": "UOM",
                "read_only": 1,
                "insert_after": "custom_sec_qty",
            },
            {
                "fieldname": "custom_existing_supplier_invoice_no",
                "label": "Existing Supplier Invoice No",
                "fieldtype": "Data",
                "read_only": 1,
                "insert_after": "custom_sec_uom",
            },
            {
                "fieldname": "custom_existing_invoice_wt",
                "label": "Existing Invoice Wt",
                "fieldtype": "Float",
                "read_only": 1,
                "insert_after": "custom_existing_supplier_invoice_no",
            },
            {
                "fieldname": "custom_existing_inward_date",
                "label": "Existing Inward Date",
                "fieldtype": "Date",
                "read_only": 1,
                "insert_after": "custom_existing_invoice_wt",
            },
        ],
    }
    create_custom_fields(custom_fields, update=True)


def create_purchase_receipt_client_script():
    if frappe.db.exists("Client Script", PR_CLIENT_SCRIPT_NAME):
        frappe.db.set_value("Client Script", PR_CLIENT_SCRIPT_NAME, "script", PR_CLIENT_SCRIPT)
        frappe.db.set_value("Client Script", PR_CLIENT_SCRIPT_NAME, "enabled", 1)
    else:
        frappe.get_doc({
            "doctype": "Client Script",
            "name": PR_CLIENT_SCRIPT_NAME,
            "dt": "Purchase Receipt",
            "view": "Form",
            "enabled": 1,
            "script": PR_CLIENT_SCRIPT,
        }).insert(ignore_permissions=True)
    frappe.db.commit()


def create_material_request_custom_fields():
    custom_fields = {
        "Material Request": [
            {
                "fieldname": "custom_material_planning",
                "label": "Material Planning",
                "fieldtype": "Link",
                "options": "Material Planning",
                "read_only": 1,
                "insert_after": "amended_from",
                "in_list_view": 0,
            },
        ],
        "Material Request Item": [
            {
                "fieldname": "custom_parent_item_group",
                "label": "Parent Item Group",
                "fieldtype": "Data",
                "fetch_from": "item_code.custom_parent_item_group",
                "read_only": 1,
                "insert_after": "item_name",
                "in_list_view": 0,
            },
            {
                "fieldname": "custom_item_calculation_type",
                "label": "Item Calculation Type",
                "fieldtype": "Data",
                "fetch_from": "item_code.custom_item_calculation_type",
                "read_only": 1,
                "insert_after": "custom_parent_item_group",
                "in_list_view": 0,
            },
            {
                "fieldname": "custom_sec_qty",
                "label": "Sec Qty",
                "fieldtype": "Float",
                "insert_after": "uom",
                "in_list_view": 1,
            },
            {
                "fieldname": "custom_sec_uom",
                "label": "Sec UOM",
                "fieldtype": "Link",
                "options": "UOM",
                "fetch_from": "item_code.custom_secondary_uom",
                "read_only": 1,
                "insert_after": "custom_sec_qty",
                "in_list_view": 1,
            },
            {
                "fieldname": "custom_unit_weight",
                "label": "Unit Weight",
                "fieldtype": "Float",
                "fetch_from": "item_code.custom_unit_weight",
                "read_only": 1,
                "insert_after": "custom_sec_uom",
                "in_list_view": 1,
            },
            {
                "fieldname": "custom_thickness",
                "label": "Thickness",
                "fieldtype": "Float",
                "mandatory_depends_on": "eval:doc.custom_parent_item_group==='Plates'",
                "depends_on": "eval:doc.custom_parent_item_group === 'Plates'",
                "insert_after": "custom_unit_weight",
                "in_list_view": 1,
            },
            {
                "fieldname": "custom_length",
                "label": "Length",
                "fieldtype": "Float",
                "mandatory_depends_on": "eval:['Structurals','Plates'].includes(doc.custom_parent_item_group)",
                "depends_on": "eval:['Structurals','Plates'].includes(doc.custom_parent_item_group)",
                "insert_after": "custom_thickness",
                "in_list_view": 1,
            },
            {
                "fieldname": "custom_width",
                "label": "Width",
                "fieldtype": "Float",
                "mandatory_depends_on": "eval:doc.custom_parent_item_group==='Plates'",
                "depends_on": "eval:doc.custom_parent_item_group === 'Plates'",
                "insert_after": "custom_length",
                "in_list_view": 1,
            },
        ],
    }
    create_custom_fields(custom_fields, update=True)


def create_material_request_client_script():
    if frappe.db.exists("Client Script", MR_CLIENT_SCRIPT_NAME):
        frappe.db.set_value("Client Script", MR_CLIENT_SCRIPT_NAME, "script", MR_CLIENT_SCRIPT)
        frappe.db.set_value("Client Script", MR_CLIENT_SCRIPT_NAME, "enabled", 1)
    else:
        frappe.get_doc({
            "doctype": "Client Script",
            "name": MR_CLIENT_SCRIPT_NAME,
            "dt": "Material Request",
            "view": "Form",
            "enabled": 1,
            "script": MR_CLIENT_SCRIPT,
        }).insert(ignore_permissions=True)
    frappe.db.commit()


def create_rfq_custom_fields():
    custom_fields = {
        "Request for Quotation Item": [
            {
                "fieldname": "custom_parent_item_group",
                "label": "Parent Item Group",
                "fieldtype": "Data",
                "read_only": 1,
                "insert_after": "item_name",
                "in_list_view": 0,
            },
            {
                "fieldname": "custom_item_calculation_type",
                "label": "Item Calculation Type",
                "fieldtype": "Data",
                "read_only": 1,
                "insert_after": "custom_parent_item_group",
                "in_list_view": 0,
            },
            {
                "fieldname": "custom_sec_qty",
                "label": "Sec Qty",
                "fieldtype": "Float",
                "read_only": 1,
                "insert_after": "qty",
                "in_list_view": 1,
            },
            {
                "fieldname": "custom_sec_uom",
                "label": "Sec UOM",
                "fieldtype": "Link",
                "options": "UOM",
                "read_only": 1,
                "insert_after": "custom_sec_qty",
                "in_list_view": 1,
            },
            {
                "fieldname": "custom_unit_weight",
                "label": "Unit Weight",
                "fieldtype": "Float",
                "read_only": 1,
                "insert_after": "custom_sec_uom",
                "in_list_view": 1,
            },
            {
                "fieldname": "custom_thickness",
                "label": "Thickness",
                "fieldtype": "Float",
                "read_only": 1,
                "depends_on": "eval:doc.custom_parent_item_group === 'Plates'",
                "insert_after": "custom_unit_weight",
                "in_list_view": 1,
            },
            {
                "fieldname": "custom_length",
                "label": "Length",
                "fieldtype": "Float",
                "read_only": 1,
                "depends_on": "eval:['Structurals','Plates'].includes(doc.custom_parent_item_group)",
                "insert_after": "custom_thickness",
                "in_list_view": 1,
            },
            {
                "fieldname": "custom_width",
                "label": "Width",
                "fieldtype": "Float",
                "read_only": 1,
                "depends_on": "eval:doc.custom_parent_item_group === 'Plates'",
                "insert_after": "custom_length",
                "in_list_view": 1,
            },
        ],
    }
    create_custom_fields(custom_fields, update=True)


def create_rfq_client_script():
    if frappe.db.exists("Client Script", RFQ_CLIENT_SCRIPT_NAME):
        frappe.db.set_value("Client Script", RFQ_CLIENT_SCRIPT_NAME, "script", RFQ_CLIENT_SCRIPT)
        frappe.db.set_value("Client Script", RFQ_CLIENT_SCRIPT_NAME, "enabled", 1)
    else:
        frappe.get_doc({
            "doctype": "Client Script",
            "name": RFQ_CLIENT_SCRIPT_NAME,
            "dt": "Request for Quotation",
            "view": "Form",
            "enabled": 1,
            "script": RFQ_CLIENT_SCRIPT,
        }).insert(ignore_permissions=True)
    frappe.db.commit()


def create_sq_custom_fields():
    custom_fields = {
        "Supplier Quotation Item": [
            {
                "fieldname": "custom_parent_item_group",
                "label": "Parent Item Group",
                "fieldtype": "Data",
                "fetch_from": "item_code.custom_parent_item_group",
                "read_only": 1,
                "insert_after": "item_name",
                "in_list_view": 0,
            },
            {
                "fieldname": "custom_item_calculation_type",
                "label": "Item Calculation Type",
                "fieldtype": "Data",
                "fetch_from": "item_code.custom_item_calculation_type",
                "read_only": 1,
                "insert_after": "custom_parent_item_group",
                "in_list_view": 0,
            },
            {
                "fieldname": "custom_sec_qty",
                "label": "Sec Qty",
                "fieldtype": "Float",
                "insert_after": "uom",
                "in_list_view": 1,
            },
            {
                "fieldname": "custom_sec_uom",
                "label": "Sec UOM",
                "fieldtype": "Link",
                "options": "UOM",
                "fetch_from": "item_code.custom_secondary_uom",
                "read_only": 1,
                "insert_after": "custom_sec_qty",
                "in_list_view": 1,
            },
            {
                "fieldname": "custom_unit_weight",
                "label": "Unit Weight",
                "fieldtype": "Float",
                "fetch_from": "item_code.custom_unit_weight",
                "read_only": 1,
                "insert_after": "custom_sec_uom",
                "in_list_view": 1,
            },
            {
                "fieldname": "custom_thickness",
                "label": "Thickness",
                "fieldtype": "Float",
                "mandatory_depends_on": "eval:doc.custom_parent_item_group==='Plates'",
                "depends_on": "eval:doc.custom_parent_item_group === 'Plates'",
                "insert_after": "custom_unit_weight",
                "in_list_view": 1,
            },
            {
                "fieldname": "custom_length",
                "label": "Length",
                "fieldtype": "Float",
                "mandatory_depends_on": "eval:['Structurals','Plates'].includes(doc.custom_parent_item_group)",
                "depends_on": "eval:['Structurals','Plates'].includes(doc.custom_parent_item_group)",
                "insert_after": "custom_thickness",
                "in_list_view": 1,
            },
            {
                "fieldname": "custom_width",
                "label": "Width",
                "fieldtype": "Float",
                "mandatory_depends_on": "eval:doc.custom_parent_item_group==='Plates'",
                "depends_on": "eval:doc.custom_parent_item_group === 'Plates'",
                "insert_after": "custom_length",
                "in_list_view": 1,
            },
        ],
    }
    create_custom_fields(custom_fields, update=True)


def create_sq_client_script():
    if frappe.db.exists("Client Script", SQ_CLIENT_SCRIPT_NAME):
        frappe.db.set_value("Client Script", SQ_CLIENT_SCRIPT_NAME, "script", SQ_CLIENT_SCRIPT)
        frappe.db.set_value("Client Script", SQ_CLIENT_SCRIPT_NAME, "enabled", 1)
    else:
        frappe.get_doc({
            "doctype": "Client Script",
            "name": SQ_CLIENT_SCRIPT_NAME,
            "dt": "Supplier Quotation",
            "view": "Form",
            "enabled": 1,
            "script": SQ_CLIENT_SCRIPT,
        }).insert(ignore_permissions=True)
    frappe.db.commit()


def create_bom_custom_fields():
    # Frappe blocks Int→Data via its API; do it directly in DB if still Int.
    existing = frappe.db.get_value(
        "Custom Field",
        {"dt": "BOM Item", "fieldname": "custom_item_number"},
        "fieldtype",
    )
    if existing == "Int":
        frappe.db.sql(
            "UPDATE `tabCustom Field` SET fieldtype='Data' "
            "WHERE dt='BOM Item' AND fieldname='custom_item_number'"
        )
        frappe.db.commit()
        try:
            frappe.db.sql_ddl(
                "ALTER TABLE `tabBOM Item` MODIFY COLUMN custom_item_number VARCHAR(140)"
            )
        except Exception:
            pass  # column may already be VARCHAR on this site

    create_custom_fields(
        {
            "BOM": [
                {
                    "fieldname": "custom_drawing",
                    "fieldtype": "Link",
                    "label": "Drawing Reference",
                    "options": "Drawing",
                    "insert_after": "project",
                    "read_only": 1,
                    "no_copy": 1,
                    "print_hide": 1,
                },
                {
                    "fieldname": "custom_customer_drawing_number",
                    "fieldtype": "Data",
                    "label": "Cust Drawing Number",
                    "insert_after": "custom_drawing",
                    "read_only": 1,
                    "in_standard_filter": 1,
                    "no_copy": 1,
                },
            ],
            "BOM Item": [
                {
                    "fieldname": "custom_item_number",
                    "fieldtype": "Data",
                    "label": "Item Number",
                    "insert_after": "item_code",
                    "read_only": 1,
                },
                {
                    "fieldname": "custom_material_spec",
                    "fieldtype": "Data",
                    "label": "Material Spec",
                    "insert_after": "description",
                    "read_only": 1,
                },
                {
                    "fieldname": "custom_unit_weight",
                    "fieldtype": "Float",
                    "label": "Unit Weight",
                    "insert_after": "custom_material_spec",
                    "read_only": 1,
                },
                {
                    "fieldname": "custom_thickness",
                    "fieldtype": "Float",
                    "label": "Thickness",
                    "insert_after": "custom_unit_weight",
                    "read_only": 1,
                },
                {
                    "fieldname": "custom_length",
                    "fieldtype": "Float",
                    "label": "Length",
                    "insert_after": "custom_thickness",
                    "read_only": 1,
                },
                {
                    "fieldname": "custom_width",
                    "fieldtype": "Float",
                    "label": "Width",
                    "insert_after": "custom_length",
                    "read_only": 1,
                },
                {
                    "fieldname": "custom_sec_qty",
                    "fieldtype": "Float",
                    "label": "Sec Qty",
                    "insert_after": "uom",
                    "read_only": 1,
                },
                {
                    "fieldname": "custom_sec_uom",
                    "fieldtype": "Link",
                    "label": "Sec UOM",
                    "options": "UOM",
                    "insert_after": "custom_sec_qty",
                    "read_only": 1,
                },
            ],
        },
        update=True,
    )


def create_so_custom_fields():
    create_custom_fields(
        {
            "Sales Order": [
                {
                    "fieldname": "custom_tab_duno_mark_no",
                    "fieldtype": "Tab Break",
                    "label": "Drawing Import",
                    "insert_after": "pricing_rules",
                },
                {
                    "fieldname": "custom_bom_import_section",
                    "fieldtype": "Section Break",
                    "label": "BOM File",
                    "insert_after": "custom_tab_duno_mark_no",
                },
                {
                    "fieldname": "custom_bom_excel_file",
                    "fieldtype": "Attach",
                    "label": "BOM Excel File",
                    "insert_after": "custom_bom_import_section",
                    "description": "Upload the customer BOM Excel file.",
                },
                {
                    "fieldname": "custom_bom_action_btns",
                    "fieldtype": "HTML",
                    "label": "BOM Actions",
                    "insert_after": "custom_bom_excel_file",
                },
                {
                    "fieldname": "custom_drawing_list_section",
                    "fieldtype": "Section Break",
                    "label": "Drawing List",
                    "insert_after": "custom_bom_excel_file",
                },
                {
                    "fieldname": "custom_duno_items",
                    "fieldtype": "Table",
                    "label": "Drawing List",
                    "options": "Sales Order DUNO Item",
                    "insert_after": "custom_drawing_list_section",
                    "allow_on_submit": 1,
                },
                {
                    "fieldname": "custom_raw_materials_section",
                    "fieldtype": "Section Break",
                    "label": "Raw Materials",
                    "insert_after": "custom_duno_items",
                },
                {
                    "fieldname": "custom_rm_verify_btn",
                    "fieldtype": "HTML",
                    "label": "RM Verify Button",
                    "insert_after": "custom_raw_materials_section",
                },
                {
                    "fieldname": "custom_raw_materials_verified",
                    "fieldtype": "Check",
                    "label": "Raw Materials Verified",
                    "read_only": 1,
                    "hidden": 1,
                    "insert_after": "custom_rm_verify_btn",
                },
                {
                    "fieldname": "custom_so_raw_materials",
                    "fieldtype": "Table",
                    "label": "Raw Materials",
                    "options": "Sales Order Drawing Raw Material",
                    "insert_after": "custom_raw_materials_verified",
                    "allow_on_submit": 1,
                },
            ]
        },
        update=True,
    )


def create_so_client_script():
    if frappe.db.exists("Client Script", SO_CLIENT_SCRIPT_NAME):
        frappe.db.set_value("Client Script", SO_CLIENT_SCRIPT_NAME, "script", SO_CLIENT_SCRIPT)
        frappe.db.set_value("Client Script", SO_CLIENT_SCRIPT_NAME, "enabled", 1)
    else:
        frappe.get_doc({
            "doctype": "Client Script",
            "name": SO_CLIENT_SCRIPT_NAME,
            "dt": "Sales Order",
            "view": "Form",
            "enabled": 1,
            "script": SO_CLIENT_SCRIPT,
        }).insert(ignore_permissions=True)
    frappe.db.commit()


def create_bom_client_script():
    if frappe.db.exists("Client Script", BOM_CLIENT_SCRIPT_NAME):
        frappe.db.set_value("Client Script", BOM_CLIENT_SCRIPT_NAME, "script", BOM_CLIENT_SCRIPT)
        frappe.db.set_value("Client Script", BOM_CLIENT_SCRIPT_NAME, "enabled", 1)
    else:
        frappe.get_doc({
            "doctype": "Client Script",
            "name": BOM_CLIENT_SCRIPT_NAME,
            "dt": "BOM",
            "view": "Form",
            "enabled": 1,
            "script": BOM_CLIENT_SCRIPT,
        }).insert(ignore_permissions=True)
    frappe.db.commit()


# ─────────────────────────────────────────────────────────────────────────────
# Production Plan — Subcontracting Plan tab + Process Planning table
# ─────────────────────────────────────────────────────────────────────────────

def create_production_plan_custom_fields():
    create_custom_fields(
        {
            "Production Plan": [
                {
                    "fieldname": "custom_subcontracting_plan_tab",
                    "fieldtype": "Tab Break",
                    "label": "Subcontracting Plan",
                    "insert_after": "amended_from",
                },
                {
                    "fieldname": "custom_process_planning_section",
                    "fieldtype": "Section Break",
                    "label": "Process Planning",
                    "insert_after": "custom_subcontracting_plan_tab",
                },
                {
                    "fieldname": "custom_process_planning",
                    "fieldtype": "Table",
                    "label": "Process Planning",
                    "options": "Process Planning",
                    "insert_after": "custom_process_planning_section",
                },
                {
                    "fieldname": "custom_vendor_contractor_section",
                    "fieldtype": "Section Break",
                    "label": "Subcontractor",
                    "insert_after": "custom_process_planning",
                    "depends_on": "eval:doc.custom_process_planning && doc.custom_process_planning.some(r => r.work_type === 'Subcontractor')",
                },
                {
                    "fieldname": "custom_vendor_contractor",
                    "fieldtype": "Link",
                    "label": "Vendor/Contractor",
                    "options": "Supplier",
                    "insert_after": "custom_vendor_contractor_section",
                    "depends_on": "eval:doc.custom_process_planning && doc.custom_process_planning.some(r => r.work_type === 'Subcontractor')",
                },
            ],
        },
        update=True,
    )


PRODUCTION_PLAN_CLIENT_SCRIPT = """
frappe.ui.form.on("Production Plan", {
	refresh(frm) {
		if (frm.doc.docstatus !== 1) return;

		var ops = frm.doc.custom_process_planning || [];
		var has_sub      = ops.some(function(r) { return r.work_type === "Subcontractor"; });
		var has_internal = ops.some(function(r) { return r.work_type === "Internal Jobcard"; });
		var has_vendor   = !!frm.doc.custom_vendor_contractor;

		// ── Subcontracting Order button (all-sub or mixed) ──────────────────
		if (has_sub && has_vendor) {
			frm.add_custom_button(__("Subcontracting Order"), function() {
				frappe.call({
					method: "manufyxinvenzaerp.subcontracting_management.subcontracting.create_sco_from_production_plan",
					args: { pp_name: frm.doc.name },
					freeze: true,
					callback: function(r) {
						if (r.message) {
							frappe.msgprint({
								title: __("Subcontracting Order Created (Draft)"),
								message: __("Set Supplier / Source / WIP Warehouses then submit: ") +
									'<a href="/app/subcontracting-order/' + encodeURIComponent(r.message) + '">' + r.message + "</a>",
								indicator: "green"
							});
							frm.reload_doc();
						}
					}
				});
			}, __("Create"));
		}

		// ── Work Order button (all-internal or mixed) ────────────────────────
		if (has_internal) {
			frm.add_custom_button(__("Work Order"), function() {
				if (has_sub) {
					// Scenario 3: mixed — create WO with only Internal Jobcard ops
					frappe.call({
						method: "manufyxinvenzaerp.subcontracting_management.subcontracting.create_work_order_from_pp",
						args: { pp_name: frm.doc.name },
						freeze: true,
						callback: function(r) {
							if (r.message) {
								frappe.msgprint({
									title: __("Work Order Created"),
									message: __("Work Order (internal operations only): ") +
										'<a href="/app/work-order/' + encodeURIComponent(r.message) + '">' + r.message + "</a>",
									indicator: "green"
								});
								frm.reload_doc();
							}
						}
					});
				} else {
					// Scenario 1: all-internal — use standard ERPNext WO creation
					frappe.call({
						method: "frappe.client.run_doc_method",
						args: { dt: "Production Plan", dn: frm.doc.name, method: "make_work_order" },
						freeze: true,
						callback: function() { frm.reload_doc(); }
					});
				}
			}, __("Create"));
		}

		frm.page.set_inner_btn_group_as_primary(__("Create"));
	}
});

frappe.ui.form.on("Production Plan Item", {
	bom_no(frm, cdt, cdn) {
		var row = locals[cdt][cdn];
		if (!row.bom_no || row.idx !== 1) return;
		frappe.call({
			method: "manufyxinvenzaerp.production_management.production_utils.get_routing_operations_for_bom",
			args: { bom_name: row.bom_no },
			callback: function(r) {
				if (!r.message || !r.message.length) return;
				frm.clear_table("custom_process_planning");
				r.message.forEach(function(op) {
					var child = frm.add_child("custom_process_planning");
					frappe.model.set_value(child.doctype, child.name, "operation_name", op.operation);
					frappe.model.set_value(child.doctype, child.name, "work_type", "Internal Jobcard");
				});
				frm.refresh_field("custom_process_planning");
			}
		});
	}
});
""".strip()


def create_production_plan_client_script():
    if frappe.db.exists("Client Script", PRODUCTION_PLAN_CLIENT_SCRIPT_NAME):
        frappe.db.set_value(
            "Client Script", PRODUCTION_PLAN_CLIENT_SCRIPT_NAME, "script", PRODUCTION_PLAN_CLIENT_SCRIPT
        )
        frappe.db.set_value("Client Script", PRODUCTION_PLAN_CLIENT_SCRIPT_NAME, "enabled", 1)
    else:
        frappe.get_doc({
            "doctype": "Client Script",
            "name": PRODUCTION_PLAN_CLIENT_SCRIPT_NAME,
            "dt": "Production Plan",
            "view": "Form",
            "enabled": 1,
            "script": PRODUCTION_PLAN_CLIENT_SCRIPT,
        }).insert(ignore_permissions=True)
    frappe.db.commit()


# ─────────────────────────────────────────────────────────────────────────────
# Job Card — Raw Material Consumption tab
# ─────────────────────────────────────────────────────────────────────────────

def create_job_card_custom_fields():
    create_custom_fields(
        {
            "Job Card": [
                {
                    "fieldname": "custom_raw_material_consumption_tab",
                    "fieldtype": "Tab Break",
                    "label": "Raw Material Consumption",
                    "insert_after": "amended_from",
                },
                {
                    "fieldname": "custom_raw_material_consumption",
                    "fieldtype": "Table",
                    "label": "Raw Material Consumption",
                    "options": "Job Card Raw Material",
                    "insert_after": "custom_raw_material_consumption_tab",
                },
            ],
        },
        update=True,
    )


JOB_CARD_CLIENT_SCRIPT = """
// Debounce helper — avoids redundant calculations on rapid keystrokes
var _jc_timers = {};
function jc_debounce(key, fn, delay) {
\tclearTimeout(_jc_timers[key]);
\t_jc_timers[key] = setTimeout(fn, delay || 400);
}

// On form load: populate table once from server if it is empty
frappe.ui.form.on("Job Card", {
\tonload(frm) {
\t\tif (frm.is_new() || !frm.doc.name) return;
\t\tif (frm.doc.custom_raw_material_consumption && frm.doc.custom_raw_material_consumption.length > 0) return;
\t\tfrappe.call({
\t\t\tmethod: "manufyxinvenzaerp.production_management.production_utils.get_raw_materials_for_job_card",
\t\t\targs: { job_card_name: frm.doc.name },
\t\t\tcallback: function(r) {
\t\t\t\tif (!r.message || !r.message.length) return;
\t\t\t\tfrm.clear_table("custom_raw_material_consumption");
\t\t\t\tr.message.forEach(function(row_data) {
\t\t\t\t\tvar child = frm.add_child("custom_raw_material_consumption");
\t\t\t\t\t$.extend(locals[child.doctype][child.name], row_data);
\t\t\t\t});
\t\t\t\tfrm.refresh_field("custom_raw_material_consumption");
\t\t\t}
\t\t});
\t}
});

// Child table field change handlers
frappe.ui.form.on("Job Card Raw Material", {
\tcurrent_sec_qty(frm, cdt, cdn) {
\t\tjc_debounce(cdn + "_seq", function() { jc_calculate_qty(frm, cdt, cdn); });
\t},
\tlength(frm, cdt, cdn) {
\t\tjc_debounce(cdn + "_len", function() { jc_calculate_qty(frm, cdt, cdn); });
\t},
\twidth(frm, cdt, cdn) {
\t\tjc_debounce(cdn + "_wid", function() { jc_calculate_qty(frm, cdt, cdn); });
\t},
\tthickness(frm, cdt, cdn) {
\t\tjc_debounce(cdn + "_thk", function() { jc_calculate_qty(frm, cdt, cdn); });
\t},
\tmanual_qty(frm, cdt, cdn) {
\t\tjc_debounce(cdn + "_man", function() { jc_warn_manual_qty(frm, cdt, cdn); });
\t}
});

function jc_calculate_qty(frm, cdt, cdn) {
\tvar row = locals[cdt][cdn];
\tvar group = row.parent_item_group;
\tvar qty = null;

\tif (group === "Structurals") {
\t\tif (row.length && row.unit_weight && row.current_sec_qty) {
\t\t\tqty = (row.length / 1000) * row.unit_weight * row.current_sec_qty;
\t\t}
\t} else if (group === "Plates") {
\t\tif (row.length && row.width && row.thickness && row.unit_weight && row.current_sec_qty) {
\t\t\tqty = (row.length / 1000) * (row.width / 1000) * row.thickness * row.unit_weight * row.current_sec_qty;
\t\t}
\t}

\tif (qty !== null) {
\t\tfrappe.model.set_value(cdt, cdn, "current_stock_qty", flt(qty, 3));
\t\tjc_debounce(cdn + "_warn", function() { jc_warn_qty_exceeded(frm, cdt, cdn, qty); });
\t}
}

function jc_warn_qty_exceeded(frm, cdt, cdn, current_qty) {
\tvar row = locals[cdt][cdn];
\tvar transferred = flt(row.transferred_qty);
\tvar prev_consumed = flt(row.prev_operation_consumed_stock_qty);
\tvar prev_sec = flt(row.prev_operation_sec_qty);
\tvar curr_sec = flt(row.current_sec_qty);
\tvar seq = frm.doc.sequence_id || 1;

\t// Warning: current qty exceeds transferred WIP stock
\tif (transferred > 0 && flt(current_qty) > transferred) {
\t\tvar remaining = flt(transferred - prev_consumed, 3);
\t\tfrappe.show_alert({
\t\t\tmessage: __("Item \\"{0}\\": {1} Kg transferred to WIP, {2} Kg already consumed. Allowed: {3} Kg", [
\t\t\t\trow.item_code, transferred, prev_consumed, remaining
\t\t\t]),
\t\t\tindicator: "orange"
\t\t}, 8);
\t}

\t// Warning: Nos entered exceed previous operation's completed Nos (ops 2–12)
\tif (seq > 1 && prev_sec > 0 && curr_sec > prev_sec) {
\t\tfrappe.show_alert({
\t\t\tmessage: __("Item \\"{0}\\": previous operation completed {1} Nos — you entered {2} Nos which exceeds it.", [
\t\t\t\trow.item_code, prev_sec, curr_sec
\t\t\t]),
\t\t\tindicator: "orange"
\t\t}, 8);
\t}
}

function jc_warn_manual_qty(frm, cdt, cdn) {
\tvar row = locals[cdt][cdn];
\tvar transferred = flt(row.transferred_qty);
\tvar manual = flt(row.manual_qty);
\tif (transferred > 0 && manual > transferred) {
\t\tfrappe.show_alert({
\t\t\tmessage: __("Item \\"{0}\\": manual qty {1} Kg exceeds transferred WIP qty {2} Kg.", [
\t\t\t\trow.item_code, manual, transferred
\t\t\t]),
\t\t\tindicator: "orange"
\t\t}, 8);
\t}
}
""".strip()


STOCK_ENTRY_CLIENT_SCRIPT = """
// Debounce helper
var _se_timers = {};
function se_debounce(key, fn, delay) {
\tclearTimeout(_se_timers[key]);
\t_se_timers[key] = setTimeout(fn, delay || 400);
}

frappe.ui.form.on("Stock Entry Detail", {
\titem_code(frm, cdt, cdn) {
\t\tvar row = locals[cdt][cdn];
\t\tif (!row.item_code) return;

\t\t// Dismiss the "Add Batch Nos" dialog that ERPNext auto-opens for batch items —
\t\t// batches are auto-created on submit; the user must not fill them manually here.
\t\tif (frm.doc.stock_entry_type === "Material Receipt") {
\t\t\tvar _check = setInterval(function() {
\t\t\t\tif (cur_dialog && cur_dialog.get_title && cur_dialog.get_title() === __("Add Batch Nos")) {
\t\t\t\t\tcur_dialog.hide();
\t\t\t\t\tclearInterval(_check);
\t\t\t\t}
\t\t\t}, 50);
\t\t\tsetTimeout(function() { clearInterval(_check); }, 5000);
\t\t}

\t\tfrappe.db.get_value(
\t\t\t"Item", row.item_code,
\t\t\t["custom_parent_item_group", "custom_unit_weight", "custom_secondary_uom"],
\t\t\tfunction(values) {
\t\t\t\tif (!values) return;
\t\t\t\tfrappe.model.set_value(cdt, cdn, "custom_parent_item_group", values.custom_parent_item_group || "");
\t\t\t\tfrappe.model.set_value(cdt, cdn, "custom_unit_weight", values.custom_unit_weight || 0);
\t\t\t\tfrappe.model.set_value(cdt, cdn, "custom_sec_uom", values.custom_secondary_uom || "");
\t\t\t}
\t\t);
\t},
\tbatch_no(frm, cdt, cdn) {
\t\tvar row = locals[cdt][cdn];
\t\tif (!row.batch_no) return;
\t\tvar should_fetch = (
\t\t\tfrm.doc.stock_entry_type === "Material Issue" ||
\t\t\t(frm.doc.stock_entry_type === "Repack" && !row.is_finished_item)
\t\t);
\t\tif (!should_fetch) return;
\t\tfrappe.db.get_value(
\t\t\t"Batch", row.batch_no,
\t\t\t["custom_sec_qty", "custom_sec_uom", "custom_thickness", "custom_length", "custom_width"],
\t\t\tfunction(values) {
\t\t\t\tif (!values) return;
\t\t\t\tfrappe.model.set_value(cdt, cdn, "custom_sec_qty", values.custom_sec_qty || 0);
\t\t\t\tfrappe.model.set_value(cdt, cdn, "custom_sec_uom", values.custom_sec_uom || "");
\t\t\t\tfrappe.model.set_value(cdt, cdn, "custom_thickness", values.custom_thickness || 0);
\t\t\t\tfrappe.model.set_value(cdt, cdn, "custom_length", values.custom_length || 0);
\t\t\t\tfrappe.model.set_value(cdt, cdn, "custom_width", values.custom_width || 0);
\t\t\t\tse_debounce(cdn + "_calc", function() { se_calculate_qty(frm, cdt, cdn); });
\t\t\t}
\t\t);
\t},
\tcustom_sec_qty(frm, cdt, cdn) {
\t\tse_debounce(cdn + "_seq", function() { se_calculate_qty(frm, cdt, cdn); });
\t},
\tcustom_thickness(frm, cdt, cdn) {
\t\tse_debounce(cdn + "_thk", function() { se_calculate_qty(frm, cdt, cdn); });
\t},
\tcustom_length(frm, cdt, cdn) {
\t\tse_debounce(cdn + "_len", function() { se_calculate_qty(frm, cdt, cdn); });
\t},
\tcustom_width(frm, cdt, cdn) {
\t\tse_debounce(cdn + "_wid", function() { se_calculate_qty(frm, cdt, cdn); });
\t},
\tuom(frm, cdt, cdn) {
\t\tvar row = locals[cdt][cdn];
\t\tif (["Structurals", "Plates"].includes(row.custom_parent_item_group)) {
\t\t\tfrappe.show_alert({
\t\t\t\tmessage: __("Quantity is a calculated value. Recalculating…"),
\t\t\t\tindicator: "orange"
\t\t\t}, 5);
\t\t\tse_debounce(cdn + "_uom", function() { se_calculate_qty(frm, cdt, cdn); });
\t\t}
\t}
});

function se_calculate_qty(frm, cdt, cdn) {
\tvar row = locals[cdt][cdn];
\tvar group = row.custom_parent_item_group;
\tvar qty = null;
\tif (group === "Structurals") {
\t\tif (row.custom_length && row.custom_unit_weight && row.custom_sec_qty) {
\t\t\tqty = (row.custom_length / 1000) * row.custom_unit_weight * row.custom_sec_qty;
\t\t} else {
\t\t\tse_warn_missing_fields(row, group);
\t\t}
\t} else if (group === "Plates") {
\t\tif (row.custom_length && row.custom_width && row.custom_thickness && row.custom_unit_weight && row.custom_sec_qty) {
\t\t\tqty = (row.custom_length / 1000) * (row.custom_width / 1000) * row.custom_thickness * row.custom_unit_weight * row.custom_sec_qty;
\t\t} else {
\t\t\tse_warn_missing_fields(row, group);
\t\t}
\t}
\tif (qty !== null) {
\t\tfrappe.model.set_value(cdt, cdn, "qty", flt(qty, 3));
\t}
}

function se_warn_missing_fields(row, group) {
\tvar missing = [];
\tif (group === "Structurals") {
\t\tif (!row.custom_length) missing.push("Length");
\t\tif (!row.custom_unit_weight) missing.push("Unit Weight");
\t\tif (!row.custom_sec_qty) missing.push("Sec Qty");
\t} else if (group === "Plates") {
\t\tif (!row.custom_length) missing.push("Length");
\t\tif (!row.custom_width) missing.push("Width");
\t\tif (!row.custom_thickness) missing.push("Thickness");
\t\tif (!row.custom_unit_weight) missing.push("Unit Weight");
\t\tif (!row.custom_sec_qty) missing.push("Sec Qty");
\t}
\tif (missing.length) {
\t\tfrappe.show_alert({
\t\t\tmessage: "Row " + row.idx + ": Missing for " + group + " formula: " + missing.join(", "),
\t\t\tindicator: "orange"
\t\t});
\t}
}
""".strip()


def create_job_card_client_script():
    if frappe.db.exists("Client Script", JOB_CARD_CLIENT_SCRIPT_NAME):
        frappe.db.set_value(
            "Client Script", JOB_CARD_CLIENT_SCRIPT_NAME, "script", JOB_CARD_CLIENT_SCRIPT
        )
        frappe.db.set_value("Client Script", JOB_CARD_CLIENT_SCRIPT_NAME, "enabled", 1)
    else:
        frappe.get_doc({
            "doctype": "Client Script",
            "name": JOB_CARD_CLIENT_SCRIPT_NAME,
            "dt": "Job Card",
            "view": "Form",
            "enabled": 1,
            "script": JOB_CARD_CLIENT_SCRIPT,
        }).insert(ignore_permissions=True)
    frappe.db.commit()


def create_stock_entry_custom_fields():
    create_custom_fields(
        {
            "Stock Entry Detail": [
                {
                    "fieldname": "custom_parent_item_group",
                    "fieldtype": "Data",
                    "label": "Parent Item Group",
                    "fetch_from": "item_code.custom_parent_item_group",
                    "read_only": 1,
                    "insert_after": "item_name",
                },
                {
                    "fieldname": "custom_unit_weight",
                    "fieldtype": "Float",
                    "label": "Unit Weight",
                    "fetch_from": "item_code.custom_unit_weight",
                    "read_only": 1,
                    "insert_after": "custom_parent_item_group",
                },
                {
                    "fieldname": "custom_sec_qty",
                    "fieldtype": "Float",
                    "label": "Sec Qty (Nos)",
                    "in_list_view": 1,
                    "insert_after": "custom_unit_weight",
                },
                {
                    "fieldname": "custom_sec_uom",
                    "fieldtype": "Link",
                    "options": "UOM",
                    "label": "Sec UOM",
                    "fetch_from": "item_code.custom_secondary_uom",
                    "read_only": 1,
                    "insert_after": "custom_sec_qty",
                },
                {
                    "fieldname": "custom_thickness",
                    "fieldtype": "Float",
                    "label": "Thickness (mm)",
                    "depends_on": "eval:doc.custom_parent_item_group=='Plates'",
                    "insert_after": "custom_sec_uom",
                },
                {
                    "fieldname": "custom_length",
                    "fieldtype": "Float",
                    "label": "Length (mm)",
                    "depends_on": "eval:['Structurals','Plates'].includes(doc.custom_parent_item_group)",
                    "insert_after": "custom_thickness",
                },
                {
                    "fieldname": "custom_width",
                    "fieldtype": "Float",
                    "label": "Width (mm)",
                    "depends_on": "eval:doc.custom_parent_item_group=='Plates'",
                    "insert_after": "custom_length",
                },
                {
                    "fieldname": "custom_supplier",
                    "fieldtype": "Link",
                    "options": "Supplier",
                    "label": "Supplier",
                    "insert_after": "custom_width",
                },
                {
                    "fieldname": "custom_existing_supplier_invoice_no",
                    "fieldtype": "Data",
                    "label": "Existing Supplier Invoice No",
                    "depends_on": "eval:['Structurals','Plates'].includes(doc.custom_parent_item_group)",
                    "insert_after": "custom_supplier",
                },
                {
                    "fieldname": "custom_existing_invoice_wt",
                    "fieldtype": "Float",
                    "label": "Existing Invoice Wt",
                    "depends_on": "eval:['Structurals','Plates'].includes(doc.custom_parent_item_group)",
                    "insert_after": "custom_existing_supplier_invoice_no",
                },
                {
                    "fieldname": "custom_existing_inward_date",
                    "fieldtype": "Date",
                    "label": "Existing Inward Date",
                    "depends_on": "eval:['Structurals','Plates'].includes(doc.custom_parent_item_group)",
                    "insert_after": "custom_existing_invoice_wt",
                },
            ],
        },
        update=True,
    )


def create_stock_entry_client_script():
    if frappe.db.exists("Client Script", STOCK_ENTRY_CLIENT_SCRIPT_NAME):
        frappe.db.set_value(
            "Client Script", STOCK_ENTRY_CLIENT_SCRIPT_NAME, "script", STOCK_ENTRY_CLIENT_SCRIPT
        )
        frappe.db.set_value("Client Script", STOCK_ENTRY_CLIENT_SCRIPT_NAME, "enabled", 1)
    else:
        frappe.get_doc({
            "doctype": "Client Script",
            "name": STOCK_ENTRY_CLIENT_SCRIPT_NAME,
            "dt": "Stock Entry",
            "view": "Form",
            "enabled": 1,
            "script": STOCK_ENTRY_CLIENT_SCRIPT,
        }).insert(ignore_permissions=True)
    frappe.db.commit()


# ─────────────────────────────────────────────────────────────────────────────
# Subcontracting Management — Subcontracting Order custom fields + client scripts
# ─────────────────────────────────────────────────────────────────────────────

def remove_sco_purchase_order_mandatory():
    """Remove mandatory from SCO fields that are not required in the PP → SCO flow."""
    for args in [
        {"doctype": "Subcontracting Order", "fieldname": "purchase_order", "property": "reqd", "value": 0, "property_type": "Check"},
        {"doctype": "Subcontracting Order", "fieldname": "service_items", "property": "reqd", "value": 0, "property_type": "Check"},
        {"doctype": "Subcontracting Order Item", "fieldname": "warehouse", "property": "reqd", "value": 0, "property_type": "Check"},
    ]:
        frappe.make_property_setter(args)
    frappe.db.commit()


def create_sco_custom_fields():
    create_custom_fields(
        {
            "Subcontracting Order": [
                {
                    "fieldname": "custom_production_plan",
                    "fieldtype": "Link",
                    "label": "Production Plan",
                    "options": "Production Plan",
                    "read_only": 1,
                    "insert_after": "supplier",
                },
                {
                    "fieldname": "custom_work_order",
                    "fieldtype": "Link",
                    "label": "Work Order",
                    "options": "Work Order",
                    "read_only": 1,
                    "insert_after": "custom_production_plan",
                },
                {
                    "fieldname": "custom_all_ops_complete",
                    "fieldtype": "Check",
                    "label": "All Operations Complete",
                    "read_only": 1,
                    "insert_after": "custom_work_order",
                },
                {
                    "fieldname": "custom_source_warehouse",
                    "fieldtype": "Link",
                    "label": "Source Warehouse (RM)",
                    "options": "Warehouse",
                    "reqd": 1,
                    "insert_after": "custom_all_ops_complete",
                    "description": "Warehouse to transfer raw materials FROM to the supplier",
                },
                {
                    "fieldname": "custom_wip_warehouse",
                    "fieldtype": "Link",
                    "label": "WIP Transfer Warehouse",
                    "options": "Warehouse",
                    "insert_after": "custom_source_warehouse",
                    "description": "Warehouse to transfer consumed material TO for internal Job Cards (Scenario 3)",
                },
                {
                    "fieldname": "custom_return_warehouse",
                    "fieldtype": "Link",
                    "label": "Return/Transfer Warehouse",
                    "options": "Warehouse",
                    "insert_after": "custom_wip_warehouse",
                    "description": "Warehouse to receive unconsumed materials back from supplier",
                },
            ],
        },
        update=True,
    )


SCO_CLIENT_SCRIPT = """
frappe.ui.form.on("Subcontracting Order", {
\trefresh(frm) {
\t\tif (frm.doc.docstatus === 1 && frm.doc.custom_production_plan) {
\t\t\t// Transfer Raw Materials to Supplier Warehouse
\t\t\tfrm.add_custom_button(__("Raw Materials to Supplier"), function() {
\t\t\t\tif (!frm.doc.custom_source_warehouse) {
\t\t\t\t\tfrappe.msgprint(__("Please set the Source Warehouse (RM) field first."));
\t\t\t\t\treturn;
\t\t\t\t}
\t\t\t\tfrappe.call({
\t\t\t\t\tmethod: "manufyxinvenzaerp.subcontracting_management.subcontracting.create_send_to_subcontractor_entry",
\t\t\t\t\targs: { sco_name: frm.doc.name },
\t\t\t\t\tfreeze: true,
\t\t\t\t\tcallback: function(r) {
\t\t\t\t\t\tif (r.message) {
\t\t\t\t\t\t\tfrappe.msgprint({
\t\t\t\t\t\t\t\ttitle: __("Stock Entry Created"),
\t\t\t\t\t\t\t\tmessage: __("Review and submit the stock entry: ") +
\t\t\t\t\t\t\t\t\t'<a href="/app/stock-entry/' + encodeURIComponent(r.message) + '">' + r.message + "</a>",
\t\t\t\t\t\t\t\tindicator: "green"
\t\t\t\t\t\t\t});
\t\t\t\t\t\t\tfrm.reload_doc();
\t\t\t\t\t\t}
\t\t\t\t\t}
\t\t\t\t});
\t\t\t}, __("Transfer"));

\t\t\t// Create Supplier Operation Entries
\t\t\tfrm.add_custom_button(__("Supplier Operation Entries"), function() {
\t\t\t\tfrappe.call({
\t\t\t\t\tmethod: "manufyxinvenzaerp.subcontracting_management.subcontracting.create_supplier_operation_entries",
\t\t\t\t\targs: { sco_name: frm.doc.name },
\t\t\t\t\tfreeze: true,
\t\t\t\t\tcallback: function(r) {
\t\t\t\t\t\tif (r.message && r.message.length) {
\t\t\t\t\t\t\tfrappe.msgprint({
\t\t\t\t\t\t\t\ttitle: __("Supplier Operation Entries Created"),
\t\t\t\t\t\t\t\tmessage: r.message.join(", "),
\t\t\t\t\t\t\t\tindicator: "green"
\t\t\t\t\t\t\t});
\t\t\t\t\t\t} else {
\t\t\t\t\t\t\tfrappe.msgprint(__("All Supplier Operation Entries already exist."));
\t\t\t\t\t\t}
\t\t\t\t\t\tfrm.reload_doc();
\t\t\t\t\t}
\t\t\t\t});
\t\t\t}, __("Create"));

\t\t\tif (frm.doc.custom_all_ops_complete) {
\t\t\t\t// Scenario 3: Transfer consumed material to company WIP for internal Job Cards
\t\t\t\tfrm.add_custom_button(__("Transfer to Company WIP"), function() {
\t\t\t\t\tif (!frm.doc.custom_wip_warehouse) {
\t\t\t\t\t\tfrappe.msgprint(__("Please set the WIP Transfer Warehouse field first."));
\t\t\t\t\t\treturn;
\t\t\t\t\t}
\t\t\t\t\tfrappe.call({
\t\t\t\t\t\tmethod: "manufyxinvenzaerp.subcontracting_management.subcontracting.create_wip_transfer_stock_entry",
\t\t\t\t\t\targs: { sco_name: frm.doc.name },
\t\t\t\t\t\tfreeze: true,
\t\t\t\t\t\tcallback: function(r) {
\t\t\t\t\t\t\tif (r.message) {
\t\t\t\t\t\t\t\tfrappe.msgprint({
\t\t\t\t\t\t\t\t\ttitle: __("WIP Transfer Created"),
\t\t\t\t\t\t\t\t\tmessage: __("Review and submit: ") +
\t\t\t\t\t\t\t\t\t\t'<a href="/app/stock-entry/' + encodeURIComponent(r.message) + '">' + r.message + "</a>",
\t\t\t\t\t\t\t\t\tindicator: "green"
\t\t\t\t\t\t\t\t});
\t\t\t\t\t\t\t\tfrm.reload_doc();
\t\t\t\t\t\t\t}
\t\t\t\t\t\t}
\t\t\t\t\t});
\t\t\t\t}, __("Transfer"));

\t\t\t\t// Scenario 2: Return unconsumed raw materials to store
\t\t\t\tfrm.add_custom_button(__("Transfer Unconsumed Materials"), function() {
\t\t\t\t\tif (!frm.doc.custom_return_warehouse) {
\t\t\t\t\t\tfrappe.msgprint(__("Please set the Return/Transfer Warehouse field first."));
\t\t\t\t\t\treturn;
\t\t\t\t\t}
\t\t\t\t\tfrappe.call({
\t\t\t\t\t\tmethod: "manufyxinvenzaerp.subcontracting_management.subcontracting.create_return_stock_entry",
\t\t\t\t\t\targs: { sco_name: frm.doc.name, target_warehouse: frm.doc.custom_return_warehouse },
\t\t\t\t\t\tfreeze: true,
\t\t\t\t\t\tcallback: function(r) {
\t\t\t\t\t\t\tif (r.message) {
\t\t\t\t\t\t\t\tfrappe.msgprint({
\t\t\t\t\t\t\t\t\ttitle: __("Stock Entry Created"),
\t\t\t\t\t\t\t\t\tmessage: __("Transfer Stock Entry: ") +
\t\t\t\t\t\t\t\t\t\t'<a href="/app/stock-entry/' + encodeURIComponent(r.message) + '">' + r.message + "</a>",
\t\t\t\t\t\t\t\t\tindicator: "green"
\t\t\t\t\t\t\t\t});
\t\t\t\t\t\t\t\tfrm.reload_doc();
\t\t\t\t\t\t\t}
\t\t\t\t\t\t}
\t\t\t\t\t});
\t\t\t\t}, __("Transfer"));
\t\t\t}
\t\t}
\t}
});
""".strip()


SOE_CLIENT_SCRIPT = """
var _soe_timers = {};
function soe_debounce(key, fn, delay) {
\tclearTimeout(_soe_timers[key]);
\t_soe_timers[key] = setTimeout(fn, delay || 400);
}

frappe.ui.form.on("Supplier Operation Item", {
\tcurrent_sec_qty(frm, cdt, cdn) {
\t\tsoe_debounce(cdn + "_seq", function() { soe_calculate_qty(frm, cdt, cdn); });
\t},
\tlength(frm, cdt, cdn) {
\t\tsoe_debounce(cdn + "_len", function() { soe_calculate_qty(frm, cdt, cdn); });
\t},
\twidth(frm, cdt, cdn) {
\t\tsoe_debounce(cdn + "_wid", function() { soe_calculate_qty(frm, cdt, cdn); });
\t},
\tthickness(frm, cdt, cdn) {
\t\tsoe_debounce(cdn + "_thk", function() { soe_calculate_qty(frm, cdt, cdn); });
\t},
\tmanual_qty(frm, cdt, cdn) {
\t\tsoe_debounce(cdn + "_man", function() { soe_warn_manual_qty(frm, cdt, cdn); });
\t}
});

function soe_calculate_qty(frm, cdt, cdn) {
\tvar row = locals[cdt][cdn];
\tvar group = row.parent_item_group;
\tvar qty = null;

\tif (group === "Structurals") {
\t\tif (row.length && row.unit_weight && row.current_sec_qty) {
\t\t\tqty = (row.length / 1000) * row.unit_weight * row.current_sec_qty;
\t\t}
\t} else if (group === "Plates") {
\t\tif (row.length && row.width && row.thickness && row.unit_weight && row.current_sec_qty) {
\t\t\tqty = (row.length / 1000) * (row.width / 1000) * row.thickness * row.unit_weight * row.current_sec_qty;
\t\t}
\t}

\tif (qty !== null) {
\t\tfrappe.model.set_value(cdt, cdn, "current_stock_qty", flt(qty, 3));
\t\tsoe_debounce(cdn + "_warn", function() { soe_warn_exceeded(frm, cdt, cdn, qty); });
\t}
}

function soe_warn_exceeded(frm, cdt, cdn, current_qty) {
\tvar row = locals[cdt][cdn];
\tvar transferred_stock = flt(row.transferred_stock_qty);
\tvar transferred_sec = flt(row.transferred_sec_qty);
\tvar prev_sec = flt(row.prev_operation_sec_qty);
\tvar curr_sec = flt(row.current_sec_qty);
\tvar seq = frm.doc.sequence_id || 1;

\tif (transferred_stock > 0 && flt(current_qty) > transferred_stock) {
\t\tfrappe.show_alert({
\t\t\tmessage: __("Item \\"{0}\\": {1} Nos ({2} Kg) transferred. You entered {3} Nos ({4} Kg).", [
\t\t\t\trow.item_code, transferred_sec, transferred_stock,
\t\t\t\tcurr_sec, flt(current_qty, 3)
\t\t\t]),
\t\t\tindicator: "orange"
\t\t}, 8);
\t}

\tif (seq > 1 && prev_sec > 0 && curr_sec > prev_sec) {
\t\tfrappe.show_alert({
\t\t\tmessage: __("Item \\"{0}\\": Previous operation completed {1} Nos. You entered {2} Nos.", [
\t\t\t\trow.item_code, prev_sec, curr_sec
\t\t\t]),
\t\t\tindicator: "orange"
\t\t}, 8);
\t}
}

function soe_warn_manual_qty(frm, cdt, cdn) {
\tvar row = locals[cdt][cdn];
\tvar transferred = flt(row.transferred_stock_qty);
\tvar manual = flt(row.manual_qty);
\tif (transferred > 0 && manual > transferred) {
\t\tfrappe.show_alert({
\t\t\tmessage: __("Item \\"{0}\\": manual qty {1} Kg exceeds transferred qty {2} Kg.", [
\t\t\t\trow.item_code, manual, transferred
\t\t\t]),
\t\t\tindicator: "orange"
\t\t}, 8);
\t}
}
""".strip()


def create_sco_client_script():
    if frappe.db.exists("Client Script", SCO_CLIENT_SCRIPT_NAME):
        frappe.db.set_value("Client Script", SCO_CLIENT_SCRIPT_NAME, "script", SCO_CLIENT_SCRIPT)
        frappe.db.set_value("Client Script", SCO_CLIENT_SCRIPT_NAME, "enabled", 1)
    else:
        frappe.get_doc({
            "doctype": "Client Script",
            "name": SCO_CLIENT_SCRIPT_NAME,
            "dt": "Subcontracting Order",
            "view": "Form",
            "enabled": 1,
            "script": SCO_CLIENT_SCRIPT,
        }).insert(ignore_permissions=True)
    frappe.db.commit()


def create_soe_client_script():
    if frappe.db.exists("Client Script", SOE_CLIENT_SCRIPT_NAME):
        frappe.db.set_value("Client Script", SOE_CLIENT_SCRIPT_NAME, "script", SOE_CLIENT_SCRIPT)
        frappe.db.set_value("Client Script", SOE_CLIENT_SCRIPT_NAME, "enabled", 1)
    else:
        frappe.get_doc({
            "doctype": "Client Script",
            "name": SOE_CLIENT_SCRIPT_NAME,
            "dt": "Supplier Operation Entry",
            "view": "Form",
            "enabled": 1,
            "script": SOE_CLIENT_SCRIPT,
        }).insert(ignore_permissions=True)
    frappe.db.commit()
