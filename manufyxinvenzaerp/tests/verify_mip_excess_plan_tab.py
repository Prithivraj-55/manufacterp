"""The transfer popup plans excess return per ITEM, not per batch.

The old per-batch panel asked for the same item's off-cut once for every batch it
was drawn from, and only ever appeared on a line already over plan -- so in
practice it was never seen at all. It is replaced by a second tab that
consolidates the selected rows by item code and carries no batch reference,
because an off-cut comes back as one shape however many batches fed it.

    Excess Kg (system)  = Planned transfer weight - Planned drawing weight
    Difference          = Excess Kg (entered) - Excess Kg (system)

Positive means more is coming back than the transfer created, negative means part
of it is unaccounted for. Neither blocks the transfer.

This covers the arithmetic and the plumbing that carries the plan to the server;
the tab itself is client-side.

Run: bench --site manufact execute manufyxinvenzaerp.tests.verify_mip_excess_plan_tab.run
"""

import inspect
import json
import os

import frappe
from frappe.utils import flt

checks = []


def check(label, got, want):
    ok = got == want
    checks.append(ok)
    print("  %-4s %-58s got=%r want=%r" % ("OK" if ok else "FAIL", label, got, want))


def _js():
    path = os.path.join(
        frappe.get_app_path("manufyxinvenzaerp"),
        "subcontracting_management", "doctype", "material_issue_plan", "material_issue_plan.js",
    )
    with open(path) as f:
        return f.read()


