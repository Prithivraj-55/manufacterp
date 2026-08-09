"""Transfer / CNC / excess-return Stock Entries issued from a Material Issue Plan.

Mirrors the equivalent SCO functions in subcontracting.py (create_send_to_subcontractor_entry,
get_sco_pending_items, create_partial_transfer, create_cnc_to_supplier_entry,
create_return_stock_entry) but keyed by Material Issue Plan instead of SCO/WO directly, so a
single implementation serves both this round (SCO) and the deferred WO round without changes.
Every Stock Entry created here dual-writes custom_mip_ref alongside the standard
subcontracting_order/custom_sco_ref (or custom_wo_ref) fields, so the existing SCO/WO weight
rollups in production_management/stock_entry.py keep working unchanged, fed by these entries
instead of the old SCO-button-created ones.
"""

import json as _json
import math

import frappe
from frappe import _
from frappe.utils import flt

from manufyxinvenzaerp.subcontracting_management.subcontracting import _get_mp_reserved_batches
from manufyxinvenzaerp.subcontracting_management.doctype.material_issue_plan.material_issue_plan import (
    get_target_context,
)
from manufyxinvenzaerp.utils.dimension_formula import calculate_qty

_DIMENSION_DRIVEN_GROUPS = {"Structurals", "Plates"}


def _ensure_mip_editable(mip):
    """Server-side lock: once a Material Issue Plan is Completed (see
    _maybe_mark_completed), block every action here that would create a new Stock
    Entry against it. Defense-in-depth alongside disable_form() in
    material_issue_plan.js, which is what actually hides these buttons in the UI --
    this guard is what stops a direct/scripted call from bypassing that."""
    if mip.status == "Completed":
        frappe.throw(_("{0} is Completed and locked for further changes.").format(mip.name))


def _linked_mp_names(mip):
    return _linked_mp_names_and_duno_scope(mip)[0]


def _linked_mp_names_and_duno_scope(mip):
    """Material Plannings linked to this MIP's Production Plan items, each paired
    with the set of DUNO/Mark Nos this Production Plan actually covers for it.

    A single Material Planning document can be shared across several Production
    Plans -- only some of its drawings pulled into any one of them at a time.
    Without this scope, every reserved batch in the WHOLE Material Planning gets
    offered for transfer here, including batches reserved for drawings that
    belong to a completely different, not-yet-planned job (they'd move to the
    wrong supplier/warehouse if transferred from here). A Material Planning where
    any po_items row is missing a duno_mark_no falls back to no filtering for it
    -- the same "take the whole Material Planning's totals" fallback already used
    elsewhere (create_sco_from_production_plan) for undated rows.
    """
    pp = frappe.get_doc("Production Plan", mip.production_plan)
    mp_names = []
    seen = set()
    dunos_by_mp = {}
    has_blank_by_mp = set()
    for pi in pp.po_items:
        mp_name = pi.get("custom_material_planning")
        if not mp_name:
            continue
        if mp_name not in seen:
            seen.add(mp_name)
            mp_names.append(mp_name)
        duno = pi.get("custom_duno_mark_no")
        if duno:
            dunos_by_mp.setdefault(mp_name, set()).add(duno)
        else:
            has_blank_by_mp.add(mp_name)
    duno_scope = {mp: (None if mp in has_blank_by_mp else dunos_by_mp.get(mp)) for mp in mp_names}
    return mp_names, duno_scope


def _tag_stock_entry(se_dict, mip_name, ctx):
    se_dict["custom_mip_ref"] = mip_name
    se_dict[ctx.link_field] = ctx.name
    se_dict[ctx.ref_field] = ctx.name
    return se_dict


