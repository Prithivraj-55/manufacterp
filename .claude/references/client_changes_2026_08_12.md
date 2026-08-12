# Client change requests — meeting 2026-08-12

Working list for the next stretch of work. **Nothing here is started.** Each task is
sized to be done on its own, so we can pick them off one at a time as tokens allow.

Blocked items are marked **[Q<n>]** — they need an answer from `~/Downloads/claude doubts.docx`
before the task can be finished (some can be started, just not completed).

Status legend: `[ ]` not started · `[~]` in progress · `[x]` done

---

## T1 — Stock Entry rate is 0 on some items  ·  [Q1]

**Asked for:** cost on Stock Entry lines should come from the purchase / valuation rate.

**Found:** no production code sets `basic_rate` anywhere — only `sample_data.py` and the
test fixtures do. Every Stock Entry this app builds (transfer, CNC leg, final manufacture,
excess return) leaves rate to ERPNext, which values a Material Transfer from the source
warehouse's own valuation. So a 0 rate means the stock went IN at 0 — most likely the
opening `Material Receipt`, or a Purchase Receipt line with no rate — rather than the
transfer being at fault.

**Work:** trace one 0-rate line back to the receipt that created the batch, confirm where
the 0 originates, then fix at that point. Only fall back to stamping `basic_rate` on our
own Stock Entry rows if the incoming valuation genuinely cannot be relied on.

Files: `production_management/stock_entry.py`, `subcontracting_management/material_issue_plan_transfer.py`,
`subcontracting_management/subcontracting.py`, `purchase_receipt_management/purchase_receipt.py`

---

## T2 — Hide "To CNC Warehouse" once CNC material has moved

**Asked for:** stop showing "To CNC Warehouse" after the planned raw material has been
transferred. If a CNC checkbox is later enabled in Material Planning, that flows into the
Material Issue Plan and the button must come back — then hide again once that material moves.

**Found:** `material_issue_plan.js:544` shows the button on `if (frm.doc.cnc_warehouse)`
alone, so it is permanently visible. "CNC to Supplier/WIP" is already conditional, via the
whitelisted `has_cnc_stock`.

**Work:** add a companion check ("are any CNC-flagged rows still pending transfer to CNC?")
and gate the button on it. Reuse `get_mip_cnc_pending_items` rather than adding a new query.
Naturally self-correcting: a newly CNC-flagged row becomes pending again and the button
returns, no extra state to store.

Files: `subcontracting_management/doctype/material_issue_plan/material_issue_plan.js`,
`subcontracting_management/material_issue_plan_transfer.py`

---

## T3 — Verify Material Planning reservations can be unfrozen

**Asked for:** confirm the existing unfreeze/unreserve works.

**Found:** `unreserve_batches` and `unreserve_exact_match_batches` both exist, plus a per-row
Unreserve button. Verification only — no change expected.

**Work:** check unreserve behaves correctly *after* a partial transfer and after a Stock
Entry is cancelled (the reservation flag is cleared on submit, so the interesting case is
whether a partly-transferred row can still be released and what happens to what already
shipped). Write it up; only change code if it misbehaves.

Files: `production_management/doctype/material_planning/material_planning.py`

---

## T4 — Cut Sheet W2 must reach the Batch master  ·  [Q2]

**Asked for:** after the final Stock Entry, the W2 weight / dimensions / Kg should all be
updated on the batch. Observed: Total available qty does not agree with the W2 figures.

**Found:** `_apply_cut_sheet_w2` (`stock_entry.py:219`) and `_apply_cut_sheet_batch_size`
already rewrite the batch's dimensions, and `_reduce_batch_sec_qty` adjusts `custom_sec_qty`
separately. Two different writers touching the same batch is the likely source of the
mismatch — quantity and dimensions can end up describing different states.

**Work:** reproduce with a cut-sheet job through to final Stock Entry, compare batch
`custom_sec_qty` / dimensions / derived Kg against W2, and make the two writers agree.
Needs Q2 answered: which figure is authoritative.

