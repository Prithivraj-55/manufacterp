# Client change requests — meeting 2026-08-12

Working list. **Nothing here is started.** Each task stands alone so we can take them
one at a time.

All 10 open questions were answered on 2026-08-13 (`~/Downloads/claude doubts.docx`);
the decisions are folded in below. Where a mark and a written comment disagreed, the
comment wins — that was the client's instruction.

Status legend: `[ ]` not started · `[~]` in progress · `[x]` done · `[–]` dropped

---

## What the answers changed

| | |
|---|---|
| **T1 dropped** | Not a code problem. Client will purchase with a proper rate and retest. Core costing left alone. |
| **T9 collapsed** | No doctype rename. The existing "Job work order" label is a single **Translation** record — do the same for Operation Entry. 125-reference rename avoided entirely. |
| **T8 shrank** | Two batches of one item *should* be two rows. The real complaint was **ordering** — rows of the same item must sit together. |
| **T7 grew** | `return_type` is removed outright, and unreturned excess must still be consumed at the final Stock Entry so raw-material cost lands correctly. |
| **T6 grew** | New **"Save and Close"** draft step: the popup must persist without validating. |

**T6 and T8 are now one design.** "Save and Close" needs somewhere to persist the
edited Sec Qty and excess details, and T8's Consolidate Item table on the Material
Issue Plan is the natural home. Build T8 first, then T6 reads and writes it — doing
them the other way round means building the popup's persistence twice.

---

## T1 — Stock Entry rate is 0  ·  **[–] DROPPED**

> "Don't change the code, next time i will purchase with proper rate and test it, so
> don't change the core functionality, leave as it is."

Confirmed as source data, not code: nothing in the app sets a rate, so ERPNext values
transfers from the source warehouse and a 0 means the stock went in at 0. No work.

---

## T2 — Hide "To CNC Warehouse" once CNC material has moved  ·  `[ ]`

`material_issue_plan.js:544` shows the button on `if (frm.doc.cnc_warehouse)` alone, so
it never goes away. "CNC to Supplier/WIP" is already conditional via `has_cnc_stock`.

Gate it on "are any CNC-flagged rows still pending transfer to CNC?", reusing
`get_mip_cnc_pending_items`. Self-correcting by design: flag a new row for CNC in
Material Planning, it becomes pending again, the button returns — no stored state.

`material_issue_plan.js`, `material_issue_plan_transfer.py`

---

## T3 — Verify Material Planning reservations can be unfrozen  ·  `[ ]`

`unreserve_batches` and `unreserve_exact_match_batches` both exist, plus a per-row
button. Verification only.

Check the interesting cases: unreserve *after* a partial transfer, and after a Stock
Entry is cancelled (submit clears the reservation flag, so what happens to the part
already shipped?). Report; change code only if it misbehaves.

---

## T4 — Cut Sheet W2 must land in the stock balance  ·  `[ ]`

> "In cut sheet W2 section, Dimensions, Sec qty will be entered, based on that Kg will
> be calculated, while stock entry you can consume the W1 qty, but ensure W2 qty is
> added in the stock balance."

So: W1 is what the Stock Entry consumes; **the batch must be left holding exactly W2**,
with its dimensions, Sec Qty and Kg all agreeing. Today `_apply_cut_sheet_w2` rewrites
dimensions while `_reduce_batch_sec_qty` moves quantity separately, which is why the
balance and the W2 figures disagree.

⚠️ **Confirm before building:** if the batch's opening weight minus W1 does not equal
W2 (saw cut loss, or the remnant measured differently), something must absorb the
difference. My proposal: trust W2 as physical truth and book the shortfall as a
consumption adjustment, so the ledger still balances. Will raise the exact numbers when
we start.

`production_management/stock_entry.py`, `doctype/cut_sheet/cut_sheet.py`

---

## T5 — Nature of Work + Rate Schedule in the BOM template  ·  `[ ]`

> "validate using the Record name, user will add the record name in template. (also add
> the column in download template also) … if the document is not matching means, show
> there, (after correction only able to verify and proceed further)."

- Two columns on the **download template** (`so_drawing_import.py:687`) and its samples
- Validate by **record name exists in the master** — no format rule, so the client's
  numbering can change without breaking imports
- On **Verify Raw Materials**: list every unmatched value and **block** until corrected

Both masters already exist. Rate Schedule is `autoname: field:rs_no`, so its name is the
title being typed — the existence check is a plain link validation.

`drawing_management/so_drawing_import.py`, `doctype/rate_schedule/`, `doctype/nature_of_work/`

---

## T6 — Capture excess in the transfer popup  ·  `[ ]`  *(after T8)*

> "add option as 'Save and Close' … on click save draft and close popup, will click the
> transfer button to continue the work, you can activate the validation while transfer,
> no need validation on save draft."

Three parts:

**T6a — expandable excess row.** One per transfer line, shown where there is a
difference (Sec Qty is adjusted by hand, so a difference is the normal case). Enter
excess dimensions + Sec Qty. The popup is already hand-built HTML, so this fits inside
the existing dialog.

**T6b — Save and Close.** Persists the edited Sec Qty and excess entries **without
validating**, closes the popup, and reopens with the same values. Validation runs only
on Transfer. Needs the T8 table as its store.

**T6c — return warehouse.** New field on the excess table, defaulting to the plan's
**raw-material (source) warehouse**, editable per row (typically to a scrap warehouse).
Note: source warehouse, *not* the excess return warehouse.

Then remove the excess fields from the raw-material row — `excess_return_applicable`,
`excess_calc_qty`, `excess_length/width/sec_qty`, `excess_return_date` — plus everything
feeding them (`_sync_excess_return_from_raw_materials`, the Cut Sheet W2 auto-suggest,
and the client handlers keyed to those fields).

