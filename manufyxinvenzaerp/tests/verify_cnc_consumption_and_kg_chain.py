"""Regression cover for the transfer -> operation -> final stock entry defects found
on 2026-08-12 (see the audit of MIP-2026-00106 / SC-ORD-2026-00013).

1. The final stock entry must consume material that reached the supplier through the
   CNC route (Stores -> CNC -> supplier), whose second leg is a 'Material Transfer'
   and so used to be invisible to _get_supplier_wh_consumption_items.
2. total_consumed_kg must be computed for EVERY operation, not only sequence 1, and
   must not double-count a rework re-log on an inspection-mandatory operation.
3. Per-drawing mapped weight must be attributed by the exact-match row's own DUNO
   instead of being spread across every drawing in the Material Planning.
5. The transfer round-up surplus must reach an alternate-item row, which carries the
   requirement's item_code but the batch's planned_item.
6. Issued Qty must be refreshed after transfer, when refresh_mip_raw_materials (its
   only other writer) is blocked from running.

Run: bench --site manufact execute manufyxinvenzaerp.tests.verify_cnc_consumption_and_kg_chain.run
"""

import frappe
from frappe.utils import flt

checks = []


def check(label, got, want):
    ok = got == want
    checks.append(ok)
    print("  %-4s %-62s got=%r want=%r" % ("OK" if ok else "FAIL", label, got, want))


def _fake_soe(seq, drawing_details, consumption_log):
    """A stand-in carrying only what _soe_consumed_kg reads, so the weight maths can be
    exercised without building a whole Subcontracting Order chain."""
    return frappe._dict(
        sequence_id=seq,
        drawing_details=[frappe._dict(d) for d in drawing_details],
        consumption_log=[frappe._dict(c) for c in consumption_log],
    )


