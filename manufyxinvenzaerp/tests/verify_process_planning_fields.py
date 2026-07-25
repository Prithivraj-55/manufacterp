"""Verify Phase 3.2: Process Planning gained Create Operation (renamed from the
original Skip Operation, semantics inverted -- defaults to enabled) and
Inspection Mandatory checkboxes.

Run via: bench --site manufact execute manufyxinvenzaerp.tests.verify_process_planning_fields.run
"""

import frappe


def run():
    meta = frappe.get_meta("Process Planning")
    for fn in ["create_operation", "inspection_mandatory"]:
        f = meta.get_field(fn)
        print(fn, "->", (f.fieldtype, f.label, f.default) if f else "MISSING")
        assert f, f"Process Planning is missing field {fn}"
        assert f.fieldtype == "Check", f"{fn} should be a Check field"

    print("\nALL CHECKS DONE — Process Planning has both new checkboxes.")
