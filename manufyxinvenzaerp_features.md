# Manufyxinvenzaerp — Implemented Features
**App:** manufyxinvenzaerp | **Platform:** Frappe v15 / ERPNext v15 | **Site:** manufact
**Date:** 2026-07-16

---

## 1. Item Master Customization

### 1.1 Parent Item Group Enforcement
- `Parent Item Group` is a mandatory custom field on the Item master.
- Drives calculation type automatically:
  - **Structurals / Plates** → Formula Weight Calculation
  - **Nuts and Bolts** → Normal Weight Calculation

### 1.2 UOM Validation per Item Group
- **Structurals / Plates**: Primary UOM must be `Kg`; Secondary UOM must be `Nos`.
- **Nuts and Bolts**: Primary UOM must be `Nos`; Secondary UOM must be `Kg`.
- System throws an error if mismatched UOMs are set.

### 1.3 Batch Configuration Rules
- For Structurals / Plates with `Has Batch No` enabled:
  - `Custom Batch Abbreviation (Prefix)` is mandatory.
  - `Create New Batch` is auto-enabled.
- Batch prefix cannot be changed once batches exist for the item (prevents data inconsistency).

### 1.4 Locked Fields after Transactions
Once stock or order transactions exist for an item, the following fields are locked (cannot be changed):
- Parent Item Group, Default UOM, Unit Weight, Secondary UOM, Custom Batch Abbreviation.

---

## 2. Drawing Management

### 2.1 Drawing Doctype (Custom)
A new central doctype representing the engineering drawing for a Finished Good.

**Key fields:** Sales Order link, Customer, FG Item Code, DUNO/Mark No, Revision Number, Qty to Manufacture, Drawing Items (child table), Total Weight, Status.

### 2.2 Drawing Revision Management
- `Rev No` auto-increments when a Drawing is amended (starts at 0).
- Cancelling a Drawing automatically sets status to `Old Revision`.

### 2.3 Drawing Item Calculation Engine
Formula-based quantity calculation on each line item depending on `Parent Item Group`:
- **Structurals**: `Qty = (Length/1000) × Unit Weight × Sec Qty`
- **Plates**: `Qty = (L/1000) × (W/1000) × Thickness × Unit Weight × Sec Qty`
- **Nuts and Bolts**: `Sec Qty = Qty × Unit Weight`

Total Weight is summed across all items. Missing required dimension fields trigger a warning on save and block submission.

### 2.4 Drawing Lifecycle
`Working` → (submit + mark_as_final_revision) → `Final Revision` → (used for BOM creation)

### 2.5 CSV Import for Drawing Items
- Button on Drawing to upload a CSV file with item rows.
- Server-side parsing: fetches item master data, runs formula calculation, returns ready-to-insert rows.
- Accepts flexible column names (case-insensitive); auto-assigns item numbers if not provided.

### 2.6 Sales Order Integration
- **Create Drawings from SO**: One Drawing created per SO line item; blocked if a Drawing already exists for the SO.
- **Dashboard Link**: Drawings appear in the Sales Order connections dashboard.

### 2.7 BOM Creation from Drawing
- BOM can only be created from a submitted `Final Revision` Drawing.
- All drawing item dimensions (L, W, T, Unit Weight, Sec Qty, Sec UOM, Material Spec, Item Number) are carried into BOM Item custom fields.
- **BOM Validation (via hook)**: Any BOM linked to a Drawing enforces:
  - Drawing items cannot be removed from the BOM.
  - Quantities and dimensions are restored from the Drawing if manually edited in the BOM.

### 2.8 Production Plan Creation from BOM
- BOM must be submitted.
- Auto-populates the Process Planning child table from the BOM's routing operations.

---

## 3. BOM Override

- ERPNext's standard `BOM` doctype is extended via `override_doctype_class`.
- Custom fields added: Drawing reference (`custom_drawing`), DUNO/Mark No (`custom_duno_mark_no`).
- Custom BOM search in Material Planning: searches by BOM name, item code, item name, or DUNO/Mark No.

---

## 4. Material Planning (Custom Doctype)

The largest and most complex module. Drives all raw material identification, stock matching, batch reservation, and downstream MR/PP creation.

### 4.1 BOM Explosion & Raw Materials
- Multiple BOMs (with qty to manufacture) can be added to one Material Planning.
- `Get Raw Materials` explodes each BOM into a flat raw materials list.
- Reverses the formula to compute `Sec Qty (NOS)` from Kg for each Structural/Plate item.
- Cross-validates computed Sec Qty against the stored BOM value and warns on mismatch.

