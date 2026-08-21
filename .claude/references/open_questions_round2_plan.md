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

## Item F — M3+M4: partial transfer should release only what moved  `[ ]`

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

One to two days. The largest of the audit items, and the one with the most ways to be
subtly wrong, so it gets its own tests before and after.

---

## Item G — T6d: retire the old excess fields  `[ ]`

The excess fields on the Material Issue Plan raw-material row —
`excess_return_applicable`, `excess_calc_qty`, `excess_length/width/sec_qty`,
`excess_return_date` — were replaced by the transfer popup's excess tab (T6a–T6c, live).
They are now a second, stale way to say the same thing. Remove them along with
`_sync_excess_return_from_raw_materials`, the Cut Sheet W2 auto-suggest that writes them
and the client handlers keyed to them.

Half a day. Must land before Item H, which rewrites what feeds this table.
Field deletion — I will confirm again immediately before running it.

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

## Item I — The 11 whitelisted methods with no caller  `[ ]`

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
