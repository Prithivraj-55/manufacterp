import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt

from manufyxinvenzaerp.utils.dimension_formula import calculate_qty


class MaterialIssuePlan(Document):
    def after_insert(self):
        """First save populates the drawing/raw-material list automatically —
        mirrors how create_sco_from_production_plan populates SCO Drawing Items
        immediately at creation rather than requiring a separate manual step."""
        if self.production_plan:
            populate_from_production_plan(self.name)

    def validate(self):
        """Recompute Cut Sheet's To Use (W1) / Balance (W2) Calc Qty (Phase 5.2),
        auto-suggest an Excess Return row from a Cut Sheet row's Balance once
        it's calculated (Phase 5.5), then recompute Excess Calc Qty for every
        raw_materials row flagged Excess Return Applicable and sync (create/
        update, never duplicate) a matching row in excess_return_items for each
        (Phase 5.3). Order matters: the auto-suggestion must run before the
        excess-return sync so a freshly-suggested row gets picked up in the
        same save. Also mirrors each row's batch Remarks (Phase 6.3)."""
        _sync_cut_sheet_calc(self)
        _auto_suggest_excess_from_cut_sheet(self)
        _sync_excess_return_from_raw_materials(self)
        _sync_batch_remarks(self)

    def on_trash(self):
        """Remove Batch Change Log rows referencing this MIP from all linked
        Material Planning documents so no orphaned audit trail remains."""
        frappe.db.delete(
            "Material Planning Batch Change Log",
            {"material_issue_plan": self.name},
        )


@frappe.whitelist()
def create_from_subcontracting_order(sco_name):
    """Create (or return the existing) Material Issue Plan pre-filled from an SCO."""
    existing = frappe.db.get_value("Material Issue Plan", {"subcontracting_order": sco_name})
    if existing:
        return existing

    sco = frappe.db.get_value("Subcontracting Order", sco_name, ["company", "custom_production_plan"], as_dict=True)
    if not sco or not sco.custom_production_plan:
        frappe.throw(_("This Subcontracting Order has no linked Production Plan."))

    mip = frappe.new_doc("Material Issue Plan")
    mip.company = sco.company
    mip.production_plan = sco.custom_production_plan
    mip.subcontracting_order = sco_name
    mip.insert(ignore_permissions=True)
    return mip.name


@frappe.whitelist()
def create_from_work_order(wo_name):
    """Create (or return the existing) Material Issue Plan pre-filled from a Work Order."""
    existing = frappe.db.get_value("Material Issue Plan", {"work_order": wo_name})
    if existing:
        return existing

    wo = frappe.db.get_value("Work Order", wo_name, ["company", "production_plan"], as_dict=True)
    if not wo or not wo.production_plan:
        frappe.throw(_("This Work Order has no linked Production Plan."))

    mip = frappe.new_doc("Material Issue Plan")
    mip.company = wo.company
    mip.production_plan = wo.production_plan
    mip.work_order = wo_name
    mip.insert(ignore_permissions=True)
    return mip.name


