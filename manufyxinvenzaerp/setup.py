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
\t\tsetTimeout(function() { calculate_qty(frm, cdt, cdn); }, 600);
\t},
\tcustom_length(frm, cdt, cdn) { calculate_qty(frm, cdt, cdn); },
\tcustom_width(frm, cdt, cdn) { calculate_qty(frm, cdt, cdn); },
\tcustom_thickness(frm, cdt, cdn) { calculate_qty(frm, cdt, cdn); },
\tcustom_sec_qty(frm, cdt, cdn) { calculate_qty(frm, cdt, cdn); },
\tcustom_unit_weight(frm, cdt, cdn) { calculate_qty(frm, cdt, cdn); },
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

function calculate_qty(frm, cdt, cdn) {
\tvar row = locals[cdt][cdn];
\tvar group = row.custom_parent_item_group;
\tvar qty = null;

\tif (group === "Structurals") {
\t\tif (row.custom_length && row.custom_unit_weight && row.custom_sec_qty) {
\t\t\tqty = (row.custom_length / 1000) * row.custom_unit_weight * row.custom_sec_qty;
\t\t} else {
\t\t\twarn_missing_fields(row, group);
\t\t}
\t} else if (group === "Plates") {
\t\tif (row.custom_length && row.custom_width && row.custom_thickness && row.custom_unit_weight && row.custom_sec_qty) {
\t\t\tqty = (row.custom_length / 1000) * (row.custom_width / 1000) * row.custom_thickness * row.custom_unit_weight * row.custom_sec_qty;
\t\t} else {
\t\t\twarn_missing_fields(row, group);
\t\t}
\t}

\tif (qty !== null) {
\t\tfrappe.model.set_value(cdt, cdn, "qty", flt(qty, 3));
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
\t\tsetTimeout(function() { pr_calculate_qty(frm, cdt, cdn); }, 600);
\t},
\tcustom_length(frm, cdt, cdn) { pr_calculate_qty(frm, cdt, cdn); },
\tcustom_width(frm, cdt, cdn) { pr_calculate_qty(frm, cdt, cdn); },
\tcustom_thickness(frm, cdt, cdn) { pr_calculate_qty(frm, cdt, cdn); },
\tcustom_sec_qty(frm, cdt, cdn) { pr_calculate_qty(frm, cdt, cdn); },
\tcustom_unit_weight(frm, cdt, cdn) { pr_calculate_qty(frm, cdt, cdn); },
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

function pr_calculate_qty(frm, cdt, cdn) {
\tvar row = locals[cdt][cdn];
\tvar group = row.custom_parent_item_group;
\tvar qty = null;

\tif (group === "Structurals") {
\t\tif (row.custom_length && row.custom_unit_weight && row.custom_sec_qty) {
\t\t\tqty = (row.custom_length / 1000) * row.custom_unit_weight * row.custom_sec_qty;
\t\t} else {
\t\t\tpr_warn_missing_fields(row, group);
\t\t}
\t} else if (group === "Plates") {
\t\tif (row.custom_length && row.custom_width && row.custom_thickness && row.custom_unit_weight && row.custom_sec_qty) {
\t\t\tqty = (row.custom_length / 1000) * (row.custom_width / 1000) * row.custom_thickness * row.custom_unit_weight * row.custom_sec_qty;
\t\t} else {
\t\t\tpr_warn_missing_fields(row, group);
\t\t}
\t}

\tif (qty !== null) {
\t\tfrappe.model.set_value(cdt, cdn, "qty", flt(qty, 3));
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
\t}
});

