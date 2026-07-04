---
name: project1-manufyxinvenzaerp
description: >
  Load this skill whenever the user mentions: manufyxinvenzaerp, manufact site,
  drawing_management, item_management, material_request_management,
  production_management, production_plan_management, purchase_order_management,
  purchase_receipt_management, subcontracting_management, rfq_management,
  sq_management, Material Planning, Process Planning, Drawing, BOM override,
  Supplier Operation Entry, or any doctype/module in this app.
---

# Project: manufyxinvenzaerp

## Environment

| Key         | Value                                                    |
|-------------|----------------------------------------------------------|
| Bench       | frappe-bench1                                            |
| Site        | manufact                                                 |
| App         | manufyxinvenzaerp                                        |
| App root    | apps/manufyxinvenzaerp/                                  |
| Python pkg  | apps/manufyxinvenzaerp/manufyxinvenzaerp/                |
| Frappe      | v15                                                      |
| ERPNext     | v15                                                      |

## First thing every session

**Read `.claude/references/app_map.md` before doing anything else.**
It is the single source of truth for file paths, method names, and module layout
and is regenerated automatically on each git commit.

## Safety rule — never delete without asking first

**Never delete any file, database record, or other data — including your own
scratch/debug scripts and stray files you didn't create — without asking the
user for explicit permission first.** This applies even when a permission
mode that bypasses tool-call prompts (e.g. auto-accept) is active; that mode
governs tool-call approval, not this rule. Ask before running `rm`,
`frappe.delete_doc`, dropping/truncating anything, or any other irreversible
removal — no exceptions for "it's just a temp file" or "I made it, so it's
mine to clean up." If a file turns out to be unfamiliar or another party's
in-progress work, leave it alone and flag it instead of deleting it.

(This was violated once: a debug script was deleted via `rm -f` — including,
in one case, another party's uncommitted scratch file — without asking.
Ask first, every time, going forward.)

## Reference files — when to read what

| File                                | Read when …                                                                       |
|-------------------------------------|-----------------------------------------------------------------------------------|
| `.claude/references/app_map.md`     | Any task — always read first; contains full file inventory and method index       |
| `.claude/references/doctypes.md`    | Adding/changing a doctype, controller, or child table                             |
| `.claude/references/hooks.md`       | Touching doc_events, override_doctype_class, fixtures, or app lifecycle hooks     |
| `.claude/references/api.md`         | Adding or calling a `@frappe.whitelist()` method; checking existing API surface   |
| `.claude/references/deployment.md`  | Running bench commands, migrating, exporting fixtures, restarting                 |

## App architecture overview

