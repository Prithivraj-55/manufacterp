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
WO_CLIENT_SCRIPT_NAME = "Work Order-wo-drawing-buttons"
WO_OPS_SCRIPT_NAME = "Work Order-jc-operations-summary"
JC_DRAWING_CLIENT_SCRIPT_NAME = "Job Card-drawing-consumption-logic"

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
		_so_render_duno_view_all_btn(frm);
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

	var $row = $('<div style="display:flex;align-items:center;gap:10px;padding:4px 0 8px">').appendTo($w);

	var has_unlocked = (frm.doc.custom_so_raw_materials || []).some(function(r) { return !r.is_locked; });
	var verified = !!frm.doc.custom_raw_materials_verified;

	if (has_unlocked) {
		$('<button class="btn btn-sm btn-default">')
			.text(__("Verify Raw Materials"))
			.on("click", function() { _so_verify_rm(frm); })
			.appendTo($row);
	}

	$('<button class="btn btn-sm btn-default">')
		.html(frappe.utils.icon("eye", "sm") + "&nbsp;" + __("View All"))
		.on("click", function() { _so_show_table_popup(frm, "custom_so_raw_materials"); })
		.appendTo($row);

	if (!has_unlocked) return;

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

// ── View All button above the Drawing List grid ───────────────────────────

