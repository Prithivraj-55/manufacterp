## About This Fork
This is an active customization fork maintained by **Prithivraj Thangadurai** 
(ERPNext Techno-Functional Consultant). Features and modules documented below 
were designed, developed, and tested using AI-assisted development (Claude Code), 
with manual code review and validation before each commit.

# manufyxinvenzaerp

A production-grade custom Frappe/ERPNext application (v15) built for manufacturing operations. It extends ERPNext's core procurement, production, and subcontracting workflows with custom doctypes, deep hook integrations, and a batch/secondary-quantity tracking system.

---

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Modules](#modules)
  - [Drawing Management](#1-drawing-management)
  - [Item Management](#2-item-management)
  - [Material Request Management](#3-material-request-management)
  - [Purchase Order Management](#4-purchase-order-management)
  - [Purchase Receipt Management](#5-purchase-receipt-management)
  - [RFQ Management](#6-rfq-management)
  - [Supplier Quotation Management](#7-supplier-quotation-management)
  - [Production Management](#8-production-management)
  - [Production Plan Management](#9-production-plan-management)
  - [Subcontracting Management](#10-subcontracting-management)
- [Custom Doctypes](#custom-doctypes)
- [ERPNext Overrides](#erpnext-overrides)
- [Fixtures & Custom Fields](#fixtures--custom-fields)
- [Test Suite](#test-suite)
- [Installation](#installation)
- [Key Bench Commands](#key-bench-commands)

---

## Overview

This app models a sheet-metal / CNC job-shop workflow where raw material (coil/sheet) is purchased by weight, tracked as named batches, and consumed through multi-stage operations that may include in-house production or subcontracting to external suppliers. The key problems it solves:

- **Drawing-driven BOM creation** — engineers attach technical drawings to Sales Orders; the app generates Bills of Materials and Production Plans directly from those drawings.
- **Batch reservation & secondary-qty tracking** — batches carry a secondary quantity (kg weight alongside ERPNext's primary UOM). Material Planning reserves specific batches before production starts and releases them on Stock Entry submit/cancel.
- **Full procurement chain enrichment** — every procurement doctype (MR → RFQ → SQ → PO → PR) is extended with custom UOM fields, validation, and weight/qty recalculation.
- **Subcontracting via Supplier Operation Entry** — a custom doctype that tracks material sent to, processed by, and returned from external subcontractors at drawing-item granularity.

---

## Architecture

```
manufyxinvenzaerp/
├── drawing_management/        # Drawing → BOM → Production Plan flow
├── item_management/           # Item validation (batch config, UOM, groups)
├── material_request_management/
├── purchase_order_management/
├── purchase_receipt_management/
├── rfq_management/
├── sq_management/
├── production_management/     # Job Card, Stock Entry hooks; Material Planning doctype
├── production_plan_management/
├── subcontracting_management/ # SCO override; Supplier Operation Entry; Material Issue Plan
├── utils/                     # Shared pure-function modules (added 2026-07-16 remediation pass):
│                               #   dimension_formula.py (qty formula, missing-field check),
│                               #   reference_copy.py (copy-from-parent-transaction helper) —
│                               #   consolidates logic that was previously duplicated across
│                               #   6-8 doctype-specific files each; see manufyxinvenzaerp_features.md §18.2
├── fixtures/                  # custom_field.json, property_setter.json
├── public/js/                 # Client-side JS injected into core ERPNext doctypes
├── patches/                   # Data migration patches
└── tests/                     # pytest test suite (run via bench; gated in CI as of 2026-07-16 — see below)
```

**Conventions:**
- ERPNext standard doctypes are extended through `doc_events` hooks only — no Document subclasses, except for `BOM`, `Subcontracting Order`, and `Stock Entry` (see the ERPNext Overrides table below), which require method overrides.
- All whitelisted API functions follow the path `manufyxinvenzaerp.<module>.<file>.<function>` and are called from JS via `frappe.call()`.
- Private helper functions are prefixed with `_` consistently across all modules.

---

## Modules

### 1. Drawing Management

**Path:** `drawing_management/`

The core of the manufacturing flow. Engineers create **Drawing** documents linked to a Sales Order. Each drawing holds line items (parts/components) with quantities and raw material specifications.

**What was built:**
- **`Drawing` doctype** — custom document with child table `Drawing Item`. Tracks revision status, BOM linkage, and per-row qty/weight calculations. Validates completeness before submission.
- **`drawing_utils.py`** — whitelisted utility functions callable from JS:
  - `create_drawings_from_so` — auto-creates Drawing records from a Sales Order's items.
  - `create_bom_from_drawing` — generates an ERPNext BOM directly from a submitted Drawing.
  - `create_production_plan_from_bom` — chains BOM → Production Plan creation.
  - `mark_as_final_revision` — marks a drawing revision as the active version.
  - `parse_drawing_items_csv` — bulk-imports drawing line items from a CSV.
  - `get_batches_for_drawing_item` — returns available batch stock for a drawing's raw material.
- **`so_drawing_import.py`** — Excel-based bulk BOM import: parses a structured BOM template, validates raw materials, and creates Drawing + BOM records in one operation.
- **`bom_class_override.py`** — overrides the ERPNext `BOM` class to customise cost calculation, item rate lookup, BOM diff, and child-item queries.
- **`sales_order.py`** — hook on Sales Order `validate` to recalculate raw material quantities when SO quantities change.

**Custom child tables:** `Drawing Item`, `Production Plan BOM Raw Material`, `Sales Order Drawing Raw Material`, `Sales Order Duno Item`

---

### 2. Item Management

**Path:** `item_management/`

**What was customized:**
- Validates item configuration on save: enforces correct batch number series prefix, ensures UOM conversion factors are set, restricts changes to locked fields once transactions exist.
- `validate_batch_configuration` — ensures batch-tracked items have the correct batch series and naming rules.
- `validate_uom_configuration` — checks that weight UOM conversion factors are non-zero.
- `has_item_transactions` — whitelisted check used by the client to gate field editability.

---

### 3. Material Request Management

**Path:** `material_request_management/`

**What was customized:**
- `validate_material_request` — enforces that all MR items carry the custom weight/UOM fields before saving.
- `before_submit_material_request` — recalculates secondary qty (kg) from primary qty × UOM conversion factor, ensuring submitted MRs always have accurate weight data.
- `get_mr_item_uom` — whitelisted link-field query that filters UOM options to weight-compatible units for MR items.

---

### 4. Purchase Order Management

**Path:** `purchase_order_management/`

**What was customized:**
- `validate_purchase_order` / `before_submit_purchase_order` — same weight-field enforcement pattern as MR.
- `_recalculate_qty` — recalculates secondary qty on all PO items.
- `_check_missing_fields` — raises a combined validation error listing every row with missing data.
- `get_po_item_uom` — whitelisted UOM link-field query for PO items.

---

### 5. Purchase Receipt Management

**Path:** `purchase_receipt_management/`

**What was built/customized:**
- **Batch auto-creation on insert** — when a PR is created from a PO, `before_insert_batch` fires and `_setup_batch_from_purchase_receipt` creates a named Batch record automatically, copying supplier info, heat number, and custom fields from the PO item.
- `validate_purchase_receipt` / `before_submit_purchase_receipt` — weight-field validation consistent with MR/PO.
- `get_mp_for_pr` — given a PR, returns linked Material Planning documents for the received items.
- `allocate_pr_stock_to_mp` — whitelisted function that allocates newly received stock to an existing Material Planning reservation, updating batch mapping rows.
- `get_pr_item_uom` — whitelisted UOM link-field query for PR items.

---

### 6. RFQ Management

**Path:** `rfq_management/`

**What was customized:**
- `validate_rfq` — calls `_copy_from_mr_item` to propagate custom weight/UOM fields from the originating Material Request item into the RFQ line, so suppliers receive weight-aware quote requests.

---

### 7. Supplier Quotation Management

**Path:** `sq_management/`

**What was customized:**
- `validate_supplier_quotation` / `before_submit_supplier_quotation` — weight-field enforcement; copies from linked RFQ item if blank.
- `_recalculate_qty` — recalculates secondary qty on SQ items.
- `get_sq_item_uom` — whitelisted UOM link-field query for SQ items.

---

### 8. Production Management

**Path:** `production_management/`

The most complex module. Contains the **Material Planning** doctype (950+ lines) and hooks into Job Card and Stock Entry.

**What was built:**

#### Material Planning (Custom Doctype)
The central planning document that bridges a BOM/Sales Order with raw material allocation:

- `get_raw_materials` — explodes the BOM and fetches required raw material quantities.
- `check_stock_availability` — classifies each required item into three buckets:
  - **Exact Match** — batch in stock with sufficient secondary qty.
  - **Mapping** — partial stock; map multiple batches to cover the requirement.
  - **Unavailable** — no suitable stock; triggers purchase.
- `reserve_batches` / `unreserve_batches` — locks/unlocks batch secondary qty so the same coil isn't allocated to two jobs simultaneously.
- `reserve_exact_match_batches` / `unreserve_exact_match_batches` — handles the exact-match bucket separately.
- `finalize_mapping` — confirms the batch-to-item mapping and writes reservation records.
- `make_production_plan` — creates an ERPNext Production Plan from the Material Planning document.
- `make_material_request` — creates MRs for unavailable items directly from the planning document.
- `auto_purchase_from_mp` — end-to-end: creates MR → RFQ → SQ → PO for unavailable items in one action.
- `update_so_difference_kg` — reconciles planned vs. actual weights back to the Sales Order.

#### Job Card Hooks (`job_card.py`)
- `validate_job_card` — validates that transferred raw material quantities don't exceed what was allocated in the Material Planning batch mapping.
- `before_submit_manufacture_stock_entry` — fired on the linked Stock Entry; validates WIP stock before the manufacture entry is submitted.

#### Stock Entry Hooks (`stock_entry.py`)
- `validate_stock_entry` — validates batch qty availability for material transfer entries.
- `on_submit_stock_entry` — reduces `sec_qty` on consumed Batch records; releases Material Planning batch reservations; updates SCO/WO transferred and CNC weight fields.
- `on_cancel_stock_entry` — restores batch `sec_qty` and Material Planning reservations on cancellation.

#### Production Utils (`production_utils.py`)
- `get_routing_operations_for_bom` — whitelisted; returns routing operations for a BOM for use in the Material Planning JS.
- `get_raw_materials_for_job_card` — whitelisted; returns the raw material requirement for a Job Card factoring in prior transfers and subcontractor consumption.

#### Inspection Workflow (`inspection.py`)
QC sign-off workflow shared identically by Job Card and Supplier Operation Entry, scoped to the `Fitup Inspection` and `Final Inspection` routing operations only:
- `add_inspection_call` — whitelisted; logs a new inspection call round from the source doc's Inspection Call Date, auto-advancing Inspection Status Open → Working.
- `create_inspection_entry` — whitelisted; creates a draft **Inspection Entry** (submittable doctype) prefilled with traceability (Work Order/SCO/Production Plan/Sales Order/Customer/Supplier) from the latest pending call round.
- `on_submit_inspection_entry` — propagates the QC result back to the parent's Inspection Call Log row and sets overall Inspection Status to Completed (fully cleared) or Working (rework remains, awaiting the next call).
- `before_submit_job_card_inspection_gate` / `before_submit_soe_inspection_gate` — block Job Card/SOE submission for these two operations until Inspection Status is Completed.
- `_resolve_traceability` — resolves Sales Order/Customer from the source doc's own drawing-detail rows, falling back to the linked Work Order.

**Custom child tables:** `Job Card Raw Material`, `Material Planning Available Raw Material`, `Material Planning BOM Item`, `Material Planning Material Mapping`, `Material Planning Raw Material`, `Material Planning Unavailable Item`, `Production Plan Available Raw Material`, `Inspection Call Log` (one row per inspection call round, on Job Card and Supplier Operation Entry)

**Custom master doctypes:** `Storage Location`, `Store Location`, `Process Planning`

**Custom submittable doctype:** `Inspection Entry` — QC's Ok/Not Ok + Total Checked/Cleared/Rework Qty sign-off record for a single inspection round.

**Custom reports:** `Manufyxinvenza Stock Balance` — script report showing stock by batch with secondary qty (kg). `Inspection Status Report` — one row per inspection round across all Job Cards/SOEs at the two inspection checkpoints, with full traceability and rework history.

---

### 9. Production Plan Management

**Path:** `production_plan_management/`

**What was customized:**
- Overrides ERPNext's `get_items_for_material_requests` to inject Material Planning weight data into the material request generation flow.
- `get_mp_planned_weights` — returns planned weight totals per item from linked Material Planning docs.
- `get_pp_drawings_for_picker` — builds a drawing picker for the Production Plan UI, sourcing rows from both Material Planning documents and Sales Orders.
- `make_material_request` — custom version that creates MRs with weight fields populated.
- `after_save_production_plan` / `unlink_production_plan_on_trash` — maintain bidirectional links between Production Plan and Material Planning on save, cancel, and delete.
- `get_operations_from_routing` / `get_standard_routing_operations` — whitelisted helpers for the Production Plan operations table.

---

### 10. Subcontracting Management

**Path:** `subcontracting_management/`

**What was built:**

#### Supplier Operation Entry (Custom Doctype)
A custom document that tracks a subcontractor's work at drawing-item granularity — what was sent, what was processed (CNC'd/fabricated), what was returned, and what excess material remains.

Key lifecycle hooks:
- `validate_supplier_operation_entry` — validates quantities, drawing completions, and excess material.
- `before_submit_supplier_operation_entry` — final checks before committing the operation record.
- `on_submit_supplier_operation_entry` — propagates available/processed quantities to the next operation in sequence; updates SCO drawing item completion status.
- `on_update_supplier_operation_entry` / `before_delete_supplier_operation_entry` — maintain data integrity on edits and deletes.

#### Subcontracting Order Override (`overrides.py`)
- `CustomSubcontractingOrder` — extends ERPNext's SCO to support the PP-driven subcontracting flow.
- `CustomStockEntry` — extends Stock Entry to add SCO-aware weight tracking.

#### Subcontracting Utilities (`subcontracting.py`)
Whitelisted functions that drive the UI buttons on Production Plan, SCO, and Work Order:

| Function | Purpose |
|---|---|
| `create_sco_from_production_plan` | Creates a Subcontracting Order from a Production Plan |
| `create_work_order_from_pp` | Creates Work Orders for in-house operations |
| `create_supplier_operation_entries` | Bulk-creates SOE records for all operations on an SCO |
| `create_send_to_subcontractor_entry` | Stock Entry: transfers material from store to supplier warehouse |
| `create_cnc_to_supplier_entry` | Stock Entry: transfers CNC-processed material to supplier |
| `create_return_stock_entry` | Stock Entry: returns material from supplier back to store |
| `create_finished_goods_entry` | Stock Entry: books finished goods on SCO completion |
| `create_partial_transfer` | Partial material transfer for in-progress operations |
| `get_sco_pending_items` | Returns items still pending completion on an SCO |
| `get_soe_summary` | Dashboard summary of all SOE records for an SCO |
| `get_wo_pending_items` / `create_partial_wo_transfer` | Work Order equivalents of the SCO transfer functions |
| `create_cnc_to_wip_entry` | Transfers CNC output to WIP warehouse for Work Orders |
| `create_return_stock_entry_for_wo` | Returns unused material for Work Orders |
| `get_jc_summary` | Job Card completion summary for a Work Order |
| `backfill_drawing_item_qty` | Back-fills historical drawing qty data |

**Custom child tables:** `SCO Drawing Item`, `SCO Excess Material Item`, `SOE Consumption Log`, `SOE Drawing Detail`, `Supplier Operation Item`, `Job Card Consumption Log` (Job Card's own drawing-level consumption log — split from `SOE Consumption Log` so Job Card keeps Employee/From Time/To Time while the Supplier Operation Entry version stays lean)

#### Inspection Tab (own-schema fields, not fixtures)
Supplier Operation Entry carries the same Inspection tab as Job Card (Inspection Status, Inspection Call Date, Inspection Call Log table), gated to the `Fitup Inspection`/`Final Inspection` operations. Since SOE is an app-owned doctype, these fields live directly in its own `.json` rather than as Custom Field fixtures — see `production_management/inspection.py` (§8) for the shared logic.

---

## Custom Doctypes

| Doctype | Module | Type |
|---|---|---|
| Drawing | drawing_management | Primary document |
| Drawing Item | drawing_management | Child table |
| Nature of Work | drawing_management | Master |
| Production Plan BOM Raw Material | drawing_management | Child table |
| Sales Order Drawing Raw Material | drawing_management | Child table |
| Sales Order Duno Item | drawing_management | Child table |
| Material Planning | production_management | Primary document |
| Material Planning Available Raw Material | production_management | Child table |
| Material Planning BOM Item | production_management | Child table |
| Material Planning Material Mapping | production_management | Child table |
| Material Planning Raw Material | production_management | Child table |
| Material Planning Unavailable Item | production_management | Child table |
| Job Card Raw Material | production_management | Child table |
| Process Planning | production_management | Primary document |
| Production Plan Available Raw Material | production_management | Child table |
| Storage Location | production_management | Master |
| Store Location | production_management | Master |
| Inspection Entry | production_management | Primary document (submittable) |
| Inspection Call Log | production_management | Child table |
| Supplier Operation Entry | subcontracting_management | Primary document |
| Supplier Operation Item | subcontracting_management | Child table |
| SCO Drawing Item | subcontracting_management | Child table |
| SCO Excess Material Item | subcontracting_management | Child table |
| SOE Consumption Log | subcontracting_management | Child table |
| SOE Drawing Detail | subcontracting_management | Child table |
| Job Card Consumption Log | subcontracting_management | Child table |
| Manufyxinvenza Settings | manufyxinvenzaerp | Settings singleton |

---

## ERPNext Overrides

| ERPNext Doctype | Override | Location |
|---|---|---|
| BOM | `BOM` class — custom cost calc, item rate, BOM diff | `drawing_management/bom_class_override.py` |
| Subcontracting Order | `CustomSubcontractingOrder` — PP-driven SCO flow | `subcontracting_management/overrides.py` |
| Stock Entry | `CustomStockEntry` — SCO-aware weight tracking | `subcontracting_management/overrides.py` |
| Sales Order dashboard | Custom dashboard connections (Drawings) | `drawing_management/drawing_utils.py` |
| Subcontracting Order dashboard | Custom dashboard connections (SOE summary) | `subcontracting_management/subcontracting.py` |

Client-side JS is injected into these ERPNext doctypes via `app_include_js` / `doctype_js` hooks:

- **Item** — batch and UOM field controls
- **BOM** — drawing linkage and routing picker
- **Production Plan** — drawing picker, weight summary, SCO/WO creation buttons
- **Purchase Order** — weight UOM field and recalculation
- **Purchase Receipt** — weight UOM field and MP allocation button
- **Batch** — secondary qty display
- **Job Card** — raw material consumption grid, Inspection tab controls
- **Inspection Entry** — Ok/Not Ok, Rework Qty field behavior
- **Supplier Operation Entry** — consumption grid, Inspection tab controls

### A second, parallel client-side delivery mechanism: `setup.py` Client Scripts

**This app ships client-side JS through two independent mechanisms, not one** — a gap in this document until now (Phase 1 HP-03 / Report 2 §3.6, Report 4 of the internal audit series). Alongside the `public/js/*.js` files above (loaded via `hooks.py`'s `doctype_js`), `setup.py` also *installs Client Script database records* on every `after_install`/`after_migrate`, via ~17 `create_*_client_script()` functions (e.g. `create_purchase_order_client_script`, `create_production_plan_client_script`). These are force-synced (updated if they already exist, created if not) every time the app is installed or migrated — they are not fixtures, and `fixtures = ["Custom Field", "Property Setter"]` in `hooks.py` does not cover them.

**Doctypes driven by a `setup.py` Client Script:**

| Doctype | Also has a `public/js/*.js` file? |
|---|---|
| Item | Yes — `item.js` |
| Purchase Order | Yes — `purchase_order.js` |
| Purchase Receipt | Yes — `purchase_receipt.js` |
| BOM | Yes — `bom.js` |
| Production Plan | Yes — `production_plan.js` |
| Job Card (×2 scripts — consumption logic + drawing consumption) | Yes — `job_card.js` |
| Subcontracting Order (×2 scripts — main + ops) | No |
| Supplier Operation Entry | Yes — `supplier_operation_entry.js` |
| Work Order (×2 scripts — main + ops) | No |
| Material Request | No |
| Request for Quotation | No |
| Supplier Quotation | No |
| Sales Order | No |
| Stock Entry | No |

**Why this matters:** for the doctypes in the "Yes" column, **both** mechanisms are live for the same form at the same time — a developer editing the seemingly-complete `public/js/purchase_order.js` may not realize that some of the live dimension-recalculation/field-toggle behavior on that same form actually comes from `setup.py`'s embedded `PO_CLIENT_SCRIPT` string instead (or in addition). For the doctypes in the "No" column (Material Request, RFQ, Supplier Quotation, Sales Order, Stock Entry, Subcontracting Order, Work Order), `setup.py` is the **only** client-side delivery path — there is no `public/js/` file to look in at all. Before editing client-side behavior for any of these doctypes, check both `public/js/` and the corresponding `*_CLIENT_SCRIPT` string in `setup.py` (search for the doctype's `*_CLIENT_SCRIPT_NAME` constant near the top of the file).

---

## Fixtures & Custom Fields

All custom fields and property setters are managed as Frappe fixtures (not through `setup.py` at runtime in production). The fixture files are:

- `fixtures/custom_field.json` — all custom fields added to standard ERPNext doctypes
- `fixtures/property_setter.json` — field property overrides (mandatory, hidden, read-only flags)

Regenerate after changes:

```bash
bench --site manufact export-fixtures --app manufyxinvenzaerp
```

---

## Test Suite

Tests live in `tests/` and use Frappe's pytest integration (`bench run-tests`).

| Test file | What it covers |
|---|---|
| `test_material_planning.py` | Unit tests: exact-match, partial-stock, unavailable, mixed-item batch classification |
| `test_e2e_material_planning.py` | End-to-end flow: get raw materials → check stock → get batch item → make production plan |
| `test_purchase_order_creation.py` | PO creation from Material Planning unavailable items; supplier linking; partial selection |
| `test_alternate_item.py` | Alternate item substitution in unavailable rows |
| `test_classification_logic.py` | Stock classification edge cases |
| `test_po_edge_cases.py` | PO creation edge cases (MR cancel, multi-PO) |
| `test_unavailable_actions.py` | Actions on unavailable-item rows |

Run all tests:

```bash
bench --site manufact run-tests --app manufyxinvenzaerp
```

Run a single file:

```bash
bench --site manufact run-tests --module manufyxinvenzaerp.tests.test_material_planning
```

**CI gate (added 2026-07-16):** `.github/workflows/main.yml` now runs a `test` job — a fresh site, `bench run-tests --app manufyxinvenzaerp` — that the production `deploy` job depends on (`needs: test`). Previously the pipeline had no test-execution step at all; a failing test could not block a deploy. If `test` fails, `deploy` is skipped entirely and production is left untouched.

Two stray test-shaped files exist outside this convention, worth knowing about if `bench run-tests` behaves unexpectedly:
- `production_management/doctype/material_planning/test_material_planning.py` — a real (currently empty/placeholder) `FrappeTestCase`, just misplaced.
- `production_management/manual_release_check.py` — **not a real test** despite formerly being named `test_release.py` (renamed 2026-07-16). It's a one-off manual debug script with hardcoded document names and its own `frappe.db.commit()`, meant to be run deliberately via `bench execute manufyxinvenzaerp.production_management.manual_release_check.run` against a site that has the specific records it references — not picked up by `bench run-tests` anymore now that it no longer matches the `test_*.py` pattern.

---

## Installation

```bash
cd /path/to/frappe-bench
bench get-app https://github.com/your-org/manufyxinvenzaerp --branch main
bench --site your-site install-app manufyxinvenzaerp
bench --site your-site migrate
```

---

## Key Bench Commands

```bash
# Apply DB migrations after code changes
bench --site manufact migrate

# Clear cache
bench --site manufact clear-cache

# Build JS/CSS assets
bench build --app manufyxinvenzaerp

# Restart workers and web server
bench restart

# Export fixtures
bench --site manufact export-fixtures --app manufyxinvenzaerp

# Run all tests
bench --site manufact run-tests --app manufyxinvenzaerp

# Open console / REPL
bench --site manufact console
```

---

## License

MIT
