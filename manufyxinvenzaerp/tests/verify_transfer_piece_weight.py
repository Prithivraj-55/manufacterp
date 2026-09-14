"""Transfer popup: what one piece weighs, and how much of a batch a plan may take.

Reported on MIP-2026-00005 (14 Sep 2026): raising PLATE16's 0.48 Nos to 1 whole piece
was refused -- "Batch PLT16-T16-L12000-W1500-R008 has only 2260.8 Kg free. 1.0 Nos needs
2262.108 Kg" -- on a batch holding exactly one 2,260.8 Kg plate.

Two defects, both fixed here, both pinned below.

1. A piece was priced as planned Kg / planned Sec Nos. Sec Nos is stored to 3 decimals,
   so for a small fraction that division is wrong: 1,085.812 / 0.480 = 2,262.108 where
   the plate weighs 2,260.8. Worse, on PLATE12 (6.264 Kg = 0.004433 Nos, stored 0.004)
   one piece came out at 1,566 Kg against a real 1,413 -- the popup would have shipped
   153 Kg too much and booked 153 Kg of excess that never existed, and a transfer to
   the supplier does not recalculate weight from dimensions on its own.

2. Availability was physical stock only. That already included this plan's own
   reservation (correct), but ignored stock other drawings or plans hold reserved, so
   a transfer could take steel promised elsewhere.

Everything here is read-only or synthetic. Check 9 asserts nothing was written.

Run: bench --site manufact execute manufyxinvenzaerp.tests.verify_transfer_piece_weight.run
"""

import math
import re

import frappe
from frappe.utils import flt

from manufyxinvenzaerp.subcontracting_management import material_issue_plan_transfer as t

checks = []


def check(label, got, want):
    ok = got == want
    checks.append(ok)
    print("  %-4s %-66s got=%r want=%r" % ("OK" if ok else "FAIL", label, got, want))


def _plate(qty, sec, L, W, T, uw=7.85, rows=1, group="Plates"):
    return {"qty": qty, "custom_sec_qty": sec, "custom_length": L, "custom_width": W,
            "custom_thickness": T, "custom_unit_weight": uw, "custom_parent_item_group": group,
            "source_rows": rows}


