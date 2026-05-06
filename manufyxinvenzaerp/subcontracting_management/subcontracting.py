import frappe
from frappe import _
from frappe.utils import flt, today

FORMULA_GROUPS = {"Structurals", "Plates"}


# ─────────────────────────────────────────────────────────────────────────────
# Dashboard override
# ─────────────────────────────────────────────────────────────────────────────

def get_sco_dashboard_data(data):
    """Add Supplier Operation Entry to the Subcontracting Order dashboard."""
    data["transactions"].append({
        "label": _("Operations"),
        "items": ["Supplier Operation Entry"],
    })
    return data


# ─────────────────────────────────────────────────────────────────────────────
# Whitelisted API functions
# ─────────────────────────────────────────────────────────────────────────────

@frappe.whitelist()
def create_sco_from_production_plan(pp_name):
    """Create a Draft Subcontracting Order from a submitted Production Plan.
    Works with or without a Work Order — if no WO exists, falls back to
    Production Plan items for the FG item / qty / BOM.
    """
    pp = frappe.get_doc("Production Plan", pp_name)

    sub_ops = [r for r in (pp.custom_process_planning or []) if r.work_type == "Subcontractor"]
    if not sub_ops:
        frappe.throw(_("No Subcontractor operations found in the Process Planning table."))
    if not pp.custom_vendor_contractor:
        frappe.throw(_("Please set the Vendor/Contractor on the Production Plan before creating a Subcontracting Order."))

    # Try to find an existing Work Order
    wo_list = frappe.get_all("Work Order", filters={"production_plan": pp_name}, limit=1, pluck="name")
    wo_name = wo_list[0] if wo_list else None

    if wo_name:
        wo = frappe.get_doc("Work Order", wo_name)
        fg_item = wo.production_item
        fg_qty = wo.qty
        fg_warehouse = wo.fg_warehouse
        bom_no = wo.bom_no
    else:
        # All-subcontractor flow — no WO needed; use Production Plan items directly
        if not pp.po_items:
            frappe.throw(_("No items found in the Production Plan. Please add items to manufacture first."))
        pp_item = pp.po_items[0]
        fg_item = pp_item.item_code
        fg_qty = pp_item.planned_qty
        fg_warehouse = pp_item.warehouse or ""
        bom_no = pp_item.bom_no

    company = (
        frappe.defaults.get_user_default("Company")
        or frappe.db.get_single_value("Global Defaults", "default_company")
    )
    currency = (
        frappe.db.get_value("Company", company, "default_currency")
        or frappe.db.get_single_value("Global Defaults", "default_currency")
        or "INR"
    )
    uom = frappe.db.get_value("Item", fg_item, "stock_uom") or "Nos"

    sco = frappe.get_doc({
        "doctype": "Subcontracting Order",
        "company": company,
        "currency": currency,
        "conversion_rate": 1,
        "supplier": pp.custom_vendor_contractor,
        "schedule_date": today(),
        "items": [{
            "item_code": fg_item,
            "qty": flt(fg_qty) or 1,
            "uom": uom,
            "warehouse": fg_warehouse or "",
            "bom": bom_no,
            "rate": 0,
            "subcontracting_conversion_factor": 1,
        }],
        "custom_production_plan": pp_name,
        "custom_work_order": wo_name or "",
    })
    # Skip ERPNext's standard SCO validation — it requires a linked Purchase Order
    # which is not part of this PP → SCO direct flow. The user reviews the Draft
    # and submits manually after setting supplier_warehouse.
    sco.flags.ignore_validate = True
    sco.insert(ignore_permissions=True, ignore_mandatory=True)
    return sco.name


