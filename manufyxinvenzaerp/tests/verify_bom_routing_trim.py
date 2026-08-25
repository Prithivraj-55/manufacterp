"""Standard Manufacturing Routing carries the operations the shop actually runs, in
order, and every operation dropped from it still exists as a master.

Nothing is ever deleted here -- an operation is only excluded from future
default-provisioning, so the Job Cards and Supplier Operation Entries of jobs already
raised keep pointing at something real.

Material Issue joined that list on 2026-08-25: issuing material is what the Material
Issue Plan does, and carrying it as an operation as well made every job start on a step
nobody worked. It is commented out in production_utils.OPERATIONS rather than deleted,
and its master is still here -- which is what the REMOVED check below insists on.

Run via: bench --site manufact execute manufyxinvenzaerp.tests.verify_bom_routing_trim.run
"""

import frappe

KEPT = ["Fit-up", "Welding", "Final", "Blasting", "Painting"]
REMOVED = ["Material Issue", "Cutting Status", "Material Matching", "Despatch",
           "Fitup Inspection", "Welding Inspection", "Final Inspection"]


def run():
    routing = frappe.get_doc("Routing", "Standard Manufacturing Routing")
    ops = [r.operation for r in routing.operations]
    print("Routing operations:", ops)
    assert ops == KEPT, f"Expected {KEPT}, got {ops}"

    for op in REMOVED:
        exists = frappe.db.exists("Operation", op)
        print(f"Removed-from-routing Operation master still exists ({op}): {bool(exists)}")
        assert exists, f"{op} master should NOT have been deleted"

    for op in KEPT:
        exists = frappe.db.exists("Operation", op)
        print(f"Kept Operation master exists ({op}): {bool(exists)}")
        assert exists, f"{op} master should exist"

    # Sequence 1 is the first operation the shop actually works. The report reads the
    # material issued to a job against whatever sits at sequence 1, so a routing that
    # renumbered wrongly would put the Kg under the wrong heading.
    first = min(routing.operations, key=lambda r: r.sequence_id or 0)
    print("Sequence 1 is:", first.operation, "at sequence_id", first.sequence_id)
    assert first.operation == KEPT[0], f"Expected {KEPT[0]} at sequence 1, got {first.operation}"
    assert first.sequence_id == 1, f"Expected sequence_id 1, got {first.sequence_id}"

    print("\nALL CHECKS DONE — Routing trimmed correctly, no master data deleted.")
