import frappe
from frappe import _
from frappe.utils import flt, today


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
    Populates drawing items and total weight from Material Planning reservations.
    """
    pp = frappe.get_doc("Production Plan", pp_name)

    sub_ops = [r for r in (pp.custom_process_planning or []) if r.work_type == "Subcontractor"]
    if not sub_ops:
        frappe.throw(_("No Subcontractor operations found in the Process Planning table."))
    if not pp.custom_vendor_contractor:
        frappe.throw(_("Please set the Vendor/Contractor on the Production Plan before creating a Subcontracting Order."))

    wo_list = frappe.get_all("Work Order", filters={"production_plan": pp_name}, limit=1, pluck="name")
    wo_name = wo_list[0] if wo_list else None

    if wo_name:
        wo = frappe.get_doc("Work Order", wo_name)
        fg_item = wo.production_item
        fg_qty = wo.qty
        fg_warehouse = wo.fg_warehouse
        bom_no = wo.bom_no
    else:
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

    # Build drawing items and total weight from Material Planning reservations
    drawing_rows = []
    total_weight = 0.0
    for pi in pp.po_items:
        mp_name    = pi.get("custom_material_planning")
        duno       = pi.get("custom_duno_mark_no") or ""
        weight     = _get_mp_drawing_weight(mp_name, duno)
        total_weight += weight
        drawing_rows.append({
            "drawing": pi.get("custom_drawing"),
            "item_code": pi.item_code,
            "item_name": pi.get("item_name") or frappe.db.get_value("Item", pi.item_code, "item_name") or pi.item_code,
            "duno_mark_no": duno,
            "customer_drawing_number": pi.get("custom_customer_drawing_number"),
            "material_planning": mp_name,
            "customer_weight_kg": flt(pi.get("custom_customer_weight_kg"), 3),
            "total_weight_kg": flt(weight, 3),
        })

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
        "custom_total_weight_kg": flt(total_weight, 3),
        "custom_source_warehouse": pp.custom_raw_material_warehouse or "",
    })
    sco.flags.ignore_validate = True
    sco.insert(ignore_permissions=True, ignore_mandatory=True)

    # Insert drawing item rows directly after SCO creation
    for row_data in drawing_rows:
        row_data.update({
            "doctype": "SCO Drawing Item",
            "parent": sco.name,
            "parenttype": "Subcontracting Order",
            "parentfield": "custom_drawing_items",
        })
        frappe.get_doc(row_data).insert(ignore_permissions=True)

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
    wo.set_required_items()
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
    Op 1 available_to_consume = SCO's transferred weight (0 if not yet transferred).
    Op 2+ available_to_consume = previous SOE's total_consumed_kg.
    """
    sco = frappe.get_doc("Subcontracting Order", sco_name)
    if sco.docstatus != 1:
        frappe.throw(_("Subcontracting Order must be submitted before creating Supplier Operation Entries."))

    pp_name = sco.custom_production_plan
    if not pp_name:
        frappe.throw(_("Subcontracting Order is not linked to a Production Plan."))

    return _create_soes_for_sco(sco)


@frappe.whitelist()
def create_send_to_subcontractor_entry(sco_name):
    """Create a draft 'Send to Subcontractor' Stock Entry.
    Fetches reserved batches from Material Planning linked to each PP item.
    """
    sco = frappe.get_doc("Subcontracting Order", sco_name)
    if not sco.supplier_warehouse:
        frappe.throw(_("Please set the Supplier Warehouse on the Subcontracting Order first."))
    if not sco.get("custom_source_warehouse"):
        frappe.throw(_("Please set the Source Warehouse (RM) on the Subcontracting Order first."))
    if sco.docstatus != 1:
        frappe.throw(_("Subcontracting Order must be submitted first."))

    pp_name = sco.custom_production_plan
    if not pp_name:
        frappe.throw(_("Subcontracting Order is not linked to a Production Plan."))

    pp = frappe.get_doc("Production Plan", pp_name)
    source_warehouse = sco.custom_source_warehouse
    supplier_warehouse = sco.supplier_warehouse

    # Collect items from all Material Plannings linked to PP items.
    # Deduplicate MP names — the same MP may be linked to multiple PP items (drawings),
    # and calling _get_mp_reserved_batches more than once per MP would sum batches N times.
    raw_items = []
    seen_mps = set()
    for pi in pp.po_items:
        mp_name = pi.get("custom_material_planning")
        if not mp_name or mp_name in seen_mps:
            continue
        seen_mps.add(mp_name)
        raw_items.extend(_get_mp_reserved_batches(mp_name, source_warehouse, supplier_warehouse))

    if not raw_items:
        frappe.throw(_("No reserved batches found in Material Planning to transfer. "
                       "Ensure batches are reserved in the linked Material Planning documents."))

    # Deduplicate: same item + batch → merge primary qty and sec_qty
    merged = {}
    for item in raw_items:
        key = (item["item_code"], item.get("batch_no") or "")
        if key in merged:
            merged[key]["qty"] = flt(merged[key]["qty"] + item["qty"], 3)
            merged[key]["custom_sec_qty"] = flt(
                merged[key].get("custom_sec_qty", 0) + item.get("custom_sec_qty", 0), 3
            )
        else:
            merged[key] = item.copy()

    se = frappe.get_doc({
        "doctype": "Stock Entry",
        "stock_entry_type": "Send to Subcontractor",
        "subcontracting_order": sco_name,
        "items": list(merged.values()),
    })
    se.insert(ignore_permissions=True)
    return se.name


