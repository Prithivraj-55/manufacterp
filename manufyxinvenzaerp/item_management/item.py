import frappe
from frappe import _

FORMULA_GROUPS = {"Structurals", "Plates"}


def validate_item(doc, method):
    validate_parent_item_group(doc)
    set_calculation_type(doc)
    validate_uom_configuration(doc)
    validate_batch_configuration(doc)


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
            frappe.msgprint(
                _(
                    "System is configured for Primary UOM as KG for {0}. "
                    "If any other UOM is entered, amount calculation may mismatch"
                ).format(parent_group),
                indicator="orange",
                title=_("UOM Configuration Warning"),
            )
        if doc.custom_secondary_uom and doc.custom_secondary_uom != "Nos":
            frappe.msgprint(
                _(
                    "System is configured for Secondary UOM as NOS for {0}. "
                    "If any other UOM is entered, amount calculation may mismatch"
                ).format(parent_group),
                indicator="orange",
                title=_("Secondary UOM Warning"),
            )
    elif parent_group == "Nuts and Bolts":
        if doc.stock_uom and doc.stock_uom != "Nos":
            frappe.msgprint(
                _(
                    "System is configured for Primary UOM as NOS for {0}. "
                    "If any other UOM is entered, amount calculation may mismatch"
                ).format(parent_group),
                indicator="orange",
                title=_("UOM Configuration Warning"),
            )
        if doc.custom_secondary_uom and doc.custom_secondary_uom != "Kg":
            frappe.msgprint(
                _(
                    "System is configured for Secondary UOM as KG for {0}. "
                    "If any other UOM is entered, amount calculation may mismatch"
                ).format(parent_group),
                indicator="orange",
                title=_("Secondary UOM Warning"),
            )


def validate_batch_configuration(doc):
    if doc.has_batch_no and not doc.custom_batch_prefix:
        frappe.throw(_("Custom Batch Abbreviation is required when Has Batch No is enabled"))