@frappe.whitelist()
def get_mip_pending_items(mip_name):
    """Raw-material items reserved for this plan but not yet transferred. Each row
    also carries duno_mark_no/drawing so the transfer popup can filter by them."""
    mip = frappe.get_doc("Material Issue Plan", mip_name)
    ctx = get_target_context(mip)
    if not mip.source_warehouse:
        frappe.throw(_("Please set the Source Warehouse (RM) on this Material Issue Plan first."))

    source_warehouse = mip.source_warehouse
    primary_warehouse = ctx.primary_warehouse
    cnc_warehouse = mip.cnc_warehouse or ""

    raw_items = []
    mp_names, duno_scope = _linked_mp_names_and_duno_scope(mip)
    # Round Up Sec Qty for Transfer (Material Planning field, default on): when several
    # drawings share one purchased batch, the combined Sec Qty needed for one transfer can
    # come out fractional (e.g. 13.982 Nos) -- physically impossible to hand over. If ANY
    # linked Material Planning has this enabled, round up below; off keeps the exact
    # fractional Kg calculation this function has always returned.
    round_up_enabled = any(
        frappe.db.get_value("Material Planning", m, "round_up_transfer_sec_qty") for m in mp_names
    )
    for mp_name in mp_names:
        raw_items.extend(_get_mp_reserved_batches(
            mp_name, source_warehouse, primary_warehouse, duno_filter=duno_scope.get(mp_name)
        ))

    # Cut Sheet (client change request Phase 5.2): a row flagged Cut Sheet only
    # ever offers its To Use (W1) qty for transfer -- the Balance (W2) portion
    # is what the same batch gets resized down to on submit, not more material
    # to send onward. Capping here (rather than after the primary_done/cnc_done
    # netting below) means once W1 has been fully transferred, this row simply
    # stops appearing as pending -- the untransferred remainder is never offered.
    cut_sheet_qty_by_key = {
        (r.item_code, r.batch_no): flt(r.use_calc_qty)
        for r in (mip.raw_materials or [])
        if r.cut_sheet and r.batch_no
    }
    for item in raw_items:
        cap = cut_sheet_qty_by_key.get((item["item_code"], item.get("batch_no")))
        if cap is not None:
            item["qty"] = flt(min(flt(item["qty"]), cap), 3)

    if not raw_items:
        return []

    # duno/drawing/sales_order/customer_drawing_number lookup per (item_code, batch_no),
    # from the MIP's own raw_materials snapshot, for the transfer popup's filters.
    duno_by_key = {
        (r.item_code, r.batch_no or ""): r.duno_mark_no or "" for r in (mip.raw_materials or [])
    }
    so_by_key = {
        (r.item_code, r.batch_no or ""): r.sales_order or "" for r in (mip.raw_materials or [])
    }
    cdn_by_key = {
        (r.item_code, r.batch_no or ""): r.customer_drawing_number or "" for r in (mip.raw_materials or [])
    }
    drawing_by_duno = {d.duno_mark_no: d.drawing for d in (mip.drawing_items or []) if d.duno_mark_no}

    totals = {}
    for item in raw_items:
        is_cnc = bool(item.get("cnc_process")) and bool(cnc_warehouse)
        key = (item["item_code"], item.get("batch_no") or "", is_cnc)
        if key in totals:
            totals[key]["qty"] = flt(totals[key]["qty"] + item["qty"], 3)
            totals[key]["custom_sec_qty"] = flt(
                totals[key]["custom_sec_qty"] + item.get("custom_sec_qty", 0), 3
            )
        else:
            totals[key] = dict(item)
            totals[key]["cnc_process"] = 1 if is_cnc else 0

    primary_done = {}
    for r in frappe.db.sql("""
        SELECT sed.item_code, sed.batch_no, SUM(sed.qty) AS qty
        FROM `tabStock Entry Detail` sed
        JOIN `tabStock Entry` se ON se.name = sed.parent
        WHERE se.custom_mip_ref = %s
          AND se.stock_entry_type = %s
          AND se.docstatus != 2
        GROUP BY sed.item_code, sed.batch_no
    """, (mip_name, ctx.primary_se_type), as_dict=True):
        primary_done[(r.item_code, r.batch_no or "")] = flt(r.qty)

    cnc_done = {}
    if cnc_warehouse:
        for r in frappe.db.sql("""
            SELECT sed.item_code, sed.batch_no, SUM(sed.qty) AS qty
            FROM `tabStock Entry Detail` sed
            JOIN `tabStock Entry` se ON se.name = sed.parent
            WHERE se.custom_mip_ref = %s
              AND se.stock_entry_type = 'Material Transfer'
              AND se.docstatus != 2
              AND sed.t_warehouse = %s
            GROUP BY sed.item_code, sed.batch_no
        """, (mip_name, cnc_warehouse), as_dict=True):
            cnc_done[(r.item_code, r.batch_no or "")] = flt(r.qty)

    result = []
    for (item_code, batch_no, is_cnc), item in totals.items():
        done_qty = (cnc_done if is_cnc else primary_done).get((item_code, batch_no), 0)
        pending_qty = flt(item["qty"] - done_qty, 3)
        if pending_qty <= 0:
            continue
        total_qty = flt(item["qty"])
        ratio = pending_qty / total_qty if total_qty else 0
        duno = duno_by_key.get((item_code, batch_no), "")
        result.append({
            "item_code": item_code,
            "item_name": frappe.db.get_value("Item", item_code, "item_name") or item_code,
            "batch_no": batch_no,
            "qty": pending_qty,
            "uom": item.get("uom") or "Kg",
            "custom_sec_qty": flt(flt(item.get("custom_sec_qty", 0)) * ratio, 3),
            "custom_sec_uom": item.get("custom_sec_uom") or "",
            "s_warehouse": source_warehouse,
            "t_warehouse": cnc_warehouse if is_cnc else primary_warehouse,
            "cnc_process": 1 if is_cnc else 0,
            "use_serial_batch_fields": 1,
            "custom_length": flt(item.get("custom_length", 0), 3),
            "custom_width": flt(item.get("custom_width", 0), 3),
            "custom_thickness": flt(item.get("custom_thickness", 0), 3),
            "custom_unit_weight": flt(item.get("custom_unit_weight", 0), 4),
            "custom_parent_item_group": item.get("custom_parent_item_group") or "",
            "duno_mark_no": duno,
            "drawing": drawing_by_duno.get(duno, ""),
            "sales_order": so_by_key.get((item_code, batch_no), ""),
            "customer_drawing_number": cdn_by_key.get((item_code, batch_no), ""),
        })

    if round_up_enabled:
        _round_up_sec_qty(result)

    return result