def run():
    print("=== 1. A piece is priced from its dimensions, not from a rounded fraction ===")
    reported = _plate(1085.812, 0.48, 12000, 1500, 16)
    check("the reported plate: one piece weighs", t._line_kg_per_piece(reported), (2260.8, True))
    check("so 1 Nos asks for exactly the plate", t._qty_for_sec(reported, 1)[0], 2260.8)

    tiny = _plate(6.264, 0.004, 1250, 12000, 12)
    check("a tiny fraction (0.004433 stored 0.004): one piece", t._line_kg_per_piece(tiny), (1413.0, True))
    check("old arithmetic would have said", flt(6.264 / 0.004, 3), 1566.0)

    beam = _plate(100, 1.667, 6000, 0, 0, uw=10, group="Structurals")
    check("a structural: length x unit weight", t._line_kg_per_piece(beam), (60.0, True))

    # Seven rows, each Sec Nos rounded on its own, then added up.
    merged = _plate(1965.876, 2.087, 1250, 12000, 8, rows=7)
    check("a line merged from 7 rounded rows still trusts its dimensions",
          t._line_kg_per_piece(merged)[1], True)

    print()
    print("=== 2. Dimensions that do not describe the piece are not trusted ===")
    # A Cut Sheet row: Sec Nos counts cut W1 pieces of 50 Kg, but the row carries the
    # whole plate's size. Pricing from the plate would be wildly wrong -- it must fall
    # back to the plan's own ratio, exactly as before this fix.
    cut = _plate(100, 2.0, 1250, 12000, 12)
    check("a cut-piece line falls back to the plan", t._line_kg_per_piece(cut), (50.0, False))
    bare = _plate(100, 0, 0, 0, 0)
    check("no dimensions, no Sec Nos: nothing invented", t._line_kg_per_piece(bare), (0.0, False))
    bolts = {"qty": 400, "custom_sec_qty": 100, "custom_parent_item_group": "Nuts and Bolts"}
    check("Nuts and Bolts keep the plan ratio", t._line_kg_per_piece(bolts), (4.0, False))

    print()
    print("=== 3. Kg for a typed Sec Nos ===")
    check("Sec Nos left at the plan returns the plan's exact Kg", t._qty_for_sec(reported, 0.48)[0], 1085.812)
    check("raising it prices whole pieces", t._qty_for_sec(merged, 3)[0], 2826.0)
    check("lowering it is a partial transfer", t._qty_for_sec(merged, 2)[0], 1884.0)
    check("and a partial never exceeds the plan",
          t._qty_for_sec(_plate(1000, 1.2, 1250, 12000, 8), 1.19)[0] <= 1000, True)

    print()
    print("=== 4. Live pending lines: rounding up is priced from the batch, never from the fraction ===")
    mip_names = [m for m in frappe.get_all("Material Issue Plan", filters={"status": ["!=", "Completed"]}, pluck="name")
                 if frappe.db.get_value("Material Issue Plan", m, "subcontracting_order")
                 or frappe.db.get_value("Material Issue Plan", m, "work_order")]
    lines_seen = 0
    for m in mip_names:
        for line in t.get_mip_pending_items(m):
            if not (flt(line["qty"]) > 0 and flt(line["custom_sec_qty"]) > 0):
                continue
            lines_seen += 1
            whole = max(1, math.ceil(round(flt(line["custom_sec_qty"]), 3) - 0.0001))
            res = t.update_transfer_sec_qty(m, line["item_code"], line["batch_no"], new_sec_qty=whole,
                                            cnc_process=line.get("cnc_process") or 0)
            if line["piece_from_dimensions"]:
                check("%s %s: %d Nos = %d x piece" % (m, line["item_code"], whole, whole),
                      res["qty"], flt(whole * line["kg_per_piece"], 3))
            unchanged = t.update_transfer_sec_qty(m, line["item_code"], line["batch_no"],
                                                  new_sec_qty=line["custom_sec_qty"],
                                                  cnc_process=line.get("cnc_process") or 0)
            check("%s %s: unchanged Sec Nos keeps the planned Kg" % (m, line["item_code"]),
                  (unchanged["qty"], unchanged["round_up_excess_kg"]), (flt(line["qty"], 3), 0.0))
            # Never a new false shortage on what the plan itself asks for.
            check("%s %s: planned Kg fits this plan's availability" % (m, line["item_code"]),
                  flt(line["available_for_plan"]) + 0.001 >= flt(line["qty"])
                  or flt(line["available_qty"]) + 0.001 < flt(line["qty"]), True)
    if not lines_seen:
        print("  (no pending Sec-Nos lines on this site -- skipped)")

    print()
    print("=== 5. Availability: own reservation counts, other drawings' do not ===")
    sample = None
    for m in mip_names:
        for line in t.get_mip_pending_items(m):
            if line.get("batch_no"):
                sample = (m, line)
                break
        if sample:
            break
    if not sample:
        print("  (no pending batched line -- skipped)")
    else:
        m, line = sample
        mip = frappe.get_doc("Material Issue Plan", m)
        info = t._batch_availability_for_plan(mip, line["item_code"], line["batch_no"])
        own = t._plan_rows_on_batch(mip, line["batch_no"])
        others = {(c["material_planning"], c["idx"]) for c in info.reserved_for_others}
        own_ids = set()
        for table, name in own:
            r = frappe.db.get_value(table, name, ["parent", "idx"], as_dict=True)
            own_ids.add((r.parent, r.idx))
        check("this plan's own rows are never counted against it", bool(others & own_ids), False)
        check("available = in stock - reserved for others",
              info.available, flt(max(0.0, info.in_stock - info.reserved_for_others_kg), 3))
        check("and the pending line carries that figure",
              flt(line["available_for_plan"]) <= info.available + 0.001, True)

    print()
    print("=== 6. The final check corrects a wrong Kg sent from the browser ===")
    if sample:
        m, line = sample
        if line["piece_from_dimensions"] and flt(line["custom_sec_qty"]) > 0:
            whole = max(1, math.ceil(round(flt(line["custom_sec_qty"]), 3) - 0.0001))
            sel = [{"item_code": line["item_code"], "batch_no": line["batch_no"],
                    "cnc_process": line.get("cnc_process") or 0,
                    "qty": 999999.0, "custom_sec_qty": whole}]
            want = flt(whole * line["kg_per_piece"], 3)
            try:
                t._validate_selected_against_stock(frappe.get_doc("Material Issue Plan", m), sel)
                check("browser Kg replaced by Sec Nos x piece", sel[0]["qty"], want)
                check("and the excess is measured from that", sel[0]["round_up_excess_kg"],
                      flt(max(0.0, want - flt(line["qty"])), 3))
            except frappe.ValidationError as e:
                # A genuine shortage: then the message must spell the sum out.
                msg = re.sub("<[^>]+>", " ", str(e))
                check("a shortage names the Kg asked for, per piece",
                      ("Nos ×" in msg) and ("Available for this plan" in msg) and ("Short by" in msg), True)

    print()
    print("=== 7. The shortage message ===")
    info = frappe._dict({"warehouse": "Stores", "in_stock": 2260.8, "available": 1000.0,
                         "reserved_for_others_kg": 1260.8,
                         "reserved_for_others": [{"material_planning": "MP-X", "table": "Material Mapping",
                                                  "idx": 4, "duno": "TYPE 2", "qty": 1260.8}]})
    msg = re.sub("<[^>]+>", " ", t._shortage_message("B-1", info, 2260.8, pieces=1, kg_per_piece=2260.8, planned_kg=1085.812))
    for part in ("1 Nos × 2260.8 Kg per piece = 2260.8 Kg", "In stock: 2260.8 Kg",
                 "Reserved for other drawings or plans: 1260.8 Kg", "DUNO TYPE 2",
                 "Available for this plan:", "Short by: 1260.8 Kg", "0 whole piece"):
        check("message says: %s" % part, part in msg, True)

    print()
    print("=== 8. The CNC-to-supplier leg only lowers, against what is at CNC ===")
    fake = [{"item_code": "X", "batch_no": "B", "qty": 500.0, "custom_sec_qty": 0.5, "available_qty": 500.0,
             "custom_length": 1000, "custom_width": 1000, "custom_thickness": 127.388535, "custom_unit_weight": 7.85,
             "custom_parent_item_group": "Plates"}]
    original = t.get_mip_cnc_pending_items
    try:
        t.get_mip_cnc_pending_items = lambda mip_name: fake
        mip = frappe._dict({"name": "MIP-X", "cnc_warehouse": "CNC"})
        up = t._update_cnc_forward_sec_qty(mip, "X", "B", 1)
        check("raising above what is at CNC is refused", up["blocked"], True)
        down = t._update_cnc_forward_sec_qty(mip, "X", "B", 0.25)
        check("lowering is allowed", (down["blocked"], down["qty"]), (False, 250.0))
    finally:
        t.get_mip_cnc_pending_items = original
    js = open(frappe.get_app_path("manufyxinvenzaerp", "subcontracting_management", "doctype",
                                  "material_issue_plan", "material_issue_plan.js")).read()
    check("the popup tells the server which leg it is on",
          'transfer_type: is_cnc_fwd ? "cnc_forward" : transfer_type' in js, True)
    check("the popup limits rows by this plan's availability", js.count("available_for_plan") >= 3, True)

    print()
    print("=== 9. Nothing was written ===")
    check("no uncommitted changes pending", bool(frappe.db.transaction_writes), False)

    total, failed = len(checks), checks.count(False)
    print()
    print(("%d of %d CHECKS FAILED" % (failed, total)) if failed else ("ALL %d CHECKS PASSED" % total))
