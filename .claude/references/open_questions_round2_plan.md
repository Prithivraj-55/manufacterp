# Development plan — Open Questions Round 2

Source: `~/Downloads/claude open questions.docx`, answered 21 August 2026.
Status legend: `[ ]` not started · `[~]` in progress · `[x]` done

Everything below is checked against the code as it stands on `73c6f7f`.

---

## What the answers decided

| Question | Your answer | Work it creates |
|---|---|---|
| Q1 · returned excess | Its own batch, then consumed normally | Unblocks **T7e**. Confirms what `create_mip_excess_return_entry` already does — no rework there |
| Q2 · Exact Match row with no batch | Always an error, leave the check | **None** |
| Q3 · Auto Purchase | Stays a testing aid, disabled by the Settings checkbox | **Item C** — the checkbox only hides the button today; the method is still callable |
| Q4 · audit trail | Log the decisions | **Item D** |
| Q5 · excess-tab Sec Qty | Keep as it is | **None** |
| Q6 · batch after a Cut Sheet | New Settings option: create a new batch, or keep the old one | **Item B** |
| Test data | Skip the MIP-2026-00107 rows (local site), keep the rest | **None** — Item A dropped |
| Queued work | Start everything except the manual scope | **Items E–I** |

---

## Item A — Correct the 5 excess rows on MIP-2026-00107  `[–] DROPPED`

Skipped at your instruction: local site, and new bookings are already correct.

Confirmed rather than assumed — the apportionment fix is live
(`material_issue_plan_transfer.py:305`): a drawing now takes its **proportional share**
of a requirement's weight instead of the whole thing, which is what produced the wrong
ISMB400 12.32 Kg and ISMB450 7.24 Kg figures. The case cannot recur on a new booking.

The five rows stay as they are. Their batches (from **MAT-STE-00184**, submitted 18 Aug)
sit in Stores as free stock — not reserved, not mapped, not consumed by anything.

---

## Item B — "Create New Batch for Cut Sheet Stock Entry" option  `[x]`  *(Q6)*

New checkbox on **Manufyxinvenza Settings**, in the existing Cut Sheet section beside
`cut_sheet_tolerance_percent`.

The worked case, as specified:

> Batch `ISA130-L12000-SR001` — Length 12000, 100 Kg, 1 Nos.
> Cut Sheet: W1 = 6000 mm / 1 Nos · W2 = 6000 mm / 1 Nos.
> W1 is reserved and consumed by the Stock Entry.

**Checkbox off** — the *same* batch ends at Length **6000**, Sec Qty **1**, **50 Kg**.

This is what the code already does: `apply_w2_to_batch`
(`cut_sheet.py:526`) and `_apply_cut_sheet_batch_size` (`stock_entry.py:309`) both write
W2's length, width and sec qty onto the batch **absolutely**, and they run after
`_reduce_batch_sec_qty` inside the same `on_submit_stock_entry`, so the proportional
reduction that would leave 0.5 Nos is overwritten by W2's 1 Nos. Kg follows the ledger.

So the off path is **verification, not a rewrite** — with one test written specifically
around the 0.5-vs-1 Nos case, since that ordering is the whole reason the number comes
out right and nothing currently guards it.

**Checkbox on** — the old batch is never rewritten. Two entries:

1. The normal Stock Entry consumes W1 (50 Kg) from `ISA130-L12000-SR001`, as today.
2. A **Repack** Stock Entry issues that batch's remainder and produces a **new batch**
   of the same item at Length 6000, Sec Qty 1, 50 Kg.

`_setup_batch_from_stock_entry` (`purchase_receipt.py:128`) already names and dimensions
batches created by a Repack from the finished-item row, so the new batch comes out as
e.g. `ISA130-L6000-SR<nnn>` with its dimensions, Sec Qty and Kg all correct. Existing,
tested machinery.

The repack is **created and submitted automatically** when the first entry submits, since
the Cut Sheet has already validated the W2 figures.

Side effect worth having: where the remainder does not equal W2 because of saw-cut loss,
a Repack absorbs the difference by design (in ≠ out is what it is for). That removes the
rounding decision T4 left open — no adjustment entry, no rule to agree.

Also in scope:

- **Reservations follow the material.** Any Material Planning row reserving the old batch
  is re-pointed to the new one when the repack submits, or it holds a batch with no stock.