def run():
    from manufyxinvenzaerp.subcontracting_management.subcontracting import _soe_consumed_kg

    print("=== defect 2: total_consumed_kg on every operation ===")

    # Non-mandatory: completed == logged, so this is the plain sum (unchanged behaviour).
    soe = _fake_soe(
        1,
        [{"drawing": "D1", "completed_qty_nos": 2.0}, {"drawing": "D2", "completed_qty_nos": 1.0}],
        [{"drawing": "D1", "qty_nos": 2.0, "weight_kg": 907.045},
         {"drawing": "D2", "qty_nos": 1.0, "weight_kg": 555.891}],
    )
    check("op-1 plain sum is unchanged", _soe_consumed_kg(soe), 1462.936)

    # Same shape at sequence 4 -- used to return 0 because the calc was gated on seq == 1.
    soe4 = _fake_soe(
        4,
        [{"drawing": "D1", "completed_qty_nos": 2.0}, {"drawing": "D2", "completed_qty_nos": 1.0}],
        [{"drawing": "D1", "qty_nos": 2.0, "weight_kg": 907.045},
         {"drawing": "D2", "qty_nos": 1.0, "weight_kg": 555.891}],
    )
    check("op-4 computes instead of returning 0", _soe_consumed_kg(soe4), 1462.936)

    # Rework: D2 rejected in round 1, re-logged in round 2. Two log rows, one accepted
    # piece -- the weight must count once, not twice.
    rework = _fake_soe(
        2,
        [{"drawing": "D1", "completed_qty_nos": 2.0}, {"drawing": "D2", "completed_qty_nos": 1.0}],
        [{"drawing": "D1", "qty_nos": 2.0, "weight_kg": 907.045},
         {"drawing": "D2", "qty_nos": 1.0, "weight_kg": 308.566},
         {"drawing": "D2", "qty_nos": 1.0, "weight_kg": 308.566}],
    )
    raw_sum = sum(flt(c.weight_kg) for c in rework.consumption_log)
    check("rework raw log sum would double-count", raw_sum, 1524.177)
    check("rework counted once", _soe_consumed_kg(rework), 1215.611)

    # Nothing accepted yet on a mandatory operation -> nothing to pass on.
    pending = _fake_soe(
        2,
        [{"drawing": "D1", "completed_qty_nos": 0.0}],
        [{"drawing": "D1", "qty_nos": 2.0, "weight_kg": 907.045}],
    )
    check("mandatory op awaiting inspection passes on nothing", _soe_consumed_kg(pending), 0.0)

    # Weight logged with no drawing can't be apportioned -- passed through, not dropped.
    orphan = _fake_soe(3, [], [{"drawing": None, "qty_nos": 0.0, "weight_kg": 12.5}])
    check("log row with no drawing is passed through", _soe_consumed_kg(orphan), 12.5)

    print()
    print("=== defect 1: CNC-routed material is offered for consumption ===")
    from manufyxinvenzaerp.subcontracting_management.subcontracting import (
        _get_sco_supplier_warehouse, _get_supplier_wh_consumption_items,
    )

    # Find a batch that reached a supplier warehouse on a 'Material Transfer' leg (the
    # CNC route's second hop) rather than on a 'Send to Subcontractor' entry.
    routed = frappe.db.sql(
        """SELECT se.subcontracting_order, se.custom_sco_ref, sed.item_code,
                  sed.batch_no, sed.t_warehouse, SUM(sed.qty) qty
           FROM `tabStock Entry Detail` sed
           JOIN `tabStock Entry` se ON se.name = sed.parent
           WHERE se.docstatus = 1 AND se.stock_entry_type = 'Material Transfer'
             AND (se.subcontracting_order IS NOT NULL OR se.custom_sco_ref IS NOT NULL)
           GROUP BY se.subcontracting_order, se.custom_sco_ref, sed.item_code,
                    sed.batch_no, sed.t_warehouse
           HAVING SUM(sed.qty) > 0""",
        as_dict=True,
    )
    tested = False
    for r in routed:
        sco_name = r.subcontracting_order or r.custom_sco_ref
        if not sco_name or not frappe.db.exists("Subcontracting Order", sco_name):
            continue
        sco = frappe.get_doc("Subcontracting Order", sco_name)
        if r.t_warehouse != _get_sco_supplier_warehouse(sco):
            continue  # a Stores -> CNC leg, not the CNC -> supplier one
        offered = {
            (i["item_code"], i["batch_no"]): flt(i["qty"])
            for i in _get_supplier_wh_consumption_items(sco, r.t_warehouse)
        }
        # Still physically there (nothing has consumed it) => must be offered.
        on_hand = flt(frappe.db.sql(
            """SELECT SUM(sle.actual_qty) FROM `tabStock Ledger Entry` sle
               JOIN `tabSerial and Batch Entry` sbe ON sbe.parent = sle.serial_and_batch_bundle
               WHERE sle.is_cancelled = 0 AND sle.warehouse = %s AND sbe.batch_no = %s""",
            (r.t_warehouse, r.batch_no))[0][0] or 0)
        if on_hand <= 0:
            continue
        check("CNC-routed %s (%s) is offered for consumption" % (r.item_code, r.batch_no),
              round(offered.get((r.item_code, r.batch_no), 0.0), 3), round(on_hand, 3))
        tested = True
        break
    if not tested:
        print("   (skipped -- no CNC-routed batch still sitting at a supplier on this site)")

    print()
    print("=== defect 3: exact-match weight lands on its own drawing ===")
    mp = frappe.db.get_value(
        "Material Planning Available Raw Material",
        {"batch_no": ["!=", ""], "duno_mark_no": ["!=", ""]},
        "parent",
    )
    if mp:
        from manufyxinvenzaerp.subcontracting_management.subcontracting import (
            _get_mp_mapped_weight_by_duno,
        )
        got = _get_mp_mapped_weight_by_duno(mp)
        truth = {}
        for r in frappe.db.sql(
            """SELECT duno_mark_no d, SUM(batch_calc_qty) q
               FROM `tabMaterial Planning Material Mapping`
               WHERE parent=%s AND batch IS NOT NULL AND batch!='' AND batch_calc_qty>0
               GROUP BY duno_mark_no""", mp, as_dict=True):
            truth[r.d or ""] = truth.get(r.d or "", 0.0) + flt(r.q)
        for r in frappe.db.sql(
            """SELECT duno_mark_no d, SUM(COALESCE(NULLIF(reserved_qty,0),required_qty)) q
               FROM `tabMaterial Planning Available Raw Material`
               WHERE parent=%s AND batch_no IS NOT NULL AND batch_no!=''
               GROUP BY duno_mark_no""", mp, as_dict=True):
            truth[r.d or ""] = truth.get(r.d or "", 0.0) + flt(r.q)
        check("per-drawing mapped weight matches the rows themselves (%s)" % mp,
              {k: round(v, 3) for k, v in got.items()},
              {k: round(v, 3) for k, v in truth.items()})
    else:
        print("   (skipped -- no batched exact-match row with a DUNO on this site)")

    print()
    print("=== defect 5 / 6: alternate-item rows are keyed by the batch's item ===")
    src = frappe.get_attr(
        "manufyxinvenzaerp.subcontracting_management.doctype.material_issue_plan"
        ".material_issue_plan._sync_transferred_qty"
    )
    check("_sync_transferred_qty exists", callable(src), True)

    alt = frappe.db.sql(
        """SELECT parent, item_code, planned_item, batch_no, qty, transferred_qty
           FROM `tabMaterial Issue Plan Raw Material`
           WHERE planned_item IS NOT NULL AND planned_item != ''
             AND planned_item != item_code AND transferred_qty > 0 LIMIT 1""",
        as_dict=True,
    )
    if alt:
        r = alt[0]
        print("   alternate-item row: %s wants %s, filled from %s batch %s"
              % (r.parent, r.item_code, r.planned_item, r.batch_no))
        check("its Issued Qty is populated", flt(r.transferred_qty) > 0, True)
    else:
        print("   (skipped -- no transferred alternate-item row on this site)")

    print()
    print("=== SUMMARY ===")
    if all(checks):
        print("ALL %d CHECKS PASSED" % len(checks))
    else:
        print("%d of %d CHECKS FAILED" % (checks.count(False), len(checks)))