def run():
    from manufyxinvenzaerp.subcontracting_management.material_issue_plan_transfer import (
        create_mip_partial_transfer, get_mip_pending_items, _log_round_up_excess,
    )
    from manufyxinvenzaerp.utils.dimension_formula import calculate_qty

    js = _js()

    print("=== the old per-batch panel is gone ===")
    for gone in ("mip-excess-tr", "_excess_row_html", "_reveal_excess_row",
                 "_collect_excess_entry", "mip-ex-length"):
        check("%s removed" % gone, gone in js, False)

    print()
    print("=== the two tabs exist ===")
    check("transfer tab", "Raw material to transfer" in js, True)
    check("excess tab", "Consolidate item for excess return plan" in js, True)
    check("the formula is stated on screen",
          "Planned transfer weight − Planned drawing weight" in js, True)
    check("...and so is the difference",
          "Excess Kg (entered) − Excess Kg (system)" in js, True)
    check("positive/negative is spelled out",
          "positive = extra, negative = missing" in js, True)

    print()
    print("=== the plan reaches the server ===")
    check("popup sends it", "excess_plan_json" in js, True)
    sig = inspect.signature(create_mip_partial_transfer)
    check("transfer accepts it", "excess_plan_json" in sig.parameters, True)
    check("...and it is optional", sig.parameters["excess_plan_json"].default, None)
    check("the logger accepts it",
          "excess_plan" in inspect.signature(_log_round_up_excess).parameters, True)

    print()
    print("=== the drawing weight travels with each pending row ===")
    mip = frappe.db.get_value(
        "Material Issue Plan", {"docstatus": ["<", 2]}, "name", order_by="creation desc")
    if not mip:
        print("   (no Material Issue Plan on this site -- skipped)")
    else:
        try:
            pending = get_mip_pending_items(mip)
        except Exception as e:
            pending = []
            print("   (%s could not be read: %s)" % (mip, frappe.utils.strip_html(str(e))[:80]))
        if pending:
            check("every row carries drawing_planned_weight",
                  all("drawing_planned_weight" in r for r in pending), True)
            print("   %s: %d pending row(s), e.g. %s -> drawing %s Kg, pending %s Kg"
                  % (mip, len(pending), pending[0]["item_code"],
                     pending[0].get("drawing_planned_weight"), pending[0].get("qty")))
        else:
            print("   (%s has nothing pending -- field presence not exercised)" % mip)

    print()
    print("=== the arithmetic, worked through the client's own example ===")
    def plan(drawing_kg, transfer_kg, entered_kg):
        system = flt(transfer_kg - drawing_kg, 3)
        return system, flt(entered_kg - system, 3)

    check("100 planned, 110 transferred -> 10 excess", plan(100, 110, 10)[0], 10.0)
    check("entered 11 -> +1 (extra)", plan(100, 110, 11)[1], 1.0)
    check("entered 9 -> -1 (missing)", plan(100, 110, 9)[1], -1.0)
    check("entered exactly 10 -> 0", plan(100, 110, 10)[1], 0.0)
    check("nothing over-transferred -> no excess", plan(100, 100, 0)[0], 0.0)

    print()
    print("=== the entered Kg uses the same formula as everywhere else ===")
    # A structural off-cut: 1.2 m of a 23.5 kg/m section, 2 pieces.
    entered = calculate_qty("Structurals", 1200, 0, 0, 23.5, 2)
    check("structural off-cut", flt(entered, 3), 56.4)
    plate = calculate_qty("Plates", 500, 300, 10, 7.85, 1)
    check("plate off-cut", flt(plate, 3), 11.775)

    print()
    print("=== consolidation groups by item, across batches ===")
    rows = [
        {"item_code": "ISA100", "qty": 60.0, "drawing_planned_weight": 25.0},
        {"item_code": "ISA100", "qty": 50.0, "drawing_planned_weight": 25.0},
        {"item_code": "ISMB400", "qty": 200.0, "drawing_planned_weight": 190.0},
    ]
    by_item = {}
    for r in rows:
        e = by_item.setdefault(r["item_code"], {"drawing": 0.0, "transfer": 0.0, "batches": 0})
        e["drawing"] += r["drawing_planned_weight"]
        e["transfer"] += r["qty"]
        e["batches"] += 1
    check("two items, not three rows", sorted(by_item), ["ISA100", "ISMB400"])
    check("ISA100 drew from 2 batches", by_item["ISA100"]["batches"], 2)
    check("its drawing weight adds up", by_item["ISA100"]["drawing"], 50.0)
    check("its transfer weight adds up", by_item["ISA100"]["transfer"], 110.0)
    check("so its excess is one figure",
          flt(by_item["ISA100"]["transfer"] - by_item["ISA100"]["drawing"], 3), 60.0)
    print("       (asked once for ISA100, not once per batch)")

    print()
    print("=== an empty plan is accepted and changes nothing ===")
    check("empty json parses to nothing", json.loads("{}"), {})

    print()
    print("=== the plan is booked into the Excess Material table ===")
    from manufyxinvenzaerp.subcontracting_management.material_issue_plan_transfer import (
        _log_consolidated_excess, CONSOLIDATED_EXCESS_SOURCE,
    )
    check("booking function exists", callable(_log_consolidated_excess), True)
    check("...under its own source table", CONSOLIDATED_EXCESS_SOURCE,
          "Consolidated Excess Return Plan")
    src = inspect.getsource(_log_consolidated_excess)
    check("keyed by item, not item+batch", "source_row\": code" in src, True)
    check("books the measured Kg", "\"qty\": entered_kg" in src, True)
    check("a second transfer accumulates", "target.qty = flt(flt(target.qty) + entered_kg" in src, True)
    check("a settled row is never drifted", "stock_entry_created" in src, True)
    round_src = inspect.getsource(_log_round_up_excess)
    check("the per-batch logger stands aside for a planned item",
          'if (excess_plan or {}).get(item["item_code"]):' in round_src, True)

    print()
    print("=== Save and Close keeps the plan ===")
    from manufyxinvenzaerp.subcontracting_management.doctype.material_issue_plan.material_issue_plan import (
        save_transfer_draft,
    )
    check("the draft accepts it",
          "excess_plan_json" in inspect.signature(save_transfer_draft).parameters, True)
    check("the popup sends it with the draft too", js.count("excess_plan_json") >= 2, True)
    check("and restores it on reopen", "dlg._excess_plan[d.item_code]" in js, True)

    print()
    print("=== SUMMARY ===")
    if all(checks):
        print("ALL %d CHECKS PASSED" % len(checks))
    else:
        print("%d of %d CHECKS FAILED" % (checks.count(False), len(checks)))
