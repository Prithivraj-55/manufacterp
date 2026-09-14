# SEP 10 — TASK 1
## Batch reassignment from the Consolidate Items table (Material Issue Plan)

> **Status: Phases 1-6 built and verified. Phase 7 (true atomicity) not started.**
> Every fact here was verified against source twice (exploration + an independent design pass).
> See §8 at the end for what was actually built, what changed from this plan, and why.

---

## 1. What is being built

Material Issue Plan has an **Update Batch** button on its **Raw Materials** grid: pick a row,
see its current batch, type a new one, validate, reassign. One Material Planning child row at
a time.

The same action is wanted on the **Consolidate Items** table. The difficulty: a consolidate
line is not a row — it is a *merge* of N raw-material rows, which point at N child rows across
possibly several Material Planning documents. Reassigning one consolidate line means
reassigning all of them.

**The idea that makes it tractable:** reassign every member to **Reserve Without Dimensions
(RWD)**, where a row reserves exactly its required Kg and the piece count is back-derived as a
fraction. Per-row dimension matching disappears; only total Kg has to reconcile.

**Worked example.** A line needs 1000 kg across 50 rows. Today 35 rows (700 kg) are RWD and 15
carry a batch with typed Sec Nos. After reassignment all 50 sit on the new batch as RWD, each
reserving its own Kg, and the total still reads 1000 kg.

**Long-term intent:** Consolidate Items becomes the only place batches are reassigned and the
row-level Update Batch retires. It stays for now — do not remove it in this task.

---

## 2. Decisions already taken (do not re-litigate)

| Question | Decision |
|---|---|
| Split across batches | Per batch the user enters **batch + dimensions + piece count** → yields a Kg capacity. Rows fill batch 1 in table order until capacity is used, then batch 2. **A row is never split across two batches.** |
| Exact-match (ARM) rows | **Add** a `reserve_without_dimensions` Check field to `Material Planning Available Raw Material`. Auto-enabled when the batch is assigned from the MIP; manually settable during Material Planning. Rows stay in their own table — do **not** move them into Material Mapping. |
| Nuts and Bolts | Plain batch swap, **no RWD** (Kg↔pieces is exact for countable items). |
| Partially transferred line | **Refuse the whole line.** |
| Several Material Plannings | Allowed. The confirmation must name every plan and its row count **before** writing. |
| Cut Sheet | **Ignore** — the client is dropping that feature. (But see Stage 0.3: cut-sheet *rows* must still be refused, for a different reason.) |
| Row-level Update Batch | Keep. |

---

## 3. Verified findings

### 3.1 Excess at transfer already works. No new code needed.
- Once members are RWD, Sec Nos is **fractional by design**.
- Whole pieces are settled by hand in the transfer popup.
- `_validate_selected_against_stock` (`material_issue_plan_transfer.py:87-173`) stamps
  `round_up_excess_kg` **server-side**, overwriting whatever the browser sent — so it is
  trustworthy.
- `_log_round_up_excess` (`:860-975`) turns that into a `SCO Excess Material Item` row on
  `mip.excess_return_items`.

Mapped excess becomes zero after the reassign (every row now reserves exactly its
requirement) and re-emerges as **round-up excess at transfer**. That is the designed path.

### 3.2 There is no bulk reassign anywhere.
`reassign_batch` — `production_management/doctype/material_planning/material_planning.py:3973`
— is strictly single-row, three live callers, nothing loops it.

```python
reassign_batch(material_planning_name, source_table, row_name, new_batch_no,
               dimensions=None, sec_qty=None, reserve_without_dimensions=0,
               material_issue_plan=None)
```

### 3.3 FOUR functions commit internally — savepoints are impossible.
| Function | Line |
|---|---|
| `unreserve_batches` | `:3844` |
| `unreserve_exact_match_batches` | `:3722` |
| `reserve_batches` | `:2999` |
| `reserve_exact_match_batches` | `:3663` |

MariaDB destroys every SAVEPOINT on COMMIT, so a savepoint taken before the first unreserve
no longer exists by the time you would roll back to it. **Do not attempt `frappe.db.savepoint`.**
Either accept partial application and make it recoverable (§4.3), or suppress the commits
(Phase 7).

Useful corollary: **`unreserve_batches` does not require rows to be reserved.** Its loop
(`:3814-3831`) matches on name only. It throws "No matching reserved rows found." (`:3840`)
only when *no* passed name exists in that table. So a mixed reserved/unreserved list is safe —
but never pass Material Mapping names to the ARM function or vice versa.

### 3.4 A consolidate row has no back-link.
No `material_planning`, `source_table`, `source_row`. Members must be re-derived from
`mip.raw_materials` using the same key `_sync_consolidate_items` groups on
(`material_issue_plan.py:600-601`):

```python
key = (row.planned_item or row.item_code, row.batch_no, 1 if row.cnc_process else 0)
```
Rows with no `batch_no` are skipped entirely (`:598`).

### 3.5 Consolidate Items is read-only and rebuilt on every validate.
`read_only: 1`, regenerated wholesale in `_sync_consolidate_items` (`:551-642`). **Nothing may
be written to it** — the reassign writes through to Material Planning and lets the sync
regenerate. Only `draft_*` fields survive (`_CONSOLIDATE_DRAFT_FIELDS`, `:534-548`).

### 3.6 ⚠️ Consolidate-row dimensions are the REQUIREMENT's, not the batch's.
`refresh_mip_raw_materials` writes `"length": row.length` (`material_issue_plan.py:296-298`) —
the Material Mapping row's *requirement* dims, never `batch_length/batch_width/batch_thickness`.
Only `qty`/`sec_qty` come from the batch side (`:271-272`).

