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

import frappe
from frappe import _
from frappe.utils import flt

from manufyxinvenzaerp.subcontracting_management.subcontracting import _get_mp_reserved_batches
from manufyxinvenzaerp.subcontracting_management.doctype.material_issue_plan.material_issue_plan import (
    get_target_context,
)


def _linked_mp_names(mip):
    pp = frappe.get_doc("Production Plan", mip.production_plan)
    mp_names = []
    seen = set()
    for pi in pp.po_items:
        mp_name = pi.get("custom_material_planning")
        if mp_name and mp_name not in seen:
            seen.add(mp_name)
            mp_names.append(mp_name)
    return mp_names


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
    for mp_name in _linked_mp_names(mip):
        raw_items.extend(_get_mp_reserved_batches(mp_name, source_warehouse, primary_warehouse))

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

    return result


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


def _get_already_transferred_batches(mip):
    """Return the set of batch_nos already physically moved by submitted SEs for this MIP.
    After SE submission, is_reserved is cleared on MP rows, so without this exclusion
    already-transferred batches would appear as false-positive 'unreserved' warnings."""
    filters = {"docstatus": 1}
    if mip.subcontracting_order:
        filters["custom_sco_ref"] = mip.subcontracting_order
    elif mip.work_order:
        filters["custom_wo_ref"] = mip.work_order
    else:
        return set()
    se_names = frappe.db.get_all("Stock Entry", filters=filters, pluck="name")
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

        # Exact Match rows with batch but not reserved and not already transferred
        for r in (mp.available_raw_materials or []):
            if r.item_code and r.batch_no and not r.is_reserved:
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

    return {
        "unmapped": unmapped,
        "unreserved": unreserved,
        "has_issues": bool(unmapped or unreserved),
    }


@frappe.whitelist()
def create_mip_transfer_entry(mip_name):
    """Transfer ALL pending non-CNC reserved material to the primary (Supplier/WIP)
    warehouse. CNC items are intentionally excluded — use 'To CNC Warehouse' for those."""
    mip = frappe.get_doc("Material Issue Plan", mip_name)
    ctx = get_target_context(mip)
    pending = get_mip_pending_items(mip_name)
    if not pending:
        frappe.throw(_("No reserved batches pending transfer. Ensure batches are reserved in the linked Material Planning documents."))

    primary_rows = [p for p in pending if not p["cnc_process"]]
    if not primary_rows:
        frappe.throw(_("No pending items for the primary warehouse. CNC items can be transferred using 'To CNC Warehouse'."))

    se = frappe.get_doc(_tag_stock_entry({
        "doctype": "Stock Entry",
        "stock_entry_type": ctx.primary_se_type,
        "company": ctx.company,
        "items": primary_rows,
    }, mip_name, ctx))
    frappe.db.commit()  # release read-locks before SE insert to avoid gap-lock deadlock
    se.insert(ignore_permissions=True)
    return {"primary_se": se.name}


@frappe.whitelist()
def create_mip_partial_transfer(mip_name, selected_items_json, transfer_type):
    """Create a draft Stock Entry for the caller-selected raw-material items.

    transfer_type: "primary" -> Send to Subcontractor/Material Transfer to the
                                supplier/WIP warehouse
                   "cnc"     -> Material Transfer to the CNC warehouse
    """
    selected = _json.loads(selected_items_json) if isinstance(selected_items_json, str) else selected_items_json
    if not selected:
        frappe.throw(_("No items selected for transfer."))

    mip = frappe.get_doc("Material Issue Plan", mip_name)
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
        })

    se = frappe.get_doc(_tag_stock_entry({
        "doctype": "Stock Entry",
        "stock_entry_type": se_type,
        "company": ctx.company,
        "items": se_items,
    }, mip_name, ctx))
    frappe.db.commit()
    se.insert(ignore_permissions=True)
    return se.name


@frappe.whitelist()
def create_mip_cnc_forward_entry(mip_name):
    """Forward material currently sitting in the CNC warehouse on to the
    supplier/WIP warehouse — nets already-forwarded qty against what was sent."""
    mip = frappe.get_doc("Material Issue Plan", mip_name)
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
               MAX(sed.custom_parent_item_group) AS custom_parent_item_group
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
def create_mip_excess_return_entry(mip_name):
    """Receive unconsumed/off-cut material back into stock as fresh Material
    Receipt stock (new batches, new dimensions) from mip.excess_return_items."""
    mip = frappe.get_doc("Material Issue Plan", mip_name)
    if not mip.excess_return_warehouse:
        frappe.throw(_("Please set the Excess/Return Warehouse on this Material Issue Plan first."))

    se_items = []
    new_row_names = []
    for r in (mip.excess_return_items or []):
        if r.get("stock_entry_created"):
            continue
        qty = flt(r.qty, 3)
        if not r.item_code or qty <= 0:
            continue
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
            "custom_mip_ref": mip_name,
        })

    if not se_items:
        frappe.throw(_("No new off-cut items to process. All rows already have a Stock Entry created, "
                       "or no rows with Weight (Kg) > 0 exist."))

    se = frappe.get_doc({
        "doctype": "Stock Entry",
        "stock_entry_type": "Material Receipt",
        "company": mip.company,
        "items": se_items,
    })
    frappe.db.commit()
    se.insert(ignore_permissions=True)

    for r in mip.excess_return_items:
        if r.name in new_row_names:
            r.stock_entry_created = 1
    mip.save(ignore_permissions=True)

    return se.name