@frappe.whitelist()
def create_work_order_from_pp(pp_name):
    """Create a Work Order containing ONLY the Internal Jobcard operations from the
    Production Plan's Process Planning table. Used for Scenario 3 (hybrid flow)."""
    pp = frappe.get_doc("Production Plan", pp_name)

    internal_ops = [
        r for r in (pp.custom_process_planning or [])
        if r.work_type == "Internal Jobcard"
    ]
    if not internal_ops:
        frappe.throw(_("No Internal Jobcard operations found in the Process Planning table."))

    if not pp.po_items:
        frappe.throw(_("No items found in the Production Plan."))

    pp_item = pp.po_items[0]
    bom_no = pp_item.bom_no
    if not bom_no:
        frappe.throw(_("No BOM set on the Production Plan item."))

    internal_op_names = {r.operation_name for r in internal_ops}

    company = (
        frappe.defaults.get_user_default("Company")
        or frappe.db.get_single_value("Global Defaults", "default_company")
    )

    # Get routing operations filtered to internal ones only, preserving original sequence_ids
    routing = frappe.db.get_value("BOM", bom_no, "routing")
    filtered_ops = []
    if routing:
        bom_ops = frappe.get_all(
            "BOM Operation",
            filters={
                "parent": routing,
                "parenttype": "Routing",
                "operation": ["in", list(internal_op_names)],
            },
            fields=["operation", "workstation", "time_in_mins", "sequence_id"],
            order_by="sequence_id asc",
        )
        filtered_ops = bom_ops

    wo = frappe.new_doc("Work Order")
    wo.update({
        "production_item": pp_item.item_code,
        "bom_no": bom_no,
        "qty": flt(pp_item.planned_qty) or 1,
        "company": company,
        "production_plan": pp_name,
        "fg_warehouse": pp_item.warehouse or "",
        "use_multi_level_bom": 0,
    })

    # Set required items from BOM
    wo.set_required_items()

    # Manually set only the internal operations (skip set_work_order_operations which uses all)
    wo.operations = []
    for op in filtered_ops:
        wo.append("operations", {
            "operation": op.operation,
            "workstation": op.workstation,
            "time_in_mins": flt(op.time_in_mins) or 60,
            "sequence_id": op.sequence_id,
            "status": "Pending",
        })

    wo.flags.ignore_mandatory = True
    wo.flags.ignore_validate = True
    wo.insert(ignore_permissions=True)
    return wo.name


@frappe.whitelist()
def create_supplier_operation_entries(sco_name):
    """Create one SOE per subcontractor operation (idempotent).
    Works with or without a Work Order linked to the SCO.
    """
    sco = frappe.get_doc("Subcontracting Order", sco_name)
    if sco.docstatus != 1:
        frappe.throw(_("Subcontracting Order must be submitted before creating Supplier Operation Entries."))
    if not sco.supplier_warehouse:
        frappe.throw(_("Please set the Supplier Warehouse on the Subcontracting Order first."))

    pp_name = sco.custom_production_plan
    if not pp_name:
        frappe.throw(_("Subcontracting Order is not linked to a Production Plan."))

    wo_name = sco.custom_work_order or None
    pp = frappe.get_doc("Production Plan", pp_name)

    sub_ops = sorted(
        [r for r in (pp.custom_process_planning or []) if r.work_type == "Subcontractor"],
        key=lambda r: r.idx,
    )
    if not sub_ops:
        frappe.throw(_("No Subcontractor operations found in the Production Plan."))

    # Determine BOM and required items — from WO if available, else from PP + BOM
    if wo_name:
        wo = frappe.get_doc("Work Order", wo_name)
        bom_no = wo.bom_no
        required_item_codes = [r.item_code for r in wo.required_items]
    else:
        pp_item = pp.po_items[0] if pp.po_items else None
        bom_no = pp_item.bom_no if pp_item else None
        if not bom_no:
            frappe.throw(_("No BOM found on the Production Plan. Please set a BOM on the items."))
        required_item_codes = frappe.get_all(
            "BOM Item", filters={"parent": bom_no}, pluck="item_code"
        )

    # Pre-fetch BOM item dimensions once
    bom_item_dims = {}
    if bom_no:
        for bi in frappe.get_all(
            "BOM Item",
            filters={"parent": bom_no},
            fields=["item_code", "custom_length", "custom_width", "custom_thickness"],
        ):
            bom_item_dims[bi.item_code] = bi

    created_soes = []
    prev_soe_name = None

    for seq_idx, op_row in enumerate(sub_ops, start=1):
        # Idempotency: check by work_order when available, else by subcontracting_order
        if wo_name:
            existing = frappe.db.get_value(
                "Supplier Operation Entry",
                {"work_order": wo_name, "sequence_id": seq_idx, "docstatus": ["!=", 2]},
                "name",
            )
        else:
            existing = frappe.db.get_value(
                "Supplier Operation Entry",
                {"subcontracting_order": sco_name, "sequence_id": seq_idx, "docstatus": ["!=", 2]},
                "name",
            )
        if existing:
            prev_soe_name = existing
            continue

        soe_items = []
        for ic in required_item_codes:
            item_master = frappe.db.get_value(
                "Item", ic,
                ["custom_parent_item_group", "custom_unit_weight", "custom_secondary_uom", "stock_uom", "item_name"],
                as_dict=True,
            ) or frappe._dict()

            bom_dims = bom_item_dims.get(ic, frappe._dict())
            wh_data = _get_supplier_wh_batch(ic, sco.supplier_warehouse)
            prev_data = _get_prev_soe_consumed(
                ic, seq_idx, prev_soe_name, work_order=wo_name, sco_name=sco_name
            )

            soe_items.append({
                "item_code": ic,
                "item_name": item_master.get("item_name"),
                "parent_item_group": item_master.get("custom_parent_item_group"),
                "unit_weight": item_master.get("custom_unit_weight"),
                "sec_uom": item_master.get("custom_secondary_uom"),
                "stock_uom": item_master.get("stock_uom"),
                "batch_no": wh_data.get("batch_no"),
                "transferred_sec_qty": wh_data.get("sec_qty"),
                "transferred_stock_qty": wh_data.get("stock_qty"),
                "prev_operation_sec_qty": prev_data.get("sec_qty", 0),
                "prev_operation_stock_qty": prev_data.get("stock_qty", 0),
                "thickness": flt(bom_dims.get("custom_thickness")),
                "length": flt(bom_dims.get("custom_length")),
                "width": flt(bom_dims.get("custom_width")),
            })

        soe = frappe.get_doc({
            "doctype": "Supplier Operation Entry",
            "work_order": wo_name or "",
            "subcontracting_order": sco_name,
            "production_plan": pp_name,
            "operation": op_row.operation_name,
            "sequence_id": seq_idx,
            "supplier": sco.supplier,
            "supplier_warehouse": sco.supplier_warehouse,
            "status": "Open",
            "items": soe_items,
        })
        soe.insert(ignore_permissions=True)
        prev_soe_name = soe.name
        created_soes.append(soe.name)

    return created_soes