def _round_up_sec_qty(rows):
    """Round each row's Sec Qty up to the next whole piece (Structurals/Plates only --
    the only groups where Sec Qty means a discrete physical piece), bumping its Kg to
    match via this row's own Kg-per-piece. The bump (round_up_excess_kg, 0 when no
    rounding was needed) travels with the row through the transfer popup's client-side
    selection and back into create_mip_partial_transfer/create_mip_transfer_entry, which
    log it as excess material to return once the transfer is actually created -- this
    function only computes the numbers, it never writes anything itself."""
    for row in rows:
        row["round_up_excess_kg"] = 0.0
        row["round_up_excess_pieces"] = 0.0
        if row.get("custom_parent_item_group") not in _DIMENSION_DRIVEN_GROUPS:
            continue
        sec_qty = flt(row.get("custom_sec_qty"))
        qty = flt(row.get("qty"))
        if sec_qty <= 0 or qty <= 0:
            continue
        kg_per_piece = qty / sec_qty
        rounded = math.ceil(flt(sec_qty, 6) - 0.001)
        if rounded <= sec_qty + 0.001:
            continue
        excess_pieces = rounded - sec_qty
        excess_kg = flt(excess_pieces * kg_per_piece, 3)
        row["qty"] = flt(qty + excess_kg, 3)
        row["custom_sec_qty"] = flt(rounded, 3)
        row["round_up_excess_kg"] = excess_kg
        row["round_up_excess_pieces"] = flt(excess_pieces, 3)


def _log_round_up_excess(mip, items):
    """After a transfer whose Sec Qty was rounded up (see _round_up_sec_qty), log the
    rounding surplus into excess_return_items so it flows through the existing Return
    Excess Entry workflow once physically confirmed. Keyed by (item_code, batch_no) via
    the same source_table/source_row find-or-update pattern
    _sync_excess_return_from_raw_materials already uses -- a second transfer that rounds
    up the SAME item/batch again ACCUMULATES into the one existing row instead of piling
    up a new row every time.

    Length/Width/Thickness are seeded from the BATCH's own standard dimensions (not left
    at 0) and Sec Qty from the fractional excess-piece count -- together these recompute
    back to exactly the tracked excess Kg, so the Return Excess Entry dialog shows a
    correct, non-zero starting figure instead of losing the tracked amount the moment it's
    opened (its live preview recalculates Qty FROM these fields). This is still only a
    placeholder, standing in for "one standard piece, mostly unused" -- the real leftover
    is almost never that shape, so the user is expected to overwrite these with whatever
    they actually measure once the job cuts the material, same as any other excess row."""
    SOURCE_TABLE = "Round Up Sec Qty for Transfer"
    by_key = {
        (r.source_table, r.source_row): r
        for r in (mip.excess_return_items or [])
        if r.source_table == SOURCE_TABLE
    }
    changed = False
    for item in items:
        excess_kg = flt(item.get("round_up_excess_kg"))
        if excess_kg <= 0:
            continue
        excess_pieces = flt(item.get("round_up_excess_pieces"))
        length = flt(item.get("custom_length"))
        width = flt(item.get("custom_width"))
        thickness = flt(item.get("custom_thickness"))
        source_row = f"{item['item_code']}|{item.get('batch_no') or ''}"
        key = (SOURCE_TABLE, source_row)
        target = by_key.get(key)
        if target and (target.stock_entry_created or target.mapped_material_planning):
            # Already returned to stock, or already claimed elsewhere -- start a fresh
            # row instead of drifting a historical, already-settled entry.
            target = None
        if target:
            new_qty = flt(flt(target.qty) + excess_kg, 3)
            new_pieces = flt(flt(target.sec_qty) + excess_pieces, 3)
            target.qty = new_qty
            target.sec_qty = new_pieces
            if not target.length:
                target.length = length
            if not target.width:
                target.width = width
            if not target.thickness:
                target.thickness = thickness
        else:
            target = mip.append("excess_return_items", {
                "source_table": SOURCE_TABLE,
                "source_row": source_row,
                "item_code": item["item_code"],
                "item_name": item.get("item_name") or item["item_code"],
                "parent_item_group": item.get("custom_parent_item_group") or "",
                "unit_weight": flt(item.get("custom_unit_weight")),
                "length": length,
                "width": width,
                "thickness": thickness,
                "sec_qty": excess_pieces,
                "sec_uom": item.get("custom_sec_uom") or "",
                "uom": item.get("uom") or "Kg",
                "qty": excess_kg,
                "return_type": "Return to Own Warehouse",
                "return_reason": _(
                    "Rounding surplus from \"Round Up Sec Qty for Transfer\" -- placeholder "
                    "dimensions (standard piece size); confirm the exact leftover once "
                    "this material is cut."
                ),
            })
            by_key[key] = target
        changed = True
    if changed:
        mip.save(ignore_permissions=True)


