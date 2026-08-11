"""Verify the Cut Sheet chain: one sheet cut for two marks, issued in stages.

The original Cut Sheet build handled the simple case — one row, one batch, one
transfer. This covers what the shop floor actually does, and the three ways the
old version got it wrong:

A. One sheet, several marks. A batch can carry SEVERAL Cut Sheet rows. They chain:
   row 1 cuts from the full sheet, row 2 cuts from row 1's balance, and the batch
   ends at the last COMPLETED cut. The old code kept only one row in a dict keyed
   by (item_code, batch_no) and applied that single balance to every line.

B. Partial transfers. A cut that is only half issued must not shrink the batch yet.

C. Cancellation. Cancelling a transfer puts the stock back, so the batch has to go
   back to the size it was before that cut, rather than keeping the offcut's
   dimensions while holding the full piece again.

Also covers the planning-side seed: a cut plan entered in Material Planning reaches
the Material Issue Plan, and an adjustment made on the Material Issue Plan survives
a later refresh (the precedence rule).

Uses a Plates item so Width genuinely participates in the Kg formula:
Kg = (L/1000) x (W/1000) x T x unit_weight x Sec Qty.

Run via: bench --site manufact execute manufyxinvenzaerp.tests.verify_cut_sheet_chain.run
"""

import frappe
from frappe.utils import flt, today

from manufyxinvenzaerp.tests.create_full_test_entry import get_ctx, ensure_item
from manufyxinvenzaerp.subcontracting_management.doctype.material_issue_plan.material_issue_plan import (
    populate_from_production_plan,
    refresh_mip_raw_materials,
)
from manufyxinvenzaerp.subcontracting_management.material_issue_plan_transfer import (
    get_mip_pending_items,
    create_mip_partial_transfer,
)

RESULTS = []
UW = 7.85          # kg per mm-thickness per m^2, the usual steel figure
THICK = 5.0


def check(label, cond, detail=""):
    RESULTS.append((label, bool(cond)))
    print(("PASS" if cond else "FAIL") + " -- " + label + (("  | " + detail) if detail else ""))


def plate_kg(length, width, sec_qty):
    return flt((length / 1000.0) * (width / 1000.0) * THICK * UW * sec_qty, 3)


def batch_dims(batch_no):
    return frappe.db.get_value(
        "Batch", batch_no, ["custom_length", "custom_width", "custom_sec_qty"], as_dict=True)


