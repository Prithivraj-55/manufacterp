"""T10 — the Consumption Log is capped at the drawing's real quantity, always.

Mandatory-inspection operations used to be exempt so a rejected piece could be logged
a SECOND time after rework, deliberately pushing the total past the real quantity
(4 made, 1 rejected, re-logged = 5). The client has retired that: "log will be one
time, inspection can be made many time."

The point of this test is that removing the exemption does NOT break rework. Pending
work is derived as (logged - accepted), so a rejected piece stays pending on its own
and the next inspection round picks it up with no second log entry.

Exercised against the real validator rather than a stub, so the guard, the pending
calculation and the weight rollup are all the production code paths.

Run: bench --site manufact execute manufyxinvenzaerp.tests.verify_consumption_log_hard_cap.run
"""

import frappe
from frappe.utils import flt

checks = []


def check(label, got, want):
    ok = got == want
    checks.append(ok)
    print("  %-4s %-60s got=%r want=%r" % ("OK" if ok else "FAIL", label, got, want))


def _doc(seq, mandatory, qty_to_mfg, available_nos, completed_nos, log):
    """A Supplier Operation Entry shaped just enough for the validator."""
    return frappe._dict(
        doctype="Supplier Operation Entry",
        sequence_id=seq,
        custom_inspection_mandatory=1 if mandatory else 0,
        status="Open",
        available_to_consume_kg=100000.0,
        total_consumed_kg=0.0,
        total_available_nos=0.0,
        total_completed_nos=0.0,
        drawing_details=[frappe._dict(
            drawing="DRW-CAP-1", customer_drawing_number="CAP-1", duno_mark_no="C1",
            qty_to_manufacture=qty_to_mfg,
            available_to_consume_nos=available_nos,
            completed_qty_nos=completed_nos,
            transferred_weight_kg=1000.0,
        )],
        consumption_log=[frappe._dict(drawing="DRW-CAP-1", qty_nos=n, weight_kg=w) for n, w in log],
        inspection_items=[],
        get=lambda self=None, *a, **k: None,
    )


def _blocked(err):
    """True when the save was rejected for logging more Nos than exist.

    Two guards can catch it and either is a pass. On a NON-mandatory operation
    completed_qty_nos is set straight from the log total, so the earlier
    "Completed Qty Exceeds Limit" check fires before the Nos ceiling is ever reached;
    on a mandatory one completed_qty_nos comes from Inspection instead, so the ceiling
    itself is what stops it.

    Matches the message BODY, not the dialog title -- strip_html drops the title, which
    made an earlier version of this test report false failures against working code."""
    return bool(err and (
        "Nos in total but only" in err          # step 6, the Nos ceiling
        or "exceeds Qty to Manufacture" in err  # step 2b, via completed_qty_nos
    ))


def _validate(doc):
    """Run the real validator. Returns None on success, the message on throw."""
    from manufyxinvenzaerp.subcontracting_management.subcontracting import (
        validate_supplier_operation_entry,
    )
    # set/append/get are used by the validator; frappe._dict lacks the Document API.
    doc.set = lambda field, value: doc.__setitem__(field, value)
    doc.append = lambda field, value: doc[field].append(frappe._dict(value))
    doc.get = lambda field, *a, **k: doc.__getitem__(field) if field in doc else None
    try:
        validate_supplier_operation_entry(doc, "validate")
        return None
    except Exception as e:
        return frappe.utils.strip_html(str(e))


def run():
    from manufyxinvenzaerp.subcontracting_management.subcontracting import _soe_consumed_kg

    print("=== Op-2+, inspection mandatory: the case that used to be exempt ===")
    # 4 available from the previous operation, 4 logged, 3 accepted so far.
    # Re-logging the rejected piece would make 5 -- previously allowed, now blocked.
    doc = _doc(seq=2, mandatory=True, qty_to_mfg=4, available_nos=4, completed_nos=3,
               log=[(4, 400.0), (1, 100.0)])
    err = _validate(doc)
    check("re-logging past the quantity is blocked", _blocked(err), True)
    if err:
        print("       ->", err[:150])

    print()
    print("=== the same operation, logged once (the supported way) ===")
    doc = _doc(seq=2, mandatory=True, qty_to_mfg=4, available_nos=4, completed_nos=3,
               log=[(4, 400.0)])
    err = _validate(doc)
    check("logging exactly the available qty is allowed", err, None)
    pending = [flt(r.qty_nos) for r in doc.inspection_items]
    check("1 piece still pending for the next inspection round", pending, [1.0])
    print("       rework survives without a second log entry: logged 4, accepted 3,")
    print("       so inspection_items still offers 1 Nos for round 2.")

    print()
    print("=== weight passed on scales to what was accepted ===")
    check("3 of 4 accepted -> 300 of 400 Kg carried forward", _soe_consumed_kg(doc), 300.0)
    doc.drawing_details[0].completed_qty_nos = 4
    check("round 2 accepts the last piece -> full 400 Kg", _soe_consumed_kg(doc), 400.0)

    print()
    print("=== Op-2+, NOT mandatory: unchanged behaviour ===")
    doc = _doc(seq=2, mandatory=False, qty_to_mfg=4, available_nos=4, completed_nos=0,
               log=[(5, 500.0)])
    err = _validate(doc)
    check("over-logging still blocked", _blocked(err), True)

    doc = _doc(seq=2, mandatory=False, qty_to_mfg=4, available_nos=4, completed_nos=0,
               log=[(4, 400.0)])
    check("logging up to the ceiling still allowed", _validate(doc), None)

    print()
    print("=== Op-1: capped at the drawing's own quantity ===")
    # Op-1 has no previous operation, so the ceiling is qty_to_manufacture. A mandatory
    # Op-1 had no log ceiling at all before this change.
    doc = _doc(seq=1, mandatory=True, qty_to_mfg=4, available_nos=0, completed_nos=0,
               log=[(5, 500.0)])
    err = _validate(doc)
    check("Op-1 over-logging is blocked", _blocked(err), True)

    doc = _doc(seq=1, mandatory=True, qty_to_mfg=4, available_nos=0, completed_nos=0,
               log=[(4, 400.0)])
    check("Op-1 logging exactly the quantity is allowed", _validate(doc), None)

    print()
    print("=== a drawing with no quantity set is not blocked by the Op-1 cap ===")
    doc = _doc(seq=1, mandatory=False, qty_to_mfg=0, available_nos=0, completed_nos=0,
               log=[(3, 300.0)])
    check("no ceiling to apply -> allowed", _validate(doc), None)

    print()
    print("=== SUMMARY ===")
    if all(checks):
        print("ALL %d CHECKS PASSED" % len(checks))
    else:
        print("%d of %d CHECKS FAILED" % (checks.count(False), len(checks)))
