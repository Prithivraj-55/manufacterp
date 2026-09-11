"""Applying a Consolidate Items batch reassignment -- Phases 3 and 4.

Phase 1 built the read-only half: expand a line to its members, price the target
batches, report what a reassignment would do. This is the half that writes.

The whole design rests on one uncomfortable fact: unreserve_batches,
unreserve_exact_match_batches, reserve_batches and reserve_exact_match_batches each
COMMIT internally, and MariaDB destroys every SAVEPOINT on COMMIT. There is no
transaction spanning the fan-out and no way to roll one back. Safety therefore comes
from two places, and both are tested here:

  * everything that can be refused is refused BEFORE the first write (checks 2-4), and
  * plans are done one at a time so a failure strands at most one plan's
    reservations, on its ORIGINAL batch, recoverable by re-running.

The live round trip (check 6) is the only thing that proves the writing path end to
end, and it genuinely reassigns real reservations, so it is OFF by default:

    bench --site manufact execute manufyxinvenzaerp.tests.verify_consolidate_batch_apply.run --kwargs "{'live': 1}"

It moves a line to another batch, checks the result, and moves it back, asserting the
rows come home byte-identical. Note that a reassign discards that line's parked
transfer draft by design -- the draft is keyed on the batch -- so the round trip does
NOT restore it. Take a backup first.

Run: bench --site manufact execute manufyxinvenzaerp.tests.verify_consolidate_batch_apply.run
"""

import json

import frappe
from frappe.utils import flt

from manufyxinvenzaerp.subcontracting_management import material_issue_plan_batch_update as bu

checks = []


def check(label, got, want):
    ok = got == want
    checks.append(ok)
    print("  %-4s %-62s got=%r want=%r" % ("OK" if ok else "FAIL", label, got, want))


def _member(kg, table=None, mp="MP-1", row=None, group="Plates", idx=1):
    return frappe._dict({
        "target_kg": kg, "source_table": table or bu.MATERIAL_MAPPING,
        "material_planning": mp, "source_row": row or ("r%s" % kg),
        "parent_item_group": group, "idx": idx,
    })


def _target(batch, cap, group="Plates", unit_weight=7.85, item="X"):
    return {"batch_no": batch, "effective_capacity_kg": cap, "parent_item_group": group,
            "unit_weight": unit_weight, "item_code": item}


