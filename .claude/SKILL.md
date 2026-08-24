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
| `.claude/references/hooks.md`       | Touching doc_events, override_doctype_class, or app lifecycle hooks               |
| `.claude/references/api.md`         | Adding or calling a `@frappe.whitelist()` method; checking existing API surface   |
| `.claude/references/deployment.md`  | Running bench commands, migrating, restarting, the CI pipeline and deploy backups |
| `.claude/references/client_change_request_progress.md` | Continuing the in-progress client change request — status of every phase, what's done, what's next |

## App architecture overview

```
manufyxinvenzaerp/
├── drawing_management/       # Drawing → BOM creation; BOM class override
│   ├── bom_class_override.py # Overrides ERPNext BOM with custom logic
│   ├── drawing_utils.py      # Whitelisted helpers: mark_as_final_revision,
│   │                         #   create_bom_from_drawing,
│   │                         #   create_production_plan_from_bom, parse_drawing_items_csv
│   ├── so_drawing_import.py  # The Sales Order BOM-sheet import: load, verify,
│   │                         #   create/submit drawings, create BOMs
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
│       ├── material_planning/          # Core planning doctype — largest controller
│       ├── cut_sheet/                  # One plate's nesting plan, shared across jobs
│       ├── manufyx_decision_log/       # Append-only: who reserved/reassigned/rounded up
│       ├── inspection_entry/           # QC result; also covers incoming goods
│       ├── process_planning/           # Process routing doctype
│       ├── job_card_raw_material/      # Child table
│       ├── material_planning_*         # Child tables: available_raw_material, bom_item,
│       │                               #   material_mapping, raw_material, unavailable_item
│       ├── production_plan_available_raw_material/
│       ├── storage_location/           # Master
│       └── store_location/             # Master
│
├── production_plan_management/   # Production Plan hooks
│   └── production_plan.py        # after_save_production_plan, make_material_request.
│                                 #   Also holds a dimension-aware rewrite of ERPNext's
│                                 #   get_items_for_material_requests that NOTHING CALLS —
│                                 #   never wired up via override_whitelisted_methods.
│                                 #   Left in place pending a decision.
│
├── subcontracting_management/    # Subcontracting Order override; Supplier Operation Entry
│   ├── overrides.py              # CustomSubcontractingOrder class
│   ├── subcontracting.py         # Whitelisted: create_sco_from_production_plan,
│   │                             #   create_supplier_operation_entries
│   │                             #   (Work Order / Job Card removed 2026-08-20; the
│   │                             #    SCO-keyed transfer functions removed 2026-08-24,
│   │                             #    superseded by material_issue_plan_transfer.py)
│   └── doctype/
│       ├── supplier_operation_entry/   # Custom doctype for subcontracting ops
│       └── supplier_operation_item/    # Child table
│
├── config/                   # Frappe app config (__init__.py only)
├── <module>/custom/          # Custom Field + Property Setter, one file per doctype.
│                             #   112 files, 848 fields, 337 property setters.
│                             #   Replaced fixtures/ on 2026-08-18 — see below.
├── manufyxinvenzaerp/page/   # Desk pages: bulk_permissions
├── public/js/                # Client-side JS injected into core doctypes:
│   │                         #   item.js, bom.js, production_plan.js,
│   │                         #   purchase_order.js, purchase_receipt.js
├── patches/                  # Data migration patches
└── tests/                    # 90 files, two kinds:
    ├── test_*.py             #   8 unittest modules, run by `bench run-tests`
                              #   and by CI. test_whitelist_coverage is the one to
                              #   keep green: it checks every dotted path the front
                              #   end calls is actually whitelisted, after a lost
                              #   decorator shipped a broken Reserve button to live.
    └── verify_*.py           #   74 standalone checks, each with a run() called
                              #   directly: `bench --site manufact execute
                              #   manufyxinvenzaerp.tests.<name>.run`
                              #   They print OK/FAIL per assertion and finish with
                              #   "ALL n CHECKS PASSED". Each one opens with WHY it
                              #   exists — the bug it was written for — so a failure
                              #   is readable without digging up the history.
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
- **Custom Field / Property Setter**: NOT fixtures any more (changed 2026-08-18). They live in
  per-doctype `<module>/custom/<doctype>.json` files — 112 files, 848 custom fields, 337 property
  setters — synced on every `bench migrate` by Frappe's own `sync_customizations`. Two things
  follow from that, and both have caught people out:
    - The sync only INSERTS and UPDATES. It never deletes, so removing a field from a JSON file
      does not remove it from a site; it just stops being managed. Delete it in the UI as well.
    - `setup.py` still creates ~140 of these fields through `create_custom_fields`, and it runs on
      `after_migrate`, AFTER the sync. So where the two disagree, **setup.py wins**. If you edit a
      field in Customize Form and re-export it, check `setup.py` does not define it differently or
      your change is overwritten on the next migrate.
  Re-export one doctype with `frappe.modules.utils.export_customizations(module, doctype,
  sync_on_migrate=True)` — the same function Customize Form's "Export Customizations" button calls.
  A file living in a module that is not in `modules.txt` will never sync, so keep them under the
  five registered modules.