@frappe.whitelist()
def has_cnc_stock(mip_name):
    """Returns True if at least one submitted Stock Entry has transferred material
    to this MIP's CNC warehouse, so the UI can conditionally show 'CNC to Supplier/WIP'."""
    mip = frappe.get_cached_doc("Material Issue Plan", mip_name)
    if not mip.cnc_warehouse:
        return False
    result = frappe.db.sql("""
        SELECT 1
        FROM `tabStock Entry Detail` sed
        JOIN `tabStock Entry` se ON se.name = sed.parent
        WHERE se.custom_mip_ref = %s
          AND se.stock_entry_type = 'Material Transfer'
          AND se.docstatus = 1
          AND sed.t_warehouse = %s
        LIMIT 1
    """, (mip_name, mip.cnc_warehouse))
    return bool(result)


def _get_mip_transfer_stock_entry_names(mip):
    """Names of submitted Stock Entries that physically transferred material for this
    MIP's SCO/WO (Send to Subcontractor / Material Transfer, tagged via
    custom_sco_ref/custom_wo_ref by _tag_stock_entry) -- the ones that make raw-material
    refresh unsafe/blocked. Shared by _get_already_transferred_batches and the
    "Refresh Raw Materials" guard, which needs the names themselves (not just the
    batches) to tell the user exactly what to delete to unblock a refresh."""
    filters = {"docstatus": 1}
    if mip.subcontracting_order:
        filters["custom_sco_ref"] = mip.subcontracting_order
    elif mip.work_order:
        filters["custom_wo_ref"] = mip.work_order
    else:
        return []
    return frappe.db.get_all("Stock Entry", filters=filters, pluck="name")


def _get_already_transferred_batches(mip):
    """Return the set of batch_nos already physically moved by submitted SEs for this MIP.
    After SE submission, is_reserved is cleared on MP rows, so without this exclusion
    already-transferred batches would appear as false-positive 'unreserved' warnings."""
    se_names = _get_mip_transfer_stock_entry_names(mip)
    if not se_names:
        return set()
    batch_nos = frappe.db.get_all(
        "Stock Entry Detail",
        filters={"parent": ["in", se_names]},
        pluck="batch_no",
    )
    return {b for b in batch_nos if b}