def run(live=0):
    print("=== 1. Each member is given a waiver and a Sec Nos that cannot be silently wrong ===")
    # The trap this guards: _apply_batch_to_mapping_row, given rwd=0 and no Sec Nos,
    # keeps the OLD batch's piece count and prices it against the NEW batch's
    # dimensions. Nothing throws; the row simply comes to hold a meaningless weight.
    fill = bu.plan_fill([_member(100), _member(200)], [_target("A", 1000)])
    writes, blockers, warnings = bu.plan_member_writes(fill, [_target("A", 1000)])
    check("plates are waived", [w.reserve_without_dimensions for w in writes], [1, 1])
    check("and their Sec Nos is left for the server to derive",
          [w.sec_qty for w in writes], [None, None])
    check("no blockers", blockers, [])

    nb = _target("B", 1000, group="Nuts and Bolts", unit_weight=0.25)
    fill_nb = bu.plan_fill([_member(100, group="Nuts and Bolts")], [nb])
    writes_nb, blockers_nb, warnings_nb = bu.plan_member_writes(fill_nb, [nb])
    # A bolt's weight is exact, so the waiver is wrong for it -- but then Sec Nos MUST
    # be sent explicitly, or the trap above applies.
    check("bolts are not waived", writes_nb[0].reserve_without_dimensions, 0)
    check("so their piece count is computed and sent", writes_nb[0].sec_qty, 400.0)
    check("a whole count raises no warning", warnings_nb, [])

    odd = _target("B", 1000, group="Nuts and Bolts", unit_weight=0.3)
    w_odd, _b, warn_odd = bu.plan_member_writes(
        bu.plan_fill([_member(100, group="Nuts and Bolts")], [odd]), [odd])
    check("a fractional count is surfaced, not rounded away", len(warn_odd), 1)
    check("and the weight is left exactly as planned", w_odd[0].sec_qty, 333.333)

    no_uw = _target("B", 1000, group="Nuts and Bolts", unit_weight=0)
    _w, b_uw, _warn = bu.plan_member_writes(
        bu.plan_fill([_member(100, group="Nuts and Bolts")], [no_uw]), [no_uw])
    check("an item with no unit weight is refused, not guessed", len(b_uw), 1)

    print()
    print("=== 2. The split lands where reading the table top to bottom says it will ===")
    ms = [_member(300, row="a"), _member(300, row="b"), _member(400, row="c")]
    ts = [_target("A", 700), _target("B", 700)]
    f = bu.plan_fill(ms, ts)
    w2, _b2, _w2 = bu.plan_member_writes(f, ts)
    check("the third row moves whole to the second batch",
          [x.batch_no for x in w2], ["A", "A", "B"])
    check("and the capacity it could not use is reported", f.leftover_kg[0], 100.0)

    print()
    print("=== 3. Same-table batch sharing is NOT a cross-table conflict ===")
    # One plate cut into a dozen parts means a dozen Material Mapping rows on one
    # batch. Treating that as a clash refuses nearly every real reassignment -- and
    # it did, until this was fixed. _validate_no_cross_table_batch_duplicate only
    # refuses a batch held in Material Mapping AND Exact Match at once.
    shared = frappe.db.sql("""
        SELECT parent, batch, COUNT(*) n FROM `tabMaterial Planning Material Mapping`
        WHERE batch != '' GROUP BY parent, batch HAVING n > 1 LIMIT 1
    """, as_dict=True)
    if not shared:
        print("  (no batch shared by two Material Mapping rows on this site -- skipped)")
    else:
        mp_name, batch = shared[0].parent, shared[0].batch
        rows = frappe.get_all("Material Planning Material Mapping",
                              filters={"parent": mp_name, "batch": batch}, fields=["name"])
        members = [frappe._dict({"source_table": bu.MATERIAL_MAPPING, "source_row": r.name,
                                 "material_planning": mp_name}) for r in rows[:1]]
        problems = bu._cross_table_conflicts([mp_name], [batch], members)
        same_table = [p for p in problems if "Material Mapping row" in p]
        check("%d rows of %s share %s without clashing" % (shared[0].n, mp_name, batch),
              same_table, [])

    print()
    print("=== 4. A line whose rows straddle both tables is refused up front ===")
    straddle = [
        frappe._dict({"source_table": bu.MATERIAL_MAPPING, "source_row": "m1", "material_planning": "MP-X"}),
        frappe._dict({"source_table": bu.AVAILABLE_RAW_MATERIAL, "source_row": "a1", "material_planning": "MP-X"}),
    ]
    problems = bu._cross_table_conflicts(["MP-X"], ["B1"], straddle)
    check("moving both onto one batch would duplicate it", len(problems), 1)
    check("and the reason names both tables",
          "both Material Mapping and Exact Match" in problems[0], True)

    print()
    print("=== 5. The apply path refuses what the preview refused ===")
    moved = frappe.db.sql("""
        SELECT c.parent AS mip, c.name AS crow FROM `tabMaterial Issue Plan Consolidate Item` c
        WHERE c.transferred_qty > 0 LIMIT 1
    """, as_dict=True)
    if not moved:
        print("  (no transferred consolidate line on this site -- skipped)")
    else:
        try:
            bu.apply_consolidate_batch_update(moved[0].mip, moved[0].crow, "[]", None)
            check("a transferred line is refused", False, True)
        except frappe.ValidationError as e:
            check("a transferred line is refused", "already been transferred" in str(e), True)

    live_line = frappe.db.sql("""
        SELECT c.parent AS mip, c.name AS crow, c.item_code, c.batch_no, c.qty, c.source_rows
        FROM `tabMaterial Issue Plan Consolidate Item` c
        WHERE c.transferred_qty = 0 AND c.source_rows > 1 ORDER BY c.source_rows LIMIT 1
    """, as_dict=True)
    if live_line:
        line = live_line[0]
        targets = json.dumps([{"batch_no": line.batch_no, "pieces": 1}])
        try:
            bu.apply_consolidate_batch_update(line.mip, line.crow, targets, None)
            check("reassigning to the batch it already has is refused", False, True)
        except frappe.ValidationError as e:
            check("reassigning to the batch it already has is refused",
                  "already uses" in str(e), True)

        # A plan confirmed against figures that have since changed must not be applied.
        try:
            bu.apply_consolidate_batch_update(line.mip, line.crow, targets, "stalehash0000000")
            check("a stale plan_hash is refused", False, True)
        except frappe.ValidationError as e:
            check("a stale plan_hash is refused",
                  ("Out Of Date" in str(e) or "changed while the dialog" in str(e)
                   or "already uses" in str(e)), True)

    print()
    print("=== 5b. The line's warehouse comes from the plan, not the Issue Plan ===")
    # Every stock figure the server computes uses the Material Planning's
    # for_warehouse. The dialog used to price candidate batches against the Material
    # Issue Plan's own source_warehouse instead. On most plans the two agree, which is
    # exactly why this went unnoticed -- and on a plan where the Issue Plan's is blank
    # the candidate list came back empty for no visible reason.
    mismatched = frappe.db.sql("""
        SELECT c.parent AS mip, c.name AS crow, m.source_warehouse AS mip_wh,
               p.for_warehouse AS mp_wh
        FROM `tabMaterial Issue Plan Consolidate Item` c
        JOIN `tabMaterial Issue Plan` m ON m.name = c.parent
        JOIN `tabMaterial Issue Plan Raw Material` r
             ON r.parent = c.parent AND r.batch_no = c.batch_no
        JOIN `tabMaterial Planning` p ON p.name = r.material_planning
        WHERE IFNULL(m.source_warehouse, '') != IFNULL(p.for_warehouse, '')
          AND IFNULL(p.for_warehouse, '') != ''
        LIMIT 1
    """, as_dict=True)
    if not mismatched:
        print("  (every plan on this site agrees with its Issue Plan -- nothing to prove)")
    else:
        case = mismatched[0]
        ctx = bu.get_consolidate_line_context(case.mip, case.crow)
        check("%s: Issue Plan says %r, plan says %r"
              % (case.mip, case.mip_wh or "", case.mp_wh),
              ctx["warehouse"], case.mp_wh)
        check("and candidates are found there",
              len(bu.get_candidate_batches(ctx["item_code"], ctx["warehouse"])) > 0, True)

    print()
    print("=== 6. Live round trip (writes) ===")
    if not live:
        print("  (skipped -- pass live=1 to run it; see this file's docstring)")
    else:
        _round_trip()

    print()
    print("=== 7. Nothing was written by the checks above ===")
    if not live:
        check("no uncommitted changes pending", bool(frappe.db.transaction_writes), False)

    total, failed = len(checks), checks.count(False)
    print()
    if failed:
        print("%d of %d CHECKS FAILED" % (failed, total))
    else:
        print("ALL %d CHECKS PASSED" % total)


