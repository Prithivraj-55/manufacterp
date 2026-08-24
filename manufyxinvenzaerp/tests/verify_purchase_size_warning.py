"""The purchase-size warning fires for the row you touched, and no other.

"Purchase Size Smaller Than Requirement" tells a buyer that a Consolidate Item line
is being bought in a size that cannot yield the biggest piece it was consolidated
for -- a 4000 mm bar for a 6936 mm member, or a plate with no purchase thickness set
at all.

It used to say so on every save of the whole document. Edit a batch in Material
Mapping and up came a popup about a purchase size in a different table that nobody
had gone near; leave a line's thickness blank and it came up on every save from then
on, unprompted, forever. A warning that appears when nothing relevant changed is one
people learn to dismiss without reading, which costs you the times it matters.

It now reports only Consolidate Item rows this save actually changed -- and on a
brand-new document, everything, since nothing there has been seen before.

Run: bench --site manufact execute manufyxinvenzaerp.tests.verify_purchase_size_warning.run
"""

import frappe
from frappe.utils import flt

checks = []


def check(label, got, want):
    ok = got == want
    checks.append(ok)
    print("  %-4s %-54s got=%r want=%r" % ("OK" if ok else "FAIL", label, got, want))


def _warned(mp_name, mutate=None):
    """Save the plan, optionally changing something first, and report whether the
    purchase-size warning was raised."""
    frappe.clear_messages()
    doc = frappe.get_doc("Material Planning", mp_name)
    if mutate:
        mutate(doc)
    doc.save(ignore_permissions=True)
    for entry in frappe.get_message_log():
        text = entry.get("message") if isinstance(entry, dict) else str(entry)
        if "biggest piece" in frappe.utils.strip_html(str(text)):
            return True
    return False


def _find_plan():
    """A plan that has both tables and at least one undersized purchase line."""
    for name in frappe.get_all("Material Planning", pluck="name", order_by="modified desc",
                               limit=40):
        doc = frappe.get_doc("Material Planning", name)
        if not (doc.consolidate_items and doc.unavailable_items):
            continue
        if _warned(name, lambda d: _touch_purchase_line(d)):
            frappe.db.rollback()
            return name
        frappe.db.rollback()
    return None


def _touch_purchase_line(doc):
    for row in doc.consolidate_items:
        if not row.get("alternate_item"):
            row.length = flt(row.length) + 1
            return row.item_code
    return None


def _touch_other_table(doc):
    if doc.material_mapping:
        row = doc.material_mapping[0]
        row.batch_remarks = (row.batch_remarks or "") + "."
    elif doc.available_raw_materials:
        row = doc.available_raw_materials[0]
        row.cnc_process = 0 if row.cnc_process else 1


def run():
    plan = _find_plan()
    if not plan:
        print("   No Material Planning on this site has an undersized purchase line.")
        print("   Nothing to measure — the check needs one to be meaningful.")
        return

    print("=== using %s ===" % plan)
    try:
        print()
        print("=== a save that changes nothing says nothing ===")
        check("plain save is quiet", _warned(plan), False)
        frappe.db.rollback()

        print()
        print("=== nor does editing a different table ===")
        check("editing Material Mapping is quiet",
              _warned(plan, _touch_other_table), False)
        frappe.db.rollback()

        print()
        print("=== editing the purchase line itself does say so ===")
        check("the row you touched is reported",
              _warned(plan, _touch_purchase_line), True)
        frappe.db.rollback()
    finally:
        frappe.db.rollback()

    print()
    print("=== and the rule is in the code, not just in this run ===")
    src = open(frappe.get_app_path(
        "manufyxinvenzaerp", "production_management", "doctype",
        "material_planning", "material_planning.py")).read()
    check("touched rows are worked out from the saved version",
          "def _consolidate_rows_touched(self):" in src, True)
    check("a new document still reports everything",
          "return None" in src.split("def _consolidate_rows_touched(self):")[1][:600], True)
    check("and untouched rows are skipped",
          "if touched is not None and c.name not in touched:" in src, True)

    print()
    print("=== SUMMARY ===")
    if all(checks):
        print("ALL %d CHECKS PASSED" % len(checks))
    else:
        print("%d of %d CHECKS FAILED" % (checks.count(False), len(checks)))