- **Cancellation and deletion, both modes.** Cancelling the first entry cancels the
  repack; `revert_w2_from_batch` still restores the old batch in off mode, while on mode
  removes the new batch instead, and refuses once anything has claimed it.
- **Valuation** on the new batch is verified on test rather than assumed.

**Done.** Both cut paths carry the mode -- the Cut Sheet doctype and the Material
Issue Plan's own cut rows. `tests/verify_cut_sheet_new_batch.py` walks the client's
worked example end to end in both modes: 30 checks, all passing.

One design consequence worth knowing: in new-batch mode the repack cannot fire on the
FIRST transfer the way the in-place write does. Emptying the batch while other jobs
still have pieces to collect would take the plate out from under them, so it waits
until everything the sheet promised has left the warehouse. For a sheet cut for one
job -- the worked example -- those are the same moment.

If the repack cannot be made for any reason, the attempt is rolled back to a savepoint
and the balance is written in place instead, with a message saying why. The transfer
that triggered it always stands.

`manufyxinvenza_settings.json`, `production_management/stock_entry.py`
(`_repack_remnant_to_new_batch`, `_apply_cut_sheet_w2_as_new_batch`,
`_apply_cut_sheet_balance_as_new_batch`, `_repoint_reservations`,
`_cancel_cut_sheet_repack`), `doctype/cut_sheet/cut_sheet.py` (`revert_w2_from_batch`)

---

## Item C — Close the Auto Purchase door properly  `[x]`  *(Q3)*

The Settings checkbox hides the button in two places (`setup.py:3664`,
`material_planning.js:383`) but `auto_purchase_from_mp` is still a whitelisted method —
anyone with an API key can call it with the checkbox off. Add the same check server-side
so it refuses to run. Half an hour, and it makes "disabled in production" actually true.

**Done.** `auto_purchase_from_mp` now refuses with a `PermissionError` unless the
setting is on, before it reads anything or creates anything. Verified by
`tests/verify_auto_purchase_gated.py` — 7 checks, including that the switch still lets
a genuine call through, and that the setting is put back whatever happens.

`doctype/material_planning/material_planning.py:4285`

---

## Item D — Decision log  `[x]`  *(Q4)*

A single append-only log of the decisions that people later argue about: **who reserved
a batch, who unreserved it, who reassigned it, who rounded a quantity up, and why.**
Not every field on every document — that was the option you turned down, and on a
500-drawing order it would be slow as well as unreadable.

Modelled on the existing `Material Planning Batch Change Log` pattern, but as its own
doctype so it can cover Material Planning, Material Issue Plan and Cut Sheet from one
place, with a report to read it back.

Built **before** Items F and H, so those write into it as they go instead of being
retrofitted afterwards.

**Done.** New `Manufyx Decision Log` doctype, written only by `log_decision()` in
`utils/decision_log.py`, never from a screen. Five decisions are recorded: Reserve,
Unreserve, Reassign Batch, Round Up at Transfer, Cut Sheet Balance -- across Material
Planning (both tables), the Material Issue Plan transfer popup and the Cut Sheet.

Who and when come free from the entry's own owner and creation.

Two properties the tests pin down:

- **One entry per decision, not per row.** Reserving a plan is one press of one button
  covering however many rows, so it is one entry carrying the count and the total
  weight. Reassigning a batch really is per row, so that is one entry each.
- **Logging can never break the thing it is logging.** Every failure is swallowed to
  the error log. A reservation that went through and then failed because its log entry
  could not be written would be worse than having no log.

One thing found by running the existing tests rather than by reasoning: a Dynamic Link
from the log made a Cut Sheet **undeletable** once its balance was recorded -- an audit
trail holding its own subject hostage. Fixed with `ignore_links_on_delete` in hooks,
and the property is now a test of its own.

Readable from the Manufyx Decision Log list, filterable by decision, reference type and
item. Not yet linked from the workspace -- say the word and I will add it.

`doctype/manufyx_decision_log/`, `utils/decision_log.py`, `hooks.py`,
`tests/verify_decision_log.py` (27 checks)

---

## Item E — LM3: match batches to receipt lines properly  `[x]`

`_setup_batch_from_purchase_receipt` picks the receipt line by **counting how many
batches already exist** for that item on that receipt, and using the count as an index.
It works when batches are created in row order and nothing else interferes. It breaks
when a row already has a batch, when rejected quantity creates an extra one, or when the
order differs for any reason — and then a batch silently takes another line's
dimensions. There is already a `frappe.throw` guarding the worst case, which tells you
how fragile the match is.