@frappe.whitelist()
def populate_from_production_plan(mip_name):
    """Primary population entrypoint. The linked Production Plan's items already carry
    drawing/DUNO/sales-order/customer-drawing references (set by Material Planning's
    make_production_plan) — read the drawing list straight from there, auto-link a
    matching Subcontracting/Work Order if one exists, then cascade into raw materials
    and the weight summary."""
    mip = frappe.get_doc("Material Issue Plan", mip_name)
    if not mip.production_plan:
        frappe.throw(_("Select a Production Plan first."))

    pp = frappe.get_doc("Production Plan", mip.production_plan)

    if not mip.subcontracting_order:
        mip.subcontracting_order = frappe.db.get_value(
            "Subcontracting Order",
            {"custom_production_plan": mip.production_plan, "docstatus": ["!=", 2]},
        ) or ""
    if not mip.work_order:
        mip.work_order = frappe.db.get_value(
            "Work Order",
            {"production_plan": mip.production_plan, "docstatus": ["!=", 2]},
        ) or ""

    # Source Warehouse defaults straight from the Production Plan's own Raw
    # Material Warehouse — the primary source now that this is asked for
    # explicitly, not just inferred from a Work Order.
    if not mip.source_warehouse:
        mip.source_warehouse = pp.custom_raw_material_warehouse or ""

    # Excess-return warehouse defaults from a linked WO's standard Finished Goods
    # Warehouse the first time. (Neither SCO nor Work Order carry Source/CNC
    # warehouse fields of their own anymore — both moved here permanently — so
    # there is nothing to default those two from on either side.)
    if mip.work_order and not mip.excess_return_warehouse:
        mip.excess_return_warehouse = frappe.db.get_value("Work Order", mip.work_order, "fg_warehouse") or ""

    # Supplier Warehouse — read-only display of where material is transferring
    # TO, resolved from the linked SCO's standard field. Purely informational;
    # the actual transfer destination is always re-resolved fresh at transfer
    # time via get_target_context/_resolve_warehouses.
    if mip.subcontracting_order:
        mip.supplier_warehouse = frappe.db.get_value(
            "Subcontracting Order", mip.subcontracting_order, "supplier_warehouse"
        ) or ""

    mip.set("drawing_items", [])
    for row in (pp.po_items or []):
        if not row.get("custom_drawing") and not row.get("custom_material_planning"):
            continue
        mip.append("drawing_items", {
            "drawing": row.get("custom_drawing"),
            "item_code": row.item_code,
            "item_name": row.get("custom_item_name") or row.item_name,
            "qty_to_manufacture": row.planned_qty,
            "duno_mark_no": row.get("custom_duno_mark_no"),
            "customer_drawing_number": row.get("custom_customer_drawing_number"),
            "sales_order": row.get("sales_order") or "",
            "material_planning": row.get("custom_material_planning"),
            "customer_weight_kg": row.get("custom_customer_weight_kg"),
        })

    mip.save(ignore_permissions=True)
    refresh_mip_raw_materials(mip.name)
    return mip.name


# Fields the user edits directly on an otherwise-rebuilt-from-scratch raw_materials
# row (Excess Return in Phase 5.3, Cut Sheet in Phase 5.2) -- refresh_mip_raw_materials
# fully clears and rebuilds this table from the source Material Planning on every
# call, so anything the user typed here must be explicitly carried forward onto the
# freshly-rebuilt row or it would silently vanish the next time a Purchase Receipt
# (or anything else) triggers a refresh.
_RAW_MATERIAL_EDITABLE_FIELDS = [
    "excess_return_applicable", "excess_length", "excess_width", "excess_sec_qty",
    "excess_calc_qty", "excess_return_date",
    "cut_sheet", "use_length", "use_width", "use_sec_qty", "use_calc_qty",
    "balance_length", "balance_width", "balance_sec_qty", "balance_calc_qty",
]


