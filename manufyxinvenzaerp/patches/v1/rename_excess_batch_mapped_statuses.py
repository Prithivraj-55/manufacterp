"""
Patch: rename_excess_batch_mapped_statuses

Material Mapping's Status (batch_mapped) is a plain Data field, so the stored
strings are the vocabulary the screen shows. Rows fulfilled from another job's
excess were spelled "Virtual (At Supplier)" / "Claimed (Pending Return)", which
did not read as mapped at a glance -- and the grid's status-pill formatter made
it worse by printing "Not Mapped" for any value other than "Mapped", so a row
that WAS mapped (just with no batch against it while the off-cut sat at the
supplier) looked untouched. The formatter now renders the real status, and these
two are renamed to lead with "Excess Mapped" so the origin is obvious.

Display-only: nothing keys off these strings except the "is this row mapped"
totals, and MAPPED_BATCH_STATUSES still lists both old spellings, so documents
are correct either side of this patch.
"""

import frappe

RENAMES = {
    "Virtual (At Supplier)": "Excess Mapped (At Supplier)",
    "Claimed (Pending Return)": "Excess Mapped (Pending Return)",
}


def execute():
    for old, new in RENAMES.items():
        frappe.db.set_value(
            "Material Planning Material Mapping",
            {"batch_mapped": old},
            "batch_mapped",
            new,
            update_modified=False,
        )
    frappe.db.commit()