function _so_render_duno_view_all_btn(frm) {
	var grid = frm.fields_dict["custom_duno_items"] && frm.fields_dict["custom_duno_items"].grid;
	if (!grid) return;
	var $top = grid.wrapper.find(".grid-custom-buttons");
	$top.empty();
	$('<button class="btn btn-default btn-sm">')
		.html(frappe.utils.icon("eye", "xs") + " " + __("View All"))
		.on("click", function() { _so_show_table_popup(frm, "custom_duno_items"); })
		.appendTo($top);
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

// ── Column definitions for each table's View All popup ────────────────────

const _SO_TABLE_VIEW_CONFIG = {
	custom_duno_items: {
		title: "Drawing List",
		filters: [
			{ fieldname: "duno_mark_no",   label: "Filter DUNO/Mark No…" },
			{ fieldname: "drawing_number", label: "Filter Cust Drawing Number…" },
		],
		cols: [
			{ fieldname: "assembly_group",      label: "Assembly Group" },
			{ fieldname: "item",                label: "FG Item" },
			{ fieldname: "item_name",           label: "Item Name" },
			{ fieldname: "duno_mark_no",        label: "DUNO/Mark No" },
			{ fieldname: "drawing_number",      label: "Cust Drawing Number" },
			{ fieldname: "total_quantity",      label: "Total Quantity" },
			{ fieldname: "total_weight",        label: "Customer Provided Weight (Kg)" },
			{ fieldname: "difference_kg",       label: "Difference Kg" },
			{ fieldname: "drawing",             label: "Drawing" },
			{ fieldname: "create_drawing",      label: "Create Drawing" },
			{ fieldname: "submit_drawing",      label: "Submit" },
			{ fieldname: "mark_final_revision", label: "Final Revision" },
			{ fieldname: "create_bom",          label: "Create BOM" },
		],
	},
	custom_so_raw_materials: {
		title: "Raw Materials",
		filters: [
			{ fieldname: "customer_drawing_number", label: "Filter Drawing No…" },
			{ fieldname: "material_code",           label: "Filter Material Code…" },
		],
		cols: [
			{ fieldname: "customer_drawing_number", label: "Drawing No" },
			{ fieldname: "item_no",                 label: "Item No" },
			{ fieldname: "material_code",           label: "Material Code" },
			{ fieldname: "material_name",           label: "Material Name" },
			{ fieldname: "item_group",               label: "Item Group" },
			{ fieldname: "parent_item_group",         label: "Parent Item Group" },
			{ fieldname: "grade",                   label: "Grade" },
			{ fieldname: "thickness",               label: "Thickness" },
			{ fieldname: "width",                   label: "Width" },
			{ fieldname: "length",                  label: "Length" },
			{ fieldname: "sec_qty",                 label: "Reqd Sec Qty" },
			{ fieldname: "sec_uom",                 label: "Sec UOM" },
			{ fieldname: "total_sec_qty",            label: "Total Sec Qty" },
			{ fieldname: "unit_weight",              label: "Unit Weight" },
			{ fieldname: "qty",                     label: "Weight (Primary UOM)" },
			{ fieldname: "uom",                     label: "UOM" },
			{ fieldname: "total_weight",             label: "Total Weight" },
			{ fieldname: "is_locked",               label: "Locked" },
		],
	},
};

// Generic View All popup — read-only, all configured columns, scrollable
function _so_show_table_popup(frm, fieldname) {
	var cfg = _SO_TABLE_VIEW_CONFIG[fieldname];
	if (!cfg) return;
	var rows = frm.doc[fieldname] || [];
	if (!rows.length) {
		frappe.msgprint(__("No data to display."));
		return;
	}

	var th_style = 'white-space:nowrap;padding:6px 10px;background:#f4f5f7;border-bottom:2px solid #d1d8dd;font-weight:600;font-size:11px;';
	var thead = '<tr>' + cfg.cols.map(function(c) {
		return '<th style="' + th_style + '">' + __(c.label) + '</th>';
	}).join('') + '</tr>';

	function _render_tbody(filtered_rows) {
		return filtered_rows.map(function(row, idx) {
			var cells = cfg.cols.map(function(c) {
				var val = row[c.fieldname];
				if (val === null || val === undefined) val = '';
				return '<td style="padding:5px 10px;white-space:nowrap;border-bottom:1px solid #f0f0f0;">'
					+ frappe.utils.escape_html(String(val)) + '</td>';
			}).join('');
			var bg = idx % 2 !== 0 ? 'background:#fafbfc;' : '';
			return '<tr style="' + bg + '">' + cells + '</tr>';
		}).join('');
	}

	var filter_bar = '<div style="display:flex;gap:8px;margin-bottom:8px;align-items:center;">'
		+ cfg.filters.map(function(f, i) {
			return '<input id="_so_vw_f' + i + '" type="text" placeholder="' + __(f.label) + '"'
				+ ' style="border:1px solid #d1d8dd;border-radius:4px;padding:4px 8px;font-size:12px;width:200px;">';
		}).join('')
		+ '<span id="_so_vw_count" style="font-size:12px;color:#6c757d;"></span></div>';

	var table_html = '<div style="overflow:auto;max-height:65vh;">'
		+ '<table style="font-size:12px;border-collapse:collapse;width:100%;" id="_so_vw_table">'
		+ '<thead style="position:sticky;top:0;z-index:1;">' + thead + '</thead>'
		+ '<tbody id="_so_vw_tbody">' + _render_tbody(rows) + '</tbody>'
		+ '</table></div>';

	var d = new frappe.ui.Dialog({
		title: __(cfg.title + " — {0} item(s)", [rows.length]),
		size: "extra-large",
	});
	d.$body.html(filter_bar + table_html);

	function _apply_filter() {
		var queries = cfg.filters.map(function(f, i) {
			return { fieldname: f.fieldname, q: (d.$body.find("#_so_vw_f" + i).val() || "").toLowerCase() };
		});
		var filtered = rows.filter(function(r) {
			return queries.every(function(qf) {
				return !qf.q || String(r[qf.fieldname] || "").toLowerCase().includes(qf.q);
			});
		});
		d.$body.find("#_so_vw_tbody").html(_render_tbody(filtered));
		d.$body.find("#_so_vw_count").text(filtered.length + " / " + rows.length + " " + __("rows"));
	}
	cfg.filters.forEach(function(f, i) { d.$body.find("#_so_vw_f" + i).on("input", _apply_filter); });
	_apply_filter();
	d.show();
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
    hide_sco_job_worker_warehouse()
    create_sco_custom_fields()
    create_sco_client_script()
    create_sco_ops_client_script()
    create_soe_client_script()
    create_work_order_custom_fields()
    layout_work_order_fields()
    create_wo_client_script()
    create_wo_ops_client_script()
    create_job_card_drawing_fields()
    layout_job_card_fields()
    create_jc_drawing_client_script()
    create_material_planning_auto_purchase_fields()
    create_manufacturing_settings_custom_fields()
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
    hide_sco_job_worker_warehouse()
    create_sco_custom_fields()
    create_sco_client_script()
    create_sco_ops_client_script()
    create_soe_client_script()
    create_work_order_custom_fields()
    layout_work_order_fields()
    create_wo_client_script()
    create_wo_ops_client_script()
    create_job_card_drawing_fields()
    layout_job_card_fields()
    create_jc_drawing_client_script()
    create_material_planning_auto_purchase_fields()
    create_manufacturing_settings_custom_fields()
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
            {
                "fieldname": "custom_drawing",
                "label": "Drawing",
                "fieldtype": "Link",
                "options": "Drawing",
                "insert_after": "custom_width",
                "in_list_view": 0,
            },
            {
                "fieldname": "custom_duno_mark_no",
                "label": "DUNO/Mark No",
                "fieldtype": "Data",
                "insert_after": "custom_drawing",
                "in_list_view": 0,
            },
            {
                "fieldname": "custom_customer_drawing_number",
                "label": "Customer Drawing Number",
                "fieldtype": "Data",
                "insert_after": "custom_duno_mark_no",
                "in_list_view": 0,
            },
            {
                "fieldname": "custom_sales_order",
                "label": "Sales Order",
                "fieldtype": "Link",
                "options": "Sales Order",
                "insert_after": "custom_customer_drawing_number",
                "in_list_view": 0,
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
            {
                "fieldname": "custom_drawing",
                "label": "Drawing",
                "fieldtype": "Link",
                "options": "Drawing",
                "insert_after": "custom_width",
                "in_list_view": 0,
            },
            {
                "fieldname": "custom_duno_mark_no",
                "label": "DUNO/Mark No",
                "fieldtype": "Data",
                "insert_after": "custom_drawing",
                "in_list_view": 0,
            },
            {
                "fieldname": "custom_customer_drawing_number",
                "label": "Customer Drawing Number",
                "fieldtype": "Data",
                "insert_after": "custom_duno_mark_no",
                "in_list_view": 0,
            },
            {
                "fieldname": "custom_sales_order",
                "label": "Sales Order",
                "fieldtype": "Link",
                "options": "Sales Order",
                "insert_after": "custom_customer_drawing_number",
                "in_list_view": 0,
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
            {
                "fieldname": "custom_drawing",
                "label": "Drawing",
                "fieldtype": "Link",
                "options": "Drawing",
                "insert_after": "custom_width",
                "in_list_view": 0,
            },
            {
                "fieldname": "custom_duno_mark_no",
                "label": "DUNO/Mark No",
                "fieldtype": "Data",
                "insert_after": "custom_drawing",
                "in_list_view": 0,
            },
            {
                "fieldname": "custom_customer_drawing_number",
                "label": "Customer Drawing Number",
                "fieldtype": "Data",
                "insert_after": "custom_duno_mark_no",
                "in_list_view": 0,
            },
            {
                "fieldname": "custom_sales_order",
                "label": "Sales Order",
                "fieldtype": "Link",
                "options": "Sales Order",
                "insert_after": "custom_customer_drawing_number",
                "in_list_view": 0,
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
            "Production Plan Item": [
                {
                    "fieldname": "custom_customer_weight_kg",
                    "fieldtype": "Float",
                    "label": "Customer Provided Weight (Kg)",
                    "insert_after": "custom_customer_drawing_number",
                    "in_list_view": 1,
                    "columns": 1,
                },
                {
                    "fieldname": "custom_planned_rm_weight_kg",
                    "fieldtype": "Float",
                    "label": "Planned RM Weight (Kg)",
                    "insert_after": "custom_customer_weight_kg",
                    "read_only": 1,
                    "in_list_view": 1,
                    "columns": 1,
                },
            ],
            "Production Plan": [
                {
                    "fieldname": "custom_raw_material_warehouse",
                    "fieldtype": "Link",
                    "label": "Raw Material Warehouse",
                    "options": "Warehouse",
                    "insert_after": "po_items",
                    "read_only": 1,
                    "translatable": 0,
                },
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
                    "mandatory_depends_on": "eval:doc.custom_process_planning && doc.custom_process_planning.some(r => r.work_type === 'Subcontractor')",
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

		if (!has_sub && !has_internal) {
			frm.page.set_inner_btn_group_as_primary(__("Create"));
			return;
		}

		// Single unified button handles all 3 scenarios:
		//   all-sub → SCO only | all-internal → WO only | mixed → both SCO + WO
		frm.remove_custom_button(__("Work Order / Subcontract PO"), __("Create"));
		frm.add_custom_button(__("Work Order / Subcontract PO"), function() {
			if (has_sub && !frm.doc.custom_vendor_contractor) {
				frappe.msgprint(__("Please set Vendor/Contractor on this Production Plan before creating a Subcontracting Order."));
				return;
			}
			if (has_sub && has_internal) {
				_pp_create_both(frm);
			} else if (has_sub) {
				_pp_create_sco(frm);
			} else {
				_pp_create_wo(frm);
			}
		}, __("Create"));

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

function _pp_create_sco(frm) {
	frappe.db.get_value("Subcontracting Order", {"custom_production_plan": frm.doc.name}, "name", function(r) {
		if (r && r.name) {
			frappe.msgprint({ title: __("Already Created"), message: __("Subcontracting Order: ") + '<a href="/app/subcontracting-order/' + encodeURIComponent(r.name) + '">' + r.name + "</a>", indicator: "orange" });
			return;
		}
		frappe.call({
			method: "manufyxinvenzaerp.subcontracting_management.subcontracting.create_sco_from_production_plan",
			args: { pp_name: frm.doc.name },
			freeze: true,
			callback: function(r) {
				if (r.message) {
					frappe.msgprint({ title: __("Subcontracting Order Created (Draft)"), message: __("Set Supplier / Source / WIP Warehouses then submit: ") + '<a href="/app/subcontracting-order/' + encodeURIComponent(r.message) + '">' + r.message + "</a>", indicator: "green" });
					frm.reload_doc();
				}
			}
		});
	});
}

function _pp_create_wo(frm) {
	frappe.db.get_value("Work Order", {"production_plan": frm.doc.name}, "name", function(r) {
		if (r && r.name) {
			frappe.msgprint({ title: __("Already Created"), message: __("Work Order: ") + '<a href="/app/work-order/' + encodeURIComponent(r.name) + '">' + r.name + "</a>", indicator: "orange" });
			return;
		}
		frappe.call({
			method: "manufyxinvenzaerp.subcontracting_management.subcontracting.create_work_order_from_pp",
			args: { pp_name: frm.doc.name },
			freeze: true,
			callback: function(r) {
				if (r.message) {
					frappe.msgprint({ title: __("Work Order Created (Draft)"), message: __("Set Source / WIP Warehouses then submit: ") + '<a href="/app/work-order/' + encodeURIComponent(r.message) + '">' + r.message + "</a>", indicator: "green" });
					frm.reload_doc();
				}
			}
		});
	});
}

function _pp_create_both(frm) {
	// Mixed plan: check existing records then create what is missing (SCO first, WO second)
	frappe.db.get_value("Subcontracting Order", {"custom_production_plan": frm.doc.name}, "name", function(r1) {
		var sco_name = r1 && r1.name;
		frappe.db.get_value("Work Order", {"production_plan": frm.doc.name}, "name", function(r2) {
			var wo_name = r2 && r2.name;
			if (sco_name && wo_name) {
				frappe.msgprint({
					title: __("Already Created"),
					message: "SCO: " + '<a href="/app/subcontracting-order/' + encodeURIComponent(sco_name) + '">' + sco_name + "</a>"
					       + "<br>WO: " + '<a href="/app/work-order/' + encodeURIComponent(wo_name) + '">' + wo_name + "</a>",
					indicator: "orange"
				});
				return;
			}
			var created_msgs = [];
			if (sco_name) created_msgs.push("SCO (exists): " + '<a href="/app/subcontracting-order/' + encodeURIComponent(sco_name) + '">' + sco_name + "</a>");
			if (wo_name)  created_msgs.push("WO (exists): "  + '<a href="/app/work-order/'            + encodeURIComponent(wo_name)  + '">' + wo_name  + "</a>");

			function finish() {
				frappe.msgprint({ title: __("Done"), message: created_msgs.join("<br>"), indicator: "green" });
				frm.reload_doc();
			}

			function maybe_create_wo() {
				if (wo_name) { finish(); return; }
				frappe.call({
					method: "manufyxinvenzaerp.subcontracting_management.subcontracting.create_work_order_from_pp",
					args: { pp_name: frm.doc.name },
					freeze: true, freeze_message: __("Creating Work Order…"),
					callback: function(r) {
						if (r.message) created_msgs.push("Work Order: " + '<a href="/app/work-order/' + encodeURIComponent(r.message) + '">' + r.message + "</a>");
						finish();
					}
				});
			}

			if (!sco_name) {
				frappe.call({
					method: "manufyxinvenzaerp.subcontracting_management.subcontracting.create_sco_from_production_plan",
					args: { pp_name: frm.doc.name },
					freeze: true, freeze_message: __("Creating Subcontracting Order…"),
					callback: function(r) {
						if (r.message) created_msgs.push("Subcontracting Order: " + '<a href="/app/subcontracting-order/' + encodeURIComponent(r.message) + '">' + r.message + "</a>");
						maybe_create_wo();
					}
				});
			} else {
				maybe_create_wo();
			}
		});
	});
}
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

\t// Warning: Nos entered exceed previous operation's completed Nos. prev_sec is 0
\t// when there is genuinely no predecessor, so no explicit sequence_id gate is
\t// needed — this also covers a hybrid plan's Job Card 1, fed by the last
\t// submitted Supplier Operation Entry.
\tif (prev_sec > 0 && curr_sec > prev_sec) {
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
                {
                    "fieldname": "custom_is_consumable",
                    "fieldtype": "Check",
                    "label": "Consumable",
                    "in_list_view": 1,
                    "insert_after": "custom_existing_inward_date",
                    "description": "Mark this row as a consumable (welding rods, paint, etc.). "
                                   "Stock is deducted from the source warehouse on submission.",
                },
            ],
            "Stock Entry": [
                {
                    "fieldname": "custom_sco_ref",
                    "fieldtype": "Link",
                    "label": "Subcontracting Order (PP Flow)",
                    "options": "Subcontracting Order",
                    "read_only": 1,
                    "insert_after": "subcontracting_order",
                    "description": "PP-flow SCO link — used instead of subcontracting_order "
                                   "to avoid ERPNext supplied_items validation on send-to-subcontractor SEs.",
                },
                {
                    "fieldname": "custom_wo_ref",
                    "fieldtype": "Link",
                    "label": "Work Order (PP Flow)",
                    "options": "Work Order",
                    "read_only": 1,
                    "insert_after": "custom_sco_ref",
                    "description": "PP-flow WO link — used to track WO-linked SEs without "
                                   "triggering ERPNext's own work_order SE validation logic.",
                },
                {
                    "fieldname": "custom_mip_ref",
                    "fieldtype": "Link",
                    "label": "Material Issue Plan",
                    "options": "Material Issue Plan",
                    "read_only": 1,
                    "insert_after": "custom_wo_ref",
                    "description": "Set on transfer/CNC/excess-return entries created from a "
                                   "Material Issue Plan, alongside custom_sco_ref/custom_wo_ref "
                                   "so existing weight rollups keep working unchanged.",
                },
                {
                    "fieldname": "custom_mrs_number",
                    "fieldtype": "Data",
                    "label": "MRS Number",
                    "insert_after": "custom_mip_ref",
                    "depends_on": "eval:doc.subcontracting_order",
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


def hide_sco_job_worker_warehouse():
    """Hide Job Worker Warehouse — CustomSubcontractingOrder._auto_set_supplier_warehouse
    (overrides.py) resolves it automatically from the Job Worker's dedicated Warehouse
    ('<Job Worker> - <Company Abbr>') on PP-flow SCOs, so the user no longer picks it."""
    frappe.make_property_setter(
        {
            "doctype": "Subcontracting Order",
            "fieldname": "supplier_warehouse",
            "property": "hidden",
            "value": 1,
            "property_type": "Check",
        }
    )
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
                    "fieldname": "custom_supervisor",
                    "fieldtype": "Link",
                    "label": "Supervisor Name",
                    "options": "Employee",
                    "insert_after": "custom_all_ops_complete",
                },
                {
                    "fieldname": "custom_supervisor_mobile",
                    "fieldtype": "Data",
                    "label": "Mobile",
                    "fetch_from": "custom_supervisor.cell_number",
                    "read_only": 1,
                    "insert_after": "custom_supervisor",
                },
                {
                    # Warehouse fields moved to Material Issue Plan; the actual
                    # value used to compute this now comes from there (see
                    # subcontracting.py: _get_sco_transfer_warehouses).
                    "fieldname": "custom_cnc_transferred_weight_kg",
                    "fieldtype": "Float",
                    "label": "CNC Warehouse Qty (Kg)",
                    "read_only": 1,
                    "insert_after": "custom_supervisor_mobile",
                    "description": "Weight currently sitting in CNC warehouse awaiting transfer to supplier",
                    "allow_on_submit": 1,
                },
                {
                    "fieldname": "custom_section_drawings",
                    "fieldtype": "Section Break",
                    "label": "Drawing Details",
                    "insert_after": "custom_cnc_transferred_weight_kg",
                },
                {
                    "fieldname": "custom_drawing_items",
                    "fieldtype": "Table",
                    "label": "Drawing Items",
                    "options": "SCO Drawing Item",
                    "read_only": 1,
                    "insert_after": "custom_section_drawings",
                },
                {
                    "fieldname": "custom_section_weights",
                    "fieldtype": "Section Break",
                    "label": "Weight Summary",
                    "insert_after": "custom_drawing_items",
                },
                {
                    "fieldname": "custom_customer_weight_kg",
                    "fieldtype": "Float",
                    "label": "Customer Provided Weight (Kg)",
                    "read_only": 1,
                    "insert_after": "custom_section_weights",
                    "description": "Sum of customer-provided weight across all drawings",
                },
                {
                    "fieldname": "custom_total_weight_kg",
                    "fieldtype": "Float",
                    "label": "Planned RM Weight (Kg)",
                    "read_only": 1,
                    "insert_after": "custom_customer_weight_kg",
                    "description": "Sum of planned raw-material weight across all drawings",
                },
                {
                    "fieldname": "custom_mapped_weight_kg",
                    "fieldtype": "Float",
                    "label": "Mapped Weight (Kg)",
                    "read_only": 1,
                    "insert_after": "custom_total_weight_kg",
                    "description": "Reserved/mapped batch weight from Material Planning that will be transferred to the supplier",
                },
                {
                    "fieldname": "custom_excess_weight_kg",
                    "fieldtype": "Float",
                    "label": "Excess Weight (Kg)",
                    "read_only": 1,
                    "insert_after": "custom_mapped_weight_kg",
                    "description": "Over-mapped weight (mapped beyond planned) that the supplier must return",
                },
                {
                    "fieldname": "custom_excess_banner_html",
                    "fieldtype": "HTML",
                    "label": "Excess Banner",
                    "insert_after": "custom_excess_weight_kg",
                },
                {
                    "fieldname": "custom_transferred_weight_kg",
                    "fieldtype": "Float",
                    "label": "Transferred Weight (Kg)",
                    "read_only": 1,
                    "insert_after": "custom_excess_banner_html",
                    "description": "Weight actually transferred to supplier warehouse (updated on SE submit)",
                },
                {
                    "fieldname": "custom_operations_tab",
                    "fieldtype": "Tab Break",
                    "label": "Operations",
                    "insert_after": "letter_head",
                },
                {
                    "fieldname": "custom_operations_html",
                    "fieldtype": "HTML",
                    "label": "Operations Summary",
                    "insert_after": "custom_operations_tab",
                },
            ],
        },
        update=True,
    )


SCO_CLIENT_SCRIPT = """
frappe.ui.form.on("Subcontracting Order", {
\trefresh(frm) {
\t\t// Excess material banner — mirrors the Material Planning "Difference in Kg" notice
\t\tlet $bw = frm.fields_dict["custom_excess_banner_html"] && frm.fields_dict["custom_excess_banner_html"].$wrapper;
\t\tif ($bw) {
\t\t\tlet excess = flt(frm.doc.custom_excess_weight_kg);
\t\t\tif (excess > 0) {
\t\t\t\t$bw.html('<div style="margin-top:8px;padding:8px 12px;background:#f1f8e9;border-left:3px solid #66bb6a;border-radius:3px;font-size:12px;color:#33691e;"><b>Excess material (+' + flt(excess, 3).toFixed(3) + ' Kg):</b> This much extra is mapped versus planned. Ensure the supplier returns the excess quantity after the job.</div>');
\t\t\t} else if (frm.doc.custom_all_ops_complete) {
\t\t\t\t$bw.html("");
\t\t\t}
\t\t}

\t\tif (frm.doc.docstatus === 1 && frm.doc.custom_production_plan) {

\t\t\tfrm.add_custom_button(__("Material Issue Plan"), function() {
\t\t\t\tfrappe.call({
\t\t\t\t\tmethod: "manufyxinvenzaerp.subcontracting_management.doctype.material_issue_plan.material_issue_plan.create_from_subcontracting_order",
\t\t\t\t\targs: { sco_name: frm.doc.name },
\t\t\t\t\tfreeze: true,
\t\t\t\t\tfreeze_message: __("Creating Material Issue Plan…"),
\t\t\t\t\tcallback: function(r) {
\t\t\t\t\t\tif (r.message) {
\t\t\t\t\t\t\tfrappe.set_route("Form", "Material Issue Plan", r.message);
\t\t\t\t\t\t}
\t\t\t\t\t}
\t\t\t\t});
\t\t\t}, __("Create"));

\t\t\tif (frm.doc.custom_all_ops_complete) {
\t\t\t\t// Raw materials fully supplied → produce the finished goods. Creates a
\t\t\t\t// Manufacture stock entry that consumes the supplier-warehouse stock and
\t\t\t\t// adds the finished good to inventory on submission.
\t\t\t\tfrm.add_custom_button(__("Make Final Stock Entry"), function() {
\t\t\t\t\tfrappe.call({
\t\t\t\t\t\tmethod: "manufyxinvenzaerp.subcontracting_management.subcontracting.create_finished_goods_entry",
\t\t\t\t\t\targs: { sco_name: frm.doc.name },
\t\t\t\t\t\tfreeze: true,
\t\t\t\t\t\tfreeze_message: __("Creating Final Stock Entry…"),
\t\t\t\t\t\tcallback: function(r) {
\t\t\t\t\t\t\tif (r.message) {
\t\t\t\t\t\t\t\tfrappe.msgprint({
\t\t\t\t\t\t\t\t\ttitle: __("Final Stock Entry Created"),
\t\t\t\t\t\t\t\t\tmessage: __("Review and submit the stock entry: ") +
\t\t\t\t\t\t\t\t\t\t'<a href="/app/stock-entry/' + encodeURIComponent(r.message) + '">' + r.message + "</a>",
\t\t\t\t\t\t\t\t\tindicator: "green"
\t\t\t\t\t\t\t\t});
\t\t\t\t\t\t\t\tfrm.reload_doc();
\t\t\t\t\t\t\t}
\t\t\t\t\t\t}
\t\t\t\t\t});
\t\t\t\t});
\t\t\t}

\t\t\t// Create one Supplier Operation Entry per subcontractor operation
\t\t\tif (frm.doc.custom_transferred_weight_kg) {
\t\t\t\tfrm.add_custom_button(__("Supplier Operation Entries"), function() {
\t\t\t\t\tfrappe.call({
\t\t\t\t\t\tmethod: "manufyxinvenzaerp.subcontracting_management.subcontracting.create_supplier_operation_entries",
\t\t\t\t\t\targs: { sco_name: frm.doc.name },
\t\t\t\t\t\tfreeze: true,
\t\t\t\t\t\tcallback: function(r) {
\t\t\t\t\t\t\tif (r.message && r.message.length) {
\t\t\t\t\t\t\t\tfrappe.msgprint({
\t\t\t\t\t\t\t\t\ttitle: __("Supplier Operation Entries Created"),
\t\t\t\t\t\t\t\t\tmessage: r.message.join(", "),
\t\t\t\t\t\t\t\t\tindicator: "green"
\t\t\t\t\t\t\t\t});
\t\t\t\t\t\t\t} else if (frm.doc.custom_all_ops_complete) {
\t\t\t\t\t\t\t\tfrappe.msgprint(__("All Supplier Operation Entries already exist."));
\t\t\t\t\t\t\t}
\t\t\t\t\t\t\tfrm.reload_doc();
\t\t\t\t\t\t}
\t\t\t\t\t});
\t\t\t\t}, __("Create"));
\t\t\t}

\t\t}
\t},
});

""".strip()


SCO_OPS_SCRIPT_NAME = "Subcontracting Order-operations-summary"

SCO_OPS_SCRIPT = """
frappe.ui.form.on("Subcontracting Order", {
    refresh(frm) {
        render_soe_summary(frm);
    }
});

function render_soe_summary(frm) {
    var field = frm.get_field("custom_operations_html");
    if (!field) return;
    var $w = field.$wrapper;
    if (!frm.doc.name || frm.is_new()) {
        $w.html("<div class='text-muted'>Save and submit the Subcontracting Order to create operations.</div>");
        return;
    }
    frappe.call({
        method: "manufyxinvenzaerp.subcontracting_management.subcontracting.get_soe_summary",
        args: { sco_name: frm.doc.name },
        callback(r) {
            var rows = r.message || [];
            if (!rows.length) {
                $w.html("<div style='margin-bottom:8px'><button class='btn btn-xs btn-default sco-ops-refresh'>&#8635; Refresh</button></div>"
                    + "<div class='text-muted'>No Supplier Operation Entries created yet.</div>");
                $w.find(".sco-ops-refresh").on("click", function() { render_soe_summary(frm); });
                return;
            }
            var mfg_total_all = 0, avail_nos_total = 0, cons_nos_total = 0;
            var body = rows.map(function (d, idx) {
                var color = d.status === "Completed" ? "green"
                          : (d.status === "In Progress" ? "orange" : "gray");
                var submitted = d.docstatus === 1
                    ? "<span class='indicator green'>Submitted</span>"
                    : "<span class='indicator gray'>Draft</span>";
                var mfg     = flt(d.total_qty_to_mfg || 0);
                var avail   = flt(d.avail_nos || 0);
                var consumed = flt(d.total_completed_nos || 0);
                var diff    = flt(d.diff_nos || 0);
                mfg_total_all   += mfg;
                avail_nos_total += avail;
                cons_nos_total  += consumed;
                var diff_color = diff < 0 ? "color:red" : (diff > 0 ? "color:orange" : "");
                return "<tr>"
                    + "<td class='text-center'>" + (d.sequence_id || "") + "</td>"
                    + "<td><a href='/app/supplier-operation-entry/" + encodeURIComponent(d.name) + "'>"
                        + frappe.utils.escape_html(d.operation || "") + "</a></td>"
                    + "<td><span class='indicator " + color + "'>" + (d.status || "") + "</span></td>"
                    + "<td class='text-right'>" + format_number(mfg, null, 3) + "</td>"
                    + "<td class='text-right'>" + format_number(avail, null, 3) + ((d.sequence_id || 1) == 1 ? " <small class='text-muted'>Kg</small>" : "") + "</td>"
                    + "<td class='text-right'>" + format_number(consumed, null, 3) + "</td>"
                    + "<td class='text-right' style='" + diff_color + "'>" + format_number(diff, null, 3) + "</td>"
                    + "<td class='text-center'>" + submitted + "</td>"
                    + "<td class='text-center'><button class='btn btn-xs btn-default sco-drw-btn' data-idx='" + idx + "' title='View Drawings'>&#128366;</button></td>"
                    + "</tr>";
            }).join("");
            var html = "<div style='margin-bottom:8px'><button class='btn btn-xs btn-default sco-ops-refresh'>&#8635; Refresh</button></div>"
                + "<table class='table table-bordered' style='margin-top:4px'>"
                + "<thead><tr>"
                + "<th class='text-center' style='width:60px'>Seq</th>"
                + "<th>Operation</th>"
                + "<th style='width:130px'>Status</th>"
                + "<th class='text-right'>Overall Qty (Nos)</th>"
                + "<th class='text-right'>Available to Consume (Nos)</th>"
                + "<th class='text-right'>Total Consumed (Nos)</th>"
                + "<th class='text-right'>Difference (Nos)</th>"
                + "<th class='text-center' style='width:110px'>Entry</th>"
                + "<th class='text-center' style='width:70px'>Drawings</th>"
                + "</tr></thead><tbody>" + body + "</tbody>"
                + "<tfoot><tr style='font-weight:bold'>"
                + "<td colspan='3' class='text-right'>Total</td>"
                + "<td class='text-right'>" + format_number(mfg_total_all, null, 3) + "</td>"
                + "<td class='text-right'>" + format_number(avail_nos_total, null, 3) + "</td>"
                + "<td class='text-right'>" + format_number(cons_nos_total, null, 3) + "</td>"
                + "<td class='text-right'>" + format_number(avail_nos_total - cons_nos_total, null, 3) + "</td>"
                + "<td colspan='2'></td></tr></tfoot></table>"
                + "<div class='text-muted' style='margin-top:6px;font-size:11px'>"
                + "Op-1 Available = Transferred (Kg); Op-2+ Available = sum of Available (Nos) from drawing details.</div>";
            $w.html(html);
            $w.find(".sco-ops-refresh").on("click", function() { render_soe_summary(frm); });
            $w.find(".sco-drw-btn").on("click", function() {
                var idx = parseInt($(this).data("idx"), 10);
                show_drawing_popup(rows[idx]);
            });
        }
    });
}

function show_drawing_popup(soe) {
    var drawings = soe.drawing_details || [];
    var drw_rows = drawings.map(function(d) {
        return "<tr>"
            + "<td>" + frappe.utils.escape_html(d.drawing || "") + "</td>"
            + "<td>" + frappe.utils.escape_html(d.customer_drawing_number || "") + "</td>"
            + "<td class='text-right'>" + format_number(flt(d.qty_to_manufacture || 0), null, 3) + "</td>"
            + "<td class='text-right'>" + format_number(flt(d.completed_qty_nos || 0), null, 3) + "</td>"
            + "</tr>";
    }).join("");
    var content = !drawings.length
        ? "<div class='text-muted' style='padding:12px'>No drawings attached to this operation.</div>"
        : "<table class='table table-bordered table-condensed' style='margin:0'>"
            + "<thead><tr>"
            + "<th>Drawing</th><th>Cust Drawing No</th>"
            + "<th class='text-right'>Qty to Mfg (Nos)</th>"
            + "<th class='text-right'>Completed (Nos)</th>"
            + "</tr></thead>"
            + "<tbody>" + drw_rows + "</tbody>"
            + "</table>";
    var dlg = new frappe.ui.Dialog({
        title: "Drawings — " + frappe.utils.escape_html(soe.operation || soe.name),
        fields: [{ fieldtype: "HTML", fieldname: "content" }],
    });
    dlg.fields_dict.content.$wrapper.html(content);
    dlg.show();
}
""".strip()


SOE_CLIENT_SCRIPT = """
frappe.ui.form.on("SOE Consumption Log", {
\tdrawing: function(frm) {
\t\t_sync_drawing_nos(frm);
\t},
\tqty_nos: function(frm) {
\t\t_sync_drawing_nos(frm);
\t},
\tconsumption_log_remove: function(frm) {
\t\t_sync_drawing_nos(frm);
\t},
\tconsumption_log_add: function(frm) {
\t\t_sync_drawing_nos(frm);
\t}
});

frappe.ui.form.on("Supplier Operation Entry", {
\trefresh: function(frm) {
\t\t_sync_drawing_nos(frm);
\t\t// Filter drawing link in log to only drawings present in this SOE
\t\tvar valid_drawings = (frm.doc.drawing_details || []).map(function(r) {
\t\t\treturn r.drawing;
\t\t}).filter(Boolean);
\t\tif (valid_drawings.length) {
\t\t\tfrm.fields_dict.consumption_log.grid.update_docfield_property(
\t\t\t\t"drawing", "get_query", function() {
\t\t\t\t\treturn { filters: [["Drawing", "name", "in", valid_drawings]] };
\t\t\t\t}
\t\t\t);
\t\t}
\t}
});

function _sync_drawing_nos(frm) {
\t// Sum qty_nos per drawing from the consumption log
\tvar byDrawing = {};
\t(frm.doc.consumption_log || []).forEach(function(r) {
\t\tif (r.drawing) {
\t\t\tbyDrawing[r.drawing] = (byDrawing[r.drawing] || 0) + flt(r.qty_nos);
\t\t}
\t});

\t// Push completed_qty_nos into each drawing_details row
\t(frm.doc.drawing_details || []).forEach(function(row) {
\t\tvar completed = flt(byDrawing[row.drawing] || 0, 3);
\t\tfrappe.model.set_value(row.doctype, row.name, "completed_qty_nos", completed);
\t});
\tfrm.refresh_field("drawing_details");

\t// Auto-advance status
\tvar has_log = (frm.doc.consumption_log || []).some(function(r) { return flt(r.qty_nos) > 0; });
\tif (has_log && frm.doc.status === "Open") {
\t\tfrm.set_value("status", "In Progress");
\t}

\t// Op-2+: warn if any drawing exceeds available_to_consume_nos
\tif ((frm.doc.sequence_id || 1) > 1) {
\t\tvar detailMap = {};
\t\t(frm.doc.drawing_details || []).forEach(function(r) {
\t\t\tif (r.drawing) detailMap[r.drawing] = flt(r.available_to_consume_nos);
\t\t});
\t\tvar exceeded = Object.keys(byDrawing).filter(function(d) {
\t\t\tvar avail = detailMap[d] || 0;
\t\t\treturn avail > 0 && byDrawing[d] > avail;
\t\t});
\t\tif (exceeded.length) {
\t\t\tfrappe.show_alert({
\t\t\t\tmessage: __("Completed Nos for some drawings exceeds available from the previous operation."),
\t\t\t\tindicator: "red"
\t\t\t}, 8);
\t\t}
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


def create_sco_ops_client_script():
    if frappe.db.exists("Client Script", SCO_OPS_SCRIPT_NAME):
        frappe.db.set_value("Client Script", SCO_OPS_SCRIPT_NAME, "script", SCO_OPS_SCRIPT)
        frappe.db.set_value("Client Script", SCO_OPS_SCRIPT_NAME, "enabled", 1)
    else:
        frappe.get_doc({
            "doctype": "Client Script",
            "name": SCO_OPS_SCRIPT_NAME,
            "dt": "Subcontracting Order",
            "view": "Form",
            "enabled": 1,
            "script": SCO_OPS_SCRIPT,
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


def create_manufacturing_settings_custom_fields():
    create_custom_fields(
        {
            "Manufacturing Settings": [
                {
                    "fieldname": "custom_soe_log_trigger",
                    "fieldtype": "Select",
                    "label": "SOE Log Entry Allowed When",
                    "options": "Fully Transferred\nPartially Transferred",
                    "default": "Fully Transferred",
                    "insert_after": "make_serial_no_batch_from_work_order",
                    "description": (
                        "Fully Transferred: consumption log entries are blocked until all planned "
                        "weight for that drawing has been transferred to the supplier warehouse. "
                        "Partially Transferred: log entries are always allowed."
                    ),
                },
            ],
        },
        update=True,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Work Order custom fields + client scripts  (SHARED_SCO_JC mirror)
# ─────────────────────────────────────────────────────────────────────────────

def create_work_order_custom_fields():
    """Custom fields on Work Order that mirror SCO drawing/weight/transfer fields.
    # SHARED_SCO_JC: mirrors create_sco_custom_fields()
    """
    create_custom_fields(
        {
            "Work Order": [
                {
                    "fieldname": "custom_all_ops_complete",
                    "fieldtype": "Check",
                    "label": "All Operations Complete",
                    "read_only": 1,
                    "insert_after": "wip_warehouse",
                },
                {
                    "fieldname": "custom_cnc_transferred_weight_kg",
                    "fieldtype": "Float",
                    "label": "CNC Warehouse Qty (Kg)",
                    "read_only": 1,
                    "insert_after": "custom_all_ops_complete",
                    "description": "Weight currently sitting in CNC warehouse awaiting transfer to WIP",
                    "allow_on_submit": 1,
                },
                {
                    "fieldname": "custom_section_drawings",
                    "fieldtype": "Section Break",
                    "label": "Drawing Details",
                    "insert_after": "custom_cnc_transferred_weight_kg",
                },
                {
                    "fieldname": "custom_drawing_items",
                    "fieldtype": "Table",
                    "label": "Drawing Items",
                    "options": "SCO Drawing Item",
                    "read_only": 1,
                    "insert_after": "custom_section_drawings",
                },
                {
                    "fieldname": "custom_section_weights",
                    "fieldtype": "Section Break",
                    "label": "Weight Summary",
                    "insert_after": "custom_drawing_items",
                },
                {
                    "fieldname": "custom_customer_weight_kg",
                    "fieldtype": "Float",
                    "label": "Customer Provided Weight (Kg)",
                    "read_only": 1,
                    "insert_after": "custom_section_weights",
                    "description": "Sum of customer-provided weight across all drawings",
                },
                {
                    "fieldname": "custom_total_weight_kg",
                    "fieldtype": "Float",
                    "label": "Planned RM Weight (Kg)",
                    "read_only": 1,
                    "insert_after": "custom_customer_weight_kg",
                    "description": "Sum of planned raw-material weight across all drawings",
                },
                {
                    "fieldname": "custom_mapped_weight_kg",
                    "fieldtype": "Float",
                    "label": "Mapped Weight (Kg)",
                    "read_only": 1,
                    "insert_after": "custom_total_weight_kg",
                    "description": "Reserved/mapped batch weight from Material Planning",
                },
                {
                    "fieldname": "custom_excess_weight_kg",
                    "fieldtype": "Float",
                    "label": "Excess Weight (Kg)",
                    "read_only": 1,
                    "insert_after": "custom_mapped_weight_kg",
                    "description": "Over-mapped weight that must be returned after the job",
                },
                {
                    "fieldname": "custom_excess_banner_html",
                    "fieldtype": "HTML",
                    "label": "Excess Banner",
                    "insert_after": "custom_excess_weight_kg",
                },
                {
                    "fieldname": "custom_transferred_weight_kg",
                    "fieldtype": "Float",
                    "label": "Transferred Weight (Kg)",
                    "read_only": 1,
                    "insert_after": "custom_excess_banner_html",
                    "description": "Weight actually transferred to WIP warehouse (updated on SE submit)",
                },
                {
                    "fieldname": "custom_weight_summary_column_break",
                    "fieldtype": "Column Break",
                    "insert_after": "custom_transferred_weight_kg",
                },
                {
                    "fieldname": "custom_operations_tab",
                    "fieldtype": "Tab Break",
                    "label": "Operations",
                    "insert_after": "custom_weight_summary_column_break",
                },
                {
                    "fieldname": "custom_operations_html",
                    "fieldtype": "HTML",
                    "label": "Operations Summary",
                    "insert_after": "custom_operations_tab",
                },
            ],
        },
        update=True,
    )


def layout_work_order_fields():
    """Hide/un-mandate noisy core fields and consolidate the custom drawing/
    weight/warehouse fields into the "Production Item" tab so the Work Order
    form reads as: item info -> warehouses -> drawing items -> weight summary,
    with the core Required Items grid, serial/batch section, and a handful of
    always-irrelevant fields (Stock UOM, Material Request, 4 flow checkboxes)
    hidden out of the way.
    """
    for args in [
        {"fieldname": "production_item", "property": "reqd", "value": 0},
        {"fieldname": "bom_no", "property": "reqd", "value": 0},
        {"fieldname": "qty", "property": "reqd", "value": 0},
        {"fieldname": "source_warehouse", "property": "reqd", "value": 0},
        {"fieldname": "source_warehouse", "property": "hidden", "value": 1},
        {"fieldname": "production_item", "property": "hidden", "value": 1},
        {"fieldname": "item_name", "property": "hidden", "value": 1},
        {"fieldname": "bom_no", "property": "hidden", "value": 1},
        {"fieldname": "sales_order", "property": "hidden", "value": 1},
        {"fieldname": "qty", "property": "hidden", "value": 1},
        {"fieldname": "required_items", "property": "hidden", "value": 1},
        {"fieldname": "required_items_section", "property": "hidden", "value": 1},
        {"fieldname": "allow_alternative_item", "property": "hidden", "value": 1},
        {"fieldname": "use_multi_level_bom", "property": "hidden", "value": 1},
        {"fieldname": "skip_transfer", "property": "hidden", "value": 1},
        {"fieldname": "update_consumed_material_cost_in_project", "property": "hidden", "value": 1},
        {"fieldname": "serial_no_and_batch_for_finished_good_section", "property": "hidden", "value": 1},
        {"fieldname": "has_serial_no", "property": "hidden", "value": 1},
        {"fieldname": "has_batch_no", "property": "hidden", "value": 1},
        {"fieldname": "batch_size", "property": "hidden", "value": 1},
        {"fieldname": "stock_uom", "property": "hidden", "value": 1},
        {"fieldname": "material_request", "property": "hidden", "value": 1},
        {"fieldname": "materials_and_operations_tab", "property": "hidden", "value": 1},
    ]:
        frappe.make_property_setter(
            {
                "doctype": "Work Order",
                "fieldname": args["fieldname"],
                "property": args["property"],
                "value": args["value"],
                "property_type": "Check",
            }
        )

    field_order = [
        # Tab: Production Item
        "item", "naming_series", "status", "production_item", "item_name", "image",
        "bom_no", "sales_order", "column_break1", "qty",
        "material_transferred_for_manufacturing", "produced_qty", "disassembled_qty",
        "process_loss_qty", "project",
        "section_break_ndpq", "required_items",
        "warehouses", "source_warehouse", "wip_warehouse", "custom_all_ops_complete",
        "custom_cnc_transferred_weight_kg",
        "column_break_12", "fg_warehouse", "scrap_warehouse",
        "custom_section_drawings", "custom_drawing_items",
        "custom_section_weights", "custom_customer_weight_kg", "custom_total_weight_kg",
        "custom_mapped_weight_kg", "custom_excess_weight_kg", "custom_excess_banner_html",
        "custom_transferred_weight_kg",
        # Weight Summary column 2 — mirrors SCO's Company / Date / Required By
        "custom_weight_summary_column_break", "company", "planned_start_date",
        "expected_delivery_date",
        # Tab: Configuration
        "work_order_configuration", "settings_section", "allow_alternative_item",
        "use_multi_level_bom", "column_break_17", "skip_transfer", "from_wip_warehouse",
        "update_consumed_material_cost_in_project",
        "serial_no_and_batch_for_finished_good_section", "has_serial_no", "has_batch_no",
        "column_break_18", "batch_size", "required_items_section",
        # Tab: Operations summary (custom)
        "custom_operations_tab", "custom_operations_html",
        # Tab: Operations (core) — hidden; kept in the order list so field_order
        # stays a complete permutation of every Work Order field
        "materials_and_operations_tab", "operations_section", "transfer_material_against",
        "operations", "time", "planned_end_date",
        "column_break_13", "actual_start_date", "actual_end_date", "lead_time", "section_break_22",
        "planned_operating_cost", "actual_operating_cost", "additional_operating_cost",
        "column_break_24", "corrective_operation_cost", "total_operating_cost",
        # Tab: More Info
        "more_info", "description", "stock_uom", "column_break2", "material_request",
        "material_request_item", "sales_order_item", "production_plan", "production_plan_item",
        "production_plan_sub_assembly_item", "product_bundle_item", "amended_from",
        # Tab: Connections
        "connections_tab",
    ]
    frappe.make_property_setter(
        {
            "doctype": "Work Order",
            "doctype_or_field": "DocType",
            "fieldname": None,
            "property": "field_order",
            "value": frappe.as_json(field_order),
            "property_type": "Data",
        }
    )
    frappe.db.commit()


def create_job_card_drawing_fields():
    """Custom fields on Job Card that mirror SOE drawing/consumption fields.
    # SHARED_SCO_JC: mirrors SOE's drawing_details + consumption_log fields
    """
    create_custom_fields(
        {
            "Job Card": [
                {
                    "fieldname": "custom_section_drawing_details",
                    "fieldtype": "Section Break",
                    "label": "Drawing Details",
                    "insert_after": "for_quantity",
                },
                {
                    "fieldname": "custom_drawing_details",
                    "fieldtype": "Table",
                    "label": "Drawing Details",
                    "options": "SOE Drawing Detail",
                    "read_only": 1,
                    "insert_after": "custom_section_drawing_details",
                },
                {
                    "fieldname": "custom_consumption_log_section",
                    "fieldtype": "Section Break",
                    "label": "Consumption Log",
                    "insert_after": "custom_drawing_details",
                },
                {
                    "fieldname": "custom_consumption_log",
                    "fieldtype": "Table",
                    "label": "Consumption Log",
                    "options": "Job Card Consumption Log",
                    "insert_after": "custom_consumption_log_section",
                },
                {
                    "fieldname": "custom_available_to_consume_kg",
                    "fieldtype": "Float",
                    "label": "Available to Consume (Kg)",
                    "read_only": 1,
                    "insert_after": "custom_consumption_log",
                },
                {
                    "fieldname": "custom_total_consumed_kg",
                    "fieldtype": "Float",
                    "label": "Total Consumed (Kg)",
                    "read_only": 1,
                    "insert_after": "custom_available_to_consume_kg",
                },
                {
                    "fieldname": "custom_total_available_nos",
                    "fieldtype": "Float",
                    "label": "Available to Consume (Nos)",
                    "read_only": 1,
                    "insert_after": "custom_total_consumed_kg",
                },
                {
                    "fieldname": "custom_total_completed_nos",
                    "fieldtype": "Float",
                    "label": "Total Consumed (Nos)",
                    "read_only": 1,
                    "insert_after": "custom_total_available_nos",
                },
            ],
        },
        update=True,
    )


def layout_job_card_fields():
    """Hide noisy core Job Card fields/tabs that duplicate the custom drawing/
    consumption tracking, and surface Sequence Id as a quick filter/list column.
    """
    for args in [
        {"fieldname": "bom_no", "property": "hidden", "value": 1},
        {"fieldname": "for_quantity", "property": "hidden", "value": 1},
        {"fieldname": "production_item", "property": "hidden", "value": 1},
        {"fieldname": "employee", "property": "hidden", "value": 1},
        {"fieldname": "timing_detail", "property": "hidden", "value": 1},
        {"fieldname": "scrap_items_section", "property": "hidden", "value": 1},
        {"fieldname": "scrap_items", "property": "hidden", "value": 1},
        {"fieldname": "custom_raw_material_consumption_tab", "property": "hidden", "value": 1},
        {"fieldname": "custom_raw_material_consumption", "property": "hidden", "value": 1},
        {"fieldname": "serial_and_batch_bundle", "property": "hidden", "value": 1},
        {"fieldname": "item_name", "property": "hidden", "value": 1},
        {"fieldname": "transferred_qty", "property": "hidden", "value": 1},
        {"fieldname": "requested_qty", "property": "hidden", "value": 1},
        {"fieldname": "sequence_id", "property": "in_list_view", "value": 1},
        {"fieldname": "sequence_id", "property": "in_standard_filter", "value": 1},
        {"fieldname": "work_order", "property": "in_standard_filter", "value": 1},
    ]:
        frappe.make_property_setter(
            {
                "doctype": "Job Card",
                "fieldname": args["fieldname"],
                "property": args["property"],
                "value": args["value"],
                "property_type": "Check",
            }
        )

    # Move Sequence Id out of "More Information" and into the default "Details"
    # tab (right after Qty To Manufacture), keeping every other field in place.
    field_order = [
        "naming_series", "work_order", "bom_no", "production_item", "employee",
        "column_break_4", "posting_date", "company", "for_quantity", "sequence_id",
        "custom_section_drawing_details", "custom_drawing_details",
        "custom_consumption_log_section", "custom_consumption_log",
        "custom_available_to_consume_kg", "custom_total_consumed_kg",
        "custom_total_available_nos", "custom_total_completed_nos", "total_completed_qty",
        "process_loss_qty", "scheduled_time_section", "expected_start_date", "time_required",
        "column_break_jkir", "expected_end_date", "section_break_05am", "scheduled_time_logs",
        "timing_detail", "time_logs", "section_break_13", "actual_start_date",
        "total_time_in_mins", "column_break_15", "actual_end_date", "production_section",
        "operation", "wip_warehouse", "column_break_12", "workstation_type", "workstation",
        "quality_inspection_section", "quality_inspection_template", "column_break_fcmp",
        "quality_inspection", "section_break_21", "sub_operations", "section_break_8", "items",
        "scrap_items_section", "scrap_items", "corrective_operation_section", "for_job_card",
        "is_corrective_job_card", "column_break_33", "hour_rate", "for_operation",
        "more_information", "project", "item_name", "transferred_qty", "requested_qty",
        "status", "column_break_20", "operation_row_number", "operation_id", "remarks",
        "serial_and_batch_bundle", "batch_no", "serial_no", "barcode", "job_started",
        "started_time", "current_time", "amended_from", "custom_raw_material_consumption_tab",
        "custom_raw_material_consumption", "connections_tab", "inventory_dimension",
        "storage_location",
    ]
    frappe.make_property_setter(
        {
            "doctype": "Job Card",
            "doctype_or_field": "DocType",
            "fieldname": None,
            "property": "field_order",
            "value": frappe.as_json(field_order),
            "property_type": "Data",
        }
    )
    frappe.db.commit()


# ─── WO client script (mirrors SCO_CLIENT_SCRIPT) ─────────────────────────

WO_CLIENT_SCRIPT = """
frappe.ui.form.on("Work Order", {
\trefresh(frm) {
\t\t// Hide core "Create Pick List" / "Start" / "Create Job Card" buttons — raw
\t\t// material issuance is fully delegated to Material Issue Plan instead.
\t\tfrm.remove_custom_button(__("Create Pick List"));
\t\tfrm.remove_custom_button(__("Start"));
\t\tfrm.remove_custom_button(__("Create Job Card"));

\t\t// Excess material banner — mirrors SCO banner
\t\tlet $bw = frm.fields_dict["custom_excess_banner_html"] && frm.fields_dict["custom_excess_banner_html"].$wrapper;
\t\tif ($bw) {
\t\t\tlet excess = flt(frm.doc.custom_excess_weight_kg);
\t\t\tif (excess > 0) {
\t\t\t\t$bw.html('<div style="margin-top:8px;padding:8px 12px;background:#f1f8e9;border-left:3px solid #66bb6a;border-radius:3px;font-size:12px;color:#33691e;"><b>Excess material (+' + flt(excess, 3).toFixed(3) + ' Kg):</b> This much extra is mapped versus planned. Return the excess after the job.</div>');
\t\t\t} else if (frm.doc.custom_all_ops_complete) {
\t\t\t\t$bw.html("");
\t\t\t}
\t\t}

\t\tif (frm.doc.docstatus === 1 && frm.doc.production_plan) {
\t\t\tfrm.add_custom_button(__("Material Issue Plan"), function() {
\t\t\t\tfrappe.call({
\t\t\t\t\tmethod: "manufyxinvenzaerp.subcontracting_management.doctype.material_issue_plan.material_issue_plan.create_from_work_order",
\t\t\t\t\targs: { wo_name: frm.doc.name },
\t\t\t\t\tfreeze: true,
\t\t\t\t\tfreeze_message: __("Creating Material Issue Plan…"),
\t\t\t\t\tcallback: function(r) {
\t\t\t\t\t\tif (r.message) {
\t\t\t\t\t\t\tfrappe.set_route("Form", "Material Issue Plan", r.message);
\t\t\t\t\t\t}
\t\t\t\t\t}
\t\t\t\t});
\t\t\t}, __("Create"));
\t\t}
\t},
});
""".strip()


# ─── WO operations summary script (mirrors SCO_OPS_SCRIPT) ───────────────

WO_OPS_SCRIPT = """
frappe.ui.form.on("Work Order", {
    refresh(frm) {
        render_jc_summary(frm);
    }
});

function render_jc_summary(frm) {
    var field = frm.get_field("custom_operations_html");
    if (!field) return;
    var $w = field.$wrapper;
    if (!frm.doc.name || frm.is_new()) {
        $w.html("<div class='text-muted'>Save and submit the Work Order to create Job Cards.</div>");
        return;
    }
    frappe.call({
        method: "manufyxinvenzaerp.subcontracting_management.subcontracting.get_jc_summary",
        args: { wo_name: frm.doc.name },
        callback(r) {
            var rows = r.message || [];
            if (!rows.length) {
                $w.html("<div style='margin-bottom:8px'><button class='btn btn-xs btn-default wo-ops-refresh'>&#8635; Refresh</button></div>"
                    + "<div class='text-muted'>No Job Cards found yet. Submit the Work Order to auto-create them.</div>");
                $w.find(".wo-ops-refresh").on("click", function() { render_jc_summary(frm); });
                return;
            }
            var mfg_total_all = 0, avail_nos_total = 0, cons_nos_total = 0;
            var body = rows.map(function(d, idx) {
                var color = d.status === "Completed" ? "green" : (d.status === "In Progress" ? "orange" : "gray");
                var submitted = d.docstatus === 1
                    ? "<span class='indicator green'>Submitted</span>"
                    : "<span class='indicator gray'>Draft</span>";
                var mfg      = flt(d.total_qty_to_mfg || 0);
                var avail    = flt(d.avail_nos || 0);
                var consumed = flt(d.total_completed_nos || 0);
                var diff     = flt(d.diff_nos || 0);
                mfg_total_all   += mfg;
                avail_nos_total += avail;
                cons_nos_total  += consumed;
                var diff_color = diff < 0 ? "color:red" : (diff > 0 ? "color:orange" : "");
                return "<tr>"
                    + "<td class='text-center'>" + (d.sequence_id || "") + "</td>"
                    + "<td><a href='/app/job-card/" + encodeURIComponent(d.name) + "'>"
                        + frappe.utils.escape_html(d.operation || "") + "</a></td>"
                    + "<td><span class='indicator " + color + "'>" + (d.status || "") + "</span></td>"
                    + "<td class='text-right'>" + format_number(mfg, null, 3) + "</td>"
                    + "<td class='text-right'>" + format_number(avail, null, 3) + ((d.sequence_id || 1) == 1 ? " <small class='text-muted'>Kg</small>" : "") + "</td>"
                    + "<td class='text-right'>" + format_number(consumed, null, 3) + "</td>"
                    + "<td class='text-right' style='" + diff_color + "'>" + format_number(diff, null, 3) + "</td>"
                    + "<td class='text-center'>" + submitted + "</td>"
                    + "<td class='text-center'><button class='btn btn-xs btn-default wo-drw-btn' data-idx='" + idx + "' title='View Drawings'>&#128366;</button></td>"
                    + "</tr>";
            }).join("");
            var html = "<div style='margin-bottom:8px'><button class='btn btn-xs btn-default wo-ops-refresh'>&#8635; Refresh</button></div>"
                + "<table class='table table-bordered' style='margin-top:4px'>"
                + "<thead><tr>"
                + "<th class='text-center' style='width:60px'>Seq</th>"
                + "<th>Operation</th>"
                + "<th style='width:130px'>Status</th>"
                + "<th class='text-right'>Overall Qty (Nos)</th>"
                + "<th class='text-right'>Available to Consume (Nos)</th>"
                + "<th class='text-right'>Total Consumed (Nos)</th>"
                + "<th class='text-right'>Difference (Nos)</th>"
                + "<th class='text-center' style='width:110px'>Entry</th>"
                + "<th class='text-center' style='width:70px'>Drawings</th>"
                + "</tr></thead><tbody>" + body + "</tbody>"
                + "<tfoot><tr style='font-weight:bold'>"
                + "<td colspan='3' class='text-right'>Total</td>"
                + "<td class='text-right'>" + format_number(mfg_total_all, null, 3) + "</td>"
                + "<td class='text-right'>" + format_number(avail_nos_total, null, 3) + "</td>"
                + "<td class='text-right'>" + format_number(cons_nos_total, null, 3) + "</td>"
                + "<td class='text-right'>" + format_number(avail_nos_total - cons_nos_total, null, 3) + "</td>"
                + "<td colspan='2'></td></tr></tfoot></table>"
                + "<div class='text-muted' style='margin-top:6px;font-size:11px'>"
                + "Op-1 Available = Transferred (Kg); Op-2+ Available = sum of Available (Nos) from drawing details.</div>";
            $w.html(html);
            $w.find(".wo-ops-refresh").on("click", function() { render_jc_summary(frm); });
            $w.find(".wo-drw-btn").on("click", function() {
                show_jc_drawing_popup(rows[parseInt($(this).data("idx"), 10)]);
            });
        }
    });
}

function show_jc_drawing_popup(jc) {
    var drawings = jc.drawing_details || [];
    var drw_rows = drawings.map(function(d) {
        return "<tr>"
            + "<td>" + frappe.utils.escape_html(d.drawing || "") + "</td>"
            + "<td>" + frappe.utils.escape_html(d.customer_drawing_number || "") + "</td>"
            + "<td class='text-right'>" + format_number(flt(d.qty_to_manufacture || 0), null, 3) + "</td>"
            + "<td class='text-right'>" + format_number(flt(d.completed_qty_nos || 0), null, 3) + "</td>"
            + "</tr>";
    }).join("");
    var content = !drawings.length
        ? "<div class='text-muted' style='padding:12px'>No drawings attached to this Job Card.</div>"
        : "<table class='table table-bordered table-condensed' style='margin:0'>"
            + "<thead><tr><th>Drawing</th><th>Cust Drawing No</th>"
            + "<th class='text-right'>Qty to Mfg (Nos)</th><th class='text-right'>Completed (Nos)</th>"
            + "</tr></thead><tbody>" + drw_rows + "</tbody></table>";
    var dlg = new frappe.ui.Dialog({
        title: "Drawings — " + frappe.utils.escape_html(jc.operation || jc.name),
        fields: [{ fieldtype: "HTML", fieldname: "content" }],
    });
    dlg.fields_dict.content.$wrapper.html(content);
    dlg.show();
}
""".strip()


# ─── Job Card drawing consumption script (mirrors SOE_CLIENT_SCRIPT) ─────

JC_DRAWING_CLIENT_SCRIPT = """
frappe.ui.form.on("Job Card Consumption Log", {
\tdrawing: function(frm) { _jc_sync_drawing_nos(frm); },
\tqty_nos: function(frm) { _jc_sync_drawing_nos(frm); },
\tcustom_consumption_log_remove: function(frm) { _jc_sync_drawing_nos(frm); },
\tcustom_consumption_log_add:    function(frm) { _jc_sync_drawing_nos(frm); }
});

frappe.ui.form.on("Job Card", {
\trefresh: function(frm) {
\t\tif (!frm.doc.custom_drawing_details || !frm.doc.custom_drawing_details.length) return;
\t\t_jc_sync_drawing_nos(frm);
\t\tvar valid_drawings = (frm.doc.custom_drawing_details || []).map(function(r) { return r.drawing; }).filter(Boolean);
\t\tif (valid_drawings.length) {
\t\t\tfrm.fields_dict.custom_consumption_log.grid.update_docfield_property(
\t\t\t\t"drawing", "get_query", function() { return { filters: [["Drawing", "name", "in", valid_drawings]] }; }
\t\t\t);
\t\t}
\t}
});

function _jc_sync_drawing_nos(frm) {
\tif (!frm.doc.custom_drawing_details || !frm.doc.custom_drawing_details.length) return;
\t// Sum qty_nos per drawing from the consumption log
\tvar byDrawing = {};
\t(frm.doc.custom_consumption_log || []).forEach(function(r) {
\t\tif (r.drawing) byDrawing[r.drawing] = (byDrawing[r.drawing] || 0) + flt(r.qty_nos);
\t});

\t// Push completed_qty_nos into each drawing_details row
\t(frm.doc.custom_drawing_details || []).forEach(function(row) {
\t\tfrappe.model.set_value(row.doctype, row.name, "completed_qty_nos", flt(byDrawing[row.drawing] || 0, 3));
\t});
\tfrm.refresh_field("custom_drawing_details");

\t// Auto-advance status
\tvar has_log = (frm.doc.custom_consumption_log || []).some(function(r) { return flt(r.qty_nos) > 0; });
\tif (has_log && frm.doc.status === "Open") frm.set_value("status", "In Progress");

\t// Op-2+: warn if any drawing exceeds available_to_consume_nos
\tif ((frm.doc.sequence_id || 1) > 1) {
\t\tvar detailMap = {};
\t\t(frm.doc.custom_drawing_details || []).forEach(function(r) {
\t\t\tif (r.drawing) detailMap[r.drawing] = flt(r.available_to_consume_nos);
\t\t});
\t\tvar exceeded = Object.keys(byDrawing).filter(function(d) {
\t\t\tvar avail = detailMap[d] || 0;
\t\t\treturn avail > 0 && byDrawing[d] > avail;
\t\t});
\t\tif (exceeded.length) {
\t\t\tfrappe.show_alert({ message: __("Completed Nos for some drawings exceeds available from the previous operation."), indicator: "red" }, 8);
\t\t}
\t}
}
""".strip()


def create_wo_client_script():
    # SHARED_SCO_JC: mirrors create_sco_client_script()
    if frappe.db.exists("Client Script", WO_CLIENT_SCRIPT_NAME):
        frappe.db.set_value("Client Script", WO_CLIENT_SCRIPT_NAME, "script", WO_CLIENT_SCRIPT)
        frappe.db.set_value("Client Script", WO_CLIENT_SCRIPT_NAME, "enabled", 1)
    else:
        frappe.get_doc({
            "doctype": "Client Script",
            "name": WO_CLIENT_SCRIPT_NAME,
            "dt": "Work Order",
            "view": "Form",
            "enabled": 1,
            "script": WO_CLIENT_SCRIPT,
        }).insert(ignore_permissions=True)
    frappe.db.commit()


def create_wo_ops_client_script():
    # SHARED_SCO_JC: mirrors create_sco_ops_client_script()
    if frappe.db.exists("Client Script", WO_OPS_SCRIPT_NAME):
        frappe.db.set_value("Client Script", WO_OPS_SCRIPT_NAME, "script", WO_OPS_SCRIPT)
        frappe.db.set_value("Client Script", WO_OPS_SCRIPT_NAME, "enabled", 1)
    else:
        frappe.get_doc({
            "doctype": "Client Script",
            "name": WO_OPS_SCRIPT_NAME,
            "dt": "Work Order",
            "view": "Form",
            "enabled": 1,
            "script": WO_OPS_SCRIPT,
        }).insert(ignore_permissions=True)
    frappe.db.commit()


def create_jc_drawing_client_script():
    # SHARED_SCO_JC: mirrors create_soe_client_script()
    if frappe.db.exists("Client Script", JC_DRAWING_CLIENT_SCRIPT_NAME):
        frappe.db.set_value("Client Script", JC_DRAWING_CLIENT_SCRIPT_NAME, "script", JC_DRAWING_CLIENT_SCRIPT)
        frappe.db.set_value("Client Script", JC_DRAWING_CLIENT_SCRIPT_NAME, "enabled", 1)
    else:
        frappe.get_doc({
            "doctype": "Client Script",
            "name": JC_DRAWING_CLIENT_SCRIPT_NAME,
            "dt": "Job Card",
            "view": "Form",
            "enabled": 1,
            "script": JC_DRAWING_CLIENT_SCRIPT,
        }).insert(ignore_permissions=True)
    frappe.db.commit()


# ─────────────────────────────────────────────────────────────────────────────
# Material Planning — Auto Purchase custom fields
# ─────────────────────────────────────────────────────────────────────────────

def create_material_planning_auto_purchase_fields():
    """Add supplier, warning, and button fields used by the Auto Purchase feature."""
    create_custom_fields(
        {
            "Material Planning": [
                {
                    "fieldname": "custom_auto_purchase_section",
                    "fieldtype": "Section Break",
                    "label": "Auto Purchase",
                    "insert_after": "unavailable_items",
                    "hidden": 1,
                },
                {
                    "fieldname": "custom_auto_purchase_warning",
                    "fieldtype": "HTML",
                    "options": (
                        '<div style="margin:6px 0 10px;padding:8px 14px;'
                        'background:#fff3cd;border-left:4px solid #e6a817;'
                        'border-radius:3px;font-size:12px;color:#7d4e00;">'
                        "<strong>&#9888; Testing Only</strong> &mdash; "
                        "Auto Purchase feature is only for testing purposes. "
                        "Not recommended to use in live or production environments."
                        "</div>"
                    ),
                    "insert_after": "custom_auto_purchase_section",
                },
                {
                    "fieldname": "custom_auto_purchase_supplier",
                    "fieldtype": "Link",
                    "label": "Supplier (Auto Purchase)",
                    "options": "Supplier",
                    "insert_after": "custom_auto_purchase_warning",
                    "hidden": 1,
                    "description": "Supplier for the auto-created Purchase Order.",
                },
                {
                    "fieldname": "custom_auto_purchase_btn",
                    "fieldtype": "Button",
                    "label": "Auto Purchase",
                    "insert_after": "custom_auto_purchase_supplier",
                },
            ],
        },
        update=True,
    )