**So a consolidate line's L/W/T are what the drawing asks for; its Kg is what the batch gives.**
Do **not** label them "the current batch's size" in the dialog. Another reason the RWD/Kg
approach is right: the group's dimensions are not meaningful, its total Kg is. (A group can
also legitimately span rows of different cut sizes — `_sync_consolidate_items` takes L/W/T
from the *first* member row.)

### 3.7 RWD today exists ONLY on Material Mapping.
- Field: `Material Planning Material Mapping.reserve_without_dimensions` (Check).
- `_apply_rwd_fractional_nos` (`:626-653`) runs on **every** validate. Guards: not reserved,
  has batch, `batch_parent_item_group in ("Structurals", "Plates")`, flag on. Sets
  `batch_calc_qty = row.qty` and `batch_sec_qty = _sec_nos_for_weight(row, row.qty)` —
  deliberately fractional.
- `_validate_batch_calc_qty` (`:683`) RWD branch (`:750-773`) compares `row.qty` against free
  stock and `continue`s past the normal checks.
- `reserve_batches` (`:2935-2952`) RWD branch reserves `row.qty`.

### 3.8 ⚠️ Three things about ARM that change the design
1. **ARM has no `unit_weight` field at all.** `refresh_mip_raw_materials:258-266` looks it up
   from `Item.custom_unit_weight` in a bulk query. So `_sec_nos_for_weight` — which reads five
   `batch_*` fields — **cannot be pointed at an ARM row**. It needs an adapter (§4.4).
2. **ARM `required_qty` is "Allocated Qty in Batch", not the requirement.**
   `overall_required_qty` is the requirement; `required_qty` is *this batch's share*
   (`check_stock_availability:1512-1513` splits one requirement across several ARM rows).
3. **ARM reservation is already dimensionless.** `reserve_exact_match_batches:3579` does
   `required_qty = flt(row.required_qty)` and reserves `min(required_qty, available)` — no
   `batch_calc_qty`, no `_calc_batch_qty`, no dimension arithmetic anywhere.

**Therefore the ARM equivalent of `batch_calc_qty = row.qty` is: _nothing_.** `required_qty`
already *is* the Kg reserved, and it must **never** be overwritten by an RWD routine or you
change the plan. The ARM flag's only job is to record that the batch no longer matches the
requirement's dimensions, and to make `sec_qty` a derived fractional count.

### 3.9 Kg ↔ Nos formulas (`material_planning.py:2713-2723`)
```python
Structurals:      kg_per_piece = (length / 1000) * unit_weight
Plates:           kg_per_piece = (length / 1000) * (width / 1000) * thickness * unit_weight
Nuts and Bolts:   kg_per_piece = unit_weight
```
`_sec_nos_for_weight(row, kg)` (`:2834-2854`) = `kg / kg_per_piece`, 3 dp, **no rounding**.
Do **not** confuse with `_nos_from_weight` (`:1107-1123`) which rounds to whole pieces — that
one is for purchasing.

### 3.10 What production actually looks like (restored live DB, 10 Sep)
| | count |
|---|---|
| Batched rows in Material Mapping | 54 |
| Batched rows in Available Raw Material | 8 |
| Mapping rows with a batch already RWD | 86 of 102 |
| Batched Nuts and Bolts rows | 0 |

---

## 4. Design

### 4.1 Where the code lives

New module: **`manufyxinvenzaerp/subcontracting_management/material_issue_plan_batch_update.py`**

A sibling of `material_issue_plan_transfer.py`, which is exactly this pattern: a large MIP
action extracted into its own module. `material_planning.py` is already 4,918 lines — do not
grow it.

**Do NOT refactor `reassign_batch`.** Its whole shape is *one row, one save, one document-wide
re-reserve*. The bulk path inverts all three. A shared core parameterised on every axis would
end up *being* the bulk function with a `len(rows) == 1` special case — rewriting the working
single-row path that decision 7 says must keep running.

**Reuse as-is:** `_get_batch_dims:3868` · `_calc_batch_qty:3876` · `_calc_kg_per_nos:2713` ·
`_sec_nos_for_weight:2834` · `_precheck_batch_reassignment:3891` ·
`_apply_batch_to_mapping_row:4191` · `_mark_excess_item_mapped:3933` ·
`_batch_change_remarks:3963` · `get_batch_item:2385` · `_get_batch_total_stock:2446` ·
`_get_batch_reserved_by_others:2461` · `_get_batch_inspection_block_reason:2405` ·
`_require_write:2873`

**Two surgical exceptions in `material_planning.py`:**
1. Extract `_apply_batch_to_arm_row(...)` from `reassign_batch:4128-4143` (currently inline),
   placed next to `_apply_batch_to_mapping_row:4191`. **This is where the new ARM
   `reserve_without_dimensions` write belongs**, so both the single-row and bulk paths get it
   from one place.
2. Add the `_sec_nos_for_weight` ARM adapter (§4.4).