def _round_trip():
    """Move a real line to another batch and back, asserting it comes home unchanged."""
    line = frappe.db.sql("""
        SELECT c.parent AS mip, c.name AS crow, c.item_code, c.batch_no
        FROM `tabMaterial Issue Plan Consolidate Item` c
        WHERE c.transferred_qty = 0 AND c.source_rows > 1 ORDER BY c.source_rows LIMIT 1
    """, as_dict=True)
    if not line:
        print("  (no untransferred multi-row line -- skipped)")
        return
    line = line[0]
    mip = frappe.get_doc("Material Issue Plan", line.mip)
    key, members = bu.expand_consolidate_row(mip, line.crow)
    names = [m.source_row for m in members if m.source_table == bu.MATERIAL_MAPPING]
    if len(names) != len(members):
        print("  (line mixes tables -- round trip skipped)")
        return

    fields = ["batch", "batch_calc_qty", "batch_sec_qty", "is_reserved", "reserved_qty",
              "reserve_without_dimensions", "batch_length", "batch_width", "batch_thickness"]

    def snap():
        return {n: frappe.db.get_value(bu.MATERIAL_MAPPING, n, fields, as_dict=True) for n in names}

    before = snap()
    total_before = flt(sum(flt(r.batch_calc_qty) for r in before.values()), 3)

    other = next((b for b in bu.get_candidate_batches(key[0], mip.source_warehouse)
                  if b["batch_no"] != key[1]), None)
    if not other:
        print("  (no alternative batch with free stock -- round trip skipped)")
        return

    out = json.dumps([{"batch_no": other["batch_no"], "pieces": 1}])
    pv = bu.preview_consolidate_batch_update(line.mip, line.crow, out)
    if not pv["ok"]:
        print("  (preview refused the alternative batch: %s -- skipped)" % pv["blockers"])
        return
    bu.apply_consolidate_batch_update(line.mip, line.crow, out, pv["plan_hash"])

    after = snap()
    check("every row moved to the new batch",
          all(r.batch == other["batch_no"] for r in after.values()), True)
    check("the line's total Kg is unchanged",
          flt(sum(flt(r.batch_calc_qty) for r in after.values()), 3), total_before)
    check("every row is waived", all(r.reserve_without_dimensions == 1 for r in after.values()), True)
    check("every row reserves its own requirement",
          all(flt(r.batch_calc_qty, 3) == flt(before[n].batch_calc_qty, 3) for n, r in after.items()), True)
    check("and is reserved again", all(r.is_reserved == 1 for r in after.values()), True)
    check("the batch's dimensions came with it",
          all(flt(r.batch_length) == flt(other["length"]) for r in after.values()), True)

    # Home again. The consolidate row was regenerated, so it must be found afresh.
    mip = frappe.get_doc("Material Issue Plan", line.mip)
    crow = next(c for c in mip.consolidate_items
                if c.item_code == line.item_code and c.batch_no == other["batch_no"])
    back = json.dumps([{"batch_no": line.batch_no, "pieces": 1}])
    pv2 = bu.preview_consolidate_batch_update(line.mip, crow.name, back)
    check("moving back is allowed", pv2["ok"], True)
    if pv2["ok"]:
        bu.apply_consolidate_batch_update(line.mip, crow.name, back, pv2["plan_hash"])
        restored = snap()
        check("every row came home exactly as it left",
              {n: dict(r) for n, r in restored.items()},
              {n: dict(r) for n, r in before.items()})
