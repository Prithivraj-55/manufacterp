"""
Patch: fix_bom_item_number_field_type

BOM Item.custom_item_number was originally created as Int.
Drawing items use alphanumeric item numbers (e.g. '1w27', '1p69').
cint('1w27') == 0, so every BOM item had item_number=0 and
Material Planning showed 0 for all item numbers.

Pre-model-sync step:  ALTER the DB column to VARCHAR(140) so Frappe does not
                      truncate alphanumeric values when re-syncing custom fields.

Post-model-sync step: Backfill custom_item_number on every BOM Item that is
                      linked to a Drawing, copying the value from the matching
                      Drawing Item row.
"""

import frappe


def execute():
    # ── Step 1: fix the column type if still INT ────────────────────────────
    col = frappe.db.sql(
        "SHOW COLUMNS FROM `tabBOM Item` LIKE 'custom_item_number'",
        as_dict=True,
    )
    if col and "int" in (col[0].get("Type") or "").lower():
        frappe.db.sql_ddl(
            "ALTER TABLE `tabBOM Item` MODIFY COLUMN custom_item_number VARCHAR(140)"
        )

    # ── Step 2: fix the Custom Field record if still Int ────────────────────
    frappe.db.sql(
        """
        UPDATE `tabCustom Field`
        SET fieldtype = 'Data', modified = NOW()
        WHERE dt = 'BOM Item' AND fieldname = 'custom_item_number'
          AND fieldtype = 'Int'
        """
    )

    # ── Step 3: backfill item_number from Drawing items ─────────────────────
    # For every BOM linked to a Drawing, copy item_number from Drawing Item
    # to BOM Item, matched on item_code (material_code).
    frappe.db.sql(
        """
        UPDATE `tabBOM Item` bi
        JOIN `tabBOM`         b  ON b.name  = bi.parent
        JOIN `tabDrawing Item` di ON di.parent = b.custom_drawing
                                  AND di.material_code = bi.item_code
        SET bi.custom_item_number = di.item_number
        WHERE b.custom_drawing IS NOT NULL
          AND b.custom_drawing != ''
          AND di.item_number IS NOT NULL
          AND di.item_number != ''
          AND di.item_number != '0'
        """
    )

    frappe.db.commit()