Also refactor `_sync_consolidate_items:600-601` to call the shared `consolidate_group_key`, so
the grouping rule has one home. (Note `_clear_transfer_draft:522-524` spells out a *near*-identical
key using `item_code` instead of `planned_item or item_code` — a latent inconsistency for
alternate-item rows. Leave it; don't propagate it.)

### 4.2 Signatures

```python
def consolidate_group_key(row):
    """(item, batch, cnc-leg) -- the ONE definition of a consolidate line."""
    return (row.planned_item or row.item_code, row.batch_no or "", 1 if row.cnc_process else 0)

def expand_consolidate_row(mip, consolidate_row_name):
    """-> (key, [member...]) carrying material_planning, source_table, source_row,
    item_code, planned_item, batch_no, qty, sec_qty, reqd_kg, transferred_qty,
    is_reserved, parent_item_group, unit_weight, duno_mark_no, idx.
    Re-derived from the LIVE document -- never from client input."""

@frappe.whitelist()
def get_batch_capacity(batch_no, warehouse, pieces=0, length=None, width=None, thickness=None):
    """Live feed for one target row: batch dims, item group, unit weight,
    kg_per_piece, capacity_kg, free_kg, inspection block reason. Read-only."""

@frappe.whitelist()
def preview_consolidate_batch_update(mip_name, consolidate_row_name, targets_json):
    """Stage 0 in full. Mutates nothing. ->
       {ok, plan_hash, blockers[], warnings[], group{...},
        material_plannings[{name, rows, qty, for_warehouse}],     # decision 5
        targets[{batch_no, capacity_kg, free_kg, effective_capacity_kg,
                 assigned_kg, leftover_kg, rows}],
        assignments[{source_table, source_row, material_planning, qty,
                     target_index, batch_no, sec_qty, rwd}],
        unassigned[], shortfall_kg}"""

@frappe.whitelist()
def apply_consolidate_batch_update(mip_name, consolidate_row_name, targets_json, plan_hash):
    """Stage 1 + 2. Re-runs preview internally, refuses on plan_hash mismatch.
       -> {applied[], stopped_at|None, untouched[], warnings[], partial_reservations[]}"""
```

### 4.3 Transaction design — the crux

**Atomicity is per Material Planning. Safety comes from validating everything before mutating
anything.**

**Stage 0 — pure read, zero writes.**

| # | Check | Why |
|---|---|---|
| 0.1 | Expand to members, re-derived by the grouping key | Never trust a client row list; re-derivation makes re-run safe |
| 0.2 | Refuse if the line or any member has `transferred_qty > 0` | Decision 4 |
| 0.3 | **Refuse members with `is_virtual_excess` or `cut_sheet_ref`** | `unreserve_batches:3820-3829` blanks those rows and calls `_release_row_pool_claims:93` — a side effect on a **different document** that a re-run cannot undo |
| 0.4 | `_require_write(mp)` on every involved MP | Fail on permissions before touching MP #1 |
| 0.5 | Refuse if involved MPs don't share one `for_warehouse` | All reservation arithmetic is per-warehouse |
| 0.6 | Refuse if any target batch == the group's current batch | No-op / confuses the fill |
| 0.7 | Refuse if a target batch already sits in the **other** child table of any involved MP | Pre-empts `_validate_no_cross_table_batch_duplicate:565` |
| 0.8 | Run the fill (§4.5). Refuse if `shortfall_kg > 0` | Partial application splits the line — the exact state this feature avoids |
| 0.9 | Per target: `assigned_kg <= _get_batch_total_stock(b, wh) - _get_batch_reserved_by_others(b, "", None)` | **Do NOT use `get_batch_stock_summary`** — it excludes *all* of the named MP's reservations, overstating free stock in a multi-MP fan-out. `exclude_mp=""` makes `parent != ''` match everything, which is what you want |
| 0.9b | **Treat `free_kg <= EPS` as a hard blocker** | `_validate_batch_calc_qty:746-748` has `if not batch_stock: continue` — a zero-stock batch **skips the coverage check entirely**, saves cleanly, then reserves 0 Kg with a full shortfall |
| 0.10 | `_get_batch_inspection_block_reason` per target → **warning**, not blocker | Matches `_precheck_batch_reassignment:3903` |
| 0.11 | Warn if the consolidate row has `draft_saved_on` set | Draft fields are keyed on `batch_no`; changing the batch silently discards a parked transfer draft |
| 0.12 | Emit the MP roster: name, row count, Kg, warehouse | **Decision 5** — the confirmation payload |

**Stage 1 — mutate, one MP at a time, `sorted(mp_names)`.** Per MP:

1. `unreserve_batches(mp, json.dumps(mm_member_names))` — one call, whole list, skip if empty. **[commit]**
2. `unreserve_exact_match_batches(mp, json.dumps(arm_member_names))` — same. **[commit]**
3. Re-fetch `mp`.
4. Per member: `_apply_batch_to_mapping_row(...)` or `_apply_batch_to_arm_row(...)`; append one
   `batch_change_log` row each (mirror `:4030-4044`).
5. **One** `mp.save(ignore_permissions=True)`. **[no commit]** This is where
   `_apply_rwd_fractional_nos` sets `batch_calc_qty = row.qty` and the fractional Sec Nos,
   *before* `_validate_batch_calc_qty` runs (validate order: `:147` then `:151`).
6. `_mark_excess_item_mapped` per new batch.
7. `reserve_batches(mp.name)` guarded by `if any(not r.is_reserved and r.batch ...)`, wrapped in
   the **verbatim** `except frappe.ValidationError` + `"blocked pending inspection completion"
   not in str(e)` re-raise from `:4172-4180`. Same for `reserve_exact_match_batches`. **[commit]**
8. **Read the reserve return value's `partial` list.** `reserve_batches:2946-2963` does **not
   throw** on shortfall — it reserves `min(to_reserve, available)` and records `shortfall_qty`.
   Without surfacing this, a short fan-out looks like success.
9. **One** `log_decision("Reassign Batch", rows_affected=n, ...)` per MP.

**Stage 2 —** `refresh_mip_raw_materials(mip_name)` once (the unblocked one, not
`..._manual:189` — matching `material_issue_plan.js:2295`).

**If MP #2 of 3 fails:**
- **MP #1** — fully done, **committed**.
- **MP #2** — members are **unreserved but still carry the OLD batch**. Recoverable, non-lossy.
- **MP #3** — untouched, still reserved.

This is why per-MP-sequential beats "unreserve everything first": blast radius is at most one
MP's reservations. Catch per-MP and re-throw a **composed** message:

> **Batch update stopped part-way.**
> **Applied** — MP-2026-00041: 7 rows → batch B-9 (1,842.5 Kg), reserved.
> **Stopped at** — MP-2026-00042: *free stock 120.0 Kg, needs 240.0 Kg.* Its 5 rows are
> **released from reservation but still carry batch B-3**. Reserve them again, or re-run.
> **Not touched** — MP-2026-00043 (3 rows).

**Re-running is the recovery path and works by construction:** Stage 0 re-derives members from
current state, so MP #1's rows (now on the new batch) have a different grouping key and are no
longer members. Add a `plan_hash` — `apply_*` re-runs `preview_*` internally and refuses on
mismatch, so a stale plan is never applied.

### 4.4 Extending RWD to ARM — every place that changes

| # | Where | Change |
|---|---|---|
| 1 | `material_planning_available_raw_material.json` | Add `reserve_without_dimensions` Check, default 0, `read_only: 0`, after `batch_no`, in both `fields` and `field_order`. Mirror MM's `read_only_depends_on: "eval:doc.reserve_without_dimensions"` on `sec_qty`. **No `field_order` property setter exists on this doctype**, so nothing else to update (unlike Material Mapping, which has one that silently hides unlisted fields) |
| 2 | `_apply_rwd_fractional_nos:626` | Remove the `if not self.material_mapping: return` early exit (`:645`) or an ARM-only plan skips everything. Add a second loop over `available_raw_materials`, guarded on not-reserved / has `batch_no` / flag on / `parent_item_group in ("Structurals","Plates")`. Body: `row.sec_qty = _sec_nos_for_weight_arm(row, row.required_qty)`. **Do NOT touch `required_qty`** |
| 3 | new adapter | `_sec_nos_for_weight_arm(row, kg, unit_weight=None)` builds a shim `frappe._dict(batch_parent_item_group=row.parent_item_group, batch_length=row.length, …, batch_unit_weight=unit_weight or Item.custom_unit_weight)` and delegates, keeping the formula in one place. Bulk-cache the Item lookup — copy `refresh_mip_raw_materials:258-266` |
| 4 | `_validate_batch_calc_qty:683` | **NO CHANGE.** ARM has never had stock-coverage validation; adding one changes behaviour for every existing ARM row. **Consequence: MM gets its total-Kg check free from `:750-773`, ARM does not — Stage 0.9 is the only protection. Do not skip it** |
| 5 | `reserve_exact_match_batches:3549` | **No change** — already reserves exactly `required_qty` regardless of dimensions |
| 6 | `check_mapping_batch_availability:3747` | **No change** — walks `material_mapping` only and is called from JS elsewhere. Compute ARM shortfalls in the new pre-check and merge into the same warning dict shape |
| 7 | `_sync_cut_sheet_calc:422-462` | **Looks like a landmine, isn't.** Already loops both tables and already reads `row.get("reserve_without_dimensions")` (`:440`), today `None` on ARM. Once the field exists a flagged ARM row enters the `if` — but the same condition needs `flt(row.get("batch_calc_qty"))`, permanently 0 on ARM, so the `else` still wins. **Verify when implementing** |
| 8 | `_move_skipped_arm_to_mapping:654-682` | **Must change.** Add `"reserve_without_dimensions": row.get("reserve_without_dimensions") or 0`. Without it a flagged ARM row skipped into MM arrives with no waiver and the next save throws |
| 9 | `reassign_batch` ARM branch `:4128-4143` | **Must change.** Never sets the flag today. Adding it here is the "auto-enable when assigned from the MIP" hook — **and it makes the existing per-row dialog correct too, which is why Phase 2 ships standalone** |
| 10 | `check_stock_availability:1293` | **Note, don't fix.** Rebuilds ARM wholesale, destroying hand-made assignments including the new flag. MM has a partial defence (`reserved_by_key`); ARM has none. Pre-existing |
| 11 | `_collect_batch_mapping_issues:4874-4886` | Optionally mirror the RWD Nos-vs-`Batch.custom_sec_qty` check for ARM. Low priority, report-only |
| 12 | `subcontracting.py:_get_mp_reserved_batches:1907-1945` | **No change, but this is WHY ARM must write dimensions.** It builds the Stock Entry line from `r.length/width/thickness`. Unlike MM (requirement dims on `length/*`, batch dims on `batch_*`), ARM has only one set and it goes straight onto the Stock Entry. If the bulk reassign doesn't overwrite ARM's L/W/T with the new batch's, **the transfer ships the new batch tagged with the old size** |
| 13 | `material_planning.js` | Add the flag to the ARM grid columns; optionally an `frappe.ui.form.on("Material Planning Available Raw Material", {...})` handler mirroring the MM one at `:2328-2340` |

**What breaks when the flag is off:** nothing, provided (a) the new ARM loop is guarded on the
flag — **critical**, since ARM `sec_qty` is a proportional allocation from `_alloc_sec_qty:1633`
and overwriting it unconditionally corrupts Nos accounting downstream; (b) removing the early
return doesn't change the MM loop (it doesn't); (c) `_sync_cut_sheet_calc` stays neutralised by
`batch_calc_qty == 0`.