```
manufyxinvenzaerp/
├── drawing_management/       # Drawing → BOM creation; BOM class override
│   ├── bom_class_override.py # Overrides ERPNext BOM with custom logic
│   ├── drawing_utils.py      # Whitelisted helpers: create_drawings_from_so,
│   │                         #   mark_as_final_revision, create_bom_from_drawing,
│   │                         #   create_production_plan_from_bom, parse_drawing_items_csv
│   └── doctype/
│       ├── drawing/          # Drawing doctype (controller + client JS)
│       ├── drawing_item/     # Child table for drawing line items
│       ├── nature_of_work/   # Master for work classification
│       └── production_plan_bom_raw_material/  # Child table
│
├── item_management/          # Item validation (batch config, UOM, item groups)
├── material_request_management/  # Material Request hooks + UOM custom field API
├── purchase_order_management/    # PO hooks + UOM custom field API
├── purchase_receipt_management/  # PR hooks, batch auto-creation on insert
├── rfq_management/           # RFQ validation, copies from MR item
├── sq_management/            # Supplier Quotation hooks + UOM API
│
├── production_management/    # Job Card, Stock Entry hooks; Material Planning doctype
│   ├── job_card.py           # validate_job_card, before_submit_manufacture_stock_entry
│   ├── stock_entry.py        # validate/on_submit/on_cancel; batch reservation release
│   ├── production_utils.py   # routing/workstation helpers; whitelisted: get_routing_operations_for_bom,
│   │                         #   get_raw_materials_for_job_card
│   └── doctype/
│       ├── material_planning/          # Core planning doctype — largest controller (950+ lines)
│       ├── process_planning/           # Process routing doctype
│       ├── job_card_raw_material/      # Child table
│       ├── material_planning_*         # Child tables: available_raw_material, bom_item,
│       │                               #   material_mapping, raw_material, unavailable_item
│       ├── production_plan_available_raw_material/
│       ├── storage_location/           # Master
│       └── store_location/             # Master
│
├── production_plan_management/   # Production Plan hooks; overrides get_items_for_material_requests
│   └── production_plan.py        # after_save_production_plan, make_material_request
│
├── subcontracting_management/    # Subcontracting Order override; Supplier Operation Entry
│   ├── overrides.py              # CustomSubcontractingOrder class
│   ├── subcontracting.py         # Whitelisted: create_sco_from_production_plan,
│   │                             #   create_work_order_from_pp, create_supplier_operation_entries,
│   │                             #   create_send_to_subcontractor_entry, create_wip_transfer_stock_entry,
│   │                             #   create_return_stock_entry
│   └── doctype/
│       ├── supplier_operation_entry/   # Custom doctype for subcontracting ops
│       └── supplier_operation_item/    # Child table
│
├── config/                   # Frappe app config (__init__.py only)
├── fixtures/                 # custom_field.json, property_setter.json (exported via bench)
├── public/js/                # Client-side JS injected into core doctypes:
│   │                         #   item.js, bom.js, production_plan.js,
│   │                         #   purchase_order.js, purchase_receipt.js
├── patches/                  # Data migration patches
└── tests/                    # Test suite (pytest via bench)
    ├── test_material_planning.py
    ├── test_e2e_material_planning.py
    ├── test_purchase_order_creation.py
    ├── test_alternate_item.py
    ├── test_classification_logic.py
    ├── test_po_edge_cases.py
    └── test_unavailable_actions.py
```

## Coding conventions

- **Hook pattern**: event handlers are top-level functions with signature `(doc, method)`,
  located in `<module>/<doctype_name>.py` or `<module>/<concern>.py`. Never use Document
  subclasses for ERPNext standard doctypes — use `doc_events` in hooks.py instead.
- **Whitelist API**: `@frappe.whitelist()` on standalone functions; called from JS via
  `frappe.call({ method: 'manufyxinvenzaerp.<module>.<file>.<fn>' })`.
- **Private helpers**: prefix with `_` (e.g. `_recalculate_qty`, `_check_missing_fields`).
  Consistent across all modules.
- **Class overrides**: `override_doctype_class` in hooks.py points to a class that extends
  the ERPNext base class (e.g. `BOM(ERPNextBOM)`, `CustomSubcontractingOrder`).
- **Custom UOM fields**: each procurement/supply-chain doctype has a whitelisted
  `get_<X>_item_uom` link-field query (PO, PR, MR, SQ).
- **Fixtures**: only `Custom Field` and `Property Setter` are exported; run
  `bench --site manufact export-fixtures` to regenerate `fixtures/*.json`.
- **Batch secondary qty**: several controllers track `sec_qty` on Batch records and
  release/restore on Stock Entry submit/cancel.
- **No scheduler_events** are registered (all commented out in hooks.py).

## Quick bench commands

```bash
# Run from /home/craft/frappe-bench1/

# Apply DB migrations after code changes
bench --site manufact migrate

# Clear redis + file cache
bench --site manufact clear-cache

# Build JS/CSS assets
bench build --app manufyxinvenzaerp

# Restart workers and web server
bench restart

# Export fixtures (Custom Field, Property Setter)
bench --site manufact export-fixtures --app manufyxinvenzaerp

# Run app tests
bench --site manufact run-tests --app manufyxinvenzaerp

# Run a single test file
bench --site manufact run-tests --module manufyxinvenzaerp.tests.test_material_planning

# Console / REPL
bench --site manufact console

# Reseed sample data helper
bench --site manufact execute manufyxinvenzaerp.sample_data.create_sample_data
```

## Regenerating this knowledge base

Run `.claude/update_skill.sh` from the app root to rescan and rewrite
`.claude/references/app_map.md`. This is also wired to the post-commit git hook so it
runs automatically after every commit.