@frappe.whitelist()
def create_send_to_subcontractor_entry(sco_name):
    """Create a draft 'Send to Subcontractor' Stock Entry from the SCO's BOM items."""
    sco = frappe.get_doc("Subcontracting Order", sco_name)
    if not sco.supplier_warehouse:
        frappe.throw(_("Please set the Supplier Warehouse on the Subcontracting Order first."))
    if not sco.get("custom_source_warehouse"):
        frappe.throw(_("Please set the Source Warehouse (RM) on the Subcontracting Order first."))
    if sco.docstatus != 1:
        frappe.throw(_("Subcontracting Order must be submitted first."))

    source_warehouse = sco.custom_source_warehouse

    se_items = []
    for sco_item in sco.items:
        if not sco_item.bom:
            continue
        bom_items = frappe.get_all(
            "BOM Item",
            filters={"parent": sco_item.bom, "docstatus": 1},
            fields=["item_code", "item_name", "stock_qty", "stock_uom"],
        )
        bom_qty = frappe.db.get_value("BOM", sco_item.bom, "quantity") or 1
        multiplier = flt(sco_item.qty) / flt(bom_qty)

        for bi in bom_items:
            se_items.append({
                "item_code": bi.item_code,
                "item_name": bi.item_name,
                "qty": flt(bi.stock_qty) * multiplier,
                "uom": bi.stock_uom,
                "stock_uom": bi.stock_uom,
                "s_warehouse": source_warehouse,
                "t_warehouse": sco.supplier_warehouse,
                "subcontracting_order": sco_name,
            })

    if not se_items:
        frappe.throw(_("No BOM items found to transfer."))

    se = frappe.get_doc({
        "doctype": "Stock Entry",
        "stock_entry_type": "Send to Subcontractor",
        "subcontracting_order": sco_name,
        "items": se_items,
    })
    se.insert(ignore_permissions=True)
    return se.name


