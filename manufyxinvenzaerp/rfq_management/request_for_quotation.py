import frappe
from manufyxinvenzaerp.utils.reference_copy import copy_reference_fields_if_blank

CUSTOM_FIELDS = [
    "custom_parent_item_group",
    "custom_item_calculation_type",
    "custom_sec_qty",
    "custom_sec_uom",
    "custom_unit_weight",
    "custom_thickness",
    "custom_length",
    "custom_width",
]


def validate_rfq(doc, method):
    for row in doc.items:
        _copy_from_mr_item(row)


def _copy_from_mr_item(row):
    # blank_check_fields=False: always copy, matching this function's existing
    # unconditional every-validate overwrite behavior (unlike PO/PR's
    # copy-only-if-blank pattern).
    copy_reference_fields_if_blank(
        row, "Material Request Item", "material_request_item", CUSTOM_FIELDS, blank_check_fields=False
    )