### 4.5 The fill algorithm (split mode)

**Members** ordered exactly as `mip.raw_materials` builds them
(`refresh_mip_raw_materials:271-345`): per MP in `sorted(mp_names)`, all `material_mapping` in
idx order, then all `available_raw_materials` in idx order. Deterministic and identical to what
the preview shows.

**Capacity per target:**
```python
item, group, uw = get_batch_item(b), Item.custom_parent_item_group, Item.custom_unit_weight
kg_per_piece = _calc_kg_per_nos(group, L, W, T, uw)          # :2713
capacity_kg  = _calc_batch_qty(group, L, W, T, pieces, uw)   # :3876
free_kg      = _get_batch_total_stock(b, wh) - _get_batch_reserved_by_others(b, "", None)
effective_kg = min(capacity_kg, free_kg)
```
Show `capacity_kg` and `free_kg` **separately** and warn when `free_kg < capacity_kg` — that
means the declared piece count is not physically in the warehouse.

**Fill — strict sequential first-fit, no row ever split:**
```python
EPS = 0.001
t, remaining = 0, effective_kg[0]
for m in members:
    while t < len(targets) and m.qty > remaining + EPS:
        leftover[t] = remaining          # this target is now closed
        t += 1
        remaining = effective_kg[t] if t < len(targets) else 0.0
    if t >= len(targets):
        unassigned.append(m); continue
    m.target = t
    remaining = flt(remaining - m.qty, 3)
leftover[t] = remaining
```

