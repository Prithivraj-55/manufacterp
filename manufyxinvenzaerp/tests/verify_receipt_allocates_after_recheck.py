"""Re-checking stock must not throw away rows that are already being purchased,
and a receipt must still find them if it does.

Reported from the live server: MP-2026-00012 raised a Material Request, a Purchase
Order and then Purchase Receipt PR-26-00005 for 5,507 Kg across four items -- and the
plan went on showing all thirteen requirement rows unmapped, with the received batches
sitting in the warehouse untouched. No error was logged, no message was shown, and the
PR -> PO -> MR -> plan chain was perfectly intact, so diagnose_mp_allocation reported
nothing wrong either.

Two faults met in the middle, and both are checked here.

  * check_stock_availability rebuilds every bucket from raw_materials, and a
    batch-tracked item is never classified into Unavailable Items -- only non-batch
    shortages go there. So pressing "Check Stock Availability" a second time, after
    Finalize Mapping had moved rows into Unavailable Items and an MR/PO had been
    raised against them, emptied the whole table: the rows reappeared in Material
    Mapping with no batch, and their consolidated_into links were gone.

  * allocate_pr_stock_to_mp matched candidates ONLY against unavailable_items. With
    that table now empty it matched nothing, allocated nothing, raised nothing, and
    returned a result indistinguishable from a successful allocation.

A third fault was found while fixing those, on the ordinary purchasing route rather
than the re-checked one: a partly received line wrote the row's FULL requirement onto
its Material Mapping row while also splitting the shortfall off into a second row, so
a reserve_without_dimensions row asked to reserve more of the batch than had arrived.
_validate_batch_calc_qty then refused the save and took the whole allocation down with
it -- again leaving only an Error Log entry behind. Every partly received consolidated
purchase hit that one.

Run: bench --site manufact execute manufyxinvenzaerp.tests.verify_receipt_allocates_after_recheck.run
"""

import json

import frappe
from frappe.utils import flt, today

from manufyxinvenzaerp.production_management.doctype.material_planning.material_planning import (
    check_stock_availability,
)
from manufyxinvenzaerp.purchase_receipt_management.purchase_receipt import (
    allocate_pr_stock_to_mp,
    get_mp_for_pr,
)
from manufyxinvenzaerp.tests.create_full_test_entry import ensure_batch, ensure_item, get_ctx

ITEM = "ZZTEST-RECHECK"
checks = []


def check(label, got, want):
    ok = got == want
    checks.append(ok)
    print("  %-4s %-56s got=%r want=%r" % ("OK" if ok else "FAIL", label, got, want))


def _ctx():
    """get_ctx picks a company and a warehouse with two independent "LIMIT 1"
    queries, which need not belong to each other -- and `bench run-tests`
    leaves _Test companies behind that can win the first one. Take the
    warehouse first and adopt ITS company, so the pair is always consistent."""
    ctx = get_ctx()
    row = frappe.db.sql(
        r"""SELECT name, company FROM tabWarehouse
            WHERE is_group = 0 AND company NOT LIKE '\_Test%%'
            ORDER BY creation LIMIT 1""",
        as_dict=True,
    )
    if row:
        ctx.warehouse, ctx.company = row[0]["name"], row[0]["company"]
    return ctx


def run():
    ctx = _ctx()
    item = ensure_item(ctx, ITEM, "Re-check Allocation Test Item", uom="Kg")
    frappe.db.set_value("Item", item, "custom_parent_item_group", "Structurals")
    frappe.db.set_value("Item", item, "custom_unit_weight", 10)

    mp = _make_plan(ctx, item)
    print("Test plan: %s (2 Unavailable Item rows: 50 Kg + 30 Kg)" % mp.name)

    mr = _make_material_request(mp, item)
    print("Consolidated Material Request: %s" % mr)

    print()
    print("=== re-checking stock keeps rows that are already on a Material Request ===")
    doc = frappe.get_doc("Material Planning", mp.name).as_dict()
    before = len(doc["unavailable_items"])
    res = check_stock_availability(json.dumps(doc, default=str))
    check("both ordered rows survive the re-check", len(res["unavailable_items"]), before)
    check("and it reports how many it kept", res.get("preserved_ordered_count"), before)

    kept = _keys(res["unavailable_items"])
    check("they are not duplicated into Material Mapping",
          [k for k in _keys(res["material_mapping"]) if k in kept], [])
    check("nor into Available Raw Materials",
          [k for k in _keys(res["available_raw_materials"]) if k in kept], [])

    print()
    print("=== the receipt still finds them once a re-check HAS moved them ===")
    # Exactly what the live re-check did: same rows, now in Material Mapping with
    # no batch, and Unavailable Items empty.
    moved = frappe.get_doc("Material Planning", mp.name)
    for row in moved.unavailable_items:
        moved.append("material_mapping", {
            "item_code": row.item_code, "item_name": row.item_name,
            "parent_item_group": row.parent_item_group, "unit_weight": row.unit_weight,
            "qty": row.qty, "uom": row.uom, "sec_qty": row.sec_qty, "sec_uom": row.sec_uom,
            "duno_mark_no": row.duno_mark_no, "batch": "", "batch_mapped": "Not Mapped",
        })
    moved.unavailable_items = []
    moved.flags.mfx_saved_by_another_document = True
    moved.save(ignore_permissions=True)

    moved.reload()
    print("    after the move: %d Material Mapping row(s) %s, %d Unavailable Item row(s)"
          % (len(moved.material_mapping),
             [(r.duno_mark_no, flt(r.qty), r.batch or "-") for r in moved.material_mapping],
             len(moved.unavailable_items)))

    pr_name = _make_receipt(mr, item, received=60, company=ctx.company)
    print("Purchase Receipt: %s (60 of the 80 Kg ordered)" % pr_name)
    check("it still traces to the plan", get_mp_for_pr(pr_name), [mp.name])

    after = frappe.get_doc("Material Planning", mp.name)
    rows = {r.duno_mark_no: [] for r in after.material_mapping}
    for r in after.material_mapping:
        rows[r.duno_mark_no].append(r)

    a_rows = [r for r in rows["DUNO-R1"] if r.batch]
    b_rows = [r for r in rows["DUNO-R2"] if r.batch]
    check("the first row is filled in full", [flt(r.batch_calc_qty) for r in a_rows], [50.0])
    check("the second gets only what is left", [flt(r.batch_calc_qty) for r in b_rows], [10.0])
    check("every filled row names the receipt",
          all(r.purchase_receipt == pr_name for r in a_rows + b_rows), True)
    check("and no row claims more of the batch than it needs",
          [r.idx for r in a_rows + b_rows if flt(r.batch_calc_qty) > flt(r.qty) + 0.001], [])

    # 50 + 10 is the whole 60 Kg received: claiming any more would have been
    # refused by _validate_batch_calc_qty, which is what used to happen.
    check("the batch is not over-committed",
          flt(sum(flt(r.batch_calc_qty) for r in after.material_mapping), 3), 60.0)

    print()
    print("=== running the allocation again changes nothing ===")
    again = allocate_pr_stock_to_mp(pr_name, mp.name)
    check("a retry allocates nothing further",
          (again["added_exact"], again["added_mapping"], again["filled_mapping"]), (0, 0, 0))
    retried = frappe.get_doc("Material Planning", mp.name)
    check("and the batch is still not over-committed",
          flt(sum(flt(r.batch_calc_qty) for r in retried.material_mapping), 3), 60.0)

    frappe.db.rollback()
    print()
    print("  (rolled back -- this check leaves no trace)")
    _summary()