@frappe.whitelist()
def create_wip_transfer_stock_entry(sco_name):
    """Scenario 3: Transfer CONSUMED materials from supplier warehouse to company WIP warehouse.
    Used when subcontractor ops are complete and internal Job Cards continue from WIP."""
    sco = frappe.get_doc("Subcontracting Order", sco_name)
    if not sco.supplier_warehouse:
        frappe.throw(_("Supplier Warehouse is not set on the Subcontracting Order."))
    if not sco.get("custom_wip_warehouse"):
        frappe.throw(_("Please set the WIP Transfer Warehouse on the Subcontracting Order first."))

    # Find last submitted SOE
    if sco.custom_work_order:
        filters = {"work_order": sco.custom_work_order, "docstatus": 1}
    else:
        filters = {"subcontracting_order": sco_name, "docstatus": 1}

    last_soe_name = frappe.db.get_value(
        "Supplier Operation Entry", filters, "name", order_by="sequence_id desc"
    )
    if not last_soe_name:
        frappe.throw(_("No submitted Supplier Operation Entry found for this Subcontracting Order."))

    last_soe = frappe.get_doc("Supplier Operation Entry", last_soe_name)

    se_items = []
    for row in last_soe.items:
        consumed_sec = flt(row.current_sec_qty)
        consumed_stock = flt(row.current_stock_qty)
        # For Nuts and Bolts, use manual_qty instead
        group = (row.parent_item_group or "").strip()
        if group not in FORMULA_GROUPS:
            consumed_stock = flt(row.manual_qty)
        if consumed_stock <= 0:
            continue
        se_items.append({
            "item_code": row.item_code,
            "qty": flt(consumed_stock, 3),
            "s_warehouse": sco.supplier_warehouse,
            "t_warehouse": sco.custom_wip_warehouse,
            "batch_no": row.batch_no,
            "custom_sec_qty": flt(consumed_sec, 3),
            "custom_thickness": row.thickness,
            "custom_length": row.length,
            "custom_width": row.width,
        })

    if not se_items:
        frappe.throw(_("No consumed materials found to transfer to WIP."))

    se = frappe.get_doc({
        "doctype": "Stock Entry",
        "stock_entry_type": "Material Transfer",
        "items": se_items,
    })
    se.insert(ignore_permissions=True)
    return se.name


@frappe.whitelist()
def create_return_stock_entry(sco_name, target_warehouse):
    """Transfer unconsumed materials from supplier warehouse back to company warehouse."""
    sco = frappe.get_doc("Subcontracting Order", sco_name)
    if not sco.supplier_warehouse:
        frappe.throw(_("Supplier Warehouse is not set on the Subcontracting Order."))

    # Find last submitted SOE — by work_order if set, else by subcontracting_order
    if sco.custom_work_order:
        filters = {"work_order": sco.custom_work_order, "docstatus": 1}
    else:
        filters = {"subcontracting_order": sco_name, "docstatus": 1}

    last_soe_name = frappe.db.get_value(
        "Supplier Operation Entry", filters, "name", order_by="sequence_id desc"
    )
    if not last_soe_name:
        frappe.throw(_("No submitted Supplier Operation Entry found for this Subcontracting Order."))

    last_soe = frappe.get_doc("Supplier Operation Entry", last_soe_name)

    se_items = []
    for row in last_soe.items:
        unconsumed_sec = flt(row.transferred_sec_qty) - flt(row.current_sec_qty)
        unconsumed_stock = flt(row.transferred_stock_qty) - flt(row.current_stock_qty)
        if unconsumed_sec <= 0:
            continue
        se_items.append({
            "item_code": row.item_code,
            "qty": flt(unconsumed_stock, 3),
            "s_warehouse": sco.supplier_warehouse,
            "t_warehouse": target_warehouse,
            "batch_no": row.batch_no,
            "custom_sec_qty": flt(unconsumed_sec, 3),
            "custom_thickness": row.thickness,
            "custom_length": row.length,
            "custom_width": row.width,
        })

    if not se_items:
        frappe.throw(_("No unconsumed materials found to transfer back."))

    se = frappe.get_doc({
        "doctype": "Stock Entry",
        "stock_entry_type": "Material Transfer",
        "items": se_items,
    })
    se.insert(ignore_permissions=True)
    return se.name


# ─────────────────────────────────────────────────────────────────────────────
# Doc event handlers
# ─────────────────────────────────────────────────────────────────────────────