@frappe.whitelist()
def refresh_mip_raw_materials(mip_name):
    """Rebuild the raw-material snapshot fresh from every Material Planning linked to
    this plan's drawings. Material Planning's own child tables remain the source of
    truth for reservation state — this only refreshes MIP's read-only display copy.

    A linked Material Planning commonly covers far more drawings than this one MIP
    was created for (e.g. one MP for a whole sales order's 22 beams, split across
    several MIPs of a few drawings each) -- so rows are filtered down to only the
    (sales_order, duno_mark_no) pairs actually listed in this MIP's own
    drawing_items, instead of pulling every row the linked MP(s) happen to have.
    A Material Planning is only scoped this way when EVERY drawing_items row
    pointing at it carries a real duno_mark_no -- a row with no DUNO at all
    (custom_material_planning set on the Production Plan Item without a specific
    Drawing/DUNO picked) means "pull this whole MP, unrestricted", same as before
    this filter existed, since there is no per-drawing scope to filter down to.

    User-editable fields (Excess Return / Cut Sheet — see _RAW_MATERIAL_EDITABLE_FIELDS)
    are carried forward from the row being replaced, matched by (source_table,
    source_row), since those two together uniquely identify "the same underlying
    Material Planning row" across a rebuild -- item_code/batch alone isn't enough
    when the same item appears in more than one row."""
    from manufyxinvenzaerp.subcontracting_management.material_issue_plan_transfer import (
        _get_already_transferred_batches,
    )

    mip = frappe.get_doc("Material Issue Plan", mip_name)
    mp_names = sorted({r.material_planning for r in (mip.drawing_items or []) if r.material_planning})

    drawing_keys_by_mp, wildcard_mps = {}, set()
    for r in (mip.drawing_items or []):
        if not r.material_planning:
            continue
        if not r.duno_mark_no:
            wildcard_mps.add(r.material_planning)
        else:
            drawing_keys_by_mp.setdefault(r.material_planning, set()).add((r.sales_order, r.duno_mark_no))

    transferred_batches = _get_already_transferred_batches(mip)

    old_rows_by_key = {
        (r.source_table, r.source_row): r
        for r in (mip.raw_materials or [])
        if r.source_row
    }

    # Material Planning Available Raw Material carries no unit_weight field of its
    # own (unlike Material Mapping/Unavailable Item), so it has to be looked up from
    # the Item master directly -- missing this left every ARM-sourced raw_materials
    # row (and anything derived from it, e.g. Excess Calc Qty) stuck at a wrong 0.
    unit_weight_by_item = {}
    all_mps = [frappe.get_doc("Material Planning", n) for n in mp_names]
    arm_item_codes = {r.item_code for mp in all_mps for r in (mp.available_raw_materials or []) if r.item_code}
    if arm_item_codes:
        unit_weight_by_item = dict(frappe.get_all(
            "Item", filters={"name": ["in", list(arm_item_codes)]},
            fields=["name", "custom_unit_weight"], as_list=True,
        ))

    mip.set("raw_materials", [])

    for mp in all_mps:
        mp_name = mp.name
        scoped_keys = drawing_keys_by_mp.get(mp_name) if mp_name not in wildcard_mps else None

        for row in (mp.material_mapping or []):
            if scoped_keys is not None and (row.sales_order, row.duno_mark_no) not in scoped_keys:
                continue
            qty = row.batch_calc_qty if row.batch else row.qty
            sec_qty = row.batch_sec_qty if row.batch else row.sec_qty
            planned_weight = _lookup_drawing_planned_weight(row.sales_order, row.customer_drawing_number, row.item_code)
            new_row = mip.append("raw_materials", {
                "material_planning": mp_name,
                "source_table": "Material Planning Material Mapping",
                "source_row": row.name,
                "item_code": row.item_code,
                "item_name": row.item_name,
                "planned_item": row.planned_item,
                "duno_mark_no": row.duno_mark_no,
                "customer_drawing_number": row.customer_drawing_number,
                "sales_order": row.sales_order,
                "batch_no": row.batch,
                "purchase_receipt": row.purchase_receipt,
                "parent_item_group": row.parent_item_group,
                "length": row.length,
                "width": row.width,
                "thickness": row.thickness,
                "unit_weight": row.unit_weight,
                "sec_qty": sec_qty,
                "sec_uom": row.sec_uom,
                "reqd_kg": row.qty,
                "qty": qty,
                "transferred_qty": qty if row.batch and row.batch in transferred_batches else 0,
                "drawing_planned_weight": planned_weight,
                "excess_qty": flt(flt(qty) - planned_weight, 3) if planned_weight is not None else 0,
                "is_reserved": row.is_reserved,
                "is_unavailable": 0,
                "cnc_process": row.cnc_process,
            })
            _carry_forward_editable_fields(new_row, old_rows_by_key, "Material Planning Material Mapping", row.name)

        for row in (mp.available_raw_materials or []):
            if scoped_keys is not None and (row.sales_order, row.duno_mark_no) not in scoped_keys:
                continue
            planned_weight = _lookup_drawing_planned_weight(row.sales_order, row.customer_drawing_number, row.item_code)
            new_row = mip.append("raw_materials", {
                "material_planning": mp_name,
                "source_table": "Material Planning Available Raw Material",
                "source_row": row.name,
                "item_code": row.item_code,
                "item_name": row.item_name,
                "duno_mark_no": row.duno_mark_no,
                "customer_drawing_number": row.customer_drawing_number,
                "sales_order": row.sales_order,
                "batch_no": row.batch_no,
                "purchase_receipt": row.purchase_receipt,
                "parent_item_group": row.parent_item_group,
                "length": row.length,
                "width": row.width,
                "thickness": row.thickness,
                "unit_weight": unit_weight_by_item.get(row.item_code),
                "sec_qty": row.sec_qty,
                "sec_uom": row.sec_uom,
                "reqd_kg": row.overall_required_qty or row.required_qty,
                "qty": row.required_qty,
                "transferred_qty": row.required_qty if row.batch_no and row.batch_no in transferred_batches else 0,
                "drawing_planned_weight": planned_weight,
                "excess_qty": flt(flt(row.required_qty) - planned_weight, 3) if planned_weight is not None else 0,
                "is_reserved": row.is_reserved,
                "is_unavailable": 0,
                "cnc_process": row.cnc_process,
            })
            _carry_forward_editable_fields(new_row, old_rows_by_key, "Material Planning Available Raw Material", row.name)

        for row in (mp.unavailable_items or []):
            if scoped_keys is not None and (row.sales_order, row.duno_mark_no) not in scoped_keys:
                continue
            new_row = mip.append("raw_materials", {
                "material_planning": mp_name,
                "source_table": "Material Planning Unavailable Item",
                "source_row": row.name,
                "item_code": row.item_code,
                "item_name": row.item_name,
                "duno_mark_no": row.duno_mark_no,
                "customer_drawing_number": row.customer_drawing_number,
                "sales_order": row.sales_order,
                "parent_item_group": row.parent_item_group,
                "length": row.length,
                "width": row.width,
                "thickness": row.thickness,
                "unit_weight": row.unit_weight,
                "sec_qty": row.sec_qty,
                "reqd_kg": row.qty,
                "qty": row.qty,
                "transferred_qty": 0,
                "is_reserved": 0,
                "is_unavailable": 1,
            })
            _carry_forward_editable_fields(new_row, old_rows_by_key, "Material Planning Unavailable Item", row.name)

    mip.save(ignore_permissions=True)
    refresh_weight_summary(mip_name)
    return mip.name