@frappe.whitelist()
def get_mip_readiness_check(mip_name):
    """Return a readiness summary for the MIP transfer pre-flight check.
    Checks all linked MPs for:
      - unmapped items (in unavailable_items — no batch, no stock)
      - unreserved items (batch assigned in mapping/ARM but not reserved AND not yet transferred)
    Returns {"unmapped": [...], "unreserved": [...]} so JS can warn the user
    before initiating transfer."""
    mip = frappe.get_doc("Material Issue Plan", mip_name)
    mp_names = sorted({r.material_planning for r in (mip.drawing_items or []) if r.material_planning})

    transferred_batches = _get_already_transferred_batches(mip)

    unmapped = []
    unreserved = []

    for mp_name in mp_names:
        mp = frappe.get_doc("Material Planning", mp_name)

        # Items in unavailable_items = no stock found / not yet purchased
        for r in (mp.unavailable_items or []):
            if not r.item_code:
                continue
            unmapped.append({
                "material_planning": mp_name,
                "table": "Unavailable Items",
                "row": r.idx,
                "item_code": r.item_code,
                "item_name": r.item_name or "",
                "duno_mark_no": r.duno_mark_no or "",
                "qty": flt(r.qty, 3),
                "uom": r.uom or "Kg",
            })

        # Material Mapping rows with batch but not reserved and not already transferred
        for r in (mp.material_mapping or []):
            if r.item_code and r.batch and not r.is_reserved:
                if r.batch not in transferred_batches:
                    unreserved.append({
                        "material_planning": mp_name,
                        "table": "Material Mapping",
                        "row": r.idx,
                        "item_code": r.item_code,
                        "item_name": r.item_name or "",
                        "batch": r.batch,
                        "duno_mark_no": r.duno_mark_no or "",
                        "qty": flt(r.qty, 3),
                        "uom": r.uom or "Kg",
                    })
            elif r.item_code and not r.batch:
                unmapped.append({
                    "material_planning": mp_name,
                    "table": "Material Mapping",
                    "row": r.idx,
                    "item_code": r.item_code,
                    "item_name": r.item_name or "",
                    "duno_mark_no": r.duno_mark_no or "",
                    "qty": flt(r.qty, 3),
                    "uom": r.uom or "Kg",
                })

        # Exact Match rows — batch assigned but not reserved / no batch assigned yet
        for r in (mp.available_raw_materials or []):
            if not r.item_code:
                continue
            if r.batch_no and not r.is_reserved:
                if r.batch_no not in transferred_batches:
                    unreserved.append({
                        "material_planning": mp_name,
                        "table": "Exact Match",
                        "row": r.idx,
                        "item_code": r.item_code,
                        "item_name": r.item_name or "",
                        "batch": r.batch_no,
                        "duno_mark_no": r.duno_mark_no or "",
                        "qty": flt(r.required_qty, 3),
                        "uom": r.uom or "Kg",
                    })
            elif not r.batch_no:
                unmapped.append({
                    "material_planning": mp_name,
                    "table": "Exact Match",
                    "row": r.idx,
                    "item_code": r.item_code,
                    "item_name": r.item_name or "",
                    "duno_mark_no": r.duno_mark_no or "",
                    "qty": flt(r.required_qty, 3),
                    "uom": r.uom or "Kg",
                })

    return {
        "unmapped": unmapped,
        "unreserved": unreserved,
        "has_issues": bool(unmapped or unreserved),
    }


@frappe.whitelist()
def create_mip_transfer_entry(mip_name):
    """Transfer ALL pending non-CNC reserved material to the primary (Supplier/WIP)
    warehouse. CNC items are intentionally excluded — use 'To CNC Warehouse' for those.

    WARNING (Phase 1 H-07 / Report 3 Finding H-07): the frappe.db.commit()
    below ends the request's transaction early on purpose, to release
    read-locks before the Stock Entry insert and avoid a MySQL gap-lock
    deadlock. This means everything before that line is permanently committed
    regardless of what happens afterward -- there is no rollback path if a
    later step in this function fails. Do NOT add a write above the
    frappe.db.commit() line without re-reading this warning: a write
    introduced there would no longer be all-or-nothing with the rest of this
    function.
    """
    mip = frappe.get_doc("Material Issue Plan", mip_name)
    _ensure_mip_editable(mip)
    ctx = get_target_context(mip)
    pending = get_mip_pending_items(mip_name)
    if not pending:
        frappe.throw(_("No reserved batches pending transfer. Ensure batches are reserved in the linked Material Planning documents."))

    primary_rows = [p for p in pending if not p["cnc_process"]]
    if not primary_rows:
        frappe.throw(_("No pending items for the primary warehouse. CNC items can be transferred using 'To CNC Warehouse'."))

    # get_mip_pending_items() returns unprefixed keys (duno_mark_no/drawing/sales_order/
    # customer_drawing_number) for the transfer-picker dialog's own filters -- map them onto
    # Stock Entry Detail's custom_* fieldnames here (client change request Phase 1.3).
    for row in primary_rows:
        row["custom_drawing"] = row.get("drawing") or ""
        row["custom_duno_mark_no"] = row.get("duno_mark_no") or ""
        row["custom_customer_drawing_number"] = row.get("customer_drawing_number") or ""
        row["custom_sales_order"] = row.get("sales_order") or ""

    se = frappe.get_doc(_tag_stock_entry({
        "doctype": "Stock Entry",
        "stock_entry_type": ctx.primary_se_type,
        "company": ctx.company,
        "items": primary_rows,
    }, mip_name, ctx))
    frappe.db.commit()  # release read-locks before SE insert to avoid gap-lock deadlock
    se.insert(ignore_permissions=True)
    _log_round_up_excess(mip, primary_rows)
    return {"primary_se": se.name}