@frappe.whitelist()
def get_soe_summary(sco_name):
    """Operation-wise Available to Consume / Total Consumed for a SCO's Supplier Operation
    Entries — used by the Operations tab on the Subcontracting Order."""
    return frappe.get_all(
        "Supplier Operation Entry",
        filters={"subcontracting_order": sco_name, "docstatus": ["!=", 2]},
        fields=[
            "name", "sequence_id", "operation", "status", "docstatus",
            "available_to_consume_kg", "total_consumed_kg",
        ],
        order_by="sequence_id asc",
    )


@frappe.whitelist()
def create_return_stock_entry(sco_name, target_warehouse):
    """Transfer all remaining stock in supplier warehouse back to company warehouse."""
    sco = frappe.get_doc("Subcontracting Order", sco_name)
    if not sco.supplier_warehouse:
        frappe.throw(_("Supplier Warehouse is not set on the Subcontracting Order."))

    se_items = _get_supplier_wh_current_stock(sco, target_warehouse)
    if not se_items:
        frappe.throw(_("No stock found in supplier warehouse to return."))

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
    """Compute total_consumed_kg from log rows; block if it exceeds available."""
    total = sum(flt(r.weight_kg) for r in (doc.consumption_log or []))
    doc.total_consumed_kg = flt(total, 3)

    available = flt(doc.available_to_consume_kg)
    if available > 0 and total > available:
        frappe.throw(
            _("You have entered {0} Kg, but only {1} Kg is available to consume "
              "(carried from the previous operation). Either reduce the consumed quantity "
              "to {1} Kg, or increase the completed quantity in the previous operation.")
            .format(flt(total, 3), flt(available, 3)),
            title=_("Exceeds Available to Consume"),
        )


def before_submit_supplier_operation_entry(doc, method):
    """Enforce sequential, status-gated submission:
      - Status must be 'Completed' before submit.
      - Every earlier-sequence operation for the same SCO must already be submitted.
    """
    if (doc.status or "") != "Completed":
        frappe.throw(
            _("Set Status to <b>Completed</b> before submitting this Supplier Operation Entry."),
            title=_("Operation Not Completed"),
        )

    seq = doc.sequence_id or 0
    if seq > 1:
        pending = frappe.get_all(
            "Supplier Operation Entry",
            filters={
                "subcontracting_order": doc.subcontracting_order,
                "sequence_id": ["<", seq],
                "docstatus": ["!=", 1],
            },
            fields=["sequence_id", "operation"],
            order_by="sequence_id asc",
        )
        if pending:
            first = pending[0]
            frappe.throw(
                _("Operation sequence {0} (<b>{1}</b>) is not completed yet. "
                  "Operations must be completed and submitted in sequence — "
                  "finish it before submitting sequence {2}.")
                .format(first.sequence_id, first.operation, seq),
                title=_("Complete Previous Operation First"),
            )


def _propagate_available_to_next(doc):
    """Push this operation's Total Consumed into the NEXT operation's Available to Consume.
    Only updates the next operation while it is still a draft, so a submitted/locked
    downstream entry is never overwritten."""
    next_soe = frappe.db.get_value(
        "Supplier Operation Entry",
        {
            "subcontracting_order": doc.subcontracting_order,
            "sequence_id": (doc.sequence_id or 0) + 1,
            "docstatus": 0,
        },
        "name",
    )
    if next_soe:
        frappe.db.set_value(
            "Supplier Operation Entry",
            next_soe,
            "available_to_consume_kg",
            flt(doc.total_consumed_kg, 3),
            update_modified=False,
        )


def on_update_supplier_operation_entry(doc, method):
    """Live propagation: as soon as consumption is entered/saved on a draft operation,
    flow the consumed Kg into the next operation's Available to Consume."""
    if doc.docstatus == 0:
        _propagate_available_to_next(doc)