def _carry_forward_editable_fields(new_row, old_rows_by_key, source_table, source_row):
    """Copy the Excess Return / Cut Sheet fields a user may have entered directly
    onto the raw_materials row being replaced, matched by (source_table, source_row)
    -- see _RAW_MATERIAL_EDITABLE_FIELDS. No-op if no matching old row existed."""
    old_row = old_rows_by_key.get((source_table, source_row))
    if not old_row:
        return
    for fieldname in _RAW_MATERIAL_EDITABLE_FIELDS:
        new_row.set(fieldname, old_row.get(fieldname))


def _lookup_drawing_planned_weight(sales_order, customer_drawing_number, item_code):
    """Engineering/planned raw material weight for this (sales_order,
    customer_drawing_number, item_code) from Sales Order Drawing Raw Material's
    own Total Weight -- the "Drawing/planned RM weight" Excess Qty is measured
    against (client change request Phase 5.3's worked example: 14 Kg mapped
    batch − 13 Kg drawing-planned = 1 Kg excess). Matched on the same key
    fields Material Issue Plan Raw Material actually carries (no item_number
    field exists on that row, unlike the stricter match used elsewhere in this
    app) -- returns None (not 0) when no match exists, so callers can tell
    "genuinely 0 Kg planned" apart from "no comparison available yet"."""
    if not sales_order or not item_code:
        return None
    return frappe.db.get_value(
        "Sales Order Drawing Raw Material",
        {
            "parent": sales_order,
            "material_code": item_code,
            "customer_drawing_number": customer_drawing_number or "",
        },
        "total_weight",
    )