@frappe.whitelist()
def create_mip_partial_transfer(mip_name, selected_items_json, transfer_type):
    """Create a draft Stock Entry for the caller-selected raw-material items.

    transfer_type: "primary" -> Send to Subcontractor/Material Transfer to the
                                supplier/WIP warehouse
                   "cnc"     -> Material Transfer to the CNC warehouse

    WARNING (Phase 1 H-07 / Report 3 Finding H-07): same manual mid-request
    frappe.db.commit() pattern as create_mip_transfer_entry above (releases
    read-locks before the Stock Entry insert to avoid a gap-lock deadlock) --
    do NOT add a write above that commit() call without re-reading its
    warning there first.
    """
    selected = _json.loads(selected_items_json) if isinstance(selected_items_json, str) else selected_items_json
    if not selected:
        frappe.throw(_("No items selected for transfer."))

    mip = frappe.get_doc("Material Issue Plan", mip_name)
    _ensure_mip_editable(mip)
    ctx = get_target_context(mip)
    if not mip.source_warehouse:
        frappe.throw(_("Please set the Source Warehouse (RM) on this Material Issue Plan first."))

    if transfer_type == "cnc":
        if not mip.cnc_warehouse:
            frappe.throw(_("No CNC Warehouse set on this Material Issue Plan."))
        t_warehouse = mip.cnc_warehouse
        se_type = "Material Transfer"
    else:
        t_warehouse = ctx.primary_warehouse
        se_type = ctx.primary_se_type

    se_items = []
    for item in selected:
        se_items.append({
            "item_code": item["item_code"],
            "batch_no": item.get("batch_no") or "",
            "use_serial_batch_fields": 1,
            "qty": flt(item["qty"]),
            "uom": item.get("uom") or "Kg",
            "s_warehouse": mip.source_warehouse,
            "t_warehouse": t_warehouse,
            "custom_sec_qty": flt(item.get("custom_sec_qty") or 0),
            "custom_sec_uom": item.get("custom_sec_uom") or "",
            "custom_length": flt(item.get("custom_length") or 0),
            "custom_width": flt(item.get("custom_width") or 0),
            "custom_thickness": flt(item.get("custom_thickness") or 0),
            "custom_unit_weight": flt(item.get("custom_unit_weight") or 0),
            "custom_parent_item_group": item.get("custom_parent_item_group") or "",
            "custom_drawing": item.get("drawing") or "",
            "custom_duno_mark_no": item.get("duno_mark_no") or "",
            "custom_customer_drawing_number": item.get("customer_drawing_number") or "",
            "custom_sales_order": item.get("sales_order") or "",
        })

    se = frappe.get_doc(_tag_stock_entry({
        "doctype": "Stock Entry",
        "stock_entry_type": se_type,
        "company": ctx.company,
        "items": se_items,
    }, mip_name, ctx))
    frappe.db.commit()
    se.insert(ignore_permissions=True)
    _log_round_up_excess(mip, selected)
    return se.name


@frappe.whitelist()
def create_mip_cnc_forward_entry(mip_name):
    """Forward material currently sitting in the CNC warehouse on to the
    supplier/WIP warehouse — nets already-forwarded qty against what was sent.

    WARNING (Phase 1 H-07 / Report 3 Finding H-07): same manual mid-request
    frappe.db.commit() pattern as create_mip_transfer_entry above -- do NOT
    add a write above that commit() call without re-reading its warning there
    first.
    """
    mip = frappe.get_doc("Material Issue Plan", mip_name)
    _ensure_mip_editable(mip)
    ctx = get_target_context(mip)
    cnc_warehouse = mip.cnc_warehouse
    if not cnc_warehouse:
        frappe.throw(_("No CNC Warehouse set on this Material Issue Plan."))

    sent_rows = frappe.db.sql(
        """
        SELECT sed.item_code, sed.batch_no,
               SUM(sed.qty) AS qty,
               MAX(sed.uom) AS uom,
               MAX(sed.custom_sec_qty) AS custom_sec_qty,
               MAX(sed.custom_sec_uom) AS custom_sec_uom,
               MAX(sed.custom_length) AS custom_length,
               MAX(sed.custom_width) AS custom_width,
               MAX(sed.custom_thickness) AS custom_thickness,
               MAX(sed.custom_unit_weight) AS custom_unit_weight,
               MAX(sed.custom_parent_item_group) AS custom_parent_item_group,
               MAX(sed.custom_drawing) AS custom_drawing,
               MAX(sed.custom_duno_mark_no) AS custom_duno_mark_no,
               MAX(sed.custom_customer_drawing_number) AS custom_customer_drawing_number,
               MAX(sed.custom_sales_order) AS custom_sales_order
        FROM `tabStock Entry Detail` sed
        JOIN `tabStock Entry` se ON se.name = sed.parent
        WHERE se.custom_mip_ref = %s
          AND se.stock_entry_type = 'Material Transfer'
          AND se.docstatus = 1
          AND sed.t_warehouse = %s
        GROUP BY sed.item_code, sed.batch_no
        HAVING SUM(sed.qty) > 0
        """,
        (mip_name, cnc_warehouse),
        as_dict=True,
    )
    if not sent_rows:
        frappe.throw(_("No CNC materials found. Ensure the CNC stock entry has been submitted."))

    fwd_rows = frappe.db.sql(
        """
        SELECT sed.item_code, sed.batch_no, SUM(sed.qty) AS qty
        FROM `tabStock Entry Detail` sed
        JOIN `tabStock Entry` se ON se.name = sed.parent
        WHERE se.custom_mip_ref = %s
          AND se.stock_entry_type = 'Material Transfer'
          AND se.docstatus = 1
          AND sed.s_warehouse = %s
          AND sed.t_warehouse = %s
        GROUP BY sed.item_code, sed.batch_no
        """,
        (mip_name, cnc_warehouse, ctx.primary_warehouse),
        as_dict=True,
    )
    already = {(r.item_code, r.batch_no or ""): flt(r.qty) for r in fwd_rows}

    se_items = []
    for r in sent_rows:
        key = (r.item_code, r.batch_no or "")
        net_qty = flt(r.qty, 3) - already.get(key, 0)
        if net_qty <= 0:
            continue
        se_items.append({
            "item_code": r.item_code,
            "batch_no": r.batch_no,
            "use_serial_batch_fields": 1,
            "qty": flt(net_qty, 3),
            "uom": r.uom or frappe.db.get_value("Item", r.item_code, "stock_uom") or "Kg",
            "s_warehouse": cnc_warehouse,
            "t_warehouse": ctx.primary_warehouse,
            "custom_sec_qty": flt(r.custom_sec_qty, 3),
            "custom_sec_uom": r.custom_sec_uom or "",
            "custom_length": flt(r.custom_length, 3),
            "custom_width": flt(r.custom_width, 3),
            "custom_thickness": flt(r.custom_thickness, 3),
            "custom_unit_weight": flt(r.custom_unit_weight, 4),
            "custom_parent_item_group": r.custom_parent_item_group or "",
            "custom_drawing": r.custom_drawing or "",
            "custom_duno_mark_no": r.custom_duno_mark_no or "",
            "custom_customer_drawing_number": r.custom_customer_drawing_number or "",
            "custom_sales_order": r.custom_sales_order or "",
        })

    if not se_items:
        frappe.throw(_("All CNC materials have already been transferred onward."))

    se = frappe.get_doc(_tag_stock_entry({
        "doctype": "Stock Entry",
        "stock_entry_type": "Material Transfer",
        "company": ctx.company,
        "items": se_items,
    }, mip_name, ctx))
    frappe.db.commit()
    se.insert(ignore_permissions=True)
    return se.name