### 4.2 Stock Availability Check — Three-Bucket Classification
`Check Stock Availability` classifies each raw material row into one of three buckets:

| Bucket | Condition |
|---|---|
| **Available Raw Materials** | Batch item: exact dimension batch found with free stock; Non-batch: stock ≥ required |
| **Material Mapping** | Batch item: no exact-dimension batch found (needs alternate/different-dimension batch); also partial-stock shortfall rows |
| **Unavailable Items** | Non-batch item: stock < required (needs purchase) |

- Has a `Store Location` field intended for location-filtered stock queries, but as of this writing this is not a working, populated feature in practice: `Store Location` (a doctype scoped only to the Material Planning child tables) has **zero records** and no Material Planning document has ever set it — the query path it feeds (`get_sbb_available_qty`'s `location` filter) previously raised a hard SQL error whenever a location value *was* supplied, since it queried a `store_location` column that has never existed on Stock Ledger Entry (fixed in Phase 1 HP-05 to query the correct existing column instead, `storage_location`; see the Storage Location / Store Location note in §16 below). Whether Material Planning's location filtering should instead key off `Storage Location` — the separate, real, heavily-used ERPNext Inventory Dimension already wired onto Stock Ledger Entry and 30+ other doctypes across this app — is an open product question, not yet decided.
- Accounts for reservations made by other Material Planning documents (cross-MP awareness).

### 4.3 Batch Dimension Matching (SBB/SBE)
- Batch availability is queried via `Serial and Batch Bundle` / `Serial and Batch Entry` tables (Frappe v15).
- Only batches whose `Length`, `Width`, `Thickness` exactly match the required dimensions are considered an exact match.

### 4.4 Material Mapping — Alternate/Different-Dimension Batch Assignment
- User can manually assign a different-dimension batch to Material Mapping rows.
- `Batch Calc Qty` is auto-calculated from the assigned batch's dimensions.
- Save-time validation: blocks if calculated qty exceeds available free stock; warns if below required qty.
- `Reserve Without Dimensions` flag allows bypassing dimension calc and reserving the required qty directly.
- `Finalize Mapping`: unmapped rows (no batch assigned) are moved to Unavailable Items.
- **Weight Summary — Difference in Kg**: The Details tab shows a live HTML summary of `Σ(batch_calc_qty − qty)` for all Mapped rows, coloured green (excess) or red (short).

### 4.4a Update Difference Kg in Sales Order
- Button **"Update Difference Kg in Sales Order"** in the Weight Summary section.
- On click, calls `update_so_difference_kg()` which:
  - Collects unique `(sales_order, duno_mark_no)` pairs from this MP's Material Mapping rows.
  - Queries **all** Material Planning Material Mapping rows (across all MPs) for each pair with `batch_mapped = "Mapped"`.
  - Sums `batch_calc_qty − qty` per pair and writes the result to the `difference_kg` field on the matching `Sales Order DUNO Item` row via `db.set_value` (bypasses SO submitted restriction).
- The `difference_kg` Float field is visible in the Sales Order Drawing List (DUNO Items) child table.

### 4.5 Stock Reservation
- **Reserve Batches** (Material Mapping): reserves qty per batch with partial-stock awareness; tracks intra-document same-batch usage.
- **Reserve Exact Match Batches** (Available Raw Materials): same logic for the exact-match table (supports both batch and non-batch items).
- **Unreserve**: selective unreserve by child row name, for both tables independently.
- **Check Mapping Batch Availability**: pre-flight check that shows shortfall warnings before reserving.
- Reserved rows are locked — qty/batch changes blocked on save until unreserved.

### 4.6 Cross-MP Reservation Integrity
- Reservations from all other Material Planning documents are subtracted when computing available qty.
- When a Stock Entry (Manufacture / Transfer / Issue / Repack) is submitted, reservations for consumed batches are automatically released.
- When the Stock Entry is cancelled, reservations are restored.

### 4.7 Batch Reservation Summary
- Per-batch summary of all active reservations across all MPs (shows MP name, SO, customer, project, reserved qty).

### 4.8 Move to Exact Match
- For selected Unavailable Items, re-checks if exact-dimension batch stock has arrived (e.g. after a Purchase Receipt).
- Matched rows move to Available Raw Materials; still-unavailable remain; batch items with no matching stock move to Material Mapping.

### 4.9 Make Production Plan
- Creates a draft Production Plan from the Material Planning's BOM Items list.
- Auto-links drawing, DUNO/Mark No, Sales Order, Customer, and Material Planning reference on PP items.

### 4.10 Make Material Request
- Creates Material Requests for Unavailable Items.
- Links the Material Request back to the Material Planning for traceability.
- On MR cancel or trash, the MP link is automatically cleared.

### 4.11 PR Stock Auto-Allocation to Material Planning
- After a Purchase Receipt is submitted: `Allocate PR Stock to MP` traces PR → PO → MR → Material Planning.
- Original item purchased → added to Available Raw Materials.
- Alternate item purchased → added to Material Mapping with the received batch and dimensions.

---

## 5. Purchase Order Customization

- **Formula Qty Auto-Calculation**: Qty recalculated from dimensions on save (Structurals / Plates / Nuts and Bolts).
- **Missing Fields Validation**: Warning on save; hard block on submit for Structurals and Plates (Length, Width, Thickness, Unit Weight, Sec Qty).
- **Custom Total Weight**: Sum of all Structural/Plate item quantities on the PO.
- **Custom UOM Link Query**: Link field on PO items returns only UOMs valid for the selected item.

---

## 6. Purchase Receipt Customization

- **Formula Qty Auto-Calculation**: Same formula logic as PO (Structurals / Plates / Nuts and Bolts).
- **Dimension Fields Auto-Copy from PO**: When PR is created from PO, dimension fields (L, W, T, Sec Qty) are copied from the PO item if not already set.
- **Missing Fields Validation**: Warning on save; block on submit.
- **Custom Total Weight** field on PR header.
- **Weighment Weight** (`custom_weighment_weight`): Float field on PR header to record the actual weighment weight.
- **Supplier Invoice Weight** (`custom_supplier_invoice_weight`): Float field on PR header to record the weight as per supplier invoice; placed after Weighment Weight.
- **Custom UOM Link Query** on PR items.
- **Batch Auto-Naming on Receipt**: On Batch `before_insert`, the batch ID is auto-generated as: `{Prefix}-T{Thickness}-L{Length}-W{Width}-R{ReceiptSuffix}` using the item's batch prefix and PR dimensions.
- **Batch Auto-Naming from Stock Entry (Repack / Material Receipt)**: Similar naming with `SR{suffix}`.
- **Batch Master Auto-Populated**: On SE submit for Material Receipt, the batch's `Supplier`, `Supplier Invoice No`, `Invoice Weight`, `Inward Date` custom fields are set from SE item fields.

---

## 7. Material Request Customization

- **Formula Qty Recalculation** on validate.
- **Missing Fields Validation** (warning on save; block on submit).
- **Custom UOM Link Query** on MR items.
- **Material Planning Link Field** (`custom_material_planning`) on Material Request — provides traceability back to the planning document.

---

## 8. RFQ Customization

- **Dimension fields copied from MR item** when RFQ is created from a Material Request.
- Server-side validate hook to enforce custom rules.

---

## 9. Supplier Quotation Customization

- **Custom data copied from RFQ item** if fields are blank on the SQ (dimensions, sec qty, spec).
- **Formula Qty Recalculation** on validate.
- **Missing Fields Validation**.
- **Custom UOM Link Query** on SQ items.

---

## 10. Production Plan Customization

- **Process Planning Child Table** added to Production Plan: each row has an operation name and `Work Type` (`Internal Jobcard` or `Subcontractor`).
- **Vendor/Contractor Field** on Production Plan (used when creating a Subcontracting Order).
- **Override `get_items_for_material_requests`**: custom implementation that accounts for Store Location inventory dimension and SBB-based available qty in the material request calculation.
- **SBB Available Qty Engine** (`get_sbb_available_qty`): core utility that queries Serial and Batch Bundle → Serial and Batch Entry with optional Store Location filtering and exact dimension matching.

---

## 11. Production Operations — Standard Manufacturing Routing

- On install and every migrate, 12 standard operations and matching workstations are auto-created:
  `Material Issue → Cutting Status → Material Matching → Fit-up → Fitup Inspection → Welding → Welding Inspection → Final → Final Inspection → Blasting → Painting → Despatch`
- A single `Standard Manufacturing Routing` combining all 12 in sequence is also auto-created.

---

## 12. Job Card Customization

- **Raw Material Consumption Child Table** (`custom_raw_material_consumption`) added to Job Card.
- Auto-populated from Work Order required items (with WIP stock qty, dimensions, previous operation consumption).
- **Server-side Consumption Validation**:
  - Structurals/Plates: consumed qty cannot exceed transferred qty to WIP.
  - `Current Nos` cannot exceed `Previous Operation Nos` (whenever a previous-operation Nos value exists — see below).
  - Nuts & Bolts: `manual_qty` cannot exceed WIP stock.
- **Previous Operation Data**: fetched from the preceding Job Card; falls back to the last submitted Supplier Operation Entry (Scenario 3 hybrid subcontractor → internal handoff). A Work Order's Job Cards are always locally renumbered starting at `sequence_id = 1`, so a hybrid plan's *first* Work Order Job Card also has `sequence_id = 1` — the fallback now runs for that case too (previously it only ran for `sequence_id > 1`, silently returning 0 available-to-consume for the WO's first operation after a subcontracted block). The matching "Nos can't exceed previous operation" guard, server-side and in the Job Card client script, was ungated the same way so it actually enforces once the sequence_id 1 case carries a real previous-op value.
- **Consumption Log** (`custom_consumption_log`, drawing-level Nos/Kg log with Employee, From Time, To Time) is backed by its own **Job Card Consumption Log** child doctype — kept separate from Supplier Operation Entry's own Consumption Log (see 14.5) so each side can carry different fields.

---

## 13. Stock Entry Customization

- **Formula Qty Auto-Recalculation** on validate for Repack, Material Receipt, Material Issue (Structurals/Plates only).
- **On Submit**: reduces `custom_sec_qty` on the Batch master for consumed batches (Material Issue, Repack source rows, Material Receipt linked batches).
- **Batch Supplier/Invoice fields** copied to Batch master on Material Receipt submit.
- **Automatic Release of Material Planning Reservations** on submit for consumption-type entries.
- **Automatic Restoration of Reservations** on cancel.
- **Final Operation Consumption Validation**: before a Manufacture SE is submitted, checks that all required items in the final Job Card have recorded consumption.

---

## 14. Subcontracting Management

### 14.1 Supplier Operation Entry (Custom Doctype)
A new doctype to track material consumption at each subcontractor operation.

**Key fields:** Work Order, Subcontracting Order, Production Plan, Operation, Sequence ID, Supplier, Supplier Warehouse, Status, Items child table (item code, dimensions, transferred qty, previous op qty, current consumed qty, batch).

### 14.2 Three Production Scenarios
All three scenarios are supported without code branching at the UI level:

| Scenario | Description |
|---|---|
| **Scenario 1** (All Internal) | PP → Work Order → Job Cards per operation |
| **Scenario 2** (All Subcontractor) | PP → SCO directly (no WO) → Supplier Operation Entries |
| **Scenario 3** (Hybrid) | PP → SCO (sub ops) + Work Order (internal ops); subcontractor completes first, then WIP transfer to internal |

### 14.3 Automated Document Creation from Production Plan
All actions are triggered from the Production Plan / SCO via buttons:

- **Create SCO from Production Plan**: creates a draft Subcontracting Order from subcontractor operations in Process Planning; works with or without a Work Order.
- **Create Work Order from PP**: creates a Work Order containing only the Internal Jobcard operations; links filtered routing operations.
- **Create Supplier Operation Entries** (idempotent): one SOE per subcontractor operation in sequence; pre-populates batch from supplier warehouse stock, dimensions from BOM, and previous-operation consumption from prior SOE.

### 14.4 Material Movement Stock Entries from SCO
- **Send to Subcontractor**: draft Stock Entry transferring BOM items from source warehouse to supplier warehouse.
- **WIP Transfer (Scenario 3)**: Material Transfer from supplier warehouse to company WIP warehouse based on last submitted SOE's consumed quantities.
- **Return Unconsumed Stock**: Material Transfer for leftover materials from supplier warehouse back to a specified company warehouse.

### 14.5 SOE Validation & Lifecycle
- On validate: consumed qty vs transferred; cross-operation Nos check (cannot exceed previous operation's Nos); Nuts & Bolts manual qty check.
- On submit: reduces `custom_sec_qty` on batch master for consumed items; marks `custom_all_ops_complete` on the SCO when the last operation is submitted.
- **SCO Dashboard**: Supplier Operation Entries appear in the Subcontracting Order connections dashboard.
- **Consumption Log** (`consumption_log`, drawing-level Nos/Kg log): Date, Drawing, Qty (Nos), Weight (Kg), Remark — kept lean, with no Employee/From Time/To Time fields (those stayed on Job Card's own Consumption Log, see 12).

---

## 15. Custom Fields Summary (Fixtures)

Custom fields are exported as fixtures and applied across the following standard doctypes:

| Doctype | Notable Custom Fields |
|---|---|
| Item | Parent Item Group, Calculation Type, Unit Weight, Secondary UOM, Batch Prefix |
| Batch | Sec Qty, Sec UOM, Thickness, Length, Width, Supplier, Invoice No, Invoice Weight, Inward Date |
| BOM / BOM Item | Drawing, DUNO/Mark No, Item Number, Material Spec, Dimensions, Sec Qty, Sec UOM, Sales Order, Parent Item Group |
| Purchase Order / Items | Total Weight, Dimensions, Sec Qty, Parent Item Group, UOM custom link |
| Purchase Receipt / Items | Total Weight, Weighment Weight, Supplier Invoice Weight, Dimensions, Sec Qty, Parent Item Group, Supplier fields, existing invoice fields |
| Material Request / Items | Material Planning link, Dimensions, Sec Qty |
| Supplier Quotation / Items | Dimensions, Sec Qty |
| Production Plan / Items | Drawing, DUNO/Mark No, Customer, Material Planning link; Process Planning table, Vendor/Contractor |
| Job Card | Raw Material Consumption child table, Dimensions per row, Inspection tab (Inspection Status, Inspection Call Date, Inspection Call Log table) |
| Stock Entry / Items | Dimensions, Sec Qty, Parent Item Group, Supplier, Invoice No |
| Subcontracting Order | Production Plan, Work Order, Source Warehouse, WIP Warehouse, All Ops Complete |

---

## 16. New Custom Doctypes

| Doctype | Module | Purpose |
|---|---|---|
| Drawing | drawing_management | Engineering drawing master; drives BOM and production |
| Drawing Item | drawing_management | Child table for drawing line items |
| Nature of Work | drawing_management | Master for work classification |
| Production Plan BOM Raw Material | drawing_management | Child table |
| Sales Order DUNO Item | drawing_management | Child table for SO DUNO mapping |
| Material Planning | production_management | Core raw material planning and batch reservation |
| Material Planning Available Raw Material | production_management | Child table — exact-match stock |
| Material Planning BOM Item | production_management | Child table — BOM list |
| Material Planning Material Mapping | production_management | Child table — alternate/different-dimension batch mapping |
| Material Planning Raw Material | production_management | Child table — exploded raw material list |
| Material Planning Unavailable Item | production_management | Child table — items to purchase |
| Job Card Raw Material | production_management | Child table — per-operation consumption |
| Job Card Consumption Log | subcontracting_management | Child table on Job Card — drawing-level Nos/Kg consumption log, with Employee/From Time/To Time |
| Process Planning | production_management | Child table on Production Plan — operation routing |
| Production Plan Available Raw Material | production_management | Child table |
| Storage Location / Store Location | production_management | See distinction note directly below — these are two separate doctypes, not a naming variant of one |
| Inspection Entry | production_management | Submittable QC sign-off record for Fitup Inspection / Final Inspection rounds |
| Inspection Call Log | production_management | Child table on Job Card/SOE — one row per inspection call round |
| Supplier Operation Entry | subcontracting_management | Per-operation subcontractor material consumption |
| Supplier Operation Item | subcontracting_management | Child table |

**`Storage Location` vs. `Store Location` — these are genuinely two different doctypes, not a typo:**
- **`Storage Location`** is the real, heavily-wired ERPNext Inventory Dimension — registered via `setup.py`'s `setup_storage_location()`, referenced by 32 Link-type custom fields across Stock Ledger Entry, Job Card, Purchase/Sales/Delivery/Subcontracting documents, Drawing Item, Supplier Operation Item, and Production Plan's own child tables. It has active seed data (`A-1`, `A-2`, plus site-specific locations like `B-1`/`B-2`/`B-3`/`B-5`/`CNCSET`/`CNC`).
- **`Store Location`** is a narrower doctype scoped only to the Material Planning family (6 Link fields, all within Material Planning's own child tables). As of this writing it has **zero records** in this site's real data, and no Material Planning document has ever set its `store_location` field — see §4.2 above for the related `get_sbb_available_qty` fix this ambiguity caused (Phase 1 HP-05).

---

## 17. Inspection Call / QC Workflow (Fitup Inspection & Final Inspection)

A QC sign-off workflow layered on top of Job Card and Supplier Operation Entry, scoped to exactly two routing checkpoints: **Fitup Inspection** and **Final Inspection**. Manufacturing logs the inspection call; a separate QC team records the result — matching the real-world split between the manufacturing team (fills quantities as usual, then requests a QC visit) and QC (reviews and signs off on its own page).

### 17.1 Inspection Tab on Job Card / Supplier Operation Entry
- New **Inspection** tab, visible only when `operation` is Fitup Inspection or Final Inspection (`depends_on` gated).
- **Inspection Status** (Open → Working → Completed): starts Open, flips to Working once the first call is logged, becomes Completed only once a round fully clears the checked quantity.
- **Inspection Call Date**: the entry point field the manufacturing team sets before logging a new call.
- **Inspection Call Log** (child table, read-only grid): one row per round — Round No, Inspection Call Date, linked Inspection Entry, Round Status (Pending/Completed), Rework Remarks (denormalized from the entry).

### 17.2 Buttons: Add Inspection Call / Create Inspection Entry
- **"Add Inspection Call"**: validates an Inspection Call Date is set, blocks logging a new round while one is already pending, appends a round, and auto-advances Inspection Status Open → Working.
- **"Create Inspection Entry"**: once a round is pending, creates a draft **Inspection Entry** — prefilled with Operation, Round No, Call Date, and denormalized Work Order/Subcontracting Order/Production Plan/Sales Order/Customer/Supplier traceability — and routes to it as a separate page for QC to fill in.

### 17.3 Inspection Entry (Custom Submittable Doctype)
QC fills in: **Status** (Ok/Not Ok), **Total Checked Qty**, **Cleared Qty**, **Rework Qty** (auto-computed), **Rework Remarks** (mandatory when Rework Qty > 0).

**Server-side rule**: Not Ok always implies Rework Qty > 0, and Ok always implies full clearance — `cleared_qty == total_checked_qty` with Status "Not Ok" is rejected, and partial clearance with Status "Ok" is rejected.

On submit, propagates back to the parent Job Card/SOE: marks that round's call-log row Completed, copies the rework remarks, and sets the parent's overall Inspection Status to **Completed** (fully cleared) or leaves it **Working** (rework remains — manufacturing logs a new call date and the cycle repeats).

### 17.4 Submission Gate
Job Card / Supplier Operation Entry submission is blocked for the Fitup Inspection / Final Inspection operations until Inspection Status is Completed — mirrors the existing "Status must be Completed" gate already used for the drawing-flow consumption fields.

### 17.5 Inspection Status Report
New Script Report showing **one row per inspection round** (full rework history, not just the latest): Production Plan, Sales Order, Customer, Reference Type + Reference (Work Order/Subcontracting Order), Active Doctype + Active Document (Job Card/SOE), Operation, Round No, Inspection Call Date, Inspection Status, Round Status, Total Checked Qty, Cleared Qty, Rework Qty, Rework Remarks. Filterable by Operation, Inspection Status, Production Plan, Sales Order.

### 17.6 Shared Logic Module
`production_management/inspection.py` holds all the logic shared identically by Job Card and SOE (`add_inspection_call`, `create_inspection_entry`, `on_submit_inspection_entry`, the before-submit gate, and `_resolve_traceability` — resolves Sales Order/Customer from the Job Card/SOE's own drawing-detail rows, falling back to the linked Work Order's Sales Order).

### 17.7 Roles
Inspection Entry create/write/submit access: System Manager, Manufacturing Manager, Manufacturing User, and **Quality Manager** (ERPNext's existing QC role — reused rather than creating a new one).

*Design note: ERPNext's standard Quality Inspection doctype was evaluated as an alternative and rejected — it has no accepted/rejected quantity tracking at all (purely parameter/reading-based), mandatory `item_code`/`sample_size` fields that don't map to this use case, only a single Quality Inspection Link per Job Card (no multi-round support), and no support for Supplier Operation Entry as a reference type without patching core ERPNext code.*

---

## 18. Security, Performance & Reliability Remediation (Phase 1 Audit Pass, 2026-07-16)

A ten-report internal audit (functional/BRD, architecture, bugs, performance, code quality, refactoring, dead code, security, testing, action plan) was run against this app and reorganized into a three-phase remediation plan (`PROJ001 CLAUDE FILES/PHASE_1_Critical.md`, `PHASE_2_Medium.md`, `PHASE_3_Low.md`). Most of Phase 1 (the Critical tier) has since been implemented, verified against the live site, and is summarized here. Every fix below was checked for behavior parity before/after (numeric output diffs, test-suite pass/fail signature comparisons via `git stash`, or both) — none of it changes what the app produces, only how fast/safely it gets there, except where explicitly noted as a bug fix.

### 18.1 Security
- **Removed a hardcoded production Administrator credential** from `pull_live.py` — now reads `MANUFYX_LIVE_URL`/`MANUFYX_LIVE_USER`/`MANUFYX_LIVE_PASS` from the environment and refuses to run if unset. **The credential was also found in this repo's git history** (already merged, and this repo has a live GitHub `upstream` remote) — rotating the live password and deciding whether to scrub history is an ops action outside what a code change can fix; not yet done as of this writing.
- **Duplicate-creation guard** added to `create_sco_from_production_plan` / `create_work_order_from_pp` (`subcontracting_management/subcontracting.py`) — a double-click or retry no longer creates a second Subcontracting Order / Work Order against the same Production Plan.
- **BOM-active check now runs at creation time** for the same two functions, instead of being silently skipped by the blanket `ignore_validate` flag used to insert the draft document.
- **Permission checks added** to whitelisted endpoints that previously trusted any authenticated caller:
  - Read: `get_batch_reservation_summary`, `get_batch_cross_table_usage` (`material_planning.py`), `get_mp_for_pr`, `get_pr_mp_allocations` (`purchase_receipt.py`) — now require Material Planning read permission.
  - Write: `reserve_batches`, `finalize_mapping`, `auto_purchase_from_mp` (`material_planning.py`), `create_sco_from_production_plan`, `create_work_order_from_pp`, `create_supplier_operation_entries` (`subcontracting.py`) — now require the relevant create/write permission.
- **Stored XSS fixed**: `drawing_management/doctype/drawing/drawing.js`'s Drawing Items summary table and `public/js/purchase_receipt.js`'s post-submit allocation popup now escape every interpolated Item/Batch/Material-Planning field via `frappe.utils.escape_html`, matching the pattern already used correctly in `batch.js`.

### 18.2 Performance
- **New shared formula module** `manufyxinvenzaerp/utils/dimension_formula.py` (`calculate_qty`, `calculate_sec_qty_from_qty`, `check_missing_fields`) replaces 8 independently-maintained copies of the Structurals/Plates/Nuts-and-Bolts formula across `material_request.py`, `purchase_order.py`, `purchase_receipt.py`, `supplier_quotation.py`, `sales_order.py`, `so_drawing_import.py`, `drawing_utils.py`, and the Drawing controller. Verified numerically identical to the previous per-file implementations across normal values and every edge case (missing dimensions, each item group, blank group).
- **New shared reference-copy module** `manufyxinvenzaerp/utils/reference_copy.py` (`copy_reference_fields_if_blank`, `fetch_fields`) replaces the near-identical copy-from-parent-transaction logic in `purchase_order.py`, `purchase_receipt.py`, and `request_for_quotation.py`.
- **Query batching** (the direct fix for "large document slow to save/submit"):
  - `get_raw_materials` (`material_planning.py`) — the per-row `custom_secondary_uom` Item lookup is now one batched query.
  - `check_stock_availability` (`material_planning.py`) — the whole stock-classification loop now reads from pre-fetched bulk lookups (new `get_sbb_batches_bulk` / `match_batches_by_dimension` in `production_plan.py`; new `_get_batch_reserved_by_others_bulk`, `_get_non_batch_stock_bulk`, `_get_non_batch_reserved_by_others_bulk` in `material_planning.py`) instead of issuing several queries per raw-material row.
  - `allocate_pr_stock_to_mp` (`purchase_receipt.py`) — the Purchase Order Item → Material Request Item → Material Request trace is now 3 batched queries total instead of up to 3 per PR line.
  - Added `search_index` to `item_code`, `batch`/`batch_no`, `is_reserved` on `Material Planning Material Mapping` and `Material Planning Available Raw Material` — confirmed present on the live DB after `bench migrate`.
- **Stock Entry submit-time weight refresh** — `refresh_weight_summary` (Material Issue Plan), `_refresh_wo_drawing_transferred_weights`, and `_refresh_sco_drawing_transferred_weights` (`subcontracting.py`) now set `flags.ignore_links = True` before saving, skipping Frappe's redundant Link-field re-validation on child-table rows the function never touches (none of these narrow numeric-field updates change any Link field's value). Also added `_get_mp_drawing_weights_by_duno`, a batched per-Material-Planning replacement for the old per-drawing-row `_get_mp_drawing_weight` call, now used by `refresh_weight_summary` and both SCO/WO creation functions. Measured on a real 98-row Stock Entry: the two custom submit hooks dropped from ~1.1s to ~0.56s; full end-to-end submission (including ERPNext core's own processing, which this app's code doesn't control) on a comparable 100-row entry was ~13.3s — most of the remaining time sits outside this app's own hooks and hasn't been profiled yet.
- **CI/CD test gate**: `.github/workflows/main.yml` now runs a `test` job (fresh site, full `bench run-tests`) that the `deploy` job depends on — previously the pipeline had no test-execution step at all before pushing to production.

### 18.3 Bug fixes
- **`store_location`/`storage_location` fieldname mismatch, confirmed live**: `get_sbb_available_qty` (and the new `get_sbb_batches_bulk`) filtered Stock Ledger Entry on a `store_location` column that has never existed — confirmed via `DESCRIBE` and a direct call that reproduced `OperationalError: Unknown column 'tabStock Ledger Entry.store_location'`. Fixed to query the column that actually exists, `storage_location`. Also discovered: `Store Location` (the doctype this filter was meant to key off) has **zero records** in this site's data and no Material Planning document has ever set it — this code path had essentially never been exercised.
- **Purchase Receipt submission was crashing on every submit**: `on_submit_purchase_receipt` had a wrong import path for `refresh_mip_raw_materials` (`...subcontracting_management.material_issue_plan` instead of `...subcontracting_management.doctype.material_issue_plan.material_issue_plan`), raising `ModuleNotFoundError` unconditionally, outside any try/except. Fixed and confirmed live (PR-26-00008 submitted successfully afterward, with correct Material Planning allocation across all 100 line items).
- **Silent failures now surfaced to the user**: `on_submit_purchase_receipt`'s Material Planning allocation and `_refresh_linked_mip_weight` (`stock_entry.py`) now show an orange `msgprint` when they fail, in addition to the existing `frappe.log_error` — previously a failure here was invisible until someone noticed stale data much later.
- **Stray script no longer breaks test discovery**: `production_management/test_release.py` (a one-off manual debug script, not a real test, but named so `bench run-tests` tried to import it as one and crashed before any real test could run) renamed to `manual_release_check.py`.

### 18.4 New feature — Material Issue Plan warehouse fields filtered by Company
`source_warehouse`, `supplier_warehouse`, `cnc_warehouse`, `excess_return_warehouse` on Material Issue Plan (`subcontracting_management/doctype/material_issue_plan/material_issue_plan.js`) now filter to the document's own Company via `frm.set_query`, matching the same pattern already used for `subcontracting_order`/`work_order` in this file. Previously showed every warehouse across every company in the system (62 across 10 companies on this site); now shows only the ~7 belonging to the document's own company.

### 18.5 Not yet done (flagged, not silently dropped)
- Rotating the leaked production credential and deciding on a git-history scrub (§18.1) — ops action, not a code change.
- Profiling the *rest* of Stock Entry submission time beyond this app's own two custom hooks (ERPNext core's own Stock Ledger/GL/valuation/Serial-and-Batch-Bundle processing) — the current fix only addresses this app's own custom-code overhead.
- The remaining Phase 1 items requiring business sign-off (Drawing's "All"-role grant, the RFQ/Sales Order missing-dimension gate) or a dedicated design/regression-suite effort first (the batch-matching heuristic redesign, the `bom_class_override.py` fork reduction) — see `PROJ001 CLAUDE FILES/PHASE_1_Critical.md` for the full detail on each.

---

*This document covers all major features implemented in the custom app. Minor utility helpers, internal validation guards, and test scaffolding are not listed.*