def validate_supplier_operation_entry(doc, method):
    """Server-side blocking validation for SOE consumption."""
    for row in doc.items:
        group = (row.parent_item_group or "").strip()
        if group in FORMULA_GROUPS:
            consumed_qty = flt(row.current_stock_qty)
            transferred = flt(row.transferred_stock_qty)
            if transferred and consumed_qty > transferred:
                frappe.throw(
                    _("Row {0}: Item {1} — consumed qty {2} Kg exceeds transferred qty {3} Kg.").format(
                        row.idx, row.item_code, consumed_qty, transferred
                    )
                )
            if (doc.sequence_id or 0) > 1:
                prev_sec = flt(row.prev_operation_sec_qty)
                curr_sec = flt(row.current_sec_qty)
                if prev_sec and curr_sec > prev_sec:
                    frappe.throw(
                        _("Row {0}: Item {1} — {2} Nos entered exceeds previous operation's {3} Nos.").format(
                            row.idx, row.item_code, curr_sec, prev_sec
                        )
                    )
        elif group == "Nuts and Bolts":
            if flt(row.manual_qty) > flt(row.transferred_stock_qty):
                frappe.throw(
                    _("Row {0}: Item {1} — manual qty {2} Kg exceeds transferred qty {3} Kg.").format(
                        row.idx, row.item_code, row.manual_qty, row.transferred_stock_qty
                    )
                )


def on_submit_supplier_operation_entry(doc, method):
    """Reduce batch sec_qty for consumed items; set all_ops_complete on SCO when last op done."""
    for row in doc.items:
        if not row.batch_no:
            continue
        group = (row.parent_item_group or "").strip()
        if group in FORMULA_GROUPS and flt(row.current_sec_qty):
            _reduce_batch_sec_qty(row.batch_no, flt(row.current_sec_qty))

    # Check if this is the last operation — filter by work_order if set, else by SCO
    if doc.work_order:
        remaining_filters = {
            "work_order": doc.work_order,
            "sequence_id": [">", doc.sequence_id or 0],
            "docstatus": ["!=", 2],
        }
    else:
        remaining_filters = {
            "subcontracting_order": doc.subcontracting_order,
            "sequence_id": [">", doc.sequence_id or 0],
            "docstatus": ["!=", 2],
        }

    if frappe.db.count("Supplier Operation Entry", filters=remaining_filters) == 0:
        frappe.db.set_value(
            "Subcontracting Order", doc.subcontracting_order, "custom_all_ops_complete", 1
        )


# ─────────────────────────────────────────────────────────────────────────────
# Private helpers
# ─────────────────────────────────────────────────────────────────────────────

def _get_supplier_wh_batch(item_code, warehouse):
    """Return batch_no, sec_qty (from Batch master), and stock_qty at supplier warehouse."""
    rows = frappe.db.sql(
        """
        SELECT batch_no, SUM(actual_qty) AS qty
        FROM `tabStock Ledger Entry`
        WHERE item_code = %s AND warehouse = %s AND is_cancelled = 0
        GROUP BY batch_no
        HAVING SUM(actual_qty) > 0
        ORDER BY SUM(actual_qty) DESC
        LIMIT 1
        """,
        (item_code, warehouse),
        as_dict=True,
    )
    row = rows[0] if rows else {}
    batch_no = row.get("batch_no")
    sec_qty = flt(frappe.db.get_value("Batch", batch_no, "custom_sec_qty")) if batch_no else 0
    return {
        "batch_no": batch_no,
        "sec_qty": sec_qty,
        "stock_qty": flt(row.get("qty")),
    }


def _get_prev_soe_consumed(item_code, current_sequence_id, prev_soe_name=None, work_order=None, sco_name=None):
    """Return current_sec_qty / current_stock_qty from the previous SOE's item row.
    Filters by work_order when available, falls back to sco_name.
    """
    if (current_sequence_id or 1) <= 1:
        return {}

    soe_name = prev_soe_name
    if not soe_name:
        if work_order:
            filters = {
                "work_order": work_order,
                "sequence_id": ["<", current_sequence_id],
                "docstatus": ["!=", 2],
            }
        else:
            filters = {
                "subcontracting_order": sco_name,
                "sequence_id": ["<", current_sequence_id],
                "docstatus": ["!=", 2],
            }
        soe_name = frappe.db.get_value(
            "Supplier Operation Entry", filters, "name", order_by="sequence_id desc"
        )

    if not soe_name:
        return {}

    row = frappe.db.get_value(
        "Supplier Operation Item",
        {"parent": soe_name, "item_code": item_code},
        ["current_sec_qty", "current_stock_qty"],
        as_dict=True,
    )
    if not row:
        return {}
    return {"sec_qty": flt(row.current_sec_qty), "stock_qty": flt(row.current_stock_qty)}


def _reduce_batch_sec_qty(batch_no, consumed_qty):
    current = flt(frappe.db.get_value("Batch", batch_no, "custom_sec_qty"))
    frappe.db.set_value("Batch", batch_no, "custom_sec_qty", flt(current - flt(consumed_qty), 3))
