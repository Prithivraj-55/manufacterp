"""A batch takes the dimensions of the line it actually came from.

A receipt can carry several lines of one item in different sizes. Each line becomes
its own batch, and the batch has to take that line's Length and Width -- the batch's
name is built from them, and every later decision about whether a piece fits a
requirement is made from them.

The old rule counted how many batches already existed for the document and used the
count as an index into the lines. That is a guess. It is right only while batches are
created in line order and no line already has a batch of its own, and when it is
wrong nothing says so: the batch is simply named and sized after somebody else's
line, and the error surfaces much later as a piece that will not fit.

The rule now is exact. ERPNext writes the Serial and Batch Bundle back onto a line
only after that line's batch exists, so the line being dealt with is always the first
line of this item with no bundle yet.

The case below is the one the old rule got wrong: line 1 arrives against an existing
batch, line 2 makes a new one. Counting says "no batches yet, so line 1" and stamps
3000 mm onto a 9000 mm bar.

Run: bench --site manufact execute manufyxinvenzaerp.tests.verify_batch_receipt_line_match.run
"""

import frappe
from frappe.utils import flt

from manufyxinvenzaerp.purchase_receipt_management.purchase_receipt import (
    _row_awaiting_batch,
)

checks = []

ITEM = "ZZTEST-CS-REPACK"
PREFIX = "ZZCSR"
UNIT_WEIGHT = 10.0


def check(label, got, want):
    ok = got == want
    checks.append(ok)
    print("  %-4s %-56s got=%r want=%r" % ("OK" if ok else "FAIL", label, got, want))


def _warehouse():
    for name in ("Stores - MIPL", "Work In Progress - MIPL"):
        if frappe.db.exists("Warehouse", name):
            return name
    return frappe.get_all("Warehouse", filters={"is_group": 0}, pluck="name")[0]


def _receipt(company, warehouse, rows):
    se = frappe.get_doc({
        "doctype": "Stock Entry", "stock_entry_type": "Material Receipt",
        "company": company,
        "items": [dict({
            "item_code": ITEM, "t_warehouse": warehouse, "basic_rate": 50,
            "custom_parent_item_group": "Structurals",
            "custom_unit_weight": UNIT_WEIGHT, "custom_sec_qty": 1,
        }, **r) for r in rows],
    })
    se.insert(ignore_permissions=True)
    se.submit()
    return se


def _batches_of(se_name):
    return frappe.get_all(
        "Batch",
        filters={"reference_doctype": "Stock Entry", "reference_name": se_name},
        fields=["name", "custom_length", "custom_sec_qty"],
        order_by="creation asc",
    )


def run():
    company = frappe.get_all("Company", pluck="name")[0]
    warehouse = _warehouse()
    first = second = None

    print("=== the rule itself ===")
    rows = [
        frappe._dict({"name": "row-1", "serial_and_batch_bundle": "SABB-0001"}),
        frappe._dict({"name": "row-2", "serial_and_batch_bundle": None}),
        frappe._dict({"name": "row-3", "serial_and_batch_bundle": None}),
    ]
    check("a line already dealt with is skipped",
          _row_awaiting_batch(rows).name, "row-2")
    check("with nothing dealt with, it is the first line",
          _row_awaiting_batch([frappe._dict({"name": "row-1", "serial_and_batch_bundle": None})]).name,
          "row-1")
    check("with everything dealt with, it falls back to the first",
          _row_awaiting_batch([
              frappe._dict({"name": "row-1", "serial_and_batch_bundle": "A"}),
              frappe._dict({"name": "row-2", "serial_and_batch_bundle": "B"}),
          ]).name, "row-1")
    check("no lines, no answer", _row_awaiting_batch([]), None)

    try:
        print()
        print("=== a 3000 mm bar arrives and becomes a batch ===")
        first = _receipt(company, warehouse, [{"qty": 30, "custom_length": 3000}])
        made = _batches_of(first.name)
        check("one batch", len(made), 1)
        existing = made[0].name
        check("sized 3000", flt(made[0].custom_length), 3000.0)

        print()
        print("=== now a receipt whose FIRST line tops up that batch ===")
        print("    line 1: 3000 mm, against the existing batch")
        print("    line 2: 9000 mm, needing a batch of its own")
        second = _receipt(company, warehouse, [
            {"qty": 30, "custom_length": 3000, "batch_no": existing},
            {"qty": 90, "custom_length": 9000},
        ])
        made = _batches_of(second.name)
        check("exactly one new batch was created", len(made), 1)

        new_batch = made[0]
        check("it took line 2's length, not line 1's",
              flt(new_batch.custom_length), 9000.0)
        check("and is named for it",
              new_batch.name.startswith("%s-L9000-" % PREFIX), True)
        check("its piece count came through", flt(new_batch.custom_sec_qty), 1.0)
        check("the existing batch was left alone",
              flt(frappe.db.get_value("Batch", existing, "custom_length")), 3000.0)

    finally:
        for se in (second, first):
            try:
                if se and frappe.db.get_value("Stock Entry", se.name, "docstatus") == 1:
                    frappe.get_doc("Stock Entry", se.name).cancel()
            except Exception as e:
                print("   (could not cancel %s: %s)" % (se.name, e))
        frappe.db.commit()
        print()
        print("   test entries cancelled, nothing deleted")

    print()
    print("=== SUMMARY ===")
    if all(checks):
        print("ALL %d CHECKS PASSED" % len(checks))
    else:
        print("%d of %d CHECKS FAILED" % (checks.count(False), len(checks)))