Once the cursor passes target *i* it never returns — the only variant an operator can predict
by reading the table top to bottom. One oversized row early can strand batch 1's capacity;
that is **shown, not hidden** (every target reports `assigned_kg`, `leftover_kg`, `rows`, and a
target that got zero rows is flagged). **Do not add best-fit or back-filling** — it produces an
assignment nobody can predict from the grid.

**Short capacity → refuse, never partially apply.** `ok: false`, `shortfall_kg`, unassigned
list, confirm disabled.

**Per-member Sec Nos by group:**
- **Structurals / Plates** — send `reserve_without_dimensions = 1` and `sec_qty = None`.
  `_apply_rwd_fractional_nos` derives it server-side on save. Don't compute client-side.
- **Nuts and Bolts** — RWD off. But `_apply_batch_to_mapping_row:4229` computes
  `batch_calc_qty = sec_qty * unit_weight`, and that becomes the MIP row's `qty`. So you
  **must** compute an explicit `sec_qty = row.qty / batch_unit_weight` per member and warn if
  it isn't whole. Omitting it silently changes the line's total.

All comparisons at `flt(x, 3)`, `EPS = 0.001`.

### 4.6 The dialog

`material_issue_plan.js`. `_add_consolidate_update_batch_button(frm)` mirrors
`_add_update_batch_button:401`, on the `consolidate_items` grid, position **`"top"` —
mandatory**, because that grid is `read_only: 1` and Frappe hides `.grid-footer` entirely for a
read-only grid whose rows fit one page (see the comment at `:403-406`). Use a **toolbar button
plus an in-dialog line picker**, not a per-row Button field — a Button inside a read-only grid
is exactly that trap.

**Reuse:** `_toggle_allocation_fields:2328` · `_fetch_batch_dims:2355` · `_toggle_rwd:2424`
(wording verbatim) · `_mip_batch_cell_html:2043` · the refresh/re-select flow `:2286-2318` —
but the re-find key becomes `(item_code, batch_no, cnc_process)`.

**Reuse the wording of `_kg_per_piece:2376`, not its arithmetic.** It computes from
`selected_row.unit_weight` / `parent_item_group` — the *requirement's* item, not the new
batch's. On a cross-item batch that preview figure is wrong today (harmless, because the server
recomputes). **Don't inherit the bug** — get `kg_per_piece` from `get_batch_capacity`,
server-side, off the batch's own item.

**Needs new:** `_mip_build_picker:2064` hardcodes filters (`cdn`/`duno`/`so`) and 8 columns a
consolidate row lacks. Give it a config object or write a sibling keyed on Item + Batch. Its
DOM ids (`#_mip_ub_*`) are global — scope them if both dialogs can be open.

**Button colour:** amber (`window.mfx_paint_grid(frm, "consolidate_items", { alt: ["Update Batch"] })`)
— it overwrites a decision already made. See `public/js/mfx_buttons.js`.

---

## 5. Build phases

**Phase 1 — Read-only expansion and preview.** `consolidate_group_key`,
`expand_consolidate_row`, `get_batch_capacity`, `preview_consolidate_batch_update` (Stage 0
checks 0.1–0.7, 0.9–0.12), refactor `_sync_consolidate_items:600` to the shared key. Dialog
previews only. No schema, no mutation.
*Testable:* open a line, see its N members with MP names; blockers fire on transferred /
virtual-excess / cross-table-conflicting lines.

**Phase 2 — ARM `reserve_without_dimensions`.** All of §4.4. **Independently valuable with no
bulk feature in sight** — it makes today's per-row Update Batch correct for exact-match rows.
Ship and let it soak before Phase 3 depends on it.

**Phase 3 — Single-target bulk apply.** `apply_consolidate_batch_update` with exactly one
target (no fill, no split): Stage 1 per-MP loop, composed error, `plan_hash` guard, Stage 2
refresh. Structurals/Plates only.
*Testable:* a line spanning 2 MPs moved to one new batch, both re-reserved. Then force a
failure on MP #2 (reserve the target elsewhere first) and check the composed message and the
recoverable state.

**Phase 4 — The fill algorithm.** Multiple targets, capacity/leftover/shortfall, `targets_json`
through preview and apply.
*Testable:* 10 rows, 2 targets — the cut point lands where table order says, leftovers reported.

