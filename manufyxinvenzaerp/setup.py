import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

CLIENT_SCRIPT_NAME = "Item-parent-item-group-filter"
PO_CLIENT_SCRIPT_NAME = "Purchase Order-custom-po-item-logic"
PR_CLIENT_SCRIPT_NAME = "Purchase Receipt-custom-pr-item-logic"
SO_CLIENT_SCRIPT_NAME = "Sales Order-create-drawing-button"

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
    create_so_client_script()


def after_migrate():
    create_item_custom_fields()
    create_item_client_script()
    create_purchase_order_custom_fields()
    hide_purchase_order_weight_fields()
    create_purchase_order_client_script()
    create_purchase_receipt_custom_fields()
    create_batch_custom_fields()
    create_purchase_receipt_client_script()
    create_so_client_script()


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
                "insert_after": "description",
            },
            {
                "fieldname": "custom_length",
                "label": "Length",
                "fieldtype": "Float",
                "insert_after": "custom_thickness",
            },
            {
                "fieldname": "custom_width",
                "label": "Width",
                "fieldtype": "Float",
                "insert_after": "custom_length",
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