**Fix:** pre-create the batches ourselves on Purchase Receipt submit, one per line, from
that line's own dimensions, and hand them to ERPNext instead of letting it auto-create.
That gives a real 1:1 line-to-batch link rather than a positional guess.

**Done, and by a smaller change than planned.** Pre-creating the batches ourselves
turned out to be unnecessary: ERPNext writes the Serial and Batch Bundle back onto a
line only *after* that line's batch exists, so the line being dealt with is always the
first line of this item with no bundle yet. That is exact, where counting was a guess,
and it needed no change to how batches are created.

`_row_awaiting_batch` now decides it, for receipts and for Repack / Material Receipt
Stock Entries alike -- the Stock Entry side had the same defect and now shares the rule.

`tests/verify_batch_receipt_line_match.py` -- 11 checks. The case it pins down is the
one the old rule got wrong: line 1 against an existing batch, line 2 needing a new one.
Confirmed it discriminates by putting the old rule back and watching it stamp 3000 mm
onto a 9000 mm bar.

`purchase_receipt_management/purchase_receipt.py` (`_row_awaiting_batch`,
`_setup_batch_from_purchase_receipt`, `_setup_batch_from_stock_entry`)

---

## Item F — M3+M4: partial transfer should release only what moved  `[x]`

`_release_material_planning_reservations` (`stock_entry.py:504`) clears `is_reserved`,
`reserved_qty` and `shortfall_qty` outright for every Material Planning row holding a
consumed batch, however little of it actually moved. Your answer to Q1 in the last
document settles the behaviour: **reduce the reservation by what moved**, and clear it
only when it reaches zero.

- Work out the moved quantity per batch per row rather than per batch.
- Where several rows share one batch, consume the reservations in row order — the same
  sequential rule already used for consolidated receipts, so a shortfall lands on the
  last row instead of being smeared across all of them.
- Mirror it exactly on cancellation, or a cancelled partial transfer will restore more
  than it took.
- `_get_already_transferred_batches` and `get_mip_pending_items` currently infer "this
  has been transferred" from the reservation being gone; both become quantity-aware, so
  a part-transferred row correctly stays in the pending list with its remainder.

**Done.** A row now gives up only what left the warehouse, keeps the remainder, and is
released outright only when the remainder reaches zero. Where several rows share one
batch they give it up one at a time in document order.

Cancelling unwinds in the **opposite** order -- releasing fills from the front, so
unwinding from the back returns the steel to the rows that gave it up. Cancelling the
most recent transfer lands exactly where it started, to the kilo and on the right rows.
Named limitation: cancelling an *older* transfer while a later one still stands is
still right to the kilo, but the total can come back on the wrong row of a shared
batch. Making that exact too would mean recording what every row gave up to every
entry; the aggregate is what free stock is computed from, so the trade is named rather
than paid for.

The pending-transfer list needed no change -- `_get_mp_reserved_batches` already offers
`reserved_qty`, which is now the remainder. Its Sec Qty did: it offered the row's full
piece count against a part-transferred weight, so `_sec_qty_for_reserved` scales it.

`tests/verify_partial_transfer_reservation.py` -- 11 checks, including the round trip
back to the starting 120 Kg. Confirmed it discriminates: on the old code a 30 Kg move
against 120 Kg reserved wiped both rows to (0, 0).

`production_management/stock_entry.py` (`_consumed_qty_by_batch`, `_reservation_rows`,
`_release_rows_by_qty`, `_restore_rows_by_qty`), `subcontracting_management/subcontracting.py`

---

## Item G — Retire Excess Return AND Cut Sheet from the raw-material table  `[x]`

**Scope grew on 21 August.** The original T6d retired only the excess fields. The
client extended it: *both* features come out of Material Issue Plan Raw Material,
because each now lives somewhere better —

- **Excess Return** is its own table on the same document (Excess Material Items),
  which already collects every item with its dimensions.
- **Cut Sheet** is its own doctype, where the nesting is stated once against the batch
  and shared across jobs, instead of being re-typed on every line that draws from it.

What stays is **reference only**: where the chosen batch has a Cut Sheet against it,
the row still shows the To Use (W1) and Balance (W2) dimensions, read-only, taken from
that Cut Sheet. They are what the transfer's Stock Entry carries, so they belong in
front of whoever is making it — but they are no longer typed, calculated or acted on
here.

### G1 — Excess Return comes out