**Phase 5 — Dialog polish.** MP roster confirmation (decision 5), per-member assignment table,
leftover/shortfall display, warning rendering (inspection blocks, partial reservations, dropped
draft).

**Phase 6 — Nuts and Bolts.** Exact `sec_qty = qty / unit_weight`, whole-number warning, RWD
forced off.

**Phase 7 — Optional true atomicity.** Extract `_unreserve_batches_core`,
`_unreserve_exact_match_core`, `_reserve_batches_core`, `_reserve_exact_match_core` each taking
`commit=True`; the four whitelisted functions call them with `commit=True`, the bulk path with
`commit=False`. The whole fan-out then runs in one request transaction and any `frappe.throw`
rolls everything back. **Do not just add `commit=` to the whitelisted signatures** — whitelisted
methods take arbitrary client kwargs, so a caller could disable the commit on the single-row
path. Cost: longer row locks; acceptable for a hand-driven action over tens of rows.

---

## 6. Risks — the validations most likely to fire

| # | Validation | Where | Mitigation |
|---|---|---|---|
| 1 | `_validate_no_cross_table_batch_duplicate` | `:565-587` | Cannot be *created* by the fan-out (all members of a group share one batch, already forbidden in both tables of one MP). Can fire if the **target** batch sits in the other table → Stage 0.7 |
| 2 | "Enter Sec Qty (NOS) for batch…" | `:785-786` | RWD `continue`s at `:773` before it. **The trap is forgetting the flag:** with `rwd=0` and `sec_qty=None`, `_apply_batch_to_mapping_row:4211` leaves the **old** `batch_sec_qty`, dodging the throw but computing `batch_calc_qty` from old Nos against new dims — silent nonsense. **Assert server-side** that `rwd == 1` for Structurals/Plates and an explicit `sec_qty` exists for Nuts and Bolts. Never trust the dialog |
| 3 | `_validate_batch_calc_qty` shortfall | `:756-771` RWD, `:840-850` normal | **This is the mechanism enforcing "total Kg reconciles" — lean on it, don't fight it.** Stage 0.9 makes it unreachable normally; it stays the concurrency backstop |
| 3b | **The zero-stock escape** | `:746-748` `if not batch_stock: continue` | A zero-stock target skips coverage entirely, saves clean, reserves 0. → Stage 0.9b hard blocker |
| 4 | "Stock is already reserved… Unreserve to update" | `:689-719` | Avoided by unreserving (1.1/1.2) *before* applying (1.4). **This is why the unreserve cannot be deferred** |
| 5 | `reserve_batches` "Calculated Qty is less than Required Qty" | `:2948-2952` | Non-RWD branch. Same fix as #2. `material_planning.py:2188-2200` records this exact failure chain from a previously dropped flag — a known, reproduced bug shape |
| 6 | "All rows already reserved" / "No items to reserve" | `:2902`, `:2994`, `:3558`, `:3658` | Guard both calls exactly as `reassign_batch:4171` / `:4181` do |
| 7 | `unreserve_*` "No matching reserved rows found." | `:3718`, `:3840` | Never call with an empty list; never cross MM/ARM names. Mixed reserved/unreserved is fine (§3.3) |
| 8 | `unreserve_batches` virtual-excess / cut-sheet branch | `:3820-3829` | Blanks the row and releases pool claims on **another document** — irreversible by re-run → Stage 0.3 refuses those members |
| 9 | `_get_batch_inspection_block_reason` | `:2405`, `:2921`, `:3585` | Copy `reassign_batch:4172-4188`'s substring re-raise **verbatim**; surface as a Stage 0.10 warning too |
| 10 | Unrelated pre-existing MP validations (`_validate_unique_dunos:165`, `_warn_undersized_purchase_dimensions:224`) | every `mp.save()` | Your save may be the first re-validation in months. Word the composed error as "MP-x has a pre-existing problem unrelated to the batch change" so nobody chases the wrong thing |
| 11 | **Silent partial reservation** | `reserve_batches:2946-2963` | Does **not** throw on shortfall. Stage 1.8 reads the `partial` list. Without it a short fan-out looks like success |
| 12 | Dropped transfer draft | `:534-548`, `:640-641` | Keyed on `batch_no`; changing the batch discards a parked "Save and Close" → Stage 0.11 |

### Pre-existing defects nearby (not this task's job)
- `_RAW_MATERIAL_EDITABLE_FIELDS` — the docstring at `material_issue_plan.py:225` promises a
  carry-forward that no longer exists. `old_rows_by_key` (`:248-252`) and three `new_row =`
  assignments are dead leftovers.
- `reassign_batch` cross-item ARM path reads `new_row.name` **before** `mp.save()` (`:4111`) →
  `target_row_name` is `None`, so `_mark_excess_item_mapped` and `log_decision` lose the pointer.
- `_log_round_up_excess` reads `item.get("excess_entry")` (`:924`) which no caller populates —
  unreachable branch.

---

## 7. Verification

### Real test data (verified 10 Sep, restored live DB)

| Case | Data |
|---|---|
| **Happy path** — multi-row, untransferred | `MIP-2026-00005` / `PLATE8` / 7 rows / 1965.876 kg / 0 issued |
| Second untransferred line | `MIP-2026-00005` / `PLATE25` / 3 rows / 217.344 kg |
| **Must refuse** — fully transferred | `MIP-2026-00006` / `PLATE8` / 14 rows / fully issued |
| Round-up excess already present | `MIP-2026-00004` / `ISA100` / issued 36.096 vs reqd 30.694 |

`MIP-2026-00005`'s members are all one plan (`MP-2026-00017`), all Material Mapping, all
reserved, none transferred, all already RWD — exactly the Phase 3 shape.

