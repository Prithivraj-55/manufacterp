# Manufyxinvenzaerp — Implemented Features
**App:** manufyxinvenzaerp | **Platform:** Frappe v15 / ERPNext v15 | **Site:** manufact
**Date:** 2026-06-16

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

- Uses `Store Location` (inventory dimension) for location-filtered stock queries.
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
  - For operations beyond the first: `Current Nos` cannot exceed `Previous Operation Nos`.
  - Nuts & Bolts: `manual_qty` cannot exceed WIP stock.
- **Previous Operation Data**: fetched from the preceding Job Card; falls back to the last submitted Supplier Operation Entry (for Scenario 3 hybrid subcontractor → internal handoff).

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
| Job Card | Raw Material Consumption child table, Dimensions per row |
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
| Process Planning | production_management | Child table on Production Plan — operation routing |
| Production Plan Available Raw Material | production_management | Child table |
| Storage Location / Store Location | production_management | Master doctypes for inventory dimension |
| Supplier Operation Entry | subcontracting_management | Per-operation subcontractor material consumption |
| Supplier Operation Item | subcontracting_management | Child table |

---

*This document covers all major features implemented in the custom app. Minor utility helpers, internal validation guards, and test scaffolding are not listed.*
