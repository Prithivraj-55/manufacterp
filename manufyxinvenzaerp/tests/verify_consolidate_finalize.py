"""Verify Phase 2.4: Material Planning's validate() folds unavailable_items into
the Consolidate Item table, deduped by item_code, idempotently.

Builds a clean synthetic Material Planning with two Unavailable Item rows sharing
one item_code (simulating the same raw item needed by two different drawings),
saves it, and checks:
  1. Exactly one Consolidate Item row is created for that item_code.
  2. required_kg is the sum of both rows' qty.
  3. Both source rows get consolidated_into set to the item_code.
  4. Re-saving (idempotency check) does not double-count.
  5. Adding a third Unavailable Item row with the same item_code on a later save
     correctly adds only its own qty, not a re-sum of everything.

Run via: bench --site manufact execute manufyxinvenzaerp.tests.verify_consolidate_finalize.run
"""

import frappe
from frappe.utils import flt
from manufyxinvenzaerp.tests.create_full_test_entry import get_ctx, ensure_item


def run():
    ctx = get_ctx()
    item_a = ensure_item(ctx, "ZZTEST-CONSOL-A", "Consolidate Test Item A", uom="Kg")
    # ensure_item() defaults custom_parent_item_group to whatever generic Item Group
    # the site's first non-group Item Group happens to be (e.g. "Bolt child") -- fix
    # it to match this test's rows, since Consolidate Item's own parent_item_group
    # field is fetch_from=item_code.custom_parent_item_group and will re-sync from
    # the Item master on every save, overwriting whatever we append with directly.
    frappe.db.set_value("Item", item_a, "custom_parent_item_group", "Structurals")
    frappe.db.set_value("Item", item_a, "custom_unit_weight", 10)

    mp = frappe.new_doc("Material Planning")
    mp.company = ctx.company
    mp.posting_date = frappe.utils.today()
    mp.for_warehouse = ctx.warehouse

    mp.append("unavailable_items", {
        "item_code": item_a, "item_name": "Consolidate Test Item A",
        "parent_item_group": "Structurals", "unit_weight": 10,
        "qty": 40, "uom": "Kg", "sec_qty": 4, "sec_uom": "Nos",
        "duno_mark_no": "DUNO-1",
    })
    mp.append("unavailable_items", {
        "item_code": item_a, "item_name": "Consolidate Test Item A",
        "parent_item_group": "Structurals", "unit_weight": 10,
        "qty": 25, "uom": "Kg", "sec_qty": 2.5, "sec_uom": "Nos",
        "duno_mark_no": "DUNO-2",
    })
    mp.insert(ignore_permissions=True)
    print("Created test MP:", mp.name)

    mp.reload()
    consolidate_rows = [r for r in mp.consolidate_items if r.item_code == item_a]
    print("Consolidate Item rows for item_a (expect 1):", len(consolidate_rows))
    assert len(consolidate_rows) == 1, "Expected exactly one Consolidate Item row (dedup by item_code)"

    row = consolidate_rows[0]
    print("required_kg (expect 65):", row.required_kg)
    assert flt(row.required_kg) == 65, f"Expected required_kg=65, got {row.required_kg}"

    for u in mp.unavailable_items:
        print(f"  unavailable row duno={u.duno_mark_no} consolidated_into={u.consolidated_into}")
        assert u.consolidated_into == item_a, "Expected consolidated_into == item_code"

    # Idempotency: re-save without changes should not double-count.
    mp.save(ignore_permissions=True)
    mp.reload()
    consolidate_rows = [r for r in mp.consolidate_items if r.item_code == item_a]
    print("After re-save, required_kg (expect still 65):", consolidate_rows[0].required_kg)
    assert flt(consolidate_rows[0].required_kg) == 65, "Re-save must not double-count existing rows"
    assert len(consolidate_rows) == 1, "Re-save must not create a duplicate Consolidate Item row"

    # Add a third unavailable-item row with the same item_code on a later save.
    mp.append("unavailable_items", {
        "item_code": item_a, "item_name": "Consolidate Test Item A",
        "parent_item_group": "Structurals", "unit_weight": 10,
        "qty": 10, "uom": "Kg", "sec_qty": 1, "sec_uom": "Nos",
        "duno_mark_no": "DUNO-3",
    })
    mp.save(ignore_permissions=True)
    mp.reload()
    consolidate_rows = [r for r in mp.consolidate_items if r.item_code == item_a]
    print("After adding 3rd row, required_kg (expect 75):", consolidate_rows[0].required_kg)
    assert flt(consolidate_rows[0].required_kg) == 75, "New row must add only its own qty, not re-sum"
    assert len(consolidate_rows) == 1, "Still exactly one Consolidate Item row"

    frappe.db.commit()
    print("\nALL CHECKS DONE — Consolidate Item population is correct, deduped, and idempotent.")
    print("Test MP left in place (not deleted, per standing policy):", mp.name)
