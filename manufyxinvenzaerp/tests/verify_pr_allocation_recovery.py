"""A receipt that allocates nothing says why, and can be run again.

Batches received on a Purchase Receipt are allocated into Material Planning through a
chain of four links:

    Receipt line → Purchase Order line → Material Request line → that request's plan

get_mp_for_pr is one join across all four. Break any link -- a Purchase Order raised by
hand rather than from the request, a receipt entered straight against the order -- and
the join returns nothing. Allocation never runs. And nothing said so: the receipt
submitted cleanly, the popup that lists allocated batches saw an empty list and returned
early, and the plan went on showing the material as unavailable. Reported from the live
server, where the purchased batches simply never appeared on the plan.

Two things were missing, and both are checked here:

  * a reason. The chain is now walked one line at a time and the first broken link
    named, so the answer is "the Purchase Order was not raised from the request" rather
    than silence.
  * a way back. The message shown when allocation fails has always said to "retry the
    allocation manually from the Material Planning document", and there was nowhere to
    do it -- allocate_pr_stock_to_mp had exactly one caller, the submit hook. Recovering
    meant cancelling and re-receiving stock that had physically arrived.

Run: bench --site manufact execute manufyxinvenzaerp.tests.verify_pr_allocation_recovery.run
"""

import frappe

from manufyxinvenzaerp.purchase_receipt_management.purchase_receipt import (
    diagnose_mp_allocation,
    retry_mp_allocation,
)

checks = []


def check(label, got, want):
    ok = got == want
    checks.append(ok)
    print("  %-4s %-54s got=%r want=%r" % ("OK" if ok else "FAIL", label, got, want))


def run():
    pr = frappe.db.get_value("Purchase Receipt", {"docstatus": 1}, "name")
    if not pr:
        print("=== no submitted Purchase Receipt on this site ===")
        _wiring()
        _summary()
        return

    print("=== an intact chain traces to its plan: %s ===" % pr)
    d = diagnose_mp_allocation(pr)
    print("   plans=%s broken=%s" % (d["plans"], d["broken"]))
    check("it finds at least one plan", bool(d["plans"]), True)
    check("and reports nothing broken", d["broken"], [])

    print()
    print("=== running it again is safe ===")
    # allocate_pr_stock_to_mp rebuilds its candidates from unavailable_items as that
    # table currently stands, and a row already covered is gone from it -- so a second
    # run has nothing left to match rather than allocating the same batch twice.
    before = {
        mp: (frappe.db.count("Material Planning Material Mapping", {"parent": mp}),
             frappe.db.count("Material Planning Available Raw Material", {"parent": mp}))
        for mp in d["plans"]
    }
    try:
        again = retry_mp_allocation(pr)
        check("it runs over every plan the receipt traces to",
              sorted(x["material_planning"] for x in again["results"]), d["plans"])
        check("and adds nothing the second time",
              [(x["added_exact"], x["added_mapping"]) for x in again["results"]],
              [(0, 0)] * len(again["results"]))
        after = {
            mp: (frappe.db.count("Material Planning Material Mapping", {"parent": mp}),
                 frappe.db.count("Material Planning Available Raw Material", {"parent": mp}))
            for mp in d["plans"]
        }
        check("no row count moved", after, before)
    finally:
        frappe.db.rollback()

    print()
    print("=== each broken link is named, not just noticed ===")
    row = frappe.get_all("Purchase Receipt Item", filters={"parent": pr},
                         fields=["name", "item_code", "purchase_order_item"], limit=1)[0]
    po_item = row.purchase_order_item
    mr_item = frappe.db.get_value("Purchase Order Item", po_item, "material_request_item")
    mr = frappe.db.get_value("Material Request Item", mr_item, "parent") if mr_item else None

    for label, apply, expect in (
        ("no Purchase Order behind the receipt line",
         lambda: frappe.db.set_value("Purchase Receipt Item", row.name,
                                     "purchase_order_item", "", update_modified=False),
         "not raised from a Purchase Order"),
        ("no Material Request behind the order line",
         lambda: frappe.db.set_value("Purchase Order Item", po_item,
                                     "material_request_item", "", update_modified=False),
         "not raised from a Material Request"),
        ("the request is not linked to a plan",
         lambda: frappe.db.set_value("Material Request", mr,
                                     "custom_material_planning", "", update_modified=False),
         "is not linked to a Material Planning"),
    ):
        if label.endswith("plan") and not mr:
            continue
        try:
            apply()
            broken = diagnose_mp_allocation(pr)["broken"]
            hit = [b for b in broken if b[0] == row.item_code and expect in b[1]]
            check(label, bool(hit), True)
        finally:
            frappe.db.rollback()

    _wiring()
    _summary()


def _wiring():
    print()
    print("=== and the form offers both ===")
    js = open(frappe.get_app_path("manufyxinvenzaerp", "public", "js",
                                  "purchase_receipt.js")).read()
    check("an empty allocation no longer returns in silence",
          "if (!allocs.length) return;" in js, False)
    check("it asks why instead", "_mfx_pr_report_no_allocation(frm)" in js, True)
    check("and there is a button to run it again",
          'add_custom_button(__("Allocate to Material Planning")' in js, True)
    check("on a submitted receipt only", "if (frm.doc.docstatus !== 1) return;" in js, True)
    check("an ordinary purchase with no plan behind it stays quiet",
          "if (!(d.broken || []).length) return;" in js, True)


def _summary():
    print()
    print("=== SUMMARY ===")
    if all(checks):
        print("ALL %d CHECKS PASSED" % len(checks))
    else:
        print("%d of %d CHECKS FAILED" % (checks.count(False), len(checks)))
