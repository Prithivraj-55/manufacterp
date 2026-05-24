import frappe
from frappe import _

FORMULA_GROUPS = {"Structurals", "Plates"}

_LOCKED_FIELDS = {
    "custom_parent_item_group": "Parent Item Group",
    "stock_uom": "Default Unit of Measure",
    "custom_unit_weight": "Unit Weight",
    "custom_secondary_uom": "Secondary UOM",
    "custom_batch_prefix": "Custom Batch Abbreviation",
}


def validate_item(doc, method):
    validate_parent_item_group(doc)
    set_calculation_type(doc)
    validate_uom_configuration(doc)
    validate_batch_configuration(doc)
    validate_batch_prefix(doc)
    validate_locked_fields(doc)


def validate_parent_item_group(doc):
    if not doc.custom_parent_item_group:
        frappe.throw(_("Parent Item Group is mandatory"))


def set_calculation_type(doc):
    if doc.custom_parent_item_group in FORMULA_GROUPS:
        doc.custom_item_calculation_type = "Formula Weight Calculation"
    elif doc.custom_parent_item_group == "Nuts and Bolts":
        doc.custom_item_calculation_type = "Normal Weight Calculation"


def validate_uom_configuration(doc):
    parent_group = doc.custom_parent_item_group
    if not parent_group:
        return

    if parent_group in FORMULA_GROUPS:
        if doc.stock_uom and doc.stock_uom != "Kg":
            frappe.throw(
                _(
                    "System is configured for Primary UOM as KG for {0}. "
                    "Select Default UOM as Kg for Structurals Item Group"
                ).format(parent_group),
                title=_("UOM Configuration Warning"),
            )
        if doc.custom_secondary_uom and doc.custom_secondary_uom != "Nos":
            frappe.throw(
                _(
                    "System is configured for Secondary UOM as Nos for {0}. "
                    "Select Default UOM as Nos for Structurals Item Group"
                ).format(parent_group),
                title=_("Secondary UOM Warning"),
            )
    elif parent_group == "Nuts and Bolts":
        if doc.stock_uom and doc.stock_uom != "Nos":
            frappe.throw(
                _(
                    "System is configured for Primary UOM as NOS for {0}. "
                    "Select Default UOM as Nos for Nuts and Bolts Item Group"
                ).format(parent_group),
                title=_("UOM Configuration Warning"),
            )
        if doc.custom_secondary_uom and doc.custom_secondary_uom != "Kg":
            frappe.throw(
                _(
                    "System is configured for Secondary UOM as KG for {0}. "
                    "Select Default UOM as Kg for Nuts and Bolts Item Group"
                ).format(parent_group),
                title=_("Secondary UOM Warning"),
            )


def validate_batch_configuration(doc):
    if not doc.has_batch_no:
        return

    if doc.custom_parent_item_group in FORMULA_GROUPS:
        doc.create_new_batch = 1
        if not doc.custom_batch_prefix:
            frappe.throw(
                _("Custom Batch Abbreviation is required for {0} when Has Batch No is enabled").format(
                    doc.custom_parent_item_group
                )
            )


## This validation is required to prevent changing batch prefix when batches are already created with the old prefix, which can lead to data inconsistency.
def validate_batch_prefix(doc):
    if not doc.is_new():
        old_prefix = frappe.db.get_value("Item", doc.name, "custom_batch_prefix")
        if old_prefix and old_prefix != doc.custom_batch_prefix:
            batch_exists = frappe.db.exists("Batch", {"item": doc.name})

            if batch_exists:
                frappe.throw(
                    _("Cannot change the Custom Batch Abbreviation for Item {0} because existing transactions are linked to it.").format(doc.name)
                )


def _has_transactions(item_code):
    return bool(
        frappe.db.exists("Stock Ledger Entry", {"item_code": item_code})
        or frappe.db.exists("Purchase Order Item", {"item_code": item_code, "docstatus": 1})
        or frappe.db.exists("Sales Order Item", {"item_code": item_code, "docstatus": 1})
    )


def validate_locked_fields(doc):
    if doc.is_new() or not _has_transactions(doc.name):
        return
    for field, label in _LOCKED_FIELDS.items():
        if frappe.db.get_value("Item", doc.name, field) != doc.get(field):
            frappe.throw(
                _("Cannot change {0} for Item {1} because transactions already exist.").format(
                    label, doc.name
                )
            )


@frappe.whitelist()
def has_item_transactions(item_code):
    return _has_transactions(item_code)