def _sync_excess_return_from_raw_materials(mip):
    """For every raw_materials row flagged Excess Return Applicable, recompute
    Excess Calc Qty (Kg) from its Excess Length/Width/Sec Qty (Thickness reuses
    the row's own batch Thickness), then find-or-create a matching row in
    excess_return_items -- keyed by (source_table, source_row), a row's own
    reference back to the STABLE Material Planning child row it traces to, so
    re-saving the plan updates the same excess_return_items row instead of
    duplicating it, and a row the user has since edited by hand (or that
    already has its own Stock Entry) is left alone rather than silently
    overwritten (client change request Phase 5.3).

    NOTE: raw_materials itself is fully rebuilt (fresh row names) on every
    refresh_mip_raw_materials call, so matching on row.name (as this used to)
    silently duplicated every still-pending excess entry on every subsequent
    refresh -- (source_table, source_row) is the one reference on a
    raw_materials row that stays stable across a rebuild, since it points at
    the underlying Material Planning row, not this MIP's own copy of it."""
    by_source = {
        (r.source_table, r.source_row): r
        for r in (mip.excess_return_items or [])
        if r.source_row
    }

    for row in (mip.raw_materials or []):
        if not row.excess_return_applicable:
            continue

        calc_qty = calculate_qty(
            row.parent_item_group, row.excess_length, row.excess_width,
            row.thickness, row.unit_weight, row.excess_sec_qty,
        )
        row.excess_calc_qty = flt(calc_qty, 3) if calc_qty is not None else 0

        key = (row.source_table, row.source_row)
        target = by_source.get(key)
        if target and target.stock_entry_created:
            # Already returned to stock -- leave the historical entry alone.
            continue

        if not target:
            target = mip.append("excess_return_items", {
                "source_table": row.source_table, "source_row": row.source_row,
                "source_mip_raw_material_row": row.name,
            })
            by_source[key] = target
        else:
            # raw_materials was rebuilt since this row was created -- refresh
            # the display-only pointer to whichever raw_materials row now
            # represents the same underlying source_table/source_row.
            target.source_mip_raw_material_row = row.name

        target.item_code = row.item_code
        # parent_item_group/unit_weight/sec_uom/uom are `fetch_from` fields on
        # SCO Excess Material Item, which Frappe only auto-populates via the
        # CLIENT-SIDE fetch_and_set_docfield when a user types/selects
        # item_code in the browser (see the item_code handler on "SCO Excess
        # Material Item" in material_issue_plan.js) -- appending this row
        # purely server-side, as this sync does, never triggers that, so
        # without setting them explicitly here every auto-populated row was
        # silently left with parent_item_group blank and unit_weight 0 (a
        # pre-existing bug predating Phase 5.6, found while adding the
        # dimension-aware qty recompute to create_mip_excess_return_entry,
        # which depends on both being correct).
        target.parent_item_group = row.parent_item_group
        target.unit_weight = row.unit_weight
        target.sec_uom = row.sec_uom
        target.uom = row.uom
        target.length = row.excess_length
        target.width = row.excess_width
        target.thickness = row.thickness
        target.sec_qty = row.excess_sec_qty
        target.qty = row.excess_calc_qty


def _sync_cut_sheet_calc(mip):
    """For every raw_materials row flagged Cut Sheet, recompute To Use Calc Qty
    (W1 -- the qty actually transferred) and Balance Calc Qty (W2 -- what the
    same batch's own dimensions get resized to once the transfer submits), both
    via the same shared Structurals/Plates formula as everywhere else in this
    app (client change request Phase 5.2). Purely a display/preview recompute
    here -- the actual transferred qty override and post-submit batch resize
    happen in material_issue_plan_transfer.py / stock_entry.py, reading these
    same Cut Sheet fields directly off this row at the time a transfer is made."""
    for row in (mip.raw_materials or []):
        if not row.cut_sheet:
            continue

        use_qty = calculate_qty(
            row.parent_item_group, row.use_length, row.use_width,
            row.thickness, row.unit_weight, row.use_sec_qty,
        )
        row.use_calc_qty = flt(use_qty, 3) if use_qty is not None else 0

        balance_qty = calculate_qty(
            row.parent_item_group, row.balance_length, row.balance_width,
            row.thickness, row.unit_weight, row.balance_sec_qty,
        )
        row.balance_calc_qty = flt(balance_qty, 3) if balance_qty is not None else 0


def _sync_batch_remarks(mip):
    """Mirror each raw_materials row's assigned batch's own Batch Remarks
    (client change request Phase 6.3) onto its own batch_remarks field. Not a
    fetch_from field -- raw_materials rows are entirely rebuilt server-side by
    refresh_mip_raw_materials, which never triggers Frappe's client-only
    fetch_from auto-populate (same reasoning as material_planning.py's own
    _sync_batch_remarks). One bulk query regardless of row count."""
    batch_nos = {r.batch_no for r in (mip.raw_materials or []) if r.batch_no}
    if not batch_nos:
        return
    remarks_by_batch = dict(frappe.get_all(
        "Batch", filters={"name": ["in", list(batch_nos)]},
        fields=["name", "custom_batch_remarks"], as_list=True,
    ))
    for row in (mip.raw_materials or []):
        if row.batch_no:
            row.batch_remarks = remarks_by_batch.get(row.batch_no) or ""


