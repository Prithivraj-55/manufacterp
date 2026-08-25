"""Production Report: one row per drawing, every operation across the columns.

It used to be one row per drawing *per operation*. A four-operation job with six
drawings filled twenty-four rows with the same six drawings repeated, and answering
"where is 1B1 up to" meant reading four of them and holding them in your head.

Now each drawing gets one row, and every operation the job is routed through
contributes a block of five columns to it -- quantity, status, inspection rounds, last
inspection status, and the gap in days. The operation list is not fixed: it is whatever
the jobs in view are actually routed through, in the order they run.

The two things this checks that a screenshot cannot:

  * the row count really did collapse -- one row per (Job Work Order, Drawing) and no
    more, however many operations sit behind it; and
  * the figures survived the collapse. Every operation's status still appears, in its
    own column, on the row for the drawing it belongs to.

Run: bench --site manufact execute manufyxinvenzaerp.tests.verify_production_report.run
"""

import frappe
from frappe.utils import flt

from manufyxinvenzaerp.production_management.report.production_report.production_report import (
    execute,
)

checks = []


def check(label, got, want):
    ok = got == want
    checks.append(ok)
    print("  %-4s %-56s got=%r want=%r" % ("OK" if ok else "FAIL", label, got, want))


def _labels(columns):
    return [c["label"] for c in columns]