def on_submit_supplier_operation_entry(doc, method):
    """On submit: push total_consumed_kg to next operation's available_to_consume_kg.
    Mark SCO all_ops_complete if this is the last operation.
    """
    _propagate_available_to_next(doc)

    # Check if all operations are complete
    remaining = frappe.db.count(
        "Supplier Operation Entry",
        filters={
            "subcontracting_order": doc.subcontracting_order,
            "sequence_id": [">", doc.sequence_id or 0],
            "docstatus": ["!=", 2],
        },
    )
    if remaining == 0:
        frappe.db.set_value(
            "Subcontracting Order", doc.subcontracting_order, "custom_all_ops_complete", 1
        )


# ─────────────────────────────────────────────────────────────────────────────
# Private helpers
# ─────────────────────────────────────────────────────────────────────────────

def _create_soes_for_sco(sco):
    """Create one SOE per Subcontractor operation in the linked Production Plan.
    Idempotent — skips any sequence_id that already has a live SOE.
    Op 1 gets available_to_consume_kg from custom_transferred_weight_kg (0 if not yet transferred).
    """
    pp_name = sco.custom_production_plan if hasattr(sco, "custom_production_plan") else sco.get("custom_production_plan")
    if not pp_name:
        return []

    pp = frappe.get_doc("Production Plan", pp_name)
    sub_ops = sorted(
        [r for r in (pp.custom_process_planning or []) if r.work_type == "Subcontractor"],
        key=lambda r: r.idx,
    )
    if not sub_ops:
        return []

    transferred_weight = flt(sco.get("custom_transferred_weight_kg") or 0)
    created_soes = []
    prev_soe_name = None

    for seq_idx, op_row in enumerate(sub_ops, start=1):
        existing = frappe.db.get_value(
            "Supplier Operation Entry",
            {"subcontracting_order": sco.name, "sequence_id": seq_idx, "docstatus": ["!=", 2]},
            "name",
        )
        if existing:
            prev_soe_name = existing
            continue

        if seq_idx == 1:
            available_to_consume = transferred_weight
        else:
            prev_consumed = flt(
                frappe.db.get_value("Supplier Operation Entry", prev_soe_name, "total_consumed_kg")
            ) if prev_soe_name else 0
            available_to_consume = prev_consumed

        soe = frappe.get_doc({
            "doctype": "Supplier Operation Entry",
            "subcontracting_order": sco.name,
            "production_plan": pp_name,
            "operation": op_row.operation_name,
            "sequence_id": seq_idx,
            "supplier": sco.supplier,
            "supplier_warehouse": sco.supplier_warehouse or "",
            "status": "Open",
            "available_to_consume_kg": flt(available_to_consume, 3),
            "total_consumed_kg": 0,
        })
        soe.insert(ignore_permissions=True)
        prev_soe_name = soe.name
        created_soes.append(soe.name)

    return created_soes


def _get_mp_total_weight(mp_name):
    """Sum of calculated batch weights for all reserved rows in a Material Planning document."""
    if not mp_name:
        return 0.0

    # material_mapping: batch_calc_qty (Kg) for reserved rows with a batch assigned
    mapping_weight = frappe.db.sql(
        """
        SELECT COALESCE(SUM(batch_calc_qty), 0)
        FROM `tabMaterial Planning Material Mapping`
        WHERE parent = %s AND is_reserved = 1 AND batch IS NOT NULL AND batch != ''
        """,
        mp_name,
    )[0][0] or 0

    # available_raw_material: reserved_qty (Kg) for reserved rows
    available_weight = frappe.db.sql(
        """
        SELECT COALESCE(SUM(reserved_qty), 0)
        FROM `tabMaterial Planning Available Raw Material`
        WHERE parent = %s AND is_reserved = 1
        """,
        mp_name,
    )[0][0] or 0

    return flt(mapping_weight) + flt(available_weight)


def _get_mp_drawing_weight(mp_name, duno_mark_no):
    """Per-drawing planned RM weight — sum of qty from raw_materials sub-table."""
    if not mp_name:
        return 0.0
    if duno_mark_no:
        wt = frappe.db.sql(
            """
            SELECT COALESCE(SUM(qty), 0)
            FROM `tabMaterial Planning Raw Material`
            WHERE parent = %s AND duno_mark_no = %s
            """,
            (mp_name, duno_mark_no),
        )[0][0] or 0
        return flt(wt)
    return _get_mp_total_weight(mp_name)