### New test: `tests/verify_consolidate_batch_reassign.py`
House `check()` / `run()` pattern, rolls back. Assert:
- expansion returns exactly the rows `_sync_consolidate_items` merged
- total Kg preserved across the reassign
- every MM member ends RWD with `batch_calc_qty == qty` and fractional Sec Nos
- **ARM members keep `required_qty` untouched** and get a derived fractional `sec_qty`
- a transferred line is refused
- a short/zero-stock target is refused **before** any write (assert the old batch survives)
- the split fill lands rows on the right target and reports leftover capacity
- the confirmation payload names every plan and its row count
- **a forced mid-run failure leaves MP #2 unreserved-but-on-old-batch, and a re-run recovers**

### Re-run after each phase
`verify_transfer_draft` · `verify_mip_consolidate_items` · `verify_mip_consolidated_allocation`
· `verify_reassign_batch_exact_match` · `verify_rwd_two_way` · `verify_unreserve_after_transfer`
· `verify_material_planning_health` · `bench --site manufact run-tests --app manufyxinvenzaerp`

Known pre-existing failures — **not regressions**: `verify_production_report`,
`verify_reservation_release_on_transfer`, `verify_weight_cascade_reaches_soe`.

### End-to-end after Phase 3
Reassign `MIP-2026-00005` / `PLATE8` to another PLATE8 batch, then **Select Materials to
Transfer**, round Sec Nos up to whole pieces, confirm the surplus lands in **Excess Material
Items**. That closes the loop from reassignment through to excess capture.

### Bench reminders (this bench does NOT hot-reload)
```
bench start                          # restart for any Python change
bench build --app manufyxinvenzaerp  # for public/js/
bench --site manufact clear-cache    # for doctype JS (build alone is not enough)
bench --site manufact migrate        # for the new ARM field in Phase 2
```


---

## 8. Build record — what was actually done

**Phases 1-6 are built, tested and verified against live restored production data.
Phase 7 is not started and is not needed for the feature to work.**

| Phase | State | Notes |
|---|---|---|
| 1 — read-only preview | **done** | `verify_consolidate_batch_reassign.py`, 28 checks |
| 2 — ARM `reserve_without_dimensions` | **done** | `verify_arm_reserve_without_dimensions.py`, 31 checks |
| 3 — bulk apply | **done** | merged with Phase 4, see below |
| 4 — the fill | **done** | `verify_consolidate_batch_apply.py`, 18 checks |
| 5 — dialog polish | **done** | two-step dialog, MP roster confirmation, per-row assignment table |
| 6 — Nuts and Bolts | **done** | folded into `plan_member_writes` |
| 7 — true atomicity | **not started** | optional; the per-plan sequencing in §4.3 is what bounds the damage today |

### Deviations from the plan above, and why

**Phases 3 and 4 shipped together.** The plan separated them so a single-target apply
could soak first. In the code the split is not a separate mode: `plan_fill` already
returns one assignment per member carrying its target index, and `_apply_to_one_plan`
simply writes `w.batch_no` per member. Building a single-target-only path first would
have meant writing a special case and then deleting it. Both were verified live: a
one-batch move and a two-batch split, each moved and moved back.

**Preview and apply share one code path.** `_build_plan` computes members, targets,
fill and per-row writes; `preview_*` serialises it and `apply_*` executes it. The plan
had apply "re-run preview internally"; making them two functions over one builder is
the same guarantee with no chance of the two drifting.