def run():
    columns, data = execute({})
    labels = _labels(columns)

    print("=== the columns the client asked for, in the order asked for ===")
    lead = labels[:11]
    check("traceability first, sales-order-wise", lead, [
        "Sales Order", "Customer", "Project", "Production Plan (Team)", "Job Type",
        "Job Work Order", "Supplier", "Drawing", "DUNO/Mark No", "Cust Drawing No",
        "Created On",
    ])
    tail = labels[-15:]
    check("weights, costs and completion last", tail, [
        "Customer Weight (Kg)", "Planned Weight (Kg)", "Planned Sec Nos",
        "Transferred Weight (Kg)", "Transferred Sec Nos", "Consumed RM Cost",
        "Rate Schedule", "Rate / Kg", "Consumables (Nos)", "Consumable Cost",
        "Excess Weight (Kg)", "Returned Excess Weight (Kg)", "Difference (Kg)",
        "Completed Drawing Weight (Kg)", "Completed Drawing (Nos)",
    ])
    check("and the piece count closes it", labels[-1], "Completed Drawing (Nos)")
    check("Operation and Seq are gone -- they are columns now, not rows",
          [l for l in labels if l in ("Operation", "Seq")], [])

    print()
    print("=== Created On comes from the Job Work Order, not the operation entry ===")
    # Every operation of a job was raised on its own day, so reading the date off the
    # operation made one job look like several.
    created = frappe.get_all("Subcontracting Order",
                             fields=["name", "transaction_date"], as_list=False)
    by_sco = {c.name: c.transaction_date for c in created}
    mismatched = [r["subcontracting_order"] for r in data
                  if r["subcontracting_order"] in by_sco
                  and r["created_on"] != by_sco[r["subcontracting_order"]]]
    check("every row carries its order's own date", mismatched, [])

    if not data:
        print()
        print("   No Supplier Operation Entry on this site, so the shape below cannot be")
        print("   measured against real data. The column contract above still holds.")
        _summary()
        return

    print()
    print("=== one row per drawing, not one per drawing per operation ===")
    keys = [(r["subcontracting_order"], r["drawing"]) for r in data]
    check("no drawing is listed twice on a job", len(keys), len(set(keys)))

    soes = frappe.get_all("Supplier Operation Entry",
                          fields=["name", "subcontracting_order", "operation", "sequence_id", "status"])
    expected = set()
    for d in frappe.get_all("SOE Drawing Detail",
                            filters={"parent": ["in", [s.name for s in soes]]},
                            fields=["parent", "drawing"]):
        parent = next((s for s in soes if s.name == d.parent), None)
        if parent and d.drawing:
            expected.add((parent.subcontracting_order, d.drawing))
    check("every drawing on every job still appears once", set(keys), expected)
    # The collapse is the point: state what it saved, so a regression that quietly
    # re-expands the rows is visible in the output and not only in the assertion.
    print("   %d operation entries over %d drawing rows (was %d rows before)"
          % (len(soes), len(data), sum(1 for _ in _old_shape(soes))))

    print()
    print("=== each operation writes into its own block, on the right row ===")
    ops = sorted({(s.sequence_id or 0, s.operation) for s in soes if s.operation})
    for seq, operation in ops:
        slug = frappe.scrub(operation)
        check("%s has its own columns" % operation,
              all("%s %s" % (operation, suffix) in labels
                  for suffix in ("Status", "Inspection Rounds", "Last Inspection Status")),
              True)
        check("  and a quantity in %s" % ("Kg" if seq <= 1 else "Nos"),
              "%s (%s)" % (operation, "Kg" if seq <= 1 else "Nos") in labels, True)
        check("  and a gap of its own", "%s Gap (Days, approx.)" % operation in labels, True)
        # The status a row shows for an operation must be that operation's status on
        # that job -- the check that the pivot put the values where the labels say.
        for s in soes:
            if s.operation != operation:
                continue
            rows = [r for r in data if r["subcontracting_order"] == s.subcontracting_order]
            if not rows:
                continue
            wrong = [r["drawing"] for r in rows if r.get("op_%s_status" % slug) != s.status]
            check("  %s on %s reads %r everywhere" % (operation, s.subcontracting_order, s.status),
                  wrong, [])

    print()
    print("=== a job appears the moment its Job Work Order is submitted ===")
    # Before this, the report was driven by Supplier Operation Entry: a job whose
    # operation entries had not been raised yet was simply absent, with nothing on
    # screen to say it existed. The order is what makes a job real, so the order is
    # what the report is built from now.
    victim = data[0]["subcontracting_order"]
    try:
        frappe.db.delete("Supplier Operation Entry", {"subcontracting_order": victim})
        after_data = execute({})[1]
        still = [r for r in after_data if r["subcontracting_order"] == victim]
        check("its drawings are still listed with no operations at all",
              len(still), len([r for r in data if r["subcontracting_order"] == victim]))
        check("and the weights are still on them",
              flt(still[0]["planned_weight_kg"], 3) if still else None,
              flt([r for r in data if r["subcontracting_order"] == victim][0]["planned_weight_kg"], 3))
    finally:
        frappe.db.rollback()

    print()
    print("=== a draft or cancelled Job Work Order is not a job yet ===")
    drafts = frappe.get_all("Subcontracting Order", filters={"docstatus": ["!=", 1]}, pluck="name")
    check("none of them reach the report",
          [r["subcontracting_order"] for r in data if r["subcontracting_order"] in drafts], [])
    submitted = set(frappe.get_all("Subcontracting Order", filters={"docstatus": 1}, pluck="name"))
    check("and every submitted one that has drawings does",
          sorted(submitted - {r["subcontracting_order"] for r in data}),
          sorted(n for n in submitted
                 if not frappe.db.exists("SCO Drawing Item",
                                         {"parent": n, "parenttype": "Subcontracting Order"})))

    print()
    print("=== the excess trio reconciles ===")
    # Excess, what came back, and what is still out there. Billed-to-Consume comes off
    # the difference rather than sitting in it forever: that material is scrapped by
    # decision, not awaiting collection -- the same line the Excess Material Return
    # Report draws when it builds its chase-list.
    for r in data:
        rows = _excess_rows(r["subcontracting_order"])
        booked = flt(sum(flt(x.qty) for x in rows), 3)
        back = flt(sum(flt(x.qty) for x in rows if x.stock_entry_created), 3)
        scrapped = flt(sum(flt(x.qty) for x in rows
                           if not x.stock_entry_created and x.billed_to_consume), 3)
        check("%s: booked" % r["subcontracting_order"], flt(r["excess_weight_kg"], 3), booked)
        check("  returned", flt(r["returned_excess_kg"], 3), back)
        check("  difference is what is left to chase",
              flt(r["excess_difference_kg"], 3), flt(booked - back - scrapped, 3))
        break

    print()
    print("=== completed weight is the pieces done, at the drawing's own weight ===")
    for r in data:
        if not r["completed_nos"]:
            continue
        item = frappe.db.get_value(
            "SCO Drawing Item",
            {"parent": r["subcontracting_order"], "parenttype": "Subcontracting Order",
             "drawing": r["drawing"]},
            ["total_weight_kg", "qty_to_manufacture", "completed_qty_nos"], as_dict=True)
        if not (item and flt(item.qty_to_manufacture)):
            continue
        want = flt(flt(item.total_weight_kg) / flt(item.qty_to_manufacture)
                   * flt(item.completed_qty_nos), 3)
        check("%s %s" % (r["subcontracting_order"], r["drawing"]),
              flt(r["completed_drawing_weight_kg"], 3), want)
        break

    _summary()


def _old_shape(soes):
    """What the row count used to be: one per drawing per operation."""
    for d in frappe.get_all("SOE Drawing Detail",
                            filters={"parent": ["in", [s.name for s in soes]]},
                            fields=["parent", "drawing"]):
        yield d


def _excess_rows(sco):
    mips = frappe.get_all("Material Issue Plan", filters={"subcontracting_order": sco}, pluck="name")
    if not mips:
        return []
    return frappe.get_all("SCO Excess Material Item",
                          filters={"parent": ["in", mips], "parenttype": "Material Issue Plan"},
                          fields=["qty", "stock_entry_created", "billed_to_consume"])


def _summary():
    print()
    print("=== SUMMARY ===")
    if all(checks):
        print("ALL %d CHECKS PASSED" % len(checks))
    else:
        print("%d of %d CHECKS FAILED" % (checks.count(False), len(checks)))
