import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt


class MaterialIssuePlan(Document):
    def after_insert(self):
        """First save populates the drawing/raw-material list automatically —
        mirrors how create_sco_from_production_plan populates SCO Drawing Items
        immediately at creation rather than requiring a separate manual step."""
        if self.production_plan:
            populate_from_production_plan(self.name)

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


@frappe.whitelist()
def refresh_mip_raw_materials(mip_name):
    """Rebuild the raw-material snapshot fresh from every Material Planning linked to
    this plan's drawings. Material Planning's own child tables remain the source of
    truth for reservation state — this only refreshes MIP's read-only display copy."""
    mip = frappe.get_doc("Material Issue Plan", mip_name)
    mp_names = sorted({r.material_planning for r in (mip.drawing_items or []) if r.material_planning})

    mip.set("raw_materials", [])

    for mp_name in mp_names:
        mp = frappe.get_doc("Material Planning", mp_name)

        for row in (mp.material_mapping or []):
            qty = row.batch_calc_qty if row.batch else row.qty
            sec_qty = row.batch_sec_qty if row.batch else row.sec_qty
            mip.append("raw_materials", {
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
                "qty": qty,
                "is_reserved": row.is_reserved,
                "is_unavailable": 0,
                "cnc_process": row.cnc_process,
            })

        for row in (mp.available_raw_materials or []):
            mip.append("raw_materials", {
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
                "sec_qty": row.sec_qty,
                "sec_uom": row.sec_uom,
                "qty": row.required_qty,
                "is_reserved": row.is_reserved,
                "is_unavailable": 0,
                "cnc_process": row.cnc_process,
            })

        for row in (mp.unavailable_items or []):
            mip.append("raw_materials", {
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
                "qty": row.qty,
                "is_reserved": 0,
                "is_unavailable": 1,
            })

    mip.save(ignore_permissions=True)
    refresh_weight_summary(mip_name)
    return mip.name


@frappe.whitelist()
def refresh_weight_summary(mip_name):
    """Recompute the four header weight-summary fields (and their per-drawing
    breakdown) live from the linked Material Planning(s) — reused, unmodified
    from the functions subcontracting.py already uses for SCO/WO rollups."""
    from manufyxinvenzaerp.subcontracting_management.subcontracting import (
        _get_mp_drawing_weight,
        _get_mp_mapped_weight_by_duno,
        _get_mp_excess_by_duno,
        _get_mp_actual_transferred_weight,
    )

    mip = frappe.get_doc("Material Issue Plan", mip_name)
    source_warehouse, target_warehouses = _resolve_warehouses(mip)

    if mip.subcontracting_order:
        mip.supplier_warehouse = frappe.db.get_value(
            "Subcontracting Order", mip.subcontracting_order, "supplier_warehouse"
        ) or ""

    mapped_by_mp = {}
    excess_by_mp = {}
    transferred_by_mp = {}

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
            transferred_by_mp[mp_name] = (
                flt(_get_mp_actual_transferred_weight(mp_name, source_warehouse, target_warehouses))
                if source_warehouse and target_warehouses else 0.0
            )

        d.total_weight_kg = flt(_get_mp_drawing_weight(mp_name, d.duno_mark_no), 3)
        d.mapped_weight_kg = flt(mapped_by_mp[mp_name].get(d.duno_mark_no), 3)
        d.excess_weight_kg = flt(excess_by_mp[mp_name].get(d.duno_mark_no), 3)

        total_planned += d.total_weight_kg
        allocated += d.mapped_weight_kg
        excess += d.excess_weight_kg

    # Apportion each MP's actual-transferred total across its drawings by mapped-weight
    # share — same proportional-attribution technique already used elsewhere in this
    # app (e.g. _refresh_sco_drawing_transferred_weights) rather than inventing a new one.
    mp_mapped_totals = {mp: sum(v for v in d.values()) for mp, d in mapped_by_mp.items()}
    transferred = 0.0
    for d in mip.drawing_items or []:
        mp_name = d.material_planning
        if not mp_name:
            continue
        mp_total_mapped = mp_mapped_totals.get(mp_name) or 0
        mp_transferred = transferred_by_mp.get(mp_name) or 0
        d.transferred_weight_kg = (
            flt(mp_transferred * (d.mapped_weight_kg / mp_total_mapped), 3) if mp_total_mapped else 0.0
        )
        transferred += d.transferred_weight_kg

    mip.total_planned_weight_kg = flt(total_planned, 3)
    mip.allocated_weight_kg = flt(allocated, 3)
    mip.transferred_weight_kg = flt(transferred, 3)
    mip.excess_weight_kg = flt(excess, 3)
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