Files: `production_management/stock_entry.py`, `production_management/doctype/cut_sheet/cut_sheet.py`

---

## T5 — Nature of Work + Rate Schedule in the BOM template  ·  [Q3]

**Asked for:** add both as columns in the BOM upload template; on verify-raw-materials,
check each value already exists in its master; validate the Rate Schedule title format
(e.g. `RS- O/S-001 A`).

**Found:** both masters already exist — `Nature of Work` and `Rate Schedule`
(`drawing_management/doctype/`). Rate Schedule is `autoname: field:rs_no`, so its name IS
the title being typed. The template header list is `so_drawing_import.py:687`.

**Work:** two columns onto `headers` + the sample rows; carry them through the import rows
into the Drawing; validate on verify. Q3 covers the exact title grammar and whether an
unknown value should block the import or be created.

Files: `drawing_management/so_drawing_import.py`, `drawing_management/doctype/drawing/`,
`drawing_management/doctype/rate_schedule/rate_schedule.py`

---

## T6 — Capture excess at transfer time, not on the raw-material row  ·  [Q4] [Q5]

**Asked for:** enter the excess dimensions + Sec Qty inside the transfer popup, next to the
difference quantity, in a collapsible row per line (neat UI; build it in HTML/CSS if the
standard dialog can't do it). Remove the excess fields from the raw-material table. The
return needs a warehouse (some to Stores, some to Scrap), written onto the Excess Material
table at transfer and editable afterwards.

**Found:** the raw-material row carries `excess_return_applicable`, `excess_calc_qty`,
`excess_length/width/sec_qty`, `excess_return_date` — all to be retired. `SCO Excess
Material Item` has **no warehouse field** (`return_type` is a different thing: Return to Own
Warehouse / Retain at Supplier). The popup is already hand-built HTML, so the collapsible
row is a natural fit — no need to abandon the dialog.

**Work:** new `return_warehouse` field on the excess table; expandable sub-row per popup
line; write both through on transfer; drop the raw-material fields and everything feeding
them (`_sync_excess_return_from_raw_materials`, the auto-suggest from Cut Sheet W2, and the
`SCO Excess Material Item` client handlers keyed to those fields).

This is the largest task here. Worth splitting: **T6a** popup capture + warehouse, then
**T6b** removal of the old per-row fields once T6a is proven.

Files: `subcontracting_management/doctype/material_issue_plan/material_issue_plan.js`,
`.../material_issue_plan.py`, `subcontracting_management/material_issue_plan_transfer.py`,
`subcontracting_management/doctype/sco_excess_material_item/`

---

## T7 — "Billed to consume" on the excess table  ·  [Q6]

**Asked for:** not all excess comes back. Mark the remainder "billed to consume"; when set,
no transfer/return is needed for it.

**Found:** `_maybe_mark_completed` currently holds a Material Issue Plan open until every
excess row is returned, claimed, or Retain-at-Supplier. A third settled state slots in here
cleanly.

**Work:** checkbox on `SCO Excess Material Item`; exclude those rows from the Return Excess
Entry dialog; treat as settled for completion. Q6 covers whether this is a plain checkbox or
another `return_type` option, and whether the consumed weight should still be costed.

Files: `subcontracting_management/doctype/sco_excess_material_item/`,
`subcontracting_management/material_issue_plan_transfer.py`,
`subcontracting_management/doctype/material_issue_plan/material_issue_plan.py`

---

## T8 — Consolidate Items on the Material Issue Plan  ·  [Q7]

**Asked for:** mirror Material Planning's Consolidate Items — build it from the reserved
material for the selected drawings, no batch duplication, and drive the transfer popup from
it. Also: a consolidation bug where an alternate item shows twice, once with the wrong
group's total.

**Found:** Material Planning's version is `_consolidate_unavailable_items` /
`_recalculate_consolidate_items` and groups purely by `item_code`. The transfer popup groups
by `(item_code, batch_no, is_cnc)` where `item_code` is already resolved to
`planned_item or item_code` — so two batches of the same item legitimately produce two lines,
both labelled with the alternate's code. That may be the whole of the reported bug, or only
part of it.

**Work:** reproduce the ISM100/ISM150 case on real data first and pin down whether the
duplicate is two genuine batches or a real mis-grouping — then build the table. Q7 settles
whether consolidation is per item or per item+batch, which decides the whole design.

Files: `subcontracting_management/material_issue_plan_transfer.py`,
`subcontracting_management/doctype/material_issue_plan/`,
`production_management/doctype/material_planning/material_planning.py`

---

## T9 — Rename Supplier Operation Entry → Operation Entry  ·  [Q8]

**Asked for:** rename the doctype.

**Found:** app-owned, so mechanical, but wide: **125 occurrences across 26 files**, plus the
SQL table rename, plus child tables still called `SOE Drawing Detail` / `SOE Consumption Log`,
plus reports, hooks, fixtures and the `SCO-SOE-` naming series on existing records.

**Work:** `frappe.rename_doc` in a patch, then sweep the code. Do this on its own, with a
backup first, and not interleaved with other tasks. Q8 covers the child tables and the
naming series.

---

## T10 — Consumption Log: cap at actual qty in all cases

**Asked for:** drop the rework exemption. If actual is 4, never allow more than 4 — even
across multiple rows, even after an inspection rejection.

**Found:** the exemption is deliberate and documented at `subcontracting.py:1165` (Op-2+
skips the per-drawing Nos ceiling when Inspection Mandatory is on, precisely so a rejected
piece can be re-logged).

⚠️ **Interacts with a fix made on 2026-08-12.** `_soe_consumed_kg` scales logged Kg by
accepted/logged Nos *because* rework re-logs the same piece. Once re-logging is forbidden
the scaling becomes a no-op — harmless, but the rework workflow itself changes, and it is
not obvious how a reworked piece then gets recorded. **Q9 must be answered before this is
implemented**; it is the one task here that could break an existing workflow.

Files: `subcontracting_management/subcontracting.py`, `production_management/inspection.py`

---

## T11 — Production Report  ·  [Q10]

**Asked for:** a new report — Sales Order wise, Production Plan wise, Drawing wise,
DU/Mark No wise, with customer weight, planned weight, transferred weight, excess weight.

**Found:** `production_management/report/production_report/` **already exists** and already
has Sales Order, Production Plan, Drawing, DUNO/Mark No, Consumed Kg, Completed Nos and the
inspection columns. Missing: customer weight, planned weight, transferred weight, excess
weight — all four available on `SOE Drawing Detail` / `SCO Drawing Item`.

**Work:** most likely extend the existing report rather than build a second one. Q10 confirms
that, since the existing one is operation-wise (one row per operation) while this ask reads
as drawing-wise (one row per drawing).

Files: `production_management/report/production_report/production_report.py`

---

## T12 — Customer Fund Usage: reference type + name

**Asked for:** next to Source of Funds, show the Payment Reference type (Sales Order) and
reference name (Order ID).

**Found:** the report already selects `reference_name` as a Dynamic Link labelled "Against".
The ask is for the *source* payment's own references, which is a different join — the source
Payment Entry's `Payment Entry Reference` rows.

**Work:** join those and add two columns after `custom_source_of_funds`. Smallest task on the
list; good one to start with.

Files: `accounts_management/report/customer_fund_usage/customer_fund_usage.py`

---

## Suggested order

1. **T12** — smallest, self-contained, no open questions
2. **T2** — small, no open questions
3. **T3** — verification only
4. **T11** — likely just added columns
5. **T1** — investigation, then a probably-small fix
6. **T5** — needs Q3
7. **T7** — needs Q6, small once answered
8. **T4** — needs Q2
9. **T6a / T6b** — largest; needs Q4, Q5
10. **T8** — needs Q7, and reproduce the bug first
11. **T10** — needs Q9; touches a live workflow
12. **T9** — rename last, alone, with a backup

Rename (T9) goes last deliberately: doing it earlier would churn every other task's diff.