Fields removed from `Material Issue Plan Raw Material`: `section_excess_return`,
`excess_return_applicable`, `excess_calc_qty`, `col_break_excess_return`,
`excess_length`, `excess_width`, `excess_sec_qty`, `excess_return_date`.

Code removed: `_sync_excess_return_from_raw_materials` and its call on every save,
`_RAW_TO_EXCESS_FIELDS`, the three grid handlers and `_recalc_excess_calc_qty` in the
client script.

`excess_qty` and `transfer_excess_kg` **stay** — different fields, still used by the
transfer popup and the weight summary.

### G2 — Cut Sheet functionality comes out

Fields removed: `cut_sheet`, `use_length`, `use_width`, `use_sec_qty`, `use_calc_qty`,
`balance_length`, `balance_width`, `balance_sec_qty`, `balance_calc_qty`,
`precut_length`, `precut_width`, `precut_sec_qty`, and `w2_repack_entry` (added in
Item B for this path, unnecessary once the path goes).

Code removed: `_sync_cut_sheet_calc`, `_warn_cut_sheet_mismatch`, `_cut_sheet_sheet_qty`,
`_cut_sheet_seed`, `_auto_suggest_excess_from_cut_sheet`, and in `stock_entry.py` the
whole Material-Issue-Plan-driven resize — `_resize_cut_sheet_batches`,
`_apply_cut_sheet_batch_size`, `_reapply_cut_sheet_batch_sizes` and
`_apply_cut_sheet_balance_as_new_batch`.

That last group is the real prize. The batch's balance was being written by **two**
independent mechanisms — this one and the Cut Sheet doctype's own
`apply_w2_to_batch` — which is exactly the sort of duplication that made four batches
go stranded. Afterwards there is one.

### G3 — What replaces the two things the removed fields still did

Neither can simply vanish, and both have a source that is better than the one going:

1. **The transfer cap.** A cut-sheet row must offer only its To Use (W1) weight for
   transfer, never the whole batch. Today that cap reads `use_calc_qty` off the raw
   material row (`material_issue_plan_transfer.py:254`). It moves to the Cut Sheet
   itself, reached through the Material Planning row's `cut_sheet_ref`. To be
   confirmed while building: the Material Planning row's `batch_calc_qty` is already
   set to the W1 weight by `_mp_apply_cut_sheet_to_row`, and `reserved_qty` follows
   it, so the cap may already be redundant. If it is, it goes rather than moves.

2. **The Stock Entry's dimensions.** Already sourced from Material Planning, not from
   here — `_get_mp_reserved_batches` reads the mapping row's `batch_length/width`,
   which the same function sets to W1. Nothing to move.

### G4 — The reference fields that stay

A new read-only group on the row, populated from the Cut Sheet when the batch has one:
`cut_sheet_ref` (link), `cs_use_length`, `cs_use_width`, `cs_use_sec_qty`,
`cs_balance_length`, `cs_balance_width`, `cs_balance_sec_qty`. Shown only where
`cut_sheet_ref` is set. Nothing writes back to them and nothing acts on them.

### G5 — Tests

Retired with the features they cover: `verify_mip_excess_auto_suggest`,
`verify_mip_excess_qty_fields`, `verify_mip_cut_sheet`, `verify_cut_sheet_chain`
(which tests the Material-Issue-Plan-driven resize chain specifically, and is the one
already failing on stale data). Touched, not retired: `verify_excess_claim_lifecycle`,
`verify_excess_material_mapping_row_btn`, `verify_mip_return_excess_reason`,
`verify_transfer_draft`.

A new `verify_mip_raw_material_slimmed` replaces them: the fields are gone, the
reference fields are present and read-only, the transfer still caps at W1, and the
Cut Sheet doctype is now the only thing that writes a batch's balance.

### Not in this item

Material Planning's own two tables carry the same `use_*` / `balance_*` fields
(`Material Planning Material Mapping`, `Material Planning Available Raw Material`).
The client's instruction named the Material Issue Plan's table, and those two are
where a row claims pieces from a sheet, so they stay for now. Worth raising
separately: they duplicate the Cut Sheet doctype in the same way this table did.

**Done.** 24 fields off the row, ~19,000 characters of code out of five modules, five
test modules retired and three rewritten against the shapes that remain.

Two deviations from the plan above, both worth naming:

- `verify_mip_return_excess_reason` was listed as "touched, not retired" and was in
  fact retired. Both ends of it are gone -- its setup used the Cut Sheet auto-suggest
  and its final assertion read the raw-material row's `excess_calc_qty` write-back --
  so what was left would have been a new test, not a trimmed one. **Coverage lost: the
  mandatory Return Reason on Return Excess Entry.** Worth rebuilding against the new
  shape; say the word.
- The transfer cap was re-sourced rather than dropped. It could be argued redundant --
  the mapping row's `batch_calc_qty` is already the To Use weight and `reserved_qty`
  follows it -- but that is an invariant to prove, not to assume, so `_cut_sheet_caps`
  now reads the same `use_calc_qty` from Material Planning, where the cut plan is
  actually decided.

`tests/verify_mip_raw_material_slimmed.py` -- 30 checks.

---

## Item H — T7: excess lifecycle rework  `[ ]`  *(largest)*

Now unblocked by Q1.

- **T7a** — remove `return_type` (18 references across 7 files, including the Excess
  Material Return report and its filter). Everything branching on "Retain at Supplier
  (Virtual)" is rewritten to work without it.
- **T7b** — "Billed to Consume" checkbox on the Return Excess Entry: that excess is not
  transferred back.
- **T7c** — excess is chosen and reserved in Material Planning, with the reservation no
  longer depending on return type.
- **T7d** — the returned batch maps onto its Material Planning row on receipt
  (`materialize_virtual_excess_claim` already does much of this — reuse it).
- **T7e** — where nothing physically comes back, the final Stock Entry must still consume
  it so raw-material cost is right. **Per your Q1 answer: Material Receipt into its own
  batch first, then consumed** — two documents, and the off-cut is real stock with its
  own history in between.

Three to four days.

---

## Item I — The whitelisted methods with no caller  `[x]`

Found during the dead-code sweep, left alone because "no caller in this app" is not the
same as "unreachable" — a client script, an integration or an API key can call any of
them. I will re-derive the list, check each one against the client scripts, the workspace,
the fixtures and the API logs, and come back with a per-method recommendation rather
than a bulk delete. Report only; nothing removed without your word.

---

## Also open, from chat rather than the document

## Item J — Cut Sheet: Reserve Without Dimensions, two-way  `[~]`

> "if i enable, then reqd qty (18) needs to set in Calc Qty (Kg), based on this Sec Nos
> is calculated on a read-only field, around 1.9. If unchecked, Sec Qty (NOS) is
> editable, I enter 4, then Calc Qty (Kg) is 19.625 auto-calculated, and the difference
> with 18 is the excess qty. Same for the excess item."

`reserve_without_dimensions` exists in Material Planning already but is not editable in
the Cut Sheet flow, and the calculation only runs one way (Sec Qty → Kg). Make the
checkbox editable there and drive the calculation both ways, with the unused side
read-only, and the same on the excess item. Excess mapping itself you confirmed is fine.

Half a day, and it belongs with Item B — same screen, same formula.

---

## Order of work

| # | Item | Size | Why here |
|---|---|---|---|
| 1 | **C** — Auto Purchase server guard | 30 min | Trivial, closes a real hole |
| 2 | **B + J** — Cut Sheet batch option and two-way calc | 1 day | Same screen, do them together |
| 3 | **E** — LM3 batch matching | ½ day | Independent, removes a live fragility |
| 4 | **D** — decision log | 1 day | Built before F and H so both write into it |
| 5 | **F** — partial transfer reservation | 1–2 days | |
| 6 | **G** — T6d field retirement | ½ day | Clears the way for H |
| 7 | **H** — T7 excess lifecycle | 3–4 days | Largest, depends on G |
| 8 | **I** — whitelisted method review | 2 hours | Report only |

Roughly **eight to ten working days**.

## How each item finishes

1. `bench --site manufact migrate`, then re-export fixtures if any custom field or
   property setter changed — otherwise the next migrate silently reverts it.
2. A verification script under `tests/`, self-contained, no reliance on site data.
3. A manual pass on `manufact` for the screen touched, golden path plus one edge case.
4. Commit with `[autodeploy]`, and I report what changed before starting the next item.

## Not in this plan

- `claude manual scope.docx` — you are answering it separately.
- The Subcontracting Order / Operation Entry rename — still deferred.
- Q2 and Q5 — your answers confirmed the current behaviour; there is nothing to build.
- H7 — closed, verified in the document.
- The test items, benchmark orders and API key — you asked to keep them.
- Item A — dropped; new bookings are already correct.
