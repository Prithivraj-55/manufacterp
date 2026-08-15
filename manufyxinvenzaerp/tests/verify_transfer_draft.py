"""T6b — "Save and Close": park the transfer popup's state without transferring.

The point is to step away mid-decision: a Sec Nos half adjusted, an off-cut not yet
measured, a warehouse not yet chosen. So saving is deliberately unvalidated -- checking
stock or dimensions would refuse to save exactly the unfinished state being kept. It is
all re-checked server-side when Transfer is finally pressed.

The draft lives on the Consolidate Items rows, which are otherwise fully derived and
rebuilt wholesale on every save of the plan. Surviving that rebuild is the whole
contract: without it, "Save and Close" would quietly discard the work the moment
anything re-saved the plan.

Run: bench --site manufact execute manufyxinvenzaerp.tests.verify_transfer_draft.run
"""

import json
import frappe
from frappe.utils import flt

checks = []


def check(label, got, want):
    ok = got == want
    checks.append(ok)
    print("  %-4s %-58s got=%r want=%r" % ("OK" if ok else "FAIL", label, got, want))


def run():
    from manufyxinvenzaerp.subcontracting_management.doctype.material_issue_plan.material_issue_plan import (
        save_transfer_draft, get_transfer_draft, _clear_transfer_draft,
    )

    mip_name = frappe.db.get_value(
        "Material Issue Plan Consolidate Item", {"batch_no": ["!=", ""]}, "parent")
    if not mip_name:
        print("no Material Issue Plan with consolidated rows on this site -- skipped")
        return

    mip = frappe.get_doc("Material Issue Plan", mip_name)
    row = mip.consolidate_items[0]
    key = "%s|%s|%s" % (row.item_code, row.batch_no or "", 1 if row.cnc_process else 0)
    print("plan %s, row %s / %s" % (mip_name, row.item_code, row.batch_no))

    print()
    print("=== saving parks the state, unvalidated ===")
    # Deliberately more Sec Nos than could possibly be in stock: an unfinished draft
    # must save regardless, since validating here would refuse the very state being kept.
    draft = [{
        "item_code": row.item_code, "batch_no": row.batch_no,
        "cnc_process": 1 if row.cnc_process else 0,
        "custom_sec_qty": 9999,
    }]
    # The off-cut is stated once per ITEM now, on the popup's consolidated tab,
    # rather than once per batch row -- the same off-cut comes back whichever
    # batches it was drawn from. It is parked against every batch row of that item
    # so reopening finds it whichever row it reads first.
    excess_plan = {row.item_code: {"length": 640, "width": 12, "sec_qty": 1.25,
                                   "return_warehouse": mip.source_warehouse or ""}}
    res = save_transfer_draft(mip_name, json.dumps(draft), json.dumps(excess_plan))
    check("one row saved", res.get("saved"), 1)

    got = get_transfer_draft(mip_name).get(key) or {}
    check("Sec Nos parked as typed, however implausible", flt(got.get("draft_sec_qty")), 9999.0)
    check("excess length parked", flt(got.get("draft_excess_length")), 640.0)
    check("excess width parked", flt(got.get("draft_excess_width")), 12.0)
    check("excess Sec Nos parked", flt(got.get("draft_excess_sec_qty")), 1.25)
    check("return warehouse parked", got.get("draft_return_warehouse"), mip.source_warehouse or "")
    check("stamped with a save time", bool(got.get("draft_saved_on")), True)

    print()
    print("=== it survives a re-save of the plan, which rebuilds the whole table ===")
    mip.reload()
    mip.save(ignore_permissions=True)
    frappe.db.commit()
    after = get_transfer_draft(mip_name).get(key) or {}
    check("still present after rebuild", bool(after), True)
    check("Sec Nos intact", flt(after.get("draft_sec_qty")), 9999.0)
    check("excess intact", flt(after.get("draft_excess_length")), 640.0)
    check("warehouse intact", after.get("draft_return_warehouse"), mip.source_warehouse or "")

    print()
    print("=== a row that no longer exists is skipped, not invented ===")
    ghost = [{"item_code": "ZZ-NOT-A-REAL-ITEM", "batch_no": "ZZ-NOT-A-REAL-BATCH",
              "cnc_process": 0, "custom_sec_qty": 5}]
    check("nothing saved for it", save_transfer_draft(mip_name, json.dumps(ghost)).get("saved"), 0)

    print()
    print("=== transferring clears it ===")
    _clear_transfer_draft(mip_name, [{
        "item_code": row.item_code, "batch_no": row.batch_no,
        "cnc_process": 1 if row.cnc_process else 0,
    }])
    frappe.db.commit()
    check("draft gone for that row", key in get_transfer_draft(mip_name), False)

    print()
    print("=== and clearing survives the next rebuild too ===")
    mip.reload()
    mip.save(ignore_permissions=True)
    frappe.db.commit()
    check("still gone", key in get_transfer_draft(mip_name), False)

    print()
    print("=== SUMMARY ===")
    if all(checks):
        print("ALL %d CHECKS PASSED" % len(checks))
    else:
        print("%d of %d CHECKS FAILED" % (checks.count(False), len(checks)))