def _get_mp_reserved_batches(mp_name, source_warehouse, supplier_warehouse):
    """Return SE item dicts for all reserved batches in a Material Planning document.
    Includes sec_qty, dimensions, and unit_weight for each SE line.
    """
    items = []

    # Cache item stock_uom and unit_weight to avoid N queries
    _uom_cache = {}
    _uwt_cache = {}

    def _stock_uom(item_code):
        if item_code not in _uom_cache:
            _uom_cache[item_code] = frappe.db.get_value("Item", item_code, "stock_uom") or "Kg"
        return _uom_cache[item_code]

    def _unit_weight(item_code):
        if item_code not in _uwt_cache:
            _uwt_cache[item_code] = flt(frappe.db.get_value("Item", item_code, "custom_unit_weight") or 0)
        return _uwt_cache[item_code]

    # From material_mapping: batch-assigned reserved rows
    rows = frappe.get_all(
        "Material Planning Material Mapping",
        filters={"parent": mp_name, "is_reserved": 1},
        fields=[
            "item_code", "batch", "batch_calc_qty", "batch_sec_qty",
            "batch_length", "batch_width", "batch_thickness", "batch_unit_weight",
            "batch_parent_item_group", "parent_item_group", "sec_uom",
        ],
    )
    for r in rows:
        if r.batch and flt(r.batch_calc_qty) > 0:
            items.append({
                "item_code": r.item_code,
                "batch_no": r.batch,
                # v15: use the batch_no field directly; Frappe creates the SBB on submit.
                "use_serial_batch_fields": 1,
                "qty": flt(r.batch_calc_qty, 3),
                "uom": _stock_uom(r.item_code),
                "s_warehouse": source_warehouse,
                "t_warehouse": supplier_warehouse,
                "custom_sec_qty": flt(r.batch_sec_qty, 3),
                "custom_sec_uom": r.sec_uom or "",
                "custom_length": flt(r.batch_length, 3),
                "custom_width": flt(r.batch_width, 3),
                "custom_thickness": flt(r.batch_thickness, 3),
                "custom_unit_weight": flt(r.batch_unit_weight, 4),
                "custom_parent_item_group": r.batch_parent_item_group or r.parent_item_group or "",
            })

    # From available_raw_material: exact-match reserved rows
    rows2 = frappe.get_all(
        "Material Planning Available Raw Material",
        filters={"parent": mp_name, "is_reserved": 1},
        fields=[
            "item_code", "batch_no", "reserved_qty", "available_qty",
            "sec_qty", "sec_uom", "length", "width", "thickness", "parent_item_group",
        ],
    )
    for r in rows2:
        qty = flt(r.reserved_qty) or flt(r.available_qty)
        if r.batch_no and qty > 0:
            items.append({
                "item_code": r.item_code,
                "batch_no": r.batch_no,
                # v15: use the batch_no field directly; Frappe creates the SBB on submit.
                "use_serial_batch_fields": 1,
                "qty": flt(qty, 3),
                "uom": _stock_uom(r.item_code),
                "s_warehouse": source_warehouse,
                "t_warehouse": supplier_warehouse,
                "custom_sec_qty": flt(r.sec_qty, 3),
                "custom_sec_uom": r.sec_uom or "",
                "custom_length": flt(r.length, 3),
                "custom_width": flt(r.width, 3),
                "custom_thickness": flt(r.thickness, 3),
                "custom_unit_weight": _unit_weight(r.item_code),
                "custom_parent_item_group": r.parent_item_group or "",
            })

    return items


def _get_supplier_wh_current_stock(sco, target_warehouse):
    """Return SE item dicts for all stock currently in the supplier warehouse
    that belongs to batches reserved for this SCO's PP items."""
    pp_name = sco.custom_production_plan
    if not pp_name:
        return []

    pp = frappe.get_doc("Production Plan", pp_name)

    # Collect all reserved batch numbers across all MP documents linked to this PP
    all_batches = set()
    for pi in pp.po_items:
        mp_name = pi.get("custom_material_planning")
        if not mp_name:
            continue
        for r in frappe.get_all(
            "Material Planning Material Mapping",
            filters={"parent": mp_name, "is_reserved": 1},
            fields=["batch"],
        ):
            if r.batch:
                all_batches.add(r.batch)
        for r in frappe.get_all(
            "Material Planning Available Raw Material",
            filters={"parent": mp_name, "is_reserved": 1},
            fields=["batch_no"],
        ):
            if r.batch_no:
                all_batches.add(r.batch_no)

    if not all_batches:
        return []

    se_items = []
    for batch_no in all_batches:
        rows = frappe.db.sql(
            """
            SELECT item_code, SUM(actual_qty) AS qty
            FROM `tabStock Ledger Entry`
            WHERE batch_no = %s AND warehouse = %s AND is_cancelled = 0
            GROUP BY item_code
            HAVING SUM(actual_qty) > 0
            """,
            (batch_no, sco.supplier_warehouse),
            as_dict=True,
        )
        for r in rows:
            se_items.append({
                "item_code": r.item_code,
                "batch_no": batch_no,
                # v15: use the batch_no field directly; Frappe creates the SBB on submit.
                "use_serial_batch_fields": 1,
                "qty": flt(r.qty, 3),
                "s_warehouse": sco.supplier_warehouse,
                "t_warehouse": target_warehouse,
            })

    return se_items
