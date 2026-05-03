import frappe

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
    if not row.material_request_item:
        return
    mr_item = frappe.db.get_value(
        "Material Request Item",
        row.material_request_item,
        CUSTOM_FIELDS,
        as_dict=True,
    )
    if not mr_item:
        return
    for field in CUSTOM_FIELDS:
        row.set(field, mr_item.get(field))