`material_issue_plan.js`, `material_issue_plan.py`, `material_issue_plan_transfer.py`,
`doctype/sco_excess_material_item/`

---

## T7 — Excess lifecycle rework  ·  `[ ]`  *(largest task; after T6)*

> "return type is actually not needed, remove it … billed to consume check box need to
> add in excess material return entry … if not recieved, no transfer will be happen,
> while making the final stock entry the item need to be consumed … then only the raw
> material cost will be calculated properly."

**T7a — remove `return_type`.** 18 references across 7 files including the Excess
Material Return report and its filter. Everything currently branching on
"Retain at Supplier (Virtual)" needs rewriting to work without it.

**T7b — "Billed to Consume" checkbox** on the Return Excess Entry. When set, that excess
is not transferred back.

**T7c — free-type excess mapping.** Excess is chosen in Material Planning and reserved
there; the reservation no longer depends on return type.

**T7d — map the returned batch.** Material normally comes back to the raw-material
warehouse; on receipt the batch created for it must map onto its Material Planning row.
(Some of this exists as `materialize_virtual_excess_claim` — check for reuse.)

**T7e — consume the unreturned remainder.** Where nothing physically comes back, the
final Stock Entry must still consume it so raw-material cost is right: make the return,
create the batch, consume it in the same entry.

⚠️ **Confirm before building T7e:** whether that batch is received into the raw-material
warehouse first (a Material Receipt) and then consumed — two documents — or produced
inside the Manufacture entry itself. Affects the stock ledger, so worth agreeing first.

`doctype/sco_excess_material_item/`, `material_issue_plan_transfer.py`,
`doctype/material_issue_plan/`, `doctype/material_planning/`,
`report/excess_material_return_report/`

---

## T8 — Consolidate Items on the Material Issue Plan  ·  `[ ]`  *(do before T6)*

> "1 item(same name) with 2 batches can be shown in 2 rows, no need to show only item
> wise. ensure item wise sorting is there, there should not be as mixing."

The reported ISM100/ISM150 problem is **sorting, not arithmetic**. Grouping by item +
batch is correct — a transfer has to move a specific batch. What went wrong is that rows
of one item were scattered instead of sitting together, which made two legitimate batch
lines look like a duplicate with the wrong total.

- **T8a** — new Consolidate Item table on the Material Issue Plan, built from the
  reserved material for the selected drawings, one row per item + batch, no duplication.
  This table also becomes T6's draft store.
- **T8b** — sort the transfer popup by item, then batch, so an item's rows are always
  adjacent. Small, independent, and worth doing first — it fixes the actual complaint.

I will still reproduce the ISM100/ISM150 case first and confirm the totals were right.
If any total is genuinely wrong that is a separate bug and I will report it.

`material_issue_plan_transfer.py`, `doctype/material_issue_plan/`,
`doctype/material_planning/material_planning.py` (pattern to mirror)

---

## T9 — "Operation Entry" label  ·  `[ ]`

> "just do the translation, similar to the Subcontracting order is changed to Job work
> order using the translation. update for SOE also from code."

Verified: the existing relabel is **one Translation record** — `Subcontracting Order` →
`Job work order`, language `en`. It was created by hand in the database, so a fresh site
would not have it.

Ship both from code: `Supplier Operation Entry` → `Operation Entry`, and bring the
existing Subcontracting Order one into the app so it survives a reinstall. Either a
patch or the fixtures list — check whether `Translation` is already a fixture.

No rename, no table change, no touched records. Was the riskiest task on the list;
now among the smallest.

---

## T10 — Consumption Log: hard cap at actual qty  ·  `[ ]`

> "log will be one time, inspection can be made many time."

Remove the rework exemption at `subcontracting.py:1165`. The log records what was
produced, once; inspection rounds handle accept/reject on top of it. Actual 4 means the
sum can never exceed 4.

Knock-on: `_soe_consumed_kg` (added 2026-08-12) scales logged Kg by accepted/logged Nos
precisely because re-logging existed. Once re-logging is impossible the scaling is a
no-op — harmless, and worth leaving in as a guard for historical records that already
contain a re-log.

`subcontracting.py`, `production_management/inspection.py`

---

## T11 — Production Report: add the four weights  ·  `[ ]`

Extend the existing report. It already has Sales Order, Production Plan, Drawing,
DU/Mark No and the inspection columns; add customer weight, planned weight, transferred
weight and excess weight, all available on `SOE Drawing Detail` / `SCO Drawing Item`.

`report/production_report/production_report.py`

---

## T12 — Customer Fund Usage: reference type + name  ·  `[ ]`

Add Payment Reference type (Sales Order) and reference name (Order ID) immediately after
Source of Funds. The existing `reference_name` column ("Against") is a different thing —
this needs the *source* payment's own `Payment Entry Reference` rows joined in.

`report/customer_fund_usage/customer_fund_usage.py`

---

## Order to work in

Small and unblocked first, so there is something working early:

1. **T12** — two columns, self-contained
2. **T9** — translation record, now trivial
3. **T8b** — popup sorting; fixes the actual reported complaint
4. **T2** — CNC button visibility
5. **T3** — verification only
6. **T11** — four columns on an existing report
7. **T10** — small, but changes a live workflow: test the inspection rounds after
8. **T5** — template columns + verify-time blocking
9. **T4** — needs the W2-vs-balance rounding decision confirmed
10. **T8a** — Consolidate Item table (T6's foundation)
11. **T6a / T6b / T6c** — popup excess capture, draft save, return warehouse
12. **T7a–T7e** — excess lifecycle rework; largest, and depends on T6

Items 1–7 are all independent — any of them can be picked up in any order.