**§4.4 #1 — no `read_only_depends_on` on the exact-match `sec_qty`.** The plan said to
mirror Material Mapping's. Material Mapping's `batch_sec_qty` is normally typed by the
user and goes read-only under the waiver; exact-match `sec_qty` is `read_only: 1`
always and server-derived. Mirroring would have made it hand-editable when the waiver
is off — a new and unwanted capability, over a field the plan itself (§4.4, "What
breaks when the flag is off") warns must not be written casually.

**§4.4 #13 — the flag is not a grid column.** Material Mapping's own waiver is not one
either; both are edited in the expanded row. It would also have been invisible: the
exact-match grid already declares **22 columns against Frappe's budget of 11**, so
everything from `overall_required_qty` onward is silently dropped today. Pre-existing,
reported separately, not fixed here.

**A zero guard was added to the exact-match waiver loop.** If the batch yields no
per-piece weight (a dimension or unit weight missing), the derived count is 0.
Material Mapping writes that 0; the new loop leaves the existing figure alone instead,
because exact-match `sec_qty` goes straight onto the Stock Entry as `custom_sec_qty`
and zeroing a good proportional allocation is worse than leaving a stale one.

**`_apply_batch_to_arm_row` falls back to the batch's dimensions** when the batch
changed and the caller passed none — the waiver path, where the dialog hides the
dimension inputs. Without it §4.4 #12 bites: the transfer ships the new batch tagged
with the old size. A caller that passes dimensions still wins, a same-batch round trip
changes nothing, and a Batch with no dimensions recorded does not zero the row's.

### A bug found and fixed during Phase 3

`_cross_table_conflicts` (Stage 0.7) flagged **same-table** rows sharing a batch. One
plate cut into a dozen parts is a dozen Material Mapping rows on one batch — the normal
case — and `_validate_no_cross_table_batch_duplicate` only refuses a batch held in
Material Mapping *and* Exact Match at once. As written it refused nearly every real
reassignment. It now checks only the table the members are **not** moving into, and
separately refuses a line whose own members straddle both tables (moving them onto one
batch would create the duplicate by itself). Check 3 of
`verify_consolidate_batch_apply.py` pins this against live data.

### One behaviour worth knowing

The Length/Width entered against a target batch declare a **cut size for capacity only**
— "how much of this batch may this line take". The row still records the batch's own
dimensions, because that is what `_get_mp_reserved_batches` puts on the Stock Entry.

### Verified live (restored production data, 11 Sep)

`MIP-2026-00005` / `PLATE25` / 3 rows / 217.344 Kg / `MP-2026-00017`:

* moved to `PLT25-P25-L11025-W2000-SR001` and back — rows returned byte-identical
  (batch, `batch_calc_qty`, `batch_sec_qty` 0.042/0.056/0.042, reserved, dimensions)
* Sec Nos re-derived correctly against the new piece (0.042 → 0.015 on a piece 2.8x
  larger), total Kg preserved exactly at 217.344 throughout
* split across two batches (98.125 Kg declared + the rest): row 1 → batch A, rows 2-3
  → batch B, **32.903 Kg correctly stranded** on batch A because row 2 did not fit and
  rows are never split; then merged back to one line
* the dialog was driven end to end in a real browser: line picker, live capacity,
  preview, per-row assignment table, the confirmation naming every plan, cancel, and
  the guard that drops back to Preview after any edit

**A reassign discards that line's parked transfer draft** — the draft is keyed on the
batch. The dialog warns before applying; the round trips above restored it by hand from
a backup.


---

## 9. Client review, 14 Sep 2026

| Request | Done |
|---|---|
| Rename popup labels | New Batches: Capacity → **Weight**, "free" → **Total available Weight**. Result table: Capacity → **Weight**, Free → **Total Batch Weight**, Unused → **Excess** |
| Length/Width read-only, Pieces only | Inputs read-only and filled from the Batch record. `get_batch_capacity(batch_no, warehouse, pieces)` no longer takes dimensions and `_build_plan` ignores any a caller sends. Reason: a typed cut size steered the fill but was never stored, so the Stock Entry always carried the batch's real size |
| Draft warning wording | *This line has unfinished entries saved from "Select Materials to Transfer" on {date} (not yet transferred). Changing the batch clears them — you will need to re-enter them in the transfer popup.* It is the **Save and Close** state of the transfer popup — no Stock Entry is involved |
| Hide Raw Materials Update Batch | Toolbar call commented out; row `update_batch_btn` set `hidden: 1`. **Side effect:** the freed grid width lets the **Batch** column show in Raw Materials, which the 11-column budget used to drop |
| Per-row Update Batch on Consolidate Items | New Button field `update_batch_btn` (2 cols; Issued Qty 2→1 keeps the grid at exactly 11). Drawn by a formatter + capture-phase click, because the grid is read-only. Opens the dialog preselected; transferred lines show *Transferred* |
| Confirmation shows current reservations | **Confirm Batch Reassignment** dialog: per row — Material Planning, current batch, Reserved / Not reserved, reserved Kg (read from the Material Planning row, not the Issue Plan's copy), new batch, new Kg — and the three steps Yes performs |

Also fixed while verifying:

* **The result message repeated the preview's warnings** after the user had already
  confirmed them. The apply now returns only what happened during the apply
  (inspection blocks, partial reservations) plus `from_batch` / `to_batches`, and says
  *"Unreserved N row(s) from OLD and reserved them on NEW (X Kg)."*
* **`verify_transfer_draft.py` destroyed real data.** It borrowed the first consolidate
  row on the site, overwrote its parked draft and then cleared it, committing both. On
  the restored live data that wiped a genuine Save-and-Close on MIP-2026-00005 / PLATE10
  (11 Sep 13:22, again 14 Sep 14:22). The draft was recovered from the 11 Sep 13:18
  backup. The test now prefers a row with no draft, snapshots the fields, and restores
  them in `finally`; verified by diffing every draft on the site before and after.

Verified in the browser end to end: row button → preselected line → read-only L/W →
preview → confirmation listing the three reserved rows → **Yes** → rows unreserved,
moved to `PLT25-P25-L11025-W2000-SR001` and reserved again (checked in the database) →
moved back the same way → rows byte-identical to before, every draft on the site
identical to before.


---

## 10. Excess tracking review, 14 Sep 2026

**When can excess be returned?** Any time once Excess Material Items has a row, no
matter whether the Final (Manufacture) Stock Entry exists. The Final Stock Entry
consumes only what the finished drawings need (`_consumption_for_completed`, capped at
`drawing_planned_weight`), so any surplus stays at the supplier. Excess return is a
Repack out of the supplier warehouse into stores, and it refuses with *"Not Enough Left
to Return"* if the supplier stock has already gone. The plan cannot become Completed
while any excess row is unresolved or weight is still unaccounted at the supplier, so
completion never locks out a pending return.

**Verified:** `_validate_selected_against_stock` on MIP-2026-00005, read-only. PLATE25
0.140 → 1 piece books 1,328.125 Kg and PLATE8 2.087 → 3 pieces books 860.124 Kg. Both
equal sent − planned, with the piece priced from the batch's own dimensions.

**Fixed:**
- `_resync_excess_item_mapping(batch_no)` in material_planning.py, called after the
  save in `reassign_batch` (both branches) and `_apply_to_one_plan`. Virtual-excess
  claims are left to `_release_virtual_excess_source`.
- `refresh_mip_raw_materials` now uses its long-unused `old_rows_by_key` to carry
  `transfer_excess_kg` forward when the batch is unchanged. Before this, MIP-2026-00004
  went from 6 rows / 8.719 Kg to 0 on any rebuild.

Tests: `verify_consolidate_batch_apply.py` §5d. All checks write inside a transaction
and roll back.