- **Batch secondary qty**: several controllers track `sec_qty` on Batch records and
  release/restore on Stock Entry submit/cancel. The adjustment is a single atomic UPDATE
  (`_reduce_batch_sec_qty`) — never read-modify-write, or two entries consuming one batch
  lose a write between them.
- **Work Order and Job Card carry NO customizations.** Every field, client script, hook and
  helper this app once added to them was removed — first disabled under the client's Phase 0.4
  change request, then deleted outright on 2026-08-20 (1,827 lines). Subcontracting Order and
  Operation Entry do that work instead. Do not re-add anything to those two doctypes without
  checking why they were reverted.
- **`bom_class_override.py` is a copy of ERPNext's `bom.py`.** Its module-level functions
  (`get_children`, `item_query`, `make_variant_bom`, `get_bom_items`, `get_list_context`) are
  ERPNext's own, called by the BOM form and tree view by dotted path. A dead-code sweep will
  flag them as unreferenced because nothing in THIS app calls them. Removing them breaks the
  BOM form.
- **No scheduler_events** are registered (all commented out in hooks.py).

## This bench does not hot-reload

`bench start` runs the web server with Werkzeug's auto-reloader enabled, and it does
not work here -- touching a file leaves the serving child process untouched. Verified,
not assumed: `touch` on a controller, then watch the child PID stay put.

So **a code change has no effect on the local site until `bench start` is restarted**
(Ctrl+C in that terminal, then `bench start`). `bench restart` is a no-op on this bench
-- it is for supervisor/systemd, and this runs under honcho.

This costs real time when it is forgotten: a fix lands, the screen keeps showing the old
behaviour, and the obvious conclusion is that the fix was wrong. Two separate bugs were
re-reported that way. Check the serving process's start time against the file's mtime
before doubting the code:

```bash
ps -eo pid,lstart,cmd | grep "frappe serve" | grep -v grep
stat -c '%y' <the file you changed>
```

A fresh interpreter -- `bench console`, `bench execute`, `bench run-tests` -- always has
the current code, which is why a verify script can pass while the browser still fails.

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

# Re-export ONE doctype's customizations after changing its fields in the UI.
# There is no export-fixtures step any more — see "Custom Field / Property Setter".
bench --site manufact console
>>> from frappe.modules.utils import export_customizations
>>> export_customizations("Production Management", "Material Planning", sync_on_migrate=True)

# Run app tests
bench --site manufact run-tests --app manufyxinvenzaerp

# Run a single test file
bench --site manufact run-tests --module manufyxinvenzaerp.tests.test_material_planning

# Console / REPL
bench --site manufact console

# Reseed sample data helper
bench --site manufact execute manufyxinvenzaerp.sample_data.create_sample_data
```

## Deployment and CI

The pipeline is `.github/workflows/main.yml`, triggered by a push to `main`. A push to
`devbranch` whose commit message contains `[autodeploy]` is merged to `main` by
`auto-merge-devbranch.yml`, which is what starts it.

  1. **Test gate** — spins up a throwaway bench with MariaDB and two Redis service
     containers, installs the app, and runs the suite. It must pass before anything is
     deployed. The system-dependency step installs nothing when the runner image already
     has what is needed; it used to hang for six minutes on a stalled apt mirror.
  2. **SSH Deploy** — only runs when the repository variable `LIVE_DEPLOY` is `true`
     (Settings → Secrets and variables → Actions → Variables). Unset it to exercise CI
     without touching the live server.

Every deploy takes a database backup BEFORE anything is touched, checks it with `gzip -t`,
and copies it to `frappe-bench/deploy-backups` — out of Frappe's own backup folder, which
it prunes on its own schedule. Last 10 kept. Any failure rolls the code back to the commit
the server was on and restarts it; uncommitted edits found on the server are stashed, not
discarded. The database is deliberately NOT restored automatically — that would discard
whatever users did since the backup — so the log prints the restore command instead.

## Regenerating this knowledge base

Run `.claude/update_skill.sh` from the app root. It rewrites the four generated files —
`app_map.md`, `doctypes.md`, `hooks.md` and `api.md` — by rescanning the source. It is also
wired to the post-commit git hook, so it runs after every commit.

`SKILL.md` itself is hand-written and is NOT regenerated: anything above that a script
cannot infer — why Work Order carries no customizations, which sweeps produce false
positives, which of two mechanisms wins — has to be edited here by hand.
