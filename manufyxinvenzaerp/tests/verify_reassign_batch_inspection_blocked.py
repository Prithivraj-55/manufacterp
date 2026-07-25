"""Verify Phase 6.2's trickiest interaction: reassign_batch (Phase 2.1)
delegates to reserve_batches/reserve_exact_match_batches at the end to
finalize the new reservation. If the reassigned-to batch is inspection-
blocked, those functions throw "blocked pending inspection completion" when
it's the only unreserved row -- reassign_batch must catch that SPECIFIC
throw and downgrade it to a warning, not let it propagate and abort the
whole call (which would also undo the batch/dimension assignment already
saved earlier in the same function, since nothing was committed yet).

Reuses the solo blocked row left behind by verify_mp_inspection_gate.py
(Material Planning Material Mapping row on batch ZZINSP-R022, whose source
Purchase Receipt PR-26-00022 is still "Open" -- never completed). Run
verify_mp_inspection_gate.py first if that data doesn't exist yet.

Run via: bench --site manufact execute manufyxinvenzaerp.tests.verify_reassign_batch_inspection_blocked.run
"""

import frappe
from manufyxinvenzaerp.production_management.doctype.material_planning.material_planning import reassign_batch


def run():
    row = frappe.db.get_value(
        "Material Planning Material Mapping",
        {"batch": "ZZINSP-R022"},
        ["name", "parent", "item_code", "batch", "batch_sec_qty", "is_reserved"],
        as_dict=True,
    )
    print("row before:", row)
    assert row, "Expected the solo blocked row from verify_mp_inspection_gate.py to still exist"
    assert frappe.db.get_value("Purchase Receipt", "PR-26-00022", "custom_inspection_status") != "Completed", \
        "This check depends on PR-26-00022 still being un-Completed"

    result = reassign_batch(
        material_planning_name=row.parent,
        source_table="Material Planning Material Mapping",
        row_name=row.name,
        new_batch_no=row.batch,
        dimensions=frappe.as_json({}),
        sec_qty=row.batch_sec_qty,
    )
    print("warnings:", result.get("warnings"))
    assert result.get("warnings"), "Expected at least one warning (inspection block) to be surfaced"
    assert any("inspection" in (w.get("reason") or "").lower() for w in result["warnings"]), \
        "Expected an inspection-related warning in the result"

    mp = frappe.get_doc("Material Planning", row.parent)
    updated = next(r for r in mp.material_mapping if r.name == row.name)
    print("row after reassign -- is_reserved (expect 0, still blocked):", updated.is_reserved, "| batch:", updated.batch)
    assert updated.is_reserved == 0, "Row should remain unreserved -- reassign must not have been rolled back, but reservation must still be blocked"
    assert updated.batch == "ZZINSP-R022", "The batch assignment itself must have gone through despite the reservation being blocked"

    frappe.db.commit()
    print("\nALL CHECKS DONE — reassign_batch succeeded without throwing, surfaced an inspection warning, "
          "and correctly left the row unreserved (the batch assignment itself was NOT rolled back).")
