"""Verify Phase 1.4: Standard Manufacturing Routing trimmed to the 6 required
operations, in order, and the 6 removed Operation masters still exist (not
deleted -- only excluded from future default-provisioning, so historical
Job Card/Supplier Operation Entry rows referencing them stay valid).

Run via: bench --site manufact execute manufyxinvenzaerp.tests.verify_bom_routing_trim.run
"""

import frappe

KEPT = ["Material Issue", "Fit-up", "Welding", "Final", "Blasting", "Painting"]
REMOVED = ["Cutting Status", "Material Matching", "Despatch", "Fitup Inspection", "Welding Inspection", "Final Inspection"]


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

    print("\nALL CHECKS DONE — Routing trimmed correctly, no master data deleted.")