@frappe.whitelist()
def create_mip_excess_return_entry(mip_name, rows_json=None):
    """Receive unconsumed/off-cut material back into stock as fresh Material
    Receipt stock (new batches, new dimensions) from mip.excess_return_items.

    `rows_json` (client change request Phase 5.6): an optional JSON list of
    {"name": <excess_return_items row name>, "return_reason": <text>, plus
    either "length"/"width"/"sec_qty" (Structurals/Plates rows) or "qty"
    (every other item group, e.g. Nuts and Bolts) } -- lets the "Return
    Excess Entry" dialog let the user edit the planned Qty and record why,
    right before this actually creates the Stock Entry, without re-opening
    the form first.

    Structurals/Plates rows take dimension overrides (Length/Width/Sec Qty),
    NOT a direct Qty override, and Qty is recomputed here via the same shared
    utils.dimension_formula.calculate_qty used everywhere else in this app --
    Stock Entry's own validate_stock_entry hook unconditionally recalculates
    Qty from custom_length/custom_sec_qty/custom_unit_weight for these two
    groups on Material Receipt entries, so a directly-set Qty override would
    otherwise be silently discarded the moment the Stock Entry is inserted.

    A Return Reason is mandatory for every row being processed -- either
    supplied fresh here or already saved on the row from a previous edit --
    so a direct/scripted call with no rows_json still enforces it against
    whatever the row itself already carries.

    WARNING (Phase 1 H-07 / Report 3 Finding H-07): same manual mid-request
    frappe.db.commit() pattern as create_mip_transfer_entry above -- do NOT
    add a write above that commit() call without re-reading its warning there
    first. (The mip.excess_return_items flag updates and mip.save() further
    down in this function run AFTER the commit, which is fine -- the warning
    is specifically about writes introduced ABOVE the commit() line.)
    """
    mip = frappe.get_doc("Material Issue Plan", mip_name)
    _ensure_mip_editable(mip)
    if not mip.excess_return_warehouse:
        frappe.throw(_("Please set the Finished Goods Warehouse on this Material Issue Plan first."))

    overrides = {o.get("name"): o for o in _json.loads(rows_json)} if rows_json else {}

    se_items = []
    new_row_names = []
    for r in (mip.excess_return_items or []):
        if r.get("stock_entry_created"):
            continue
        if r.get("return_type") == "Retain at Supplier (Virtual)":
            # Never physically returns to any warehouse -- no Stock Entry/Batch
            # for this row at all; it's claimed directly from this table via
            # Excess Material Mapping's virtual-excess picker instead.
            continue
        if r.get("mapped_material_planning"):
            # Already claimed straight off this table (client feedback: the
            # picker now also surfaces still-Pending default-return-type rows,
            # not just ones explicitly flagged Retain-at-Supplier -- see
            # get_available_virtual_excess_items). Once claimed, its eventual
            # physical return is the claiming job's own business, not a fresh
            # batch this button should hand out to someone else.
            continue

        override = overrides.get(r.name)
        if override:
            group = r.parent_item_group
            if group in _DIMENSION_DRIVEN_GROUPS:
                if override.get("length") not in (None, ""):
                    r.length = flt(override.get("length"), 3)
                if override.get("width") not in (None, ""):
                    r.width = flt(override.get("width"), 3)
                if override.get("sec_qty") not in (None, ""):
                    r.sec_qty = flt(override.get("sec_qty"), 3)
                calc_qty = calculate_qty(group, r.length, r.width, r.thickness, r.unit_weight, r.sec_qty)
                if calc_qty is not None:
                    r.qty = flt(calc_qty, 3)
            elif override.get("qty") not in (None, ""):
                r.qty = flt(override.get("qty"), 3)
            if (override.get("return_reason") or "").strip():
                r.return_reason = override.get("return_reason").strip()

        qty = flt(r.qty, 3)
        if not r.item_code or qty <= 0:
            continue
        if not (r.return_reason or "").strip():
            frappe.throw(_("Row {0} ({1}): a Return Reason is required before creating the return entry.")
                         .format(r.idx, r.item_code))

        new_row_names.append(r.name)
        se_items.append({
            "item_code": r.item_code,
            "qty": qty,
            "uom": r.get("uom") or frappe.db.get_value("Item", r.item_code, "stock_uom") or "Kg",
            "t_warehouse": mip.excess_return_warehouse,
            "custom_parent_item_group": r.get("parent_item_group") or "",
            "custom_unit_weight": flt(r.get("unit_weight"), 4),
            "custom_sec_qty": flt(r.get("sec_qty"), 3),
            "custom_sec_uom": r.get("sec_uom") or "",
            "custom_length": flt(r.get("length"), 3),
            "custom_width": flt(r.get("width"), 3),
            "custom_thickness": flt(r.get("thickness"), 3),
            # Same-named custom field on Batch -- ERPNext copies matching custom
            # fields from a Stock Entry item onto the batch it auto-creates, so
            # this reaches the Batch record itself, letting Excess Material
            # Mapping trace a reservation back to the row it came from.
            "custom_source_mip_excess_row": r.name,
        })

    if not se_items:
        frappe.throw(_("No new off-cut items to process. All rows already have a Stock Entry created, "
                       "or no rows with Weight (Kg) > 0 exist."))

    se = frappe.get_doc({
        "doctype": "Stock Entry",
        "stock_entry_type": "Material Receipt",
        "company": mip.company,
        "custom_mip_ref": mip_name,
        "items": se_items,
    })
    frappe.db.commit()
    se.insert(ignore_permissions=True)

    # Push the finalized (possibly user-edited) return dimensions back onto
    # the source raw_materials row's own Excess Length/Width/Sec Qty, so the
    # Reqd/Issued/Excess Qty figures (Phase 5.3) reflect what was ACTUALLY
    # returned rather than only the originally auto-suggested value.
    #
    # This pushes the DIMENSIONS, not excess_calc_qty directly: validate()'s
    # own _sync_excess_return_from_raw_materials unconditionally recomputes
    # every raw_materials row's excess_calc_qty from its OWN excess_length/
    # width/sec_qty on every save (Structurals/Plates only -- see
    # calculate_qty), regardless of stock_entry_created, so setting
    # excess_calc_qty directly here would just get silently overwritten the
    # moment mip.save() below runs validate(). Updating the dimensions lets
    # that same recompute produce the correct answer instead of fighting it.
    # Keyed by (source_table, source_row) -- the stable reference back to the
    # underlying Material Planning row -- not by the raw_materials row's own
    # name, which gets regenerated (and so would no longer match r's own
    # source_mip_raw_material_row) every time refresh_mip_raw_materials runs.
    raw_material_by_row = {
        (row.source_table, row.source_row): row
        for row in (mip.raw_materials or [])
        if row.source_row
    }
    for r in mip.excess_return_items:
        if r.name not in new_row_names:
            continue
        r.stock_entry_created = 1
        src = raw_material_by_row.get((r.source_table, r.source_row))
        if src and (r.parent_item_group or "") in _DIMENSION_DRIVEN_GROUPS:
            src.excess_length = r.length
            src.excess_width = r.width
            src.excess_sec_qty = r.sec_qty

    mip.save(ignore_permissions=True)

    return se.name
