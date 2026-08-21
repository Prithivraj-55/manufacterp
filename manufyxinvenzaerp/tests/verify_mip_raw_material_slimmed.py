"""Excess Return and Cut Sheet are gone from the raw-material table.

Both had outgrown it. Excess Return is its own table on the same document, where an
off-cut is described once with its dimensions. Cut Sheet is its own doctype, where a
sheet's nesting is stated once against its batch and shared by every job drawing from
it. Keeping editable copies on every raw-material line meant two places could disagree
about one physical plate -- and a batch's balance was being written by two independent
mechanisms, which is how four batches went stranded in the first place.

What stays on the row is reference only: where the chosen batch has a Cut Sheet, the
To Use and Balance sizes are shown, read-only, taken from that Cut Sheet. They are what
the transfer's Stock Entry carries, so whoever makes it can see them without opening
another document.

This is a removal, so most of what is worth checking is structural: the fields are
gone, the code behind them is gone, nothing still writes to them, and the one thing
they still did -- capping a cut row's transfer at its To Use weight -- now reads from
Material Planning instead.

Run: bench --site manufact execute manufyxinvenzaerp.tests.verify_mip_raw_material_slimmed.run
"""

import frappe

checks = []
ROW_DT = "Material Issue Plan Raw Material"

GONE_EXCESS = [
    "section_excess_return", "excess_return_applicable", "excess_calc_qty",
    "col_break_excess_return", "excess_length", "excess_width", "excess_sec_qty",
    "excess_return_date",
]
GONE_CUT_SHEET = [
    "section_cut_sheet", "cut_sheet", "use_length", "use_width", "use_sec_qty",
    "use_calc_qty", "balance_length", "balance_width", "balance_sec_qty",
    "balance_calc_qty", "precut_length", "precut_width", "precut_sec_qty",
    "w2_repack_entry",
]
REFERENCE = [
    "cut_sheet_ref", "cs_use_length", "cs_use_width", "cs_use_sec_qty",
    "cs_balance_length", "cs_balance_width", "cs_balance_sec_qty",
]
KEPT = ["excess_qty", "transfer_excess_kg", "qty", "transferred_qty", "batch_no"]


def check(label, got, want):
    ok = got == want
    checks.append(ok)
    print("  %-4s %-56s got=%r want=%r" % ("OK" if ok else "FAIL", label, got, want))


def _source(*parts):
    return open(frappe.get_app_path("manufyxinvenzaerp", *parts)).read()


def _row_queries(src):
    """Every query made against the raw-material table, as raw text, so the field
    lists inside them can be looked at."""
    out = []
    marker = '"Material Issue Plan Raw Material"'
    start = 0
    while True:
        i = src.find(marker, start)
        if i == -1:
            return out
        out.append(src[i:i + 400])
        start = i + 1


def run():
    meta = frappe.get_meta(ROW_DT)
    present = {f.fieldname for f in meta.fields}

    print("=== Excess Return has left the row ===")
    check("none of its fields remain", sorted(f for f in GONE_EXCESS if f in present), [])

    print()
    print("=== so has the cut plan ===")
    check("none of its fields remain", sorted(f for f in GONE_CUT_SHEET if f in present), [])

    print()
    print("=== what the row still needs is untouched ===")
    check("the figures the transfer and the summary use",
          sorted(f for f in KEPT if f not in present), [])

    print()
    print("=== the Cut Sheet sizes stay, to look at ===")
    check("all present", sorted(f for f in REFERENCE if f not in present), [])
    check("every one of them read-only",
          sorted(f for f in REFERENCE if not meta.get_field(f).read_only), [])
    check("shown only where there is a cut sheet",
          meta.get_field("section_cut_sheet_ref").depends_on, "eval:doc.cut_sheet_ref")
    check("and it points at the Cut Sheet itself",
          meta.get_field("cut_sheet_ref").options, "Cut Sheet")

    print()
    print("=== the code behind the removed fields went with them ===")
    mip = _source("subcontracting_management", "doctype", "material_issue_plan", "material_issue_plan.py")
    js = _source("subcontracting_management", "doctype", "material_issue_plan", "material_issue_plan.js")
    se = _source("production_management", "stock_entry.py")
    transfer = _source("subcontracting_management", "material_issue_plan_transfer.py")

    for fn in ("_sync_excess_return_from_raw_materials", "_auto_suggest_excess_from_cut_sheet",
               "_sync_cut_sheet_calc", "_warn_cut_sheet_mismatch", "_cut_sheet_sheet_qty",
               "_cut_sheet_seed", "_carry_forward_editable_fields", "_RAW_TO_EXCESS_FIELDS",
               "_claimed_excess_differs"):
        check("%s is gone" % fn, "def %s" % fn in mip or fn + " =" in mip, False)

    check("the live Excess Calc preview is gone", "_recalc_excess_calc_qty" in js, False)
    check("the live W1/W2 preview is gone", "_recalc_cut_sheet_qty" in js, False)

    print()
    print("=== one mechanism writes a batch's balance, not two ===")
    for fn in ("_resize_cut_sheet_batches", "_restore_cut_sheet_batches",
               "_reapply_cut_sheet_batch_sizes", "_apply_cut_sheet_batch_size",
               "_apply_cut_sheet_balance_as_new_batch"):
        check("%s is gone" % fn, "def %s" % fn in se, False)
    check("the Cut Sheet doctype's own path remains",
          "def _apply_cut_sheet_w2(" in se, True)
    check("including its new-batch mode",
          "def _apply_cut_sheet_w2_as_new_batch(" in se, True)

    print()
    print("=== the transfer still caps a cut row at its To Use weight ===")
    check("the cap survives", "cut_sheet_qty_by_key" in transfer, True)
    check("read from Material Planning now", "def _cut_sheet_caps(mip):" in transfer, True)
    check("and no longer from this document's own rows",
          "for r in (mip.raw_materials or [])\n        if r.cut_sheet" in transfer, False)

    print()
    print("=== nothing reads a raw-material field that no longer exists ===")
    # Bare field names are no guide here: Material Planning's own rows still carry
    # cut_sheet and use_calc_qty, and the Cut Sheet doctype still carries
    # w2_repack_entry. What matters is that nothing goes looking for them on THIS
    # table -- so the check is on queries against it, not on the words.
    for src, label in ((mip, "the issue plan"), (transfer, "the transfer"), (se, "the stock entry")):
        for m in _row_queries(src):
            check("%s asks this table only for fields it still has" % label,
                  sorted(f for f in GONE_EXCESS + GONE_CUT_SHEET if ('"%s"' % f) in m), [])
    check("the row's own excess fields are read nowhere",
          any(("row." + f) in src or ("r." + f) in src
              for f in ("excess_return_applicable", "excess_calc_qty", "excess_return_date")
              for src in (mip, transfer, se)), False)

    print()
    print("=== SUMMARY ===")
    if all(checks):
        print("ALL %d CHECKS PASSED" % len(checks))
    else:
        print("%d of %d CHECKS FAILED" % (checks.count(False), len(checks)))