def _make_plan(ctx, item):
    mp = frappe.new_doc("Material Planning")
    mp.company = ctx.company
    mp.posting_date = today()
    mp.for_warehouse = ctx.warehouse
    for duno, qty, sec in (("DUNO-R1", 50, 1), ("DUNO-R2", 30, 1)):
        mp.append("unavailable_items", {
            "item_code": item, "item_name": "Re-check Allocation Test Item",
            "parent_item_group": "Structurals", "unit_weight": 10,
            "qty": qty, "uom": "Kg", "sec_qty": sec, "sec_uom": "Nos",
            "duno_mark_no": duno,
        })
    mp.insert(ignore_permissions=True)
    return mp


def _make_material_request(mp, item):
    """Buy the two requirements as one consolidated line, the way the live plan
    did -- so the request carries no DUNO and covers both rows at once."""
    from manufyxinvenzaerp.production_management.doctype.material_planning.material_planning import (
        make_material_request_from_consolidate,
    )

    doc = frappe.get_doc("Material Planning", mp.name)
    consol = next(r for r in doc.consolidate_items if r.item_code == item)
    consol.length = 8000
    consol.sec_qty = 1
    doc.save(ignore_permissions=True)

    mr_name = make_material_request_from_consolidate(mp.name, json.dumps([item]))
    mr = frappe.get_doc("Material Request", mr_name)
    mr.submit()
    return mr_name


def _make_receipt(mr_name, item, received, company):
    from erpnext.buying.doctype.purchase_order.purchase_order import make_purchase_receipt
    from erpnext.stock.doctype.material_request.material_request import make_purchase_order

    # Suppliers can be restricted to particular companies ("Allowed To Transact
    # With"); picking the first one on the site hits that restriction as often
    # as not. Take one that is either unrestricted or allowed for this company.
    supplier = frappe.db.sql(
        """SELECT s.name FROM tabSupplier s
           LEFT JOIN `tabAllowed To Transact With` a
                  ON a.parent = s.name AND a.parenttype = 'Supplier'
           GROUP BY s.name
           HAVING SUM(a.name IS NOT NULL) = 0 OR SUM(a.company = %s) > 0
           LIMIT 1""",
        (company,),
    )
    if not supplier:
        frappe.throw("No supplier on this site can transact with %s" % company)
    supplier = supplier[0][0]

    po = make_purchase_order(mr_name)
    po.supplier = supplier
    for row in po.items:
        row.rate = 80
    po.insert(ignore_permissions=True)
    po.submit()

    pr = make_purchase_receipt(po.name)
    # validate_purchase_receipt recalculates Qty from the dimensions for a
    # Structurals item, so a short delivery is expressed as fewer pieces
    # (0.75 of 1 Nos = 60 of the 80 Kg), not by overwriting qty.
    pr.items[0].custom_sec_qty = 0.75
    pr.items[0].qty = received
    pr.items[0].received_qty = received
    pr.items[0].accepted_qty = received
    pr.items[0].use_serial_batch_fields = 1
    pr.items[0].batch_no = ensure_batch(item, "ZZTEST-RECHECK-BATCH-1", L=8000, sec_qty=0.75)
    pr.insert(ignore_permissions=True)
    pr.submit()
    return pr.name


def _keys(rows):
    return {
        (r.get("item_code") or "", r.get("duno_mark_no") or "", flt(r.get("qty"), 3))
        for r in rows
    }


def _summary():
    print()
    if not checks:
        print("=== NO CHECKS RUN ===")
    elif all(checks):
        print("=== ALL %d CHECKS PASSED ===" % len(checks))
    else:
        print("=== %d of %d CHECKS FAILED ===" % (checks.count(False), len(checks)))
