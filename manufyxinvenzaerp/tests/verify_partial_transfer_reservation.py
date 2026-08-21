"""A partial transfer releases only what actually moved.

Submitting a transfer used to clear the reservation on every Material Planning row
holding that batch, however little of it had gone. Move 30 Kg of a 120 Kg reservation
and the other 90 Kg went straight back to the free pool, where the next plan could
take it -- even though this job still needed it and had not been given it yet.

The client's answer, when asked: reduce the reservation by what moved. So a row now
gives up only what left the warehouse, keeps the remainder, and is released outright
only when the remainder reaches zero.

Where several rows share one batch they give it up one at a time, in document order --
the same sequential rule used when a consolidated receipt is shared out. Spread a
partial transfer proportionally instead and every row is left holding a fraction it
can never transfer cleanly; filling one row at a time leaves whole reservations
behind and the shortfall lands on the last.

Cancelling unwinds from the back, so cancelling the most recent transfer -- much the
commonest case -- lands exactly where it started.

Self-contained: builds its own batch, its own plan and its own entries, and cancels
the entries on the way out. Nothing is deleted.

Run: bench --site manufact execute manufyxinvenzaerp.tests.verify_partial_transfer_reservation.run
"""

import frappe
from frappe.utils import flt

checks = []

ITEM = "ZZTEST-CS-REPACK"
UNIT_WEIGHT = 10.0
MM = "Material Planning Material Mapping"


def check(label, got, want):
    ok = got == want
    checks.append(ok)
    print("  %-4s %-52s got=%r want=%r" % ("OK" if ok else "FAIL", label, got, want))


def _warehouse():
    for name in ("Stores - MIPL", "Work In Progress - MIPL"):
        if frappe.db.exists("Warehouse", name):
            return name
    return frappe.get_all("Warehouse", filters={"is_group": 0}, pluck="name")[0]


def _entry(se_type, company, rows):
    se = frappe.get_doc({
        "doctype": "Stock Entry", "stock_entry_type": se_type,
        "company": company, "items": rows,
    })
    se.insert(ignore_permissions=True)
    se.submit()
    return se


def _held(row_name):
    r = frappe.db.get_value(MM, row_name, ["is_reserved", "reserved_qty"], as_dict=True)
    return (int(r.is_reserved), flt(r.reserved_qty, 3))


def run():
    company = frappe.get_all("Company", pluck="name")[0]
    warehouse = _warehouse()
    receipt = move1 = move2 = None

    try:
        print("=== 120 Kg in one batch, two jobs holding it: 70 and 50 ===")
        receipt = _entry("Material Receipt", company, [{
            "item_code": ITEM, "qty": 120, "t_warehouse": warehouse, "basic_rate": 50,
            "custom_parent_item_group": "Structurals", "custom_unit_weight": UNIT_WEIGHT,
            "custom_length": 12000, "custom_sec_qty": 1,
        }])
        batch = frappe.db.get_value(
            "Batch", {"reference_doctype": "Stock Entry", "reference_name": receipt.name}, "name")

        mp = frappe.get_doc({
            "doctype": "Material Planning", "company": company,
            "posting_date": frappe.utils.today(),
            "material_mapping": [
                {"item_code": ITEM, "batch": batch, "is_reserved": 1,
                 "qty": 70, "reserved_qty": 70, "batch_calc_qty": 70, "batch_sec_qty": 7},
                {"item_code": ITEM, "batch": batch, "is_reserved": 1,
                 "qty": 50, "reserved_qty": 50, "batch_calc_qty": 50, "batch_sec_qty": 5},
            ],
        })
        mp.flags.ignore_validate = True
        mp.insert(ignore_permissions=True)
        frappe.db.commit()
        row_a, row_b = mp.material_mapping[0].name, mp.material_mapping[1].name
        check("first row holds", _held(row_a), (1, 70.0))
        check("second row holds", _held(row_b), (1, 50.0))

        print()
        print("=== 30 Kg moves ===")
        move1 = _entry("Material Issue", company, [{
            "item_code": ITEM, "qty": 30, "s_warehouse": warehouse, "batch_no": batch,
            "custom_unit_weight": UNIT_WEIGHT,
        }])
        check("the first row gave up 30 and kept the rest", _held(row_a), (1, 40.0))
        check("the second row was not touched", _held(row_b), (1, 50.0))

        print()
        print("=== another 50 Kg moves ===")
        move2 = _entry("Material Issue", company, [{
            "item_code": ITEM, "qty": 50, "s_warehouse": warehouse, "batch_no": batch,
            "custom_unit_weight": UNIT_WEIGHT,
        }])
        check("the first row is emptied and released", _held(row_a), (0, 0.0))
        check("the rest came off the second row", _held(row_b), (1, 40.0))

        print()
        print("=== cancelling the second transfer puts back exactly its 50 ===")
        frappe.get_doc("Stock Entry", move2.name).cancel()
        check("the second row is whole again", _held(row_b), (1, 50.0))
        check("and the first is back to where it was", _held(row_a), (1, 40.0))

        print()
        print("=== cancelling the first puts back its 30 ===")
        frappe.get_doc("Stock Entry", move1.name).cancel()
        check("the first row is whole again", _held(row_a), (1, 70.0))
        check("the second row is untouched", _held(row_b), (1, 50.0))
        check("nothing was invented: 120 Kg reserved, as at the start",
              flt(_held(row_a)[1] + _held(row_b)[1], 3), 120.0)

        print()
        print("   left behind: %s (the holding plan)" % mp.name)

    finally:
        for se in (move2, move1, receipt):
            try:
                if se and frappe.db.get_value("Stock Entry", se.name, "docstatus") == 1:
                    frappe.get_doc("Stock Entry", se.name).cancel()
            except Exception as e:
                print("   (could not cancel %s: %s)" % (se.name, e))
        frappe.db.commit()
        print("   test entries cancelled, nothing deleted")

    print()
    print("=== SUMMARY ===")
    if all(checks):
        print("ALL %d CHECKS PASSED" % len(checks))
    else:
        print("%d of %d CHECKS FAILED" % (checks.count(False), len(checks)))