frappe.ui.form.on("Material Request Item", {
\titem_code(frm, cdt, cdn) {
\t\tsetTimeout(function() { mr_calculate_qty(frm, cdt, cdn); }, 600);
\t},
\tcustom_length(frm, cdt, cdn) { mr_calculate_qty(frm, cdt, cdn); },
\tcustom_width(frm, cdt, cdn) { mr_calculate_qty(frm, cdt, cdn); },
\tcustom_thickness(frm, cdt, cdn) { mr_calculate_qty(frm, cdt, cdn); },
\tcustom_sec_qty(frm, cdt, cdn) { mr_calculate_qty(frm, cdt, cdn); },
\tcustom_unit_weight(frm, cdt, cdn) { mr_calculate_qty(frm, cdt, cdn); },
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

function mr_calculate_qty(frm, cdt, cdn) {
\tvar row = locals[cdt][cdn];
\tvar group = row.custom_parent_item_group;
\tvar qty = null;

\tif (group === "Structurals") {
\t\tif (row.custom_length && row.custom_unit_weight && row.custom_sec_qty) {
\t\t\tqty = (row.custom_length / 1000) * row.custom_unit_weight * row.custom_sec_qty;
\t\t} else {
\t\t\tmr_warn_missing_fields(row, group);
\t\t}
\t} else if (group === "Plates") {
\t\tif (row.custom_length && row.custom_width && row.custom_thickness && row.custom_unit_weight && row.custom_sec_qty) {
\t\t\tqty = (row.custom_length / 1000) * (row.custom_width / 1000) * row.custom_thickness * row.custom_unit_weight * row.custom_sec_qty;
\t\t} else {
\t\t\tmr_warn_missing_fields(row, group);
\t\t}
\t}

\tif (qty !== null) {
\t\tfrappe.model.set_value(cdt, cdn, "qty", flt(qty, 3));
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
\t\tsetTimeout(function() { sq_calculate_qty(frm, cdt, cdn); }, 600);
\t},
\tcustom_length(frm, cdt, cdn) { sq_calculate_qty(frm, cdt, cdn); },
\tcustom_width(frm, cdt, cdn) { sq_calculate_qty(frm, cdt, cdn); },
\tcustom_thickness(frm, cdt, cdn) { sq_calculate_qty(frm, cdt, cdn); },
\tcustom_sec_qty(frm, cdt, cdn) { sq_calculate_qty(frm, cdt, cdn); },
\tcustom_unit_weight(frm, cdt, cdn) { sq_calculate_qty(frm, cdt, cdn); },
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

function sq_calculate_qty(frm, cdt, cdn) {
\tvar row = locals[cdt][cdn];
\tvar group = row.custom_parent_item_group;
\tvar qty = null;

\tif (group === "Structurals") {
\t\tif (row.custom_length && row.custom_unit_weight && row.custom_sec_qty) {
\t\t\tqty = (row.custom_length / 1000) * row.custom_unit_weight * row.custom_sec_qty;
\t\t} else {
\t\t\tsq_warn_missing_fields(row, group);
\t\t}
\t} else if (group === "Plates") {
\t\tif (row.custom_length && row.custom_width && row.custom_thickness && row.custom_unit_weight && row.custom_sec_qty) {
\t\t\tqty = (row.custom_length / 1000) * (row.custom_width / 1000) * row.custom_thickness * row.custom_unit_weight * row.custom_sec_qty;
\t\t} else {
\t\t\tsq_warn_missing_fields(row, group);
\t\t}
\t}

\tif (qty !== null) {
\t\tfrappe.model.set_value(cdt, cdn, "qty", flt(qty, 3));
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
frappe.ui.form.on("Sales Order", {
\trefresh(frm) {
\t\tif (frm.doc.docstatus === 1) {
\t\t\tfrm.add_custom_button(__("Drawing"), function() {
\t\t\t\tfrappe.call({
\t\t\t\t\tmethod: "manufyxinvenzaerp.drawing_management.drawing_utils.create_drawings_from_so",
\t\t\t\t\targs: { so_name: frm.doc.name },
\t\t\t\t\tfreeze: true,
\t\t\t\t\tfreeze_message: __("Creating Drawings..."),
\t\t\t\t\tcallback: function(r) {
\t\t\t\t\t\tif (r.message && r.message.length) {
\t\t\t\t\t\t\tvar links = r.message.map(function(name) {
\t\t\t\t\t\t\t\treturn '<a href="/app/drawing/' + encodeURIComponent(name) + '" target="_blank">' + name + '</a>';
\t\t\t\t\t\t\t}).join(', ');
\t\t\t\t\t\t\tfrappe.msgprint({
\t\t\t\t\t\t\t\ttitle: __("Drawings Created"),
\t\t\t\t\t\t\t\tmessage: r.message.length + ' ' + __('Drawing(s) created') + ': ' + links,
\t\t\t\t\t\t\t\tindicator: 'green'
\t\t\t\t\t\t\t});
\t\t\t\t\t\t\tfrm.reload_doc();
\t\t\t\t\t\t}
\t\t\t\t\t}
\t\t\t\t});
\t\t\t}, __("Create"));
\t\t}
\t}
});
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
                "insert_after": "custom_unit_weight",
                "in_list_view": 1,
            },
            {
                "fieldname": "custom_length",
                "label": "Length",
                "fieldtype": "Float",
                "insert_after": "custom_thickness",
                "in_list_view": 1,
            },
            {
                "fieldname": "custom_width",
                "label": "Width",
                "fieldtype": "Float",
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
                "insert_after": "custom_unit_weight",
                "in_list_view": 1,
            },
            {
                "fieldname": "custom_length",
                "label": "Length",
                "fieldtype": "Float",
                "mandatory_depends_on": "eval:['Structurals','Plates'].includes(doc.custom_parent_item_group)",
                "insert_after": "custom_thickness",
                "in_list_view": 1,
            },
            {
                "fieldname": "custom_width",
                "label": "Width",
                "fieldtype": "Float",
                "mandatory_depends_on": "eval:doc.custom_parent_item_group==='Plates'",
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
                "insert_after": "custom_unit_weight",
                "in_list_view": 1,
            },
            {
                "fieldname": "custom_length",
                "label": "Length",
                "fieldtype": "Float",
                "mandatory_depends_on": "eval:['Structurals','Plates'].includes(doc.custom_parent_item_group)",
                "insert_after": "custom_thickness",
                "in_list_view": 1,
            },
            {
                "fieldname": "custom_width",
                "label": "Width",
                "fieldtype": "Float",
                "mandatory_depends_on": "eval:doc.custom_parent_item_group==='Plates'",
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
                "insert_after": "custom_unit_weight",
                "in_list_view": 1,
            },
            {
                "fieldname": "custom_length",
                "label": "Length",
                "fieldtype": "Float",
                "read_only": 1,
                "insert_after": "custom_thickness",
                "in_list_view": 1,
            },
            {
                "fieldname": "custom_width",
                "label": "Width",
                "fieldtype": "Float",
                "read_only": 1,
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
                "insert_after": "custom_unit_weight",
                "in_list_view": 1,
            },
            {
                "fieldname": "custom_length",
                "label": "Length",
                "fieldtype": "Float",
                "mandatory_depends_on": "eval:['Structurals','Plates'].includes(doc.custom_parent_item_group)",
                "insert_after": "custom_thickness",
                "in_list_view": 1,
            },
            {
                "fieldname": "custom_width",
                "label": "Width",
                "fieldtype": "Float",
                "mandatory_depends_on": "eval:doc.custom_parent_item_group==='Plates'",
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
                }
            ],
            "BOM Item": [
                {
                    "fieldname": "custom_item_number",
                    "fieldtype": "Int",
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
		if (!row.bom_no) return;
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