def _auto_suggest_excess_from_cut_sheet(mip):
    """Once a Cut Sheet row's Balance (W2) is calculated, auto-suggest it as an
    Excess Return row: seed excess_return_applicable + Excess Length/Width/Sec
    Qty from the Balance dimensions (client change request Phase 5.5). Only
    fires the FIRST time -- i.e. while excess_return_applicable is not yet set
    -- so a later manual edit to the excess fields (or an intentional uncheck)
    is never silently overwritten on a subsequent save; the plan's own spec
    calls for the suggestion to be "left editable", not re-forced every time."""
    for row in (mip.raw_materials or []):
        if not row.cut_sheet or not row.balance_calc_qty:
            continue
        if row.excess_return_applicable:
            continue

        row.excess_return_applicable = 1
        row.excess_length = row.balance_length
        row.excess_width = row.balance_width
        row.excess_sec_qty = row.balance_sec_qty


@frappe.whitelist()
def refresh_weight_summary(mip_name):
    """Recompute the four header weight-summary fields (and their per-drawing breakdown).

    Transferred weight is read directly from the linked SCO/WO's
    custom_transferred_weight_kg — already correctly computed by
    _update_sco/wo_transferred_weight — and distributed proportionally across
    drawings by planned weight share. This is independent of MP reservation
    status, so it stays accurate after SE submission clears is_reserved.
    """
    from manufyxinvenzaerp.subcontracting_management.subcontracting import (
        _get_mp_drawing_weights_by_duno,
        _get_mp_mapped_weight_by_duno,
        _get_mp_excess_by_duno,
        _get_mp_total_weight,
    )

    mip = frappe.get_doc("Material Issue Plan", mip_name)

    if mip.subcontracting_order:
        mip.supplier_warehouse = frappe.db.get_value(
            "Subcontracting Order", mip.subcontracting_order, "supplier_warehouse"
        ) or ""

    # Actual transferred weight — read from the linked SCO or WO
    actual_transferred = 0.0
    if mip.subcontracting_order:
        actual_transferred = flt(frappe.db.get_value(
            "Subcontracting Order", mip.subcontracting_order, "custom_transferred_weight_kg"
        ))
    elif mip.work_order:
        actual_transferred = flt(frappe.db.get_value(
            "Work Order", mip.work_order, "custom_transferred_weight_kg"
        ))

    mapped_by_mp = {}
    excess_by_mp = {}
    drawing_weight_by_mp = {}  # mp_name -> {duno_mark_no: planned_kg} (Phase 1 perf fix:
                                # was one live query per drawing_items row via
                                # _get_mp_drawing_weight; now one grouped query per
                                # unique mp_name, mirroring mapped_by_mp/excess_by_mp
                                # right above, which were already memoized this way.)

    total_planned = 0.0
    allocated = 0.0
    excess = 0.0

    for d in mip.drawing_items or []:
        mp_name = d.material_planning
        if not mp_name:
            continue
        if mp_name not in mapped_by_mp:
            mapped_by_mp[mp_name] = _get_mp_mapped_weight_by_duno(mp_name)
            excess_by_mp[mp_name] = _get_mp_excess_by_duno(mp_name)
        if mp_name not in drawing_weight_by_mp:
            drawing_weight_by_mp[mp_name] = _get_mp_drawing_weights_by_duno(mp_name)

        # Mirrors _get_mp_drawing_weight(mp_name, d.duno_mark_no) exactly: grouped
        # lookup for a real DUNO/Mark No, falling back to the MP's total weight
        # when it's blank -- same fallback _get_mp_drawing_weight itself uses.
        if d.duno_mark_no:
            planned_weight = drawing_weight_by_mp[mp_name].get(d.duno_mark_no, 0.0)
        else:
            planned_weight = _get_mp_total_weight(mp_name)
        d.total_weight_kg = flt(planned_weight, 3)
        d.mapped_weight_kg = flt(mapped_by_mp[mp_name].get(d.duno_mark_no), 3)
        d.excess_weight_kg = flt(excess_by_mp[mp_name].get(d.duno_mark_no), 3)

        total_planned += d.total_weight_kg
        allocated += d.mapped_weight_kg
        excess += d.excess_weight_kg

    # Distribute transferred weight across drawings by planned-weight share
    transferred = 0.0
    for d in mip.drawing_items or []:
        if not d.material_planning:
            continue
        d.transferred_weight_kg = (
            flt(actual_transferred * (d.total_weight_kg / total_planned), 3)
            if total_planned else 0.0
        )
        transferred += d.transferred_weight_kg

    mip.total_planned_weight_kg = flt(total_planned, 3)
    mip.allocated_weight_kg = flt(allocated, 3)
    mip.transferred_weight_kg = flt(transferred, 3)
    mip.excess_weight_kg = flt(excess, 3)
    # Perf: this function only ever changes the 4 header weight fields above and
    # per-row weight fields on drawing_items -- it never touches any Link field's
    # VALUE (Material Issue Plan has no validate() of its own and no doc_events
    # registered in hooks.py, so nothing else runs here either way). A plain
    # .save() still re-validates every Link field on every row of every child
    # table, including raw_materials, which this function never touches -- on a
    # ~100-row Material Issue Plan that redundant check alone measured at ~0.35s
    # of a ~1.1s Stock Entry submission. ignore_links skips only that
    # re-validation; every other part of the normal save (timestamps, the
    # Version/track_changes log, child-table diffing) is unaffected.
    mip.flags.ignore_links = True
    mip.save(ignore_permissions=True)
    return mip.name