def run():
    ctx = get_ctx()
    item = ensure_item(ctx, "ZZTEST-CUTSHEET", "Cut Sheet Chain Test Plate", uom="Kg")
    frappe.db.set_value("Item", item, {
        "custom_parent_item_group": "Plates", "custom_unit_weight": UW,
        "create_new_batch": 1, "custom_batch_prefix": "ZZCUT",
    })

    # The sheet: 1800 x 6300 x 5. Cut 1 takes 1800x3000, leaving 1800x3300.
    # Cut 2 takes 1800x2000 out of that, leaving 1800x1300.
    SHEET_L, SHEET_W = 1800.0, 6300.0
    sheet_kg = plate_kg(SHEET_L, SHEET_W, 1)
    cut1_use, cut1_bal = plate_kg(1800, 3000, 1), plate_kg(1800, 3300, 1)
    cut2_use, cut2_bal = plate_kg(1800, 2000, 1), plate_kg(1800, 1300, 1)
    print("sheet %s Kg | cut1 use %s bal %s | cut2 use %s bal %s"
          % (sheet_kg, cut1_use, cut1_bal, cut2_use, cut2_bal))

    bom = frappe.db.get_value("BOM", {"docstatus": 1, "is_active": 1},
                              ["name", "item", "quantity"], as_dict=True)
    stock_uom = frappe.db.get_value("Item", bom.item, "stock_uom") or "Nos"

    # Receive the sheet as one batch.
    se = frappe.new_doc("Stock Entry")
    se.stock_entry_type, se.company, se.posting_date = "Material Receipt", ctx.company, today()
    se.append("items", {
        "item_code": item, "qty": sheet_kg, "uom": "Kg", "t_warehouse": ctx.warehouse,
        "basic_rate": 50, "allow_zero_valuation_rate": 1,
        "custom_parent_item_group": "Plates", "custom_unit_weight": UW,
        "custom_length": SHEET_L, "custom_width": SHEET_W, "custom_thickness": THICK,
        "custom_sec_qty": 1,
    })
    se.insert(ignore_permissions=True)
    se.submit()
    batch_no = frappe.db.get_value("Batch", {"reference_doctype": "Stock Entry",
                                             "reference_name": se.name, "item": item}, "name")
    print("sheet received as batch", batch_no)

    # Material Planning: two mapping rows for two marks, both on this one batch,
    # with the cut plan entered HERE (planning side).
    mp = frappe.new_doc("Material Planning")
    mp.company, mp.posting_date, mp.for_warehouse = ctx.company, today(), ctx.warehouse
    for idx, (duno, use_w, bal_w) in enumerate(
            [("DUNO-CUT-1", 3000, 3300), ("DUNO-CUT-2", 2000, 1300)], start=1):
        mp.append("material_mapping", {
            "item_code": item, "item_name": "Cut Sheet Chain Test Plate",
            "parent_item_group": "Plates", "unit_weight": UW,
            "length": SHEET_L, "width": use_w, "thickness": THICK,
            "qty": plate_kg(SHEET_L, use_w, 1), "uom": "Kg", "sec_qty": 1, "sec_uom": "Nos",
            "duno_mark_no": duno,
            "batch": batch_no, "planned_item": item, "batch_mapped": "Mapped",
            "batch_parent_item_group": "Plates", "batch_length": SHEET_L,
            "batch_width": use_w, "batch_thickness": THICK, "batch_unit_weight": UW,
            "batch_sec_qty": 1, "batch_calc_qty": plate_kg(SHEET_L, use_w, 1),
            "reserve_without_dimensions": 1,
            "cut_sheet": 1, "use_length": SHEET_L, "use_width": use_w, "use_sec_qty": 1,
            "balance_length": SHEET_L, "balance_width": bal_w, "balance_sec_qty": 1,
        })
    mp.insert(ignore_permissions=True)

    print("\n=== planning-side cut plan ===")
    mp.reload()
    check("Material Planning computes W1 for cut 1",
          abs(flt(mp.material_mapping[0].use_calc_qty) - cut1_use) < 0.01,
          "%s vs %s" % (mp.material_mapping[0].use_calc_qty, cut1_use))
    check("Material Planning computes W2 for cut 2",
          abs(flt(mp.material_mapping[1].balance_calc_qty) - cut2_bal) < 0.01,
          "%s vs %s" % (mp.material_mapping[1].balance_calc_qty, cut2_bal))

    for r in mp.material_mapping:
        frappe.db.set_value("Material Planning Material Mapping", r.name,
                            {"is_reserved": 1, "reserved_qty": r.batch_calc_qty},
                            update_modified=False)
    frappe.db.commit()

    pp = frappe.new_doc("Production Plan")
    pp.custom_type, pp.company, pp.posting_date, pp.get_items_from = "Internal Job", ctx.company, today(), ""
    pp.append("po_items", {
        "item_code": bom.item, "bom_no": bom.name, "planned_qty": bom.quantity or 1,
        "stock_uom": stock_uom, "custom_material_planning": mp.name,
    })
    pp.append("custom_process_planning", {"operation_name": "Material Issue", "work_type": "Internal Jobcard"})
    pp.insert(ignore_permissions=True)
    pp.submit()

    # Transfers resolve their target warehouse through the linked execution document,
    # so the plan needs a Subcontracting Order before anything can be issued.
    from manufyxinvenzaerp.subcontracting_management.subcontracting import (
        create_sco_from_production_plan,
    )
    sco_name = create_sco_from_production_plan(pp.name)

    mip = frappe.new_doc("Material Issue Plan")
    mip.company, mip.posting_date = ctx.company, today()
    mip.production_plan = pp.name
    mip.subcontracting_order = sco_name
    mip.source_warehouse = ctx.warehouse
    # Must differ from the source: a Stock Entry cannot move material to where it
    # already is. An Internal Job has no supplier, so this is the WIP warehouse.
    mip.supplier_warehouse = frappe.db.get_value(
        "Warehouse", {"company": ctx.company, "is_group": 0, "name": ["!=", ctx.warehouse]}, "name")
    mip.excess_return_warehouse = ctx.warehouse
    mip.insert(ignore_permissions=True)
    populate_from_production_plan(mip.name)

    print("\n=== the cut plan reaches the Material Issue Plan ===")
    mip.reload()
    rows = [r for r in mip.raw_materials if r.item_code == item]
    check("both cut rows arrived", len(rows) == 2, "%s rows" % len(rows))
    check("cut plan was seeded from Material Planning",
          all(r.cut_sheet for r in rows) and abs(flt(rows[0].use_calc_qty) - cut1_use) < 0.01,
          "cut_sheet=%s W1=%s" % ([r.cut_sheet for r in rows], rows[0].use_calc_qty))

    # An adjustment made here must survive a refresh triggered later.
    d = frappe.get_doc("Material Issue Plan", mip.name)
    target = next(r for r in d.raw_materials if r.duno_mark_no == "DUNO-CUT-1")
    target.use_width = 3100
    d.save(ignore_permissions=True)
    frappe.db.commit()
    refresh_mip_raw_materials(mip.name)
    d.reload()
    kept = next(r for r in d.raw_materials if r.duno_mark_no == "DUNO-CUT-1")
    check("an adjustment on the Material Issue Plan survives a refresh",
          flt(kept.use_width) == 3100, "use_width=%s" % kept.use_width)

    # Put it back so the arithmetic below stays clean.
    kept.use_width = 3000
    d.save(ignore_permissions=True)
    frappe.db.commit()

    print("\n=== only W1 is offered for transfer ===")
    pending = [p for p in get_mip_pending_items(mip.name) if p["item_code"] == item]
    offered = sum(flt(p["qty"]) for p in pending)
    check("transfer is capped at the cut plan, not the whole sheet",
          offered + 0.01 < sheet_kg, "offered %s of a %s Kg sheet" % (flt(offered, 3), sheet_kg))

    print("\n=== B: a half-issued cut must not resize the batch ===")
    row = pending[0]
    half = dict(row); half["qty"] = flt(flt(row["qty"]) / 2, 3)
    se1 = create_mip_partial_transfer(mip.name, frappe.as_json([half]), "primary")
    frappe.get_doc("Stock Entry", se1).submit()
    dims = batch_dims(batch_no)
    check("batch still full width after a partial cut",
          flt(dims.custom_width) == SHEET_W, "width=%s" % dims.custom_width)

    print("\n=== A: completing cut 1 resizes to ITS balance, not cut 2's ===")
    pending = [p for p in get_mip_pending_items(mip.name) if p["item_code"] == item]
    rest = pending[0]
    rest = dict(rest); rest["qty"] = flt(flt(row["qty"]) - half["qty"], 3)
    se2 = create_mip_partial_transfer(mip.name, frappe.as_json([rest]), "primary")
    frappe.get_doc("Stock Entry", se2).submit()
    dims = batch_dims(batch_no)
    check("batch is now cut 1's balance (1800x3300)",
          flt(dims.custom_width) == 3300, "width=%s (cut2 balance would be 1300)" % dims.custom_width)

    print("\n=== C: cancelling that transfer puts the sheet back ===")
    frappe.get_doc("Stock Entry", se2).cancel()
    dims = batch_dims(batch_no)
    check("batch returns to the pre-cut width once the cut is undone",
          flt(dims.custom_width) == SHEET_W, "width=%s" % dims.custom_width)

    frappe.db.commit()
    print("\n=== SUMMARY ===")
    failed = [l for l, ok in RESULTS if not ok]
    print("FAILURES: %s" % failed if failed else "ALL %d CHECKS PASSED" % len(RESULTS))
    print("Test data left in place: %s %s %s %s" % (mp.name, pp.name, mip.name, batch_no))