def get_target_context(mip):
    """Resolve which document (SCO or WO) this plan issues material against, and the
    SE type / target warehouse / Stock Entry link field that go with it. Supports
    both so this and material_issue_plan_transfer.py need no changes for the WO round."""
    if mip.subcontracting_order:
        sco = frappe.db.get_value(
            "Subcontracting Order", mip.subcontracting_order,
            ["company", "supplier_warehouse"], as_dict=True,
        )
        if not sco:
            frappe.throw(_("Linked Subcontracting Order {0} not found.").format(mip.subcontracting_order))
        # MIP's own supplier_warehouse takes priority; fall back to SCO's field
        primary_warehouse = mip.supplier_warehouse or sco.supplier_warehouse
        if not primary_warehouse:
            frappe.throw(
                _("Supplier Warehouse is not set. Please set it directly on this Material Issue Plan "
                  "(Warehouses section) or on the linked Subcontracting Order {0}.").format(mip.subcontracting_order)
            )
        return frappe._dict({
            "doctype": "Subcontracting Order",
            "name": mip.subcontracting_order,
            "company": sco.company,
            "primary_warehouse": primary_warehouse,
            "primary_se_type": "Send to Subcontractor",
            "link_field": "subcontracting_order",
            "ref_field": "custom_sco_ref",
        })
    if mip.work_order:
        wo = frappe.db.get_value("Work Order", mip.work_order, ["company", "wip_warehouse"], as_dict=True)
        if not wo:
            frappe.throw(_("Linked Work Order {0} not found.").format(mip.work_order))
        primary_warehouse = mip.supplier_warehouse or wo.wip_warehouse
        if not primary_warehouse:
            frappe.throw(
                _("WIP Warehouse is not set. Please set it in the Supplier / WIP Warehouse field on this "
                  "Material Issue Plan or on the linked Work Order {0}.").format(mip.work_order)
            )
        return frappe._dict({
            "doctype": "Work Order",
            "name": mip.work_order,
            "company": wo.company,
            "primary_warehouse": primary_warehouse,
            "primary_se_type": "Material Transfer",
            "link_field": "work_order",
            "ref_field": "custom_wo_ref",
        })
    frappe.throw(_("This Material Issue Plan has no linked Subcontracting Order or Work Order."))


def _resolve_warehouses(mip):
    """Source + target warehouses for the live weight-summary calc.
    MIP's own supplier_warehouse takes priority; falls back to SCO/WO."""
    source_warehouse = mip.source_warehouse or None
    target_warehouses = [w for w in [mip.cnc_warehouse] if w]

    if mip.supplier_warehouse:
        target_warehouses.append(mip.supplier_warehouse)
    elif mip.subcontracting_order:
        supplier_warehouse = frappe.db.get_value("Subcontracting Order", mip.subcontracting_order, "supplier_warehouse")
        if supplier_warehouse:
            target_warehouses.append(supplier_warehouse)
    elif mip.work_order:
        wip_warehouse = frappe.db.get_value("Work Order", mip.work_order, "wip_warehouse")
        if wip_warehouse:
            target_warehouses.append(wip_warehouse)

    return source_warehouse, [w for w in target_warehouses if w]
