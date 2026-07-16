from collections import defaultdict

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
    if not frappe.has_permission("Subcontracting Order", "create"):
        frappe.throw(_("Not permitted to create Subcontracting Orders"), frappe.PermissionError)

    existing = frappe.db.get_value(
        "Subcontracting Order", {"custom_production_plan": pp_name, "docstatus": ["!=", 2]}, "name"
    )
    if existing:
        frappe.throw(
            _(
                "A Subcontracting Order ({0}) already exists for this Production Plan. "
                "Open the existing Subcontracting Order from the connections panel."
            ).format(existing)
        )

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

    # Build drawing items + weight summary from Material Planning reservations.
    # Per drawing: customer-provided weight, planned RM weight, mapped (actual
    # reserved batch) weight, and the over-mapped excess to be returned by the supplier.
    drawing_rows = []
    total_customer = total_planned = total_mapped = total_excess = 0.0
    _mapped_cache = {}   # mp_name -> {duno_mark_no: mapped_kg}
    _excess_cache = {}   # mp_name -> {duno_mark_no: excess_kg}
    _drawing_weight_cache = {}  # mp_name -> {duno_mark_no: planned_kg}
    for pi in pp.po_items:
        mp_name = pi.get("custom_material_planning")
        duno    = pi.get("custom_duno_mark_no") or ""

        if mp_name not in _mapped_cache:
            _mapped_cache[mp_name] = _get_mp_mapped_weight_by_duno(mp_name)
            _excess_cache[mp_name] = _get_mp_excess_by_duno(mp_name)
        if mp_name not in _drawing_weight_cache:
            _drawing_weight_cache[mp_name] = _get_mp_drawing_weights_by_duno(mp_name)

        if duno:
            planned = _drawing_weight_cache[mp_name].get(duno, 0.0)
            mapped = _mapped_cache[mp_name].get(duno, 0.0)
            excess = _excess_cache[mp_name].get(duno, 0.0)
        else:
            # No DUNO on the PP item — take the whole Material Planning's totals.
            planned = _get_mp_total_weight(mp_name)
            mapped = _get_mp_total_weight(mp_name)
            excess = sum(_excess_cache[mp_name].values())

        customer = flt(pi.get("custom_customer_weight_kg"), 3)
        total_customer += customer
        total_planned  += planned
        total_mapped   += mapped
        total_excess   += excess

        drawing_rows.append({
            "drawing": pi.get("custom_drawing"),
            "item_code": pi.item_code,
            "item_name": pi.get("item_name") or frappe.db.get_value("Item", pi.item_code, "item_name") or pi.item_code,
            "duno_mark_no": duno,
            "customer_drawing_number": pi.get("custom_customer_drawing_number"),
            "material_planning": mp_name,
            "customer_weight_kg": customer,
            "total_weight_kg": flt(planned, 3),
            "mapped_weight_kg": flt(mapped, 3),
            "excess_weight_kg": flt(excess, 3),
            "qty_to_manufacture": flt(pi.get("planned_qty"), 3),
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
        "custom_customer_weight_kg": flt(total_customer, 3),
        "custom_total_weight_kg": flt(total_planned, 3),
        "custom_mapped_weight_kg": flt(total_mapped, 3),
        "custom_excess_weight_kg": flt(total_excess, 3),
    })
    # Run the app's own BOM-active check explicitly rather than letting the
    # blanket ignore_validate below skip it — this is the one check from
    # CustomSubcontractingOrder.validate() that must still fire at creation
    # time, so an inactive/missing BOM is caught here, not deferred to the
    # next unrelated-looking save (see IMM-03 / Report 3 Finding C-02).
    sco._pp_validate_items()
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
    """Create a Work Order for Internal Jobcard operations from a submitted Production Plan.
    Populates custom_drawing_items and weight summary fields (mirrors create_sco_from_production_plan).
    # SHARED_SCO_JC: mirrors create_sco_from_production_plan
    """
    if not frappe.has_permission("Work Order", "create"):
        frappe.throw(_("Not permitted to create Work Orders"), frappe.PermissionError)

    existing = frappe.get_all(
        "Work Order", filters={"production_plan": pp_name, "docstatus": ["!=", 2]}, limit=1, pluck="name"
    )
    if existing:
        frappe.throw(
            _(
                "A Work Order ({0}) already exists for this Production Plan. "
                "Open the existing Work Order from the connections panel."
            ).format(existing[0])
        )

    pp = frappe.get_doc("Production Plan", pp_name)

    internal_ops = [r for r in (pp.custom_process_planning or []) if r.work_type == "Internal Jobcard"]
    if not internal_ops:
        frappe.throw(_("No Internal Jobcard operations found in the Process Planning table."))
    if not pp.po_items:
        frappe.throw(_("No items found in the Production Plan."))

    pp_item = pp.po_items[0]
    bom_no = pp_item.bom_no
    if not bom_no:
        frappe.throw(_("No BOM set on the Production Plan item."))
    # Same BOM-active check create_sco_from_production_plan's _pp_validate_items
    # runs for the SCO side — run it explicitly here too, since the
    # ignore_validate flag below would otherwise skip ERPNext core's own
    # BOM-active checks for this Work Order at the one moment it matters most
    # (see IMM-03 / Report 3 Finding C-02).
    if not frappe.db.get_value("BOM", bom_no, "is_active"):
        frappe.throw(_("BOM {0} is not active.").format(bom_no))

    company = (
        frappe.defaults.get_user_default("Company")
        or frappe.db.get_single_value("Global Defaults", "default_company")
    )

    # Build drawing items + weight summary from Material Planning (same logic as create_sco_from_production_plan).
    # SHARED_SCO_JC: identical loop to create_sco_from_production_plan
    drawing_rows = []
    total_customer = total_planned = total_mapped = total_excess = 0.0
    _mapped_cache = {}
    _excess_cache = {}
    _drawing_weight_cache = {}  # mp_name -> {duno_mark_no: planned_kg}
    for pi in pp.po_items:
        mp_name = pi.get("custom_material_planning")
        duno    = pi.get("custom_duno_mark_no") or ""

        if mp_name not in _mapped_cache:
            _mapped_cache[mp_name] = _get_mp_mapped_weight_by_duno(mp_name)
            _excess_cache[mp_name] = _get_mp_excess_by_duno(mp_name)
        if mp_name not in _drawing_weight_cache:
            _drawing_weight_cache[mp_name] = _get_mp_drawing_weights_by_duno(mp_name)

        if duno:
            planned = _drawing_weight_cache[mp_name].get(duno, 0.0)
            mapped = _mapped_cache[mp_name].get(duno, 0.0)
            excess = _excess_cache[mp_name].get(duno, 0.0)
        else:
            planned = _get_mp_total_weight(mp_name)
            mapped = _get_mp_total_weight(mp_name)
            excess = sum(_excess_cache[mp_name].values())

        customer = flt(pi.get("custom_customer_weight_kg"), 3)
        total_customer += customer
        total_planned  += planned
        total_mapped   += mapped
        total_excess   += excess

        drawing_rows.append({
            "drawing": pi.get("custom_drawing"),
            "item_code": pi.item_code,
            "item_name": pi.get("item_name") or frappe.db.get_value("Item", pi.item_code, "item_name") or pi.item_code,
            "duno_mark_no": duno,
            "customer_drawing_number": pi.get("custom_customer_drawing_number"),
            "material_planning": mp_name,
            "customer_weight_kg": customer,
            "total_weight_kg": flt(planned, 3),
            "mapped_weight_kg": flt(mapped, 3),
            "excess_weight_kg": flt(excess, 3),
            "qty_to_manufacture": flt(pi.get("planned_qty"), 3),
        })

    # Collect only Internal Jobcard operations from routing.
    internal_op_names = {r.operation_name for r in internal_ops}
    routing = frappe.db.get_value("BOM", bom_no, "routing")
    filtered_ops = []
    if routing:
        filtered_ops = frappe.get_all(
            "BOM Operation",
            filters={
                "parent": routing,
                "parenttype": "Routing",
                "operation": ["in", list(internal_op_names)],
            },
            fields=["operation", "workstation", "time_in_mins", "sequence_id"],
            order_by="sequence_id asc",
        )

    wo = frappe.new_doc("Work Order")
    wo.update({
        "production_item": pp_item.item_code,
        "bom_no": bom_no,
        "qty": flt(pp_item.planned_qty) or 1,
        "company": company,
        "production_plan": pp_name,
        "fg_warehouse": pp_item.warehouse or "",
        "use_multi_level_bom": 0,
        "custom_source_warehouse": pp.get("custom_raw_material_warehouse") or "",
        "custom_customer_weight_kg": flt(total_customer, 3),
        "custom_total_weight_kg":    flt(total_planned, 3),
        "custom_mapped_weight_kg":   flt(total_mapped, 3),
        "custom_excess_weight_kg":   flt(total_excess, 3),
    })
    # Order by the Process Planning table's own row order (not the BOM's routing
    # sequence_id) so it stays consistent with how _create_soes_for_sco orders the
    # SCO side, then renumber locally 1..N — mirrors _create_soes_for_sco's
    # enumerate(sub_ops, start=1). A mixed plan's Internal ops may start at BOM
    # sequence_id 4+, but the WO's own chain (and ERPNext core's own submit
    # validation, which requires row 1 to be sequence_id 1) needs it to start at 1.
    internal_op_idx = {r.operation_name: r.idx for r in internal_ops}
    filtered_ops.sort(key=lambda op: internal_op_idx.get(op.operation, 0))

    wo.set_required_items()
    wo.operations = []
    for local_seq, op in enumerate(filtered_ops, start=1):
        wo.append("operations", {
            "operation": op.operation,
            "workstation": op.workstation,
            "time_in_mins": flt(op.time_in_mins) or 60,
            "sequence_id": local_seq,
            "status": "Pending",
        })

    wo.flags.ignore_mandatory = True
    wo.flags.ignore_validate = True
    wo.insert(ignore_permissions=True)

    # Insert drawing item rows (same pattern as create_sco_from_production_plan).
    # SHARED_SCO_JC: mirrors SCO drawing_item insertion
    for row_data in drawing_rows:
        row_data.update({
            "doctype": "SCO Drawing Item",
            "parent": wo.name,
            "parenttype": "Work Order",
            "parentfield": "custom_drawing_items",
        })
        frappe.get_doc(row_data).insert(ignore_permissions=True)

    return wo.name


@frappe.whitelist()
def create_supplier_operation_entries(sco_name):
    """Create one SOE per subcontractor operation (idempotent).
    Op 1 available_to_consume = SCO's transferred weight (0 if not yet transferred).
    Op 2+ available_to_consume = previous SOE's total_consumed_kg.
    """
    if not frappe.has_permission("Supplier Operation Entry", "create"):
        frappe.throw(_("Not permitted to create Supplier Operation Entries"), frappe.PermissionError)

    sco = frappe.get_doc("Subcontracting Order", sco_name)
    if sco.docstatus != 1:
        frappe.throw(_("Subcontracting Order must be submitted before creating Supplier Operation Entries."))

    pp_name = sco.custom_production_plan
    if not pp_name:
        frappe.throw(_("Subcontracting Order is not linked to a Production Plan."))

    return _create_soes_for_sco(sco)


@frappe.whitelist()
def create_send_to_subcontractor_entry(sco_name):
    """Create draft Stock Entries for raw-material transfer.

    Items with cnc_process=1 (and a CNC Warehouse set on the SCO) are routed to the
    CNC warehouse via a 'Material Transfer' SE; all other items go to the supplier
    warehouse via a 'Send to Subcontractor' SE.  Returns a dict with keys
    ``supplier_se`` and/or ``cnc_se`` depending on which entries were created.
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
    cnc_warehouse = sco.get("custom_cnc_warehouse") or ""

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

    # Split into supplier items and CNC items; deduplicate within each bucket.
    supplier_merged = {}
    cnc_merged = {}
    for item in raw_items:
        is_cnc = bool(item.pop("cnc_process", 0)) and bool(cnc_warehouse)
        key = (item["item_code"], item.get("batch_no") or "")
        if is_cnc:
            target = cnc_merged
            item["t_warehouse"] = cnc_warehouse
        else:
            target = supplier_merged
        if key in target:
            target[key]["qty"] = flt(target[key]["qty"] + item["qty"], 3)
            target[key]["custom_sec_qty"] = flt(
                target[key].get("custom_sec_qty", 0) + item.get("custom_sec_qty", 0), 3
            )
        else:
            target[key] = item.copy()

    result = {}

    if supplier_merged:
        # CustomStockEntry.validate_subcontract_order skips the ERPNext supplied_items
        # check for PP-flow SCOs, so setting subcontracting_order is now safe and lets
        # Frappe's connections panel discover these SEs via the standard Link field.
        se = frappe.get_doc({
            "doctype": "Stock Entry",
            "stock_entry_type": "Send to Subcontractor",
            "subcontracting_order": sco_name,
            "custom_sco_ref": sco_name,
            "company": sco.company,
            "items": list(supplier_merged.values()),
        })
        se.insert(ignore_permissions=True)
        result["supplier_se"] = se.name

    if cnc_merged and cnc_warehouse:
        cnc_se = frappe.get_doc({
            "doctype": "Stock Entry",
            "stock_entry_type": "Material Transfer",
            "subcontracting_order": sco_name,
            "custom_sco_ref": sco_name,
            "company": sco.company,
            "items": list(cnc_merged.values()),
        })
        cnc_se.insert(ignore_permissions=True)
        result["cnc_se"] = cnc_se.name

    if not result:
        frappe.throw(_("No items to transfer."))

    return result


@frappe.whitelist()
def get_sco_pending_items(sco_name):
    """Return raw-material items not yet transferred for this SCO.

    Each row includes item_name, batch_no, qty (Kg), custom_sec_qty (Nos), cnc_process,
    and all SE item fields needed to create a transfer entry.
    Draft and submitted SEs both count as transferred (docstatus != 2).
    """
    sco = frappe.get_doc("Subcontracting Order", sco_name)
    if not sco.custom_production_plan:
        frappe.throw(_("Subcontracting Order is not linked to a Production Plan."))
    if not sco.custom_source_warehouse:
        frappe.throw(_("Please set the Source Warehouse (RM) on the Subcontracting Order first."))

    source_warehouse = sco.custom_source_warehouse
    supplier_warehouse = sco.supplier_warehouse
    cnc_warehouse = sco.get("custom_cnc_warehouse") or ""

    # Collect all reserved items from MPs linked to the Production Plan
    raw_items = []
    seen_mps = set()
    pp = frappe.get_doc("Production Plan", sco.custom_production_plan)
    for pi in pp.po_items:
        mp_name = pi.get("custom_material_planning")
        if not mp_name or mp_name in seen_mps:
            continue
        seen_mps.add(mp_name)
        raw_items.extend(_get_mp_reserved_batches(mp_name, source_warehouse, supplier_warehouse))

    if not raw_items:
        return []

    # Aggregate total reserved per (item_code, batch_no, is_cnc)
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

    # Already transferred to supplier warehouse (Send to Subcontractor SEs, not cancelled)
    supplier_done = {}
    for r in frappe.db.sql("""
        SELECT sed.item_code, sed.batch_no,
               SUM(sed.qty) AS qty,
               SUM(IFNULL(sed.custom_sec_qty, 0)) AS sec_qty
        FROM `tabStock Entry Detail` sed
        JOIN `tabStock Entry` se ON se.name = sed.parent
        WHERE se.custom_sco_ref = %s
          AND se.stock_entry_type = 'Send to Subcontractor'
          AND se.docstatus != 2
        GROUP BY sed.item_code, sed.batch_no
    """, sco_name, as_dict=True):
        supplier_done[(r.item_code, r.batch_no or "")] = flt(r.qty)

    # Already transferred to CNC warehouse (Material Transfer SEs, not cancelled)
    cnc_done = {}
    if cnc_warehouse:
        for r in frappe.db.sql("""
            SELECT sed.item_code, sed.batch_no,
                   SUM(sed.qty) AS qty,
                   SUM(IFNULL(sed.custom_sec_qty, 0)) AS sec_qty
            FROM `tabStock Entry Detail` sed
            JOIN `tabStock Entry` se ON se.name = sed.parent
            WHERE se.custom_sco_ref = %s
              AND se.stock_entry_type = 'Material Transfer'
              AND se.docstatus != 2
              AND sed.t_warehouse = %s
            GROUP BY sed.item_code, sed.batch_no
        """, (sco_name, cnc_warehouse), as_dict=True):
            cnc_done[(r.item_code, r.batch_no or "")] = flt(r.qty)

    # Compute pending items
    result = []
    for (item_code, batch_no, is_cnc), item in totals.items():
        done_qty = (cnc_done if is_cnc else supplier_done).get((item_code, batch_no), 0)
        pending_qty = flt(item["qty"] - done_qty, 3)
        if pending_qty <= 0:
            continue

        total_qty = flt(item["qty"])
        ratio = pending_qty / total_qty if total_qty else 0
        result.append({
            "item_code": item_code,
            "item_name": frappe.db.get_value("Item", item_code, "item_name") or item_code,
            "batch_no": batch_no,
            "qty": pending_qty,
            "uom": item.get("uom") or "Kg",
            "custom_sec_qty": flt(flt(item.get("custom_sec_qty", 0)) * ratio, 3),
            "custom_sec_uom": item.get("custom_sec_uom") or "",
            "s_warehouse": source_warehouse,
            "t_warehouse": cnc_warehouse if is_cnc else supplier_warehouse,
            "cnc_process": 1 if is_cnc else 0,
            "use_serial_batch_fields": 1,
            "custom_length": flt(item.get("custom_length", 0), 3),
            "custom_width": flt(item.get("custom_width", 0), 3),
            "custom_thickness": flt(item.get("custom_thickness", 0), 3),
            "custom_unit_weight": flt(item.get("custom_unit_weight", 0), 4),
            "custom_parent_item_group": item.get("custom_parent_item_group") or "",
        })

    return result


@frappe.whitelist()
def create_partial_transfer(sco_name, selected_items_json, transfer_type):
    """Create a draft Stock Entry for the caller-selected raw-material items.

    transfer_type: "supplier" → Send to Subcontractor to supplier_warehouse
                   "cnc"      → Material Transfer to custom_cnc_warehouse
    """
    import json as _json
    selected = _json.loads(selected_items_json) if isinstance(selected_items_json, str) else selected_items_json

    if not selected:
        frappe.throw(_("No items selected for transfer."))

    sco = frappe.get_doc("Subcontracting Order", sco_name)
    if sco.docstatus != 1:
        frappe.throw(_("Subcontracting Order must be submitted first."))
    if not sco.supplier_warehouse:
        frappe.throw(_("Please set the Supplier Warehouse on the Subcontracting Order first."))
    if not sco.custom_source_warehouse:
        frappe.throw(_("Please set the Source Warehouse (RM) on the Subcontracting Order first."))

    if transfer_type == "cnc":
        t_warehouse = sco.get("custom_cnc_warehouse")
        if not t_warehouse:
            frappe.throw(_("No CNC Warehouse set on this Subcontracting Order."))
        se_type = "Material Transfer"
    else:
        t_warehouse = sco.supplier_warehouse
        se_type = "Send to Subcontractor"

    se_items = []
    for item in selected:
        se_items.append({
            "item_code": item["item_code"],
            "batch_no": item.get("batch_no") or "",
            "use_serial_batch_fields": 1,
            "qty": flt(item["qty"]),
            "uom": item.get("uom") or "Kg",
            "s_warehouse": sco.custom_source_warehouse,
            "t_warehouse": t_warehouse,
            "custom_sec_qty": flt(item.get("custom_sec_qty") or 0),
            "custom_sec_uom": item.get("custom_sec_uom") or "",
            "custom_length": flt(item.get("custom_length") or 0),
            "custom_width": flt(item.get("custom_width") or 0),
            "custom_thickness": flt(item.get("custom_thickness") or 0),
            "custom_unit_weight": flt(item.get("custom_unit_weight") or 0),
            "custom_parent_item_group": item.get("custom_parent_item_group") or "",
        })

    se = frappe.get_doc({
        "doctype": "Stock Entry",
        "stock_entry_type": se_type,
        "subcontracting_order": sco_name,
        "custom_sco_ref": sco_name,
        "company": sco.company,
        "items": se_items,
    })
    se.insert(ignore_permissions=True)
    return se.name


@frappe.whitelist()
def create_cnc_to_supplier_entry(sco_name):
    """Transfer materials currently in the CNC warehouse to the supplier warehouse.

    Queries all submitted CNC Material Transfer SEs linked to this SCO, subtracts
    any quantity already forwarded to the supplier, and creates a new draft
    'Material Transfer' SE for the net remaining quantity.
    """
    sco = frappe.get_doc("Subcontracting Order", sco_name)
    if sco.docstatus != 1:
        frappe.throw(_("Subcontracting Order must be submitted first."))

    cnc_warehouse = sco.get("custom_cnc_warehouse")
    if not cnc_warehouse:
        frappe.throw(_("No CNC Warehouse set on the Subcontracting Order."))
    if not sco.supplier_warehouse:
        frappe.throw(_("Please set the Supplier Warehouse on the Subcontracting Order first."))

    # Items sent from source → CNC (grouped by item + batch)
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
        WHERE se.custom_sco_ref = %s
          AND se.stock_entry_type = 'Material Transfer'
          AND se.docstatus = 1
          AND sed.t_warehouse = %s
        GROUP BY sed.item_code, sed.batch_no
        HAVING SUM(sed.qty) > 0
        """,
        (sco_name, cnc_warehouse),
        as_dict=True,
    )

    if not sent_rows:
        frappe.throw(_("No CNC materials found. Ensure the CNC stock entry has been submitted."))

    # Items already forwarded from CNC → supplier
    fwd_rows = frappe.db.sql(
        """
        SELECT sed.item_code, sed.batch_no, SUM(sed.qty) AS qty
        FROM `tabStock Entry Detail` sed
        JOIN `tabStock Entry` se ON se.name = sed.parent
        WHERE se.custom_sco_ref = %s
          AND se.stock_entry_type = 'Material Transfer'
          AND se.docstatus = 1
          AND sed.s_warehouse = %s
          AND sed.t_warehouse = %s
        GROUP BY sed.item_code, sed.batch_no
        """,
        (sco_name, cnc_warehouse, sco.supplier_warehouse),
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
            "t_warehouse": sco.supplier_warehouse,
            "custom_sec_qty": flt(r.custom_sec_qty, 3),
            "custom_sec_uom": r.custom_sec_uom or "",
            "custom_length": flt(r.custom_length, 3),
            "custom_width": flt(r.custom_width, 3),
            "custom_thickness": flt(r.custom_thickness, 3),
            "custom_unit_weight": flt(r.custom_unit_weight, 4),
            "custom_parent_item_group": r.custom_parent_item_group or "",
        })

    if not se_items:
        frappe.throw(_("All CNC materials have already been transferred to the supplier warehouse."))

    se = frappe.get_doc({
        "doctype": "Stock Entry",
        "stock_entry_type": "Material Transfer",
        "subcontracting_order": sco_name,
        "custom_sco_ref": sco_name,
        "company": sco.company,
        "items": se_items,
    })
    se.insert(ignore_permissions=True)
    return se.name


@frappe.whitelist()
def get_soe_summary(sco_name):
    """Operation-wise summary for a SCO's Supplier Operation Entries."""
    from frappe.utils import flt

    soes = frappe.get_all(
        "Supplier Operation Entry",
        filters={"subcontracting_order": sco_name, "docstatus": ["!=", 2]},
        fields=[
            "name", "sequence_id", "operation", "status", "docstatus",
            "available_to_consume_kg", "total_consumed_kg",
        ],
        order_by="sequence_id asc",
    )
    if not soes:
        return soes

    drawing_rows = frappe.get_all(
        "SOE Drawing Detail",
        filters={"parent": ["in", [d.name for d in soes]]},
        fields=["parent", "drawing", "customer_drawing_number", "duno_mark_no",
                "qty_to_manufacture", "completed_qty_nos",
                "available_to_consume_nos", "transferred_weight_kg"],
        order_by="idx asc",
    )

    details_map = {}
    for dr in drawing_rows:
        details_map.setdefault(dr.parent, []).append(dr)

    for soe in soes:
        details = details_map.get(soe.name, [])
        soe["drawing_details"] = details
        soe["total_qty_to_mfg"] = sum(flt(d.qty_to_manufacture) for d in details)
        soe["total_completed_nos"] = sum(flt(d.completed_qty_nos) for d in details)
        seq = soe.get("sequence_id") or 1
        if seq == 1:
            soe["avail_nos"] = sum(flt(d.transferred_weight_kg) for d in details)
            soe["diff_nos"] = flt(soe["total_qty_to_mfg"]) - flt(soe["total_completed_nos"])
        else:
            soe["avail_nos"] = sum(flt(d.available_to_consume_nos) for d in details)
            soe["diff_nos"] = flt(soe["avail_nos"]) - flt(soe["total_completed_nos"])

    return soes


@frappe.whitelist()
def create_return_stock_entry(sco_name, target_warehouse):
    """Create a draft 'Material Receipt' Stock Entry that inwards the off-cut / balance
    material listed in the SCO's Excess Material Return table.

    The transferred raw material is cut and consumed into the finished good, so the leftover
    is the same item in NEW dimensions. It is therefore received as fresh stock (new batches,
    which inherit the entered dimensions via the Batch before_insert hook) rather than
    transferred back. Weight (Kg) per row is recomputed from the dimensions on validate.
    """
    sco = frappe.get_doc("Subcontracting Order", sco_name)
    if not target_warehouse:
        frappe.throw(_("Please set the Finished Goods/Return Warehouse on the Subcontracting Order first."))

    se_items = []
    new_row_names = []
    for r in (sco.get("custom_excess_return_items") or []):
        if r.get("stock_entry_created"):
            continue  # already has an SE — skip
        qty = flt(r.qty, 3)
        if not r.item_code or qty <= 0:
            continue
        new_row_names.append(r.name)
        se_items.append({
            "item_code": r.item_code,
            "qty": qty,
            "uom": r.get("uom") or frappe.db.get_value("Item", r.item_code, "stock_uom") or "Kg",
            "t_warehouse": target_warehouse,
            "custom_parent_item_group": r.get("parent_item_group") or "",
            "custom_unit_weight": flt(r.get("unit_weight"), 4),
            "custom_sec_qty": flt(r.get("sec_qty"), 3),
            "custom_sec_uom": r.get("sec_uom") or "",
            "custom_length": flt(r.get("length"), 3),
            "custom_width": flt(r.get("width"), 3),
            "custom_thickness": flt(r.get("thickness"), 3),
        })

    if not se_items:
        frappe.throw(_("No new off-cut items to process. All rows already have a Stock Entry created, "
                       "or no rows with Weight (Kg) > 0 exist."))

    se = frappe.get_doc({
        "doctype": "Stock Entry",
        "stock_entry_type": "Material Receipt",
        "company": sco.company,
        "items": se_items,
    })
    se.insert(ignore_permissions=True)

    # Lock the processed rows so they cannot be re-submitted
    for r in sco.get("custom_excess_return_items"):
        if r.name in new_row_names:
            r.stock_entry_created = 1
    sco.save(ignore_permissions=True)

    return se.name


@frappe.whitelist()
def create_finished_goods_entry(sco_name):
    """Create a draft 'Manufacture' Stock Entry that consumes the raw materials currently
    in the supplier warehouse and produces the finished good into the FG warehouse.

    Exposed via the 'Make Finished Goods Entry' button, which appears once raw materials
    have been transferred to the supplier. The user reviews and submits the draft; on
    submission the consumed RM leaves stock and the finished good is added to inventory.
    """
    sco = frappe.get_doc("Subcontracting Order", sco_name)
    if sco.docstatus != 1:
        frappe.throw(_("Subcontracting Order must be submitted first."))
    if not sco.supplier_warehouse:
        frappe.throw(_("Please set the Supplier Warehouse on the Subcontracting Order first."))
    if not flt(sco.get("custom_transferred_weight_kg")):
        frappe.throw(_("No raw material has been transferred to the supplier yet. "
                       "Transfer raw materials before making the finished-goods entry."))

    # Determine FG warehouse from SCO items or the linked Material Issue Plan's
    # excess/return warehouse (custom_return_warehouse moved there).
    fg_warehouse = ""
    if sco.items:
        fg_warehouse = sco.items[0].warehouse or ""
    if not fg_warehouse:
        mip_name = frappe.db.get_value("Material Issue Plan", {"subcontracting_order": sco.name})
        if mip_name:
            fg_warehouse = frappe.db.get_value("Material Issue Plan", mip_name, "excess_return_warehouse") or ""
    if not fg_warehouse:
        frappe.throw(_("No finished-good warehouse set. Set the warehouse on the "
                       "Subcontracting Order item (or the Finished Goods/Return Warehouse) first."))

    consumed = _get_supplier_wh_consumption_items(sco)
    if not consumed:
        frappe.throw(_("No raw-material stock found in the supplier warehouse to consume. "
                       "Ensure the raw materials have been transferred to the supplier."))

    # Build finished-goods rows from SCO Drawing Items (one row per drawing/DUNO).
    # qty_to_manufacture comes from the Production Plan Item (planned_qty).
    drawing_items = sco.get("custom_drawing_items") or []
    if not drawing_items:
        # Fallback: single FG row from sco.items when no drawing items exist
        if not sco.items:
            frappe.throw(_("No finished-good item found on the Subcontracting Order."))
        fg = sco.items[0]
        fg_rows = [{
            "item_code": fg.item_code,
            "qty": flt(fg.qty) or 1,
            "uom": frappe.db.get_value("Item", fg.item_code, "stock_uom") or fg.get("uom") or "Nos",
            "t_warehouse": fg_warehouse,
            "is_finished_item": 1,
        }]
    else:
        fg_rows = []
        for d in drawing_items:
            qty = flt(d.get("qty_to_manufacture"))
            if not qty:
                # Live-fetch from PP item using customer_drawing_number + duno_mark_no
                qty = flt(_get_pp_planned_qty(
                    sco.get("custom_production_plan"),
                    d.get("customer_drawing_number"),
                    d.get("duno_mark_no"),
                ))
            fg_rows.append({
                "item_code": d.item_code,
                "qty": qty or 1,
                "uom": frappe.db.get_value("Item", d.item_code, "stock_uom") or "Nos",
                "t_warehouse": fg_warehouse,
                "is_finished_item": 1,
                "description": (d.get("duno_mark_no") or d.get("customer_drawing_number") or ""),
            })

    items = list(consumed) + fg_rows

    se = frappe.get_doc({
        "doctype": "Stock Entry",
        "stock_entry_type": "Manufacture",
        "company": sco.company,
        "subcontracting_order": sco_name,
        "items": items,
    })
    se.insert(ignore_permissions=True)
    return se.name


# ─────────────────────────────────────────────────────────────────────────────
# Doc event handlers
# ─────────────────────────────────────────────────────────────────────────────

def validate_supplier_operation_entry(doc, method):
    """Per-drawing Nos tracking + validation.

    For all operations:
      - Sum qty_nos per drawing from consumption_log → update drawing_details.completed_qty_nos.
      - Auto-advance status from Open → In Progress when any Nos are logged.

    For Op-1 (sequence_id == 1):
      - Check the Manufacturing Settings trigger: if "Fully Transferred", block logging
        for a drawing whose transferred_weight_kg is 0.
      - Keep existing Kg over-consume guard (available_to_consume_kg from SCO transfer).

    For Op-2+ (sequence_id > 1):
      - Validate that total qty_nos per drawing does not exceed available_to_consume_nos.
    """
    seq = doc.sequence_id or 1

    # --- 1. Sum qty_nos per drawing ---
    log_nos_by_drawing = defaultdict(float)
    for r in (doc.consumption_log or []):
        if r.drawing and flt(r.qty_nos) > 0:
            log_nos_by_drawing[r.drawing] += flt(r.qty_nos)

    # --- 2. Push completed_qty_nos into drawing_details rows ---
    for row in (doc.drawing_details or []):
        row.completed_qty_nos = flt(log_nos_by_drawing.get(row.drawing or "", 0.0), 3)

    # --- 2a. Op-1: auto-set available_to_consume_nos = qty_to_manufacture when material
    #         has been transferred for that drawing (transferred_weight_kg > 0) ---
    if seq == 1:
        for row in (doc.drawing_details or []):
            if flt(row.transferred_weight_kg) > 0:
                row.available_to_consume_nos = flt(row.qty_to_manufacture, 3)

    # --- 2c. Update SOE-level Nos summary fields ---
    doc.total_available_nos = flt(
        sum(flt(r.available_to_consume_nos) for r in (doc.drawing_details or [])), 3
    )
    doc.total_completed_nos = flt(
        sum(flt(r.completed_qty_nos) for r in (doc.drawing_details or [])), 3
    )

    # --- 2b. Validate completed_qty_nos does not exceed qty_to_manufacture ---
    for row in (doc.drawing_details or []):
        qty_to_mfg = flt(row.qty_to_manufacture)
        completed = flt(row.completed_qty_nos)
        if qty_to_mfg > 0 and completed > qty_to_mfg:
            frappe.throw(
                _("Drawing {0}: Completed ({1} Nos) exceeds Qty to Manufacture ({2} Nos). "
                  "Reduce the logged quantity.")
                .format(row.customer_drawing_number or row.drawing, completed, qty_to_mfg),
                title=_("Completed Qty Exceeds Limit"),
            )

    # --- 3. Status ---
    if log_nos_by_drawing and doc.status == "Open":
        doc.status = "In Progress"

    # --- 4. Op-1: check log trigger setting ---
    if seq == 1 and log_nos_by_drawing:
        trigger = (
            frappe.db.get_single_value("Manufacturing Settings", "custom_soe_log_trigger")
            or "Fully Transferred"
        )
        if trigger == "Fully Transferred":
            detail_map = {r.drawing: r for r in (doc.drawing_details or []) if r.drawing}
            for drawing, nos in log_nos_by_drawing.items():
                row = detail_map.get(drawing)
                if row and flt(row.transferred_weight_kg) <= 0:
                    frappe.throw(
                        _("Drawing {0}: no material has been transferred to the supplier warehouse yet. "
                          "Transfer raw materials first, or change 'SOE Log Entry Allowed When' in "
                          "Manufacturing Settings to allow partial entries.")
                        .format(row.customer_drawing_number or drawing),
                        title=_("Material Not Yet Transferred"),
                    )

    # --- 5. Op-1: existing Kg over-consume guard (weight_kg in log) ---
    if seq == 1:
        total_kg = sum(flt(r.weight_kg) for r in (doc.consumption_log or []))
        doc.total_consumed_kg = flt(total_kg, 3)
        available_kg = flt(doc.available_to_consume_kg)
        if available_kg > 0 and total_kg > available_kg:
            frappe.throw(
                _("You have entered {0} Kg, but only {1} Kg is available to consume.")
                .format(flt(total_kg, 3), flt(available_kg, 3)),
                title=_("Exceeds Available to Consume"),
            )

    # --- 6. Op-2+: validate qty_nos per drawing against available_to_consume_nos ---
    if seq > 1:
        detail_map = {r.drawing: r for r in (doc.drawing_details or []) if r.drawing}
        for drawing, nos in log_nos_by_drawing.items():
            row = detail_map.get(drawing)
            available = flt(row.available_to_consume_nos) if row else 0.0
            label = (row.customer_drawing_number if row else None) or drawing
            if available <= 0:
                frappe.throw(
                    _("Drawing {0}: the previous operation has not completed any quantity "
                      "for this drawing. Consumption cannot be logged until the previous "
                      "operation is completed.")
                    .format(label),
                    title=_("Previous Operation Not Completed"),
                )
            if nos > available:
                frappe.throw(
                    _("Drawing {0}: entered {1} Nos but only {2} Nos are available "
                      "from the previous operation.")
                    .format(label, flt(nos, 3), flt(available, 3)),
                    title=_("Exceeds Available Qty"),
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
    """Push Op-1's total_consumed_kg into Op-2's available_to_consume_kg (Kg chain).
    Kept for backwards-compatibility with Op-1 Kg tracking."""
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


def _propagate_drawing_nos_to_next(doc):
    """Push per-drawing completed_qty_nos from this SOE's drawing_details into
    the next SOE's drawing_details.available_to_consume_nos.
    Only updates the next operation while it is still a draft."""
    next_soe_name = frappe.db.get_value(
        "Supplier Operation Entry",
        {
            "subcontracting_order": doc.subcontracting_order,
            "sequence_id": (doc.sequence_id or 0) + 1,
            "docstatus": 0,
        },
        "name",
    )
    if not next_soe_name:
        return

    drawing_nos = {
        r.drawing: flt(r.completed_qty_nos, 3)
        for r in (doc.drawing_details or [])
        if r.drawing
    }
    if not drawing_nos:
        return

    next_doc = frappe.get_doc("Supplier Operation Entry", next_soe_name)
    changed = False
    for row in (next_doc.drawing_details or []):
        new_val = drawing_nos.get(row.drawing or "", 0.0)
        if flt(row.available_to_consume_nos, 3) != flt(new_val, 3):
            row.available_to_consume_nos = flt(new_val, 3)
            changed = True

    if changed:
        next_doc.total_available_nos = flt(
            sum(flt(r.available_to_consume_nos) for r in (next_doc.drawing_details or [])), 3
        )
        next_doc.flags.ignore_validate = True
        next_doc.save(ignore_permissions=True)


def _update_sco_drawing_item_completion(doc):
    """Update SCO Drawing Items' completed_qty_nos from the submitted SOE's
    drawing_details so the SCO shows consolidated drawing completion."""
    drawing_nos = {
        r.drawing: flt(r.completed_qty_nos, 3)
        for r in (doc.drawing_details or [])
        if r.drawing
    }
    if not drawing_nos:
        return

    for row in frappe.get_all(
        "SCO Drawing Item",
        filters={"parent": doc.subcontracting_order},
        fields=["name", "drawing"],
    ):
        if row.drawing in drawing_nos:
            frappe.db.set_value(
                "SCO Drawing Item", row.name,
                "completed_qty_nos", drawing_nos[row.drawing],
                update_modified=False,
            )


def on_update_supplier_operation_entry(doc, method):
    """Live propagation on save: push Kg chain and per-drawing Nos to next operation."""
    if doc.docstatus == 0:
        _propagate_available_to_next(doc)
        _propagate_drawing_nos_to_next(doc)


def _push_sco_completion_to_wo(pp_name, last_soe):
    """Cross-chain counterpart of _propagate_available_to_next / _propagate_drawing_nos_to_next:
    when the SCO's final operation completes, hand its finished qty/weight off to the sibling
    Work Order's first Internal-Jobcard Job Card(s) (mixed-plan chain — some ops Subcontractor,
    the rest Internal Jobcard). No-op if there's no sibling WO yet, or no still-draft Op-1
    Job Card to push into (it will be handled by _populate_jcs_for_wo's reverse-order path
    instead, once that WO/JC is created).
    # SHARED_SCO_JC: cross-chain — no SOE-side mirror, this only runs on the SCO side
    """
    wo_name = frappe.db.get_value(
        "Work Order", {"production_plan": pp_name, "docstatus": ["!=", 2]}, "name"
    )
    if not wo_name:
        return

    nos_by_drawing = {
        r.drawing: flt(r.completed_qty_nos, 3)
        for r in (last_soe.drawing_details or []) if r.drawing
    }

    # Loop (not get_value) — a WO can in principle have more than one sequence_id=1 JC
    # if ERPNext's own batch-size splitting ever kicks in; push to all of them.
    for jc_name in frappe.get_all(
        "Job Card",
        filters={"work_order": wo_name, "sequence_id": 1, "docstatus": 0},
        pluck="name",
    ):
        jc_doc = frappe.get_doc("Job Card", jc_name)
        if not jc_doc.get("custom_drawing_details"):
            continue
        jc_doc.custom_available_to_consume_kg = flt(last_soe.total_consumed_kg, 3)
        for row in jc_doc.custom_drawing_details:
            row.available_to_consume_nos = flt(nos_by_drawing.get(row.drawing or "", 0.0), 3)
        jc_doc.custom_total_available_nos = flt(
            sum(flt(r.available_to_consume_nos) for r in jc_doc.custom_drawing_details), 3
        )
        jc_doc.flags.ignore_validate = True
        jc_doc.save(ignore_permissions=True)


def on_submit_supplier_operation_entry(doc, method):
    """On submit: propagate Kg + Nos to next operation; update SCO drawing completion;
    mark SCO all_ops_complete if this is the last operation.
    """
    _propagate_available_to_next(doc)
    _propagate_drawing_nos_to_next(doc)
    _update_sco_drawing_item_completion(doc)

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
        pp_name = frappe.db.get_value(
            "Subcontracting Order", doc.subcontracting_order, "custom_production_plan"
        )
        if pp_name:
            _push_sco_completion_to_wo(pp_name, doc)


def before_delete_supplier_operation_entry(doc, method):
    """Block deletion of an SOE if other SOEs exist for the same SCO.
    The operation chain must not be broken; cancel the SCO to delete all SOEs together.
    """
    others = frappe.db.count(
        "Supplier Operation Entry",
        {
            "subcontracting_order": doc.subcontracting_order,
            "name": ["!=", doc.name],
            "docstatus": ["!=", 2],
        },
    )
    if others:
        frappe.throw(
            _("This Supplier Operation Entry is part of an operation chain for SCO <b>{0}</b>. "
              "You cannot delete it individually — cancel the Subcontracting Order first to "
              "remove all linked Supplier Operation Entries together.")
            .format(doc.subcontracting_order),
            title=_("Cannot Delete — Linked Operations Exist"),
        )


def on_cancel_subcontracting_order(doc, method):
    """On SCO cancel: cancel submitted SOEs in reverse sequence order, then delete all.
    Ensures the sequential-submit guard in before_submit does not block cascading cancels.
    """
    soes = frappe.get_all(
        "Supplier Operation Entry",
        filters={"subcontracting_order": doc.name, "docstatus": ["!=", 2]},
        fields=["name", "docstatus", "sequence_id"],
        order_by="sequence_id desc",
    )
    for soe_info in soes:
        soe_doc = frappe.get_doc("Supplier Operation Entry", soe_info.name)
        if soe_doc.docstatus == 1:
            soe_doc.cancel()
        soe_doc.delete(ignore_permissions=True)


# ─────────────────────────────────────────────────────────────────────────────
# Private helpers
# ─────────────────────────────────────────────────────────────────────────────

def _build_soe_drawing_rows(sco, seq_idx):
    """Build drawing_details rows for a new SOE from the SCO's drawing items.

    Op-1 (seq_idx == 1): populates the planned Kg fields from the SCO Drawing Items
    (customer_weight_kg, total_weight_kg = planned). transferred_weight_kg starts at
    0 — it is not yet backed by any Stock Entry — and is kept live afterwards by
    _refresh_sco_drawing_transferred_weights() on every transfer SE submit/cancel.
    Op-2+ : only copies drawing identity + qty_to_manufacture; Kg fields are blank
    (not meaningful after the first transfer operation); available_to_consume_nos is
    filled later by _propagate_drawing_nos_to_next when Op-1 saves/submits.
    """
    rows = []
    for d in (sco.get("custom_drawing_items") or []):
        row = {
            "doctype": "SOE Drawing Detail",
            "drawing": d.drawing,
            "customer_drawing_number": d.customer_drawing_number or "",
            "duno_mark_no": d.duno_mark_no or "",
            "sales_order": d.get("sales_order") or "",
            "qty_to_manufacture": flt(d.qty_to_manufacture, 3),
            "available_to_consume_nos": 0.0,
            "completed_qty_nos": 0.0,
            "transferred_weight_kg": 0.0,
        }
        if seq_idx == 1:
            row.update({
                "customer_provided_weight_kg": flt(d.customer_weight_kg, 3),
                "planned_weight_kg": flt(d.total_weight_kg, 3),
            })
        else:
            row.update({
                "customer_provided_weight_kg": 0.0,
                "planned_weight_kg": 0.0,
            })
        rows.append(row)
    return rows


def _create_soes_for_sco(sco):
    """Create one SOE per Subcontractor operation in the linked Production Plan.
    Idempotent — skips any sequence_id that already has a live SOE.
    Op-1 gets available_to_consume_kg from custom_transferred_weight_kg (0 if not yet
    transferred). Each SOE is populated with drawing_details rows so drawing-level
    Nos tracking is available from the start.
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

        drawing_rows = _build_soe_drawing_rows(sco, seq_idx)

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
            "drawing_details": drawing_rows,
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


def _get_mp_actual_transferred_weight(mp_name, source_warehouse, target_warehouses):
    """Sum of ACTUALLY-transferred (submitted Stock Entry) weight for a Material
    Planning document's reserved batches — as opposed to _get_mp_total_weight,
    which is the reserved/mapped weight regardless of whether it has moved yet.

    Capped per item+batch at the reserved qty, so a batch used elsewhere can't
    inflate this MP's figure. target_warehouses may be a warehouse or list of
    warehouses (e.g. WIP + CNC) the material may have moved into.
    """
    if not mp_name or not source_warehouse:
        return 0.0
    if isinstance(target_warehouses, str):
        target_warehouses = [target_warehouses]
    target_warehouses = [w for w in (target_warehouses or []) if w]
    if not target_warehouses:
        return 0.0

    reserved = _get_mp_reserved_batches(mp_name, source_warehouse, None)
    if not reserved:
        return 0.0

    placeholders = ", ".join(["%s"] * len(target_warehouses))
    moved = {}
    for r in frappe.db.sql(
        f"""
        SELECT sed.item_code, sed.batch_no, SUM(sed.qty) AS qty
        FROM `tabStock Entry Detail` sed
        JOIN `tabStock Entry` se ON se.name = sed.parent
        WHERE se.stock_entry_type IN ('Material Transfer', 'Send to Subcontractor')
          AND se.docstatus = 1
          AND sed.s_warehouse = %s
          AND sed.t_warehouse IN ({placeholders})
        GROUP BY sed.item_code, sed.batch_no
        """,
        [source_warehouse] + target_warehouses,
        as_dict=True,
    ):
        moved[(r.item_code, r.batch_no or "")] = flt(r.qty)

    total = 0.0
    for item in reserved:
        key = (item["item_code"], item.get("batch_no") or "")
        total += min(flt(item["qty"]), moved.get(key, 0.0))
    return flt(total, 3)


def _refresh_wo_drawing_transferred_weights(wo):
    """Update Op-1 JC's custom_drawing_details.transferred_weight_kg rows to reflect
    ACTUAL Stock Entry transfers so far.

    Uses wo.custom_transferred_weight_kg (already correctly computed by
    _update_wo_transferred_weight) and scales each drawing's transferred weight
    proportionally to its mapped_weight_kg share of the WO total. This works
    regardless of whether MP row reservations have been cleared by SE submission.
    # SHARED_SCO_JC: mirrors _refresh_sco_drawing_transferred_weights
    """
    jc_op1 = frappe.db.get_value(
        "Job Card",
        {"work_order": wo.name, "sequence_id": 1, "docstatus": ["!=", 2]},
        "name",
    )
    if not jc_op1:
        return

    jc_doc = frappe.get_doc("Job Card", jc_op1)
    if not jc_doc.get("custom_drawing_details"):
        return

    wo_rows = {d.drawing: d for d in (wo.get("custom_drawing_items") or [])}
    total_wo_mapped = sum(flt(d.mapped_weight_kg) for d in (wo.get("custom_drawing_items") or []))
    transferred_weight = flt(wo.get("custom_transferred_weight_kg") or 0)
    ratio = min(transferred_weight / total_wo_mapped, 1.0) if total_wo_mapped else 0.0

    changed = False
    for row in jc_doc.custom_drawing_details:
        wo_row = wo_rows.get(row.drawing)
        new_val = flt(flt(wo_row.mapped_weight_kg) * ratio, 3) if wo_row else 0.0
        if flt(row.transferred_weight_kg) != new_val:
            row.transferred_weight_kg = new_val
            changed = True

    if changed:
        jc_doc.flags.ignore_validate = True
        # Perf: only row.transferred_weight_kg (a Float) changes here -- no Link
        # field's VALUE is touched, so re-validating that every Link on every
        # child row still points to a real document is pure redundant work on
        # top of the validate() this already skips. Found while investigating
        # slow Stock Entry submission (this runs from _update_wo_transferred_weight).
        jc_doc.flags.ignore_links = True
        jc_doc.save(ignore_permissions=True)


def _get_sco_transfer_warehouses(sco_name):
    """Source/CNC warehouse for an SCO, resolved via its Material Issue Plan —
    these no longer live on the SCO itself (moved to Material Issue Plan)."""
    mip_name = frappe.db.get_value("Material Issue Plan", {"subcontracting_order": sco_name})
    if not mip_name:
        return None, None
    mip = frappe.db.get_value(
        "Material Issue Plan", mip_name, ["source_warehouse", "cnc_warehouse"], as_dict=True
    )
    return (mip.source_warehouse, mip.cnc_warehouse) if mip else (None, None)


def _get_wo_transfer_warehouses(wo_name):
    """Source/CNC warehouse for a Work Order, resolved via its Material Issue Plan —
    these no longer live on the Work Order itself (moved to Material Issue Plan).
    # SHARED_SCO_JC: mirrors _get_sco_transfer_warehouses
    """
    mip_name = frappe.db.get_value("Material Issue Plan", {"work_order": wo_name})
    if not mip_name:
        return None, None
    mip = frappe.db.get_value(
        "Material Issue Plan", mip_name, ["source_warehouse", "cnc_warehouse"], as_dict=True
    )
    return (mip.source_warehouse, mip.cnc_warehouse) if mip else (None, None)


def _refresh_sco_drawing_transferred_weights(sco):
    """SOE equivalent of _refresh_wo_drawing_transferred_weights.
    Uses sco.custom_transferred_weight_kg (already correctly computed) and scales
    each drawing proportionally to its mapped_weight_kg share of the SCO total.
    # SHARED_SCO_JC: mirrors _refresh_wo_drawing_transferred_weights
    """
    soe_op1 = frappe.db.get_value(
        "Supplier Operation Entry",
        {"subcontracting_order": sco.name, "sequence_id": 1, "docstatus": ["!=", 2]},
        "name",
    )
    if not soe_op1:
        return

    soe_doc = frappe.get_doc("Supplier Operation Entry", soe_op1)
    if not soe_doc.get("drawing_details"):
        return

    sco_rows = {d.drawing: d for d in (sco.get("custom_drawing_items") or [])}
    total_sco_mapped = sum(flt(d.mapped_weight_kg) for d in (sco.get("custom_drawing_items") or []))
    transferred_weight = flt(sco.get("custom_transferred_weight_kg") or 0)
    ratio = min(transferred_weight / total_sco_mapped, 1.0) if total_sco_mapped else 0.0

    changed = False
    for row in soe_doc.drawing_details:
        sco_row = sco_rows.get(row.drawing)
        new_val = flt(flt(sco_row.mapped_weight_kg) * ratio, 3) if sco_row else 0.0
        if flt(row.transferred_weight_kg) != new_val:
            row.transferred_weight_kg = new_val
            changed = True

    if changed:
        soe_doc.flags.ignore_validate = True
        # Perf: same reasoning as _refresh_wo_drawing_transferred_weights above --
        # only row.transferred_weight_kg (a Float) changes, no Link field VALUE
        # is touched, so skip the redundant re-validation of every Link on every
        # child row on top of the validate() this already skips.
        soe_doc.flags.ignore_links = True
        soe_doc.save(ignore_permissions=True)


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


def _get_mp_drawing_weights_by_duno(mp_name):
    """Batched variant of _get_mp_drawing_weight's duno_mark_no branch -- one grouped
    query per Material Planning instead of one query per drawing row sharing that MP
    (the same N+1 shape already fixed elsewhere in this app; this one was found while
    investigating slow Stock Entry submission via refresh_weight_summary).

    Returns {duno_mark_no: planned_qty}. Callers still fall back to
    _get_mp_total_weight(mp_name) for a blank/falsy duno_mark_no, exactly as
    _get_mp_drawing_weight itself does -- this only replaces the per-duno lookup."""
    weights = defaultdict(float)
    if not mp_name:
        return weights
    for r in frappe.db.sql(
        """
        SELECT duno_mark_no, COALESCE(SUM(qty), 0) AS qty
        FROM `tabMaterial Planning Raw Material`
        WHERE parent = %s
        GROUP BY duno_mark_no
        """,
        mp_name,
        as_dict=True,
    ):
        weights[r.duno_mark_no or ""] += flt(r.qty)
    return weights


def _get_mp_mapped_weight_by_duno(mp_name):
    """Return {duno_mark_no: mapped_weight_kg} for a Material Planning document.

    Mapped weight = the batch weight allocated to each drawing — cross-mapped rows
    (Material Mapping batch_calc_qty) plus exact-match rows (Available Raw Material
    reserved_qty or required_qty). Exact-match rows carry no DUNO/Mark No, so their
    weight is attributed across drawings in proportion to each drawing's planned qty
    for that item (from the Raw Materials sub-table).

    Includes all batch-assigned rows regardless of is_reserved, so the figure stays
    accurate after SE submission clears the reservation flag.
    """
    mapped = defaultdict(float)
    if not mp_name:
        return mapped

    # Cross-mapped — already carries the DUNO/Mark No; include whether reserved or not
    for r in frappe.db.sql(
        """
        SELECT duno_mark_no, batch_calc_qty
        FROM `tabMaterial Planning Material Mapping`
        WHERE parent = %s AND batch IS NOT NULL AND batch != '' AND batch_calc_qty > 0
        """,
        mp_name,
        as_dict=True,
    ):
        mapped[r.duno_mark_no or ""] += flt(r.batch_calc_qty)

    # Exact-match — no DUNO; split per item by each drawing's planned share
    exact_rows = frappe.db.sql(
        """
        SELECT item_code,
               COALESCE(NULLIF(reserved_qty, 0), required_qty) AS qty
        FROM `tabMaterial Planning Available Raw Material`
        WHERE parent = %s AND batch_no IS NOT NULL AND batch_no != ''
          AND COALESCE(NULLIF(reserved_qty, 0), required_qty) > 0
        """,
        mp_name,
        as_dict=True,
    )
    exact_rows = [frappe._dict(r) for r in exact_rows]
    if exact_rows:
        item_duno_qty = defaultdict(lambda: defaultdict(float))  # item -> duno -> planned qty
        item_total = defaultdict(float)                          # item -> total planned qty
        for p in frappe.get_all(
            "Material Planning Raw Material",
            filters={"parent": mp_name},
            fields=["item_code", "duno_mark_no", "qty"],
        ):
            item_duno_qty[p.item_code][p.duno_mark_no or ""] += flt(p.qty)
            item_total[p.item_code] += flt(p.qty)

        for er in exact_rows:
            qty = flt(er.qty)
            if qty <= 0:
                continue
            shares = item_duno_qty.get(er.item_code)
            total = item_total.get(er.item_code, 0)
            if shares and total > 0:
                for duno, planned_qty in shares.items():
                    mapped[duno] += qty * (planned_qty / total)
            else:
                mapped[""] += qty  # exact item with no planned match → unattributed

    return mapped


def _get_mp_excess_by_duno(mp_name):
    """Return {duno_mark_no: excess_kg} per drawing for a Material Planning document.

    Excess = SUM(batch_calc_qty - qty) over Mapped Material Mapping rows — the same
    'Difference in Kg' the Material Planning screen shows: weight mapped beyond what
    was planned (cross-item over-mapping) that the supplier must return.
    """
    excess = defaultdict(float)
    if not mp_name:
        return excess
    for r in frappe.get_all(
        "Material Planning Material Mapping",
        filters={"parent": mp_name, "batch_mapped": "Mapped"},
        fields=["duno_mark_no", "batch_calc_qty", "qty"],
    ):
        excess[r.duno_mark_no or ""] += flt(r.batch_calc_qty) - flt(r.qty)
    return excess


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
            "item_code", "planned_item", "batch", "batch_calc_qty", "batch_sec_qty",
            "batch_length", "batch_width", "batch_thickness", "batch_unit_weight",
            "batch_parent_item_group", "parent_item_group", "sec_uom", "cnc_process",
            "reserve_without_dimensions", "reserved_qty",
        ],
    )
    for r in rows:
        if not r.batch:
            continue
        # Always use reserved_qty — it's the actual stock held back for this row.
        # batch_calc_qty is the full requirement which may exceed what's available (shortfall).
        qty = flt(r.reserved_qty)
        if qty <= 0:
            continue
        # When the batch belongs to a different item (cross-item mapping), planned_item
        # holds the batch's actual item — use it so ERPNext batch validation passes.
        se_item_code = r.planned_item or r.item_code
        items.append({
            "item_code": se_item_code,
            "batch_no": r.batch,
            # v15: use the batch_no field directly; Frappe creates the SBB on submit.
            "use_serial_batch_fields": 1,
            "qty": flt(qty, 3),
            "uom": _stock_uom(se_item_code),
            "s_warehouse": source_warehouse,
            "t_warehouse": supplier_warehouse,
            "custom_sec_qty": flt(r.batch_sec_qty, 3),
            "custom_sec_uom": r.sec_uom or "",
            "custom_length": flt(r.batch_length, 3),
            "custom_width": flt(r.batch_width, 3),
            "custom_thickness": flt(r.batch_thickness, 3),
            "custom_unit_weight": flt(r.batch_unit_weight, 4),
            "custom_parent_item_group": r.batch_parent_item_group or r.parent_item_group or "",
            "cnc_process": 1 if r.cnc_process else 0,
        })

    # From available_raw_material: exact-match reserved rows
    rows2 = frappe.get_all(
        "Material Planning Available Raw Material",
        filters={"parent": mp_name, "is_reserved": 1},
        fields=[
            "item_code", "batch_no", "reserved_qty", "available_qty",
            "sec_qty", "sec_uom", "length", "width", "thickness", "parent_item_group", "cnc_process",
        ],
    )
    for r in rows2:
        qty = flt(r.reserved_qty)   # available_qty is pre-reservation stock, not what's actually reserved
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
                "cnc_process": 1 if r.cnc_process else 0,
            })

    return items


def _get_pp_planned_qty(pp_name, customer_drawing_number, duno_mark_no):
    """Return planned_qty from the Production Plan Item matching the given
    customer_drawing_number + duno_mark_no. Returns 0 when no match is found."""
    if not pp_name:
        return 0
    filters = {"parent": pp_name}
    if customer_drawing_number:
        filters["custom_customer_drawing_number"] = customer_drawing_number
    if duno_mark_no:
        filters["custom_duno_mark_no"] = duno_mark_no
    result = frappe.db.get_value("Production Plan Item", filters, "planned_qty")
    return flt(result)


@frappe.whitelist()
def backfill_drawing_item_qty(sco_name):
    """Populate qty_to_manufacture on all SCO Drawing Items for an existing SCO
    by reading planned_qty from the linked Production Plan Items.
    Called once after the field is added; subsequent SCOs are populated on creation."""
    sco = frappe.get_doc("Subcontracting Order", sco_name)
    pp_name = sco.get("custom_production_plan")
    if not pp_name:
        frappe.throw(_("Subcontracting Order is not linked to a Production Plan."))

    updated = 0
    for d in (sco.get("custom_drawing_items") or []):
        qty = _get_pp_planned_qty(pp_name, d.get("customer_drawing_number"), d.get("duno_mark_no"))
        if qty:
            frappe.db.set_value("SCO Drawing Item", d.name, "qty_to_manufacture", flt(qty, 3))
            updated += 1

    frappe.db.commit()
    return updated


def _get_supplier_wh_consumption_items(sco):
    """Return SE consumption rows (issued FROM the supplier warehouse, no target) for all
    raw material transferred to the supplier for this SCO.

    Pulls items directly from submitted 'Send to Subcontractor' SEs linked to this SCO
    (via custom_sco_ref or subcontracting_order). Querying the SE Detail rows is reliable
    in Frappe v15 because SLE rows store batch tracking in Serial and Batch Bundles rather
    than in the batch_no column, making SLE batch_no lookups unreliable.
    """
    rows = frappe.db.sql(
        """
        SELECT sed.item_code, sed.batch_no, SUM(sed.qty) AS qty
        FROM `tabStock Entry Detail` sed
        JOIN `tabStock Entry` se ON se.name = sed.parent
        WHERE (se.custom_sco_ref = %s OR se.subcontracting_order = %s)
          AND se.stock_entry_type = 'Send to Subcontractor'
          AND se.docstatus = 1
        GROUP BY sed.item_code, sed.batch_no
        HAVING SUM(sed.qty) > 0
        """,
        (sco.name, sco.name),
        as_dict=True,
    )
    return [
        {
            "item_code": r.item_code,
            "batch_no": r.batch_no,
            # v15: use the batch_no field directly; Frappe creates the SBB on submit.
            "use_serial_batch_fields": 1,
            "qty": flt(r.qty, 3),
            "uom": frappe.db.get_value("Item", r.item_code, "stock_uom") or "Kg",
            "s_warehouse": sco.supplier_warehouse,
        }
        for r in rows
    ]


# ─────────────────────────────────────────────────────────────────────────────
# Work Order / Job Card mirror (SHARED_SCO_JC)
# All functions below are direct mirrors of the SCO/SOE equivalents above.
# Comment marker: SHARED_SCO_JC — grep this to find all paired functions.
# ─────────────────────────────────────────────────────────────────────────────

@frappe.whitelist()
def get_wo_pending_items(wo_name):
    """Return raw-material items not yet transferred for this WO.
    Mirrors get_sco_pending_items; uses custom_wo_ref on SE, wip_warehouse as target.
    # SHARED_SCO_JC: mirrors get_sco_pending_items
    """
    wo = frappe.get_doc("Work Order", wo_name)
    if not wo.production_plan:
        frappe.throw(_("Work Order is not linked to a Production Plan."))
    if not wo.get("custom_source_warehouse"):
        frappe.throw(_("Please set the Source Warehouse (RM) on the Work Order first."))

    source_warehouse = wo.custom_source_warehouse
    wip_warehouse    = wo.wip_warehouse or ""
    cnc_warehouse    = wo.get("custom_cnc_warehouse") or ""

    raw_items = []
    seen_mps  = set()
    pp = frappe.get_doc("Production Plan", wo.production_plan)
    for pi in pp.po_items:
        mp_name = pi.get("custom_material_planning")
        if not mp_name or mp_name in seen_mps:
            continue
        seen_mps.add(mp_name)
        raw_items.extend(_get_mp_reserved_batches(mp_name, source_warehouse, wip_warehouse))

    if not raw_items:
        return []

    totals = {}
    for item in raw_items:
        is_cnc = bool(item.get("cnc_process")) and bool(cnc_warehouse)
        key = (item["item_code"], item.get("batch_no") or "", is_cnc)
        if key in totals:
            totals[key]["qty"]            = flt(totals[key]["qty"] + item["qty"], 3)
            totals[key]["custom_sec_qty"] = flt(totals[key]["custom_sec_qty"] + item.get("custom_sec_qty", 0), 3)
        else:
            totals[key] = dict(item)
            totals[key]["cnc_process"] = 1 if is_cnc else 0

    # Already transferred to WIP (Material Transfer SEs with custom_wo_ref)
    wip_done = {}
    if wip_warehouse:
        for r in frappe.db.sql("""
            SELECT sed.item_code, sed.batch_no,
                   SUM(sed.qty) AS qty,
                   SUM(IFNULL(sed.custom_sec_qty, 0)) AS sec_qty
            FROM `tabStock Entry Detail` sed
            JOIN `tabStock Entry` se ON se.name = sed.parent
            WHERE se.custom_wo_ref = %s
              AND se.stock_entry_type = 'Material Transfer'
              AND se.docstatus != 2
              AND sed.t_warehouse = %s
              AND sed.s_warehouse != %s
            GROUP BY sed.item_code, sed.batch_no
        """, (wo_name, wip_warehouse, wip_warehouse), as_dict=True):
            wip_done[(r.item_code, r.batch_no or "")] = flt(r.qty)

    # Already transferred to CNC (Material Transfer SEs with custom_wo_ref)
    cnc_done = {}
    if cnc_warehouse:
        for r in frappe.db.sql("""
            SELECT sed.item_code, sed.batch_no,
                   SUM(sed.qty) AS qty,
                   SUM(IFNULL(sed.custom_sec_qty, 0)) AS sec_qty
            FROM `tabStock Entry Detail` sed
            JOIN `tabStock Entry` se ON se.name = sed.parent
            WHERE se.custom_wo_ref = %s
              AND se.stock_entry_type = 'Material Transfer'
              AND se.docstatus != 2
              AND sed.t_warehouse = %s
            GROUP BY sed.item_code, sed.batch_no
        """, (wo_name, cnc_warehouse), as_dict=True):
            cnc_done[(r.item_code, r.batch_no or "")] = flt(r.qty)

    result = []
    for (item_code, batch_no, is_cnc), item in totals.items():
        done_qty    = (cnc_done if is_cnc else wip_done).get((item_code, batch_no), 0)
        pending_qty = flt(item["qty"] - done_qty, 3)
        if pending_qty <= 0:
            continue
        total_qty = flt(item["qty"])
        ratio = pending_qty / total_qty if total_qty else 0
        result.append({
            "item_code":               item_code,
            "item_name":               frappe.db.get_value("Item", item_code, "item_name") or item_code,
            "batch_no":                batch_no,
            "qty":                     pending_qty,
            "uom":                     item.get("uom") or "Kg",
            "custom_sec_qty":          flt(flt(item.get("custom_sec_qty", 0)) * ratio, 3),
            "custom_sec_uom":          item.get("custom_sec_uom") or "",
            "s_warehouse":             source_warehouse,
            "t_warehouse":             cnc_warehouse if is_cnc else wip_warehouse,
            "cnc_process":             1 if is_cnc else 0,
            "use_serial_batch_fields": 1,
            "custom_length":           flt(item.get("custom_length", 0), 3),
            "custom_width":            flt(item.get("custom_width", 0), 3),
            "custom_thickness":        flt(item.get("custom_thickness", 0), 3),
            "custom_unit_weight":      flt(item.get("custom_unit_weight", 0), 4),
            "custom_parent_item_group": item.get("custom_parent_item_group") or "",
        })

    return result


@frappe.whitelist()
def create_partial_wo_transfer(wo_name, selected_items_json, transfer_type):
    """Create a draft Material Transfer Stock Entry for caller-selected items.
    transfer_type: "wip" → to wip_warehouse   "cnc" → to custom_cnc_warehouse
    # SHARED_SCO_JC: mirrors create_partial_transfer
    """
    import json as _json
    selected = _json.loads(selected_items_json) if isinstance(selected_items_json, str) else selected_items_json
    if not selected:
        frappe.throw(_("No items selected for transfer."))

    wo = frappe.get_doc("Work Order", wo_name)
    if wo.docstatus != 1:
        frappe.throw(_("Work Order must be submitted first."))
    if not wo.get("custom_source_warehouse"):
        frappe.throw(_("Please set the Source Warehouse (RM) on the Work Order first."))

    if transfer_type == "cnc":
        t_warehouse = wo.get("custom_cnc_warehouse")
        if not t_warehouse:
            frappe.throw(_("No CNC Warehouse set on this Work Order."))
    else:
        t_warehouse = wo.wip_warehouse
        if not t_warehouse:
            frappe.throw(_("Please set the WIP Warehouse on the Work Order first."))

    se_items = []
    for item in selected:
        se_items.append({
            "item_code":               item["item_code"],
            "batch_no":                item.get("batch_no") or "",
            "use_serial_batch_fields": 1,
            "qty":                     flt(item["qty"]),
            "uom":                     item.get("uom") or "Kg",
            "s_warehouse":             wo.custom_source_warehouse,
            "t_warehouse":             t_warehouse,
            "custom_sec_qty":          flt(item.get("custom_sec_qty") or 0),
            "custom_sec_uom":          item.get("custom_sec_uom") or "",
            "custom_length":           flt(item.get("custom_length") or 0),
            "custom_width":            flt(item.get("custom_width") or 0),
            "custom_thickness":        flt(item.get("custom_thickness") or 0),
            "custom_unit_weight":      flt(item.get("custom_unit_weight") or 0),
            "custom_parent_item_group": item.get("custom_parent_item_group") or "",
        })

    se = frappe.get_doc({
        "doctype":           "Stock Entry",
        "stock_entry_type":  "Material Transfer",
        "custom_wo_ref":     wo_name,
        "company":           wo.company,
        "items":             se_items,
    })
    se.insert(ignore_permissions=True)
    return se.name


@frappe.whitelist()
def create_cnc_to_wip_entry(wo_name):
    """Transfer materials from CNC warehouse to WIP warehouse.
    # SHARED_SCO_JC: mirrors create_cnc_to_supplier_entry
    """
    wo = frappe.get_doc("Work Order", wo_name)
    if wo.docstatus != 1:
        frappe.throw(_("Work Order must be submitted first."))

    cnc_warehouse = wo.get("custom_cnc_warehouse")
    if not cnc_warehouse:
        frappe.throw(_("No CNC Warehouse set on the Work Order."))
    wip_warehouse = wo.wip_warehouse
    if not wip_warehouse:
        frappe.throw(_("Please set the WIP Warehouse on the Work Order first."))

    # Items sent from source → CNC (submitted SEs only)
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
        WHERE se.custom_wo_ref = %s
          AND se.stock_entry_type = 'Material Transfer'
          AND se.docstatus = 1
          AND sed.t_warehouse = %s
        GROUP BY sed.item_code, sed.batch_no
        HAVING SUM(sed.qty) > 0
        """,
        (wo_name, cnc_warehouse),
        as_dict=True,
    )
    if not sent_rows:
        frappe.throw(_("No CNC materials found. Ensure the CNC stock entry has been submitted."))

    # Already forwarded CNC → WIP
    fwd_rows = frappe.db.sql(
        """
        SELECT sed.item_code, sed.batch_no, SUM(sed.qty) AS qty
        FROM `tabStock Entry Detail` sed
        JOIN `tabStock Entry` se ON se.name = sed.parent
        WHERE se.custom_wo_ref = %s
          AND se.stock_entry_type = 'Material Transfer'
          AND se.docstatus = 1
          AND sed.s_warehouse = %s
          AND sed.t_warehouse = %s
        GROUP BY sed.item_code, sed.batch_no
        """,
        (wo_name, cnc_warehouse, wip_warehouse),
        as_dict=True,
    )
    already = {(r.item_code, r.batch_no or ""): flt(r.qty) for r in fwd_rows}

    se_items = []
    for r in sent_rows:
        key     = (r.item_code, r.batch_no or "")
        net_qty = flt(r.qty, 3) - already.get(key, 0)
        if net_qty <= 0:
            continue
        se_items.append({
            "item_code":               r.item_code,
            "batch_no":                r.batch_no,
            "use_serial_batch_fields": 1,
            "qty":                     flt(net_qty, 3),
            "uom":                     r.uom or frappe.db.get_value("Item", r.item_code, "stock_uom") or "Kg",
            "s_warehouse":             cnc_warehouse,
            "t_warehouse":             wip_warehouse,
            "custom_sec_qty":          flt(r.custom_sec_qty, 3),
            "custom_sec_uom":          r.custom_sec_uom or "",
            "custom_length":           flt(r.custom_length, 3),
            "custom_width":            flt(r.custom_width, 3),
            "custom_thickness":        flt(r.custom_thickness, 3),
            "custom_unit_weight":      flt(r.custom_unit_weight, 4),
            "custom_parent_item_group": r.custom_parent_item_group or "",
        })

    if not se_items:
        frappe.throw(_("All CNC materials have already been transferred to the WIP warehouse."))

    se = frappe.get_doc({
        "doctype":          "Stock Entry",
        "stock_entry_type": "Material Transfer",
        "custom_wo_ref":    wo_name,
        "company":          wo.company,
        "items":            se_items,
    })
    se.insert(ignore_permissions=True)
    return se.name


@frappe.whitelist()
def create_return_stock_entry_for_wo(wo_name, target_warehouse):
    """Receive excess / off-cut material back to the return warehouse for a Work Order.
    # SHARED_SCO_JC: mirrors create_return_stock_entry
    """
    wo = frappe.get_doc("Work Order", wo_name)
    if not target_warehouse:
        frappe.throw(_("Please set the Finished Goods/Return Warehouse on the Work Order first."))

    se_items      = []
    new_row_names = []
    for r in (wo.get("custom_excess_return_items") or []):
        if r.get("stock_entry_created"):
            continue
        qty = flt(r.qty, 3)
        if not r.item_code or qty <= 0:
            continue
        new_row_names.append(r.name)
        se_items.append({
            "item_code":               r.item_code,
            "qty":                     qty,
            "uom":                     r.get("uom") or frappe.db.get_value("Item", r.item_code, "stock_uom") or "Kg",
            "t_warehouse":             target_warehouse,
            "custom_parent_item_group": r.get("parent_item_group") or "",
            "custom_unit_weight":      flt(r.get("unit_weight"), 4),
            "custom_sec_qty":          flt(r.get("sec_qty"), 3),
            "custom_sec_uom":          r.get("sec_uom") or "",
            "custom_length":           flt(r.get("length"), 3),
            "custom_width":            flt(r.get("width"), 3),
            "custom_thickness":        flt(r.get("thickness"), 3),
        })

    if not se_items:
        frappe.throw(_("No new off-cut items to process. All rows already have a Stock Entry created, "
                       "or no rows with Weight (Kg) > 0 exist."))

    se = frappe.get_doc({
        "doctype":          "Stock Entry",
        "stock_entry_type": "Material Receipt",
        "company":          wo.company,
        "items":            se_items,
    })
    se.insert(ignore_permissions=True)

    for r in wo.get("custom_excess_return_items"):
        if r.name in new_row_names:
            r.stock_entry_created = 1
    wo.save(ignore_permissions=True)

    return se.name


@frappe.whitelist()
def get_jc_summary(wo_name):
    """Operation-wise summary for a WO's Job Cards (for the operations HTML widget).
    # SHARED_SCO_JC: mirrors get_soe_summary
    """
    jcs = frappe.get_all(
        "Job Card",
        filters={"work_order": wo_name, "docstatus": ["!=", 2]},
        fields=["name", "sequence_id", "operation", "status", "docstatus",
                "custom_available_to_consume_kg", "custom_total_consumed_kg"],
        order_by="sequence_id asc",
    )
    if not jcs:
        return jcs

    drawing_rows = frappe.get_all(
        "SOE Drawing Detail",
        filters={"parent": ["in", [d.name for d in jcs]], "parentfield": "custom_drawing_details"},
        fields=["parent", "drawing", "customer_drawing_number", "duno_mark_no",
                "qty_to_manufacture", "completed_qty_nos",
                "available_to_consume_nos", "transferred_weight_kg"],
        order_by="idx asc",
    )

    details_map = {}
    for dr in drawing_rows:
        details_map.setdefault(dr.parent, []).append(dr)

    for jc in jcs:
        details             = details_map.get(jc.name, [])
        jc["drawing_details"]    = details
        jc["total_qty_to_mfg"]  = sum(flt(d.qty_to_manufacture) for d in details)
        jc["total_completed_nos"] = sum(flt(d.completed_qty_nos) for d in details)
        seq = jc.get("sequence_id") or 1
        if seq == 1:
            jc["avail_nos"] = sum(flt(d.transferred_weight_kg) for d in details)
            jc["diff_nos"]  = flt(jc["total_qty_to_mfg"]) - flt(jc["total_completed_nos"])
        else:
            jc["avail_nos"] = sum(flt(d.available_to_consume_nos) for d in details)
            jc["diff_nos"]  = flt(jc["avail_nos"]) - flt(jc["total_completed_nos"])

    return jcs


# ─── WO doc event hooks ───────────────────────────────────────────────────────

def on_submit_work_order(doc, method):
    """Populate custom_drawing_details on the auto-created Job Cards.
    ERPNext creates JCs on WO submit; we add our drawing tracking fields.
    # SHARED_SCO_JC: mirrors CustomSubcontractingOrder.on_submit (overrides.py)
    """
    _populate_jcs_for_wo(doc)


def on_cancel_work_order(doc, method):
    """ERPNext handles JC cancellation automatically; no extra cleanup needed.
    # SHARED_SCO_JC: mirrors on_cancel_subcontracting_order (simplified)
    """
    pass


# ─── Job Card doc event hooks ─────────────────────────────────────────────────

def validate_job_card_drawing_entry(doc, method):
    """Per-drawing Nos tracking + validation on Job Card.
    Early-returns when the JC has no custom_drawing_details (non-drawing-flow JCs are unaffected).
    # SHARED_SCO_JC: mirrors validate_supplier_operation_entry
    """
    if not doc.get("custom_drawing_details"):
        return

    seq = doc.sequence_id or 1

    # --- 1. Sum qty_nos per drawing from custom_consumption_log ---
    log_nos_by_drawing = defaultdict(float)
    for r in (doc.custom_consumption_log or []):
        if r.drawing and flt(r.qty_nos) > 0:
            log_nos_by_drawing[r.drawing] += flt(r.qty_nos)

    # --- 2. Push completed_qty_nos into custom_drawing_details rows ---
    for row in (doc.custom_drawing_details or []):
        row.completed_qty_nos = flt(log_nos_by_drawing.get(row.drawing or "", 0.0), 3)

    # --- 2a. Op-1: auto-set available_to_consume_nos = qty_to_manufacture when material transferred ---
    # Skipped for a chained JC (mixed-plan WO fed by a sibling SCO's completed ops) —
    # there, availability must stay exactly at whatever _push_sco_completion_to_wo /
    # _populate_jcs_for_wo's reverse path pushed (may be a partial amount), not
    # auto-inflated to the full planned qty.
    if seq == 1:
        wo_pp = frappe.db.get_value("Work Order", doc.work_order, "production_plan")
        is_chained = wo_pp and frappe.db.exists(
            "Process Planning",
            {"parent": wo_pp, "parenttype": "Production Plan", "work_type": "Subcontractor"},
        )
        if not is_chained:
            for row in (doc.custom_drawing_details or []):
                if flt(row.transferred_weight_kg) > 0:
                    row.available_to_consume_nos = flt(row.qty_to_manufacture, 3)

    # --- 2c. Update JC-level Nos summary fields ---
    doc.custom_total_available_nos = flt(
        sum(flt(r.available_to_consume_nos) for r in (doc.custom_drawing_details or [])), 3
    )
    doc.custom_total_completed_nos = flt(
        sum(flt(r.completed_qty_nos) for r in (doc.custom_drawing_details or [])), 3
    )

    # --- 2b. Validate completed_qty_nos does not exceed qty_to_manufacture ---
    for row in (doc.custom_drawing_details or []):
        qty_to_mfg = flt(row.qty_to_manufacture)
        completed  = flt(row.completed_qty_nos)
        if qty_to_mfg > 0 and completed > qty_to_mfg:
            frappe.throw(
                _("Drawing {0}: Completed ({1} Nos) exceeds Qty to Manufacture ({2} Nos). "
                  "Reduce the logged quantity.")
                .format(row.customer_drawing_number or row.drawing, completed, qty_to_mfg),
                title=_("Completed Qty Exceeds Limit"),
            )

    # --- 3. Status auto-advance ---
    if log_nos_by_drawing and doc.status == "Open":
        doc.status = "Work In Progress"

    # --- 4. Op-1: check log trigger setting ---
    if seq == 1 and log_nos_by_drawing:
        trigger = (
            frappe.db.get_single_value("Manufacturing Settings", "custom_soe_log_trigger")
            or "Fully Transferred"
        )
        if trigger == "Fully Transferred":
            detail_map = {r.drawing: r for r in (doc.custom_drawing_details or []) if r.drawing}
            for drawing, nos in log_nos_by_drawing.items():
                row = detail_map.get(drawing)
                if row and flt(row.transferred_weight_kg) <= 0:
                    frappe.throw(
                        _("Drawing {0}: no material has been transferred yet. "
                          "Transfer raw materials first, or change 'SOE Log Entry Allowed When' in "
                          "Manufacturing Settings to allow partial entries.")
                        .format(row.customer_drawing_number or drawing),
                        title=_("Material Not Yet Transferred"),
                    )

    # --- 5. Op-1: Kg over-consume guard ---
    if seq == 1:
        total_kg = sum(flt(r.weight_kg) for r in (doc.custom_consumption_log or []))
        doc.custom_total_consumed_kg = flt(total_kg, 3)
        available_kg = flt(doc.custom_available_to_consume_kg)
        if available_kg > 0 and total_kg > available_kg:
            frappe.throw(
                _("You have entered {0} Kg, but only {1} Kg is available to consume.")
                .format(flt(total_kg, 3), flt(available_kg, 3)),
                title=_("Exceeds Available to Consume"),
            )

    # --- 6. Op-2+: validate qty_nos per drawing against available_to_consume_nos ---
    if seq > 1:
        detail_map = {r.drawing: r for r in (doc.custom_drawing_details or []) if r.drawing}
        for drawing, nos in log_nos_by_drawing.items():
            row       = detail_map.get(drawing)
            available = flt(row.available_to_consume_nos) if row else 0.0
            label     = (row.customer_drawing_number if row else None) or drawing
            if available <= 0:
                frappe.throw(
                    _("Drawing {0}: the previous operation has not completed any quantity. "
                      "Consumption cannot be logged until the previous operation is completed.")
                    .format(label),
                    title=_("Previous Operation Not Completed"),
                )
            if nos > available:
                frappe.throw(
                    _("Drawing {0}: entered {1} Nos but only {2} Nos are available "
                      "from the previous operation.")
                    .format(label, flt(nos, 3), flt(available, 3)),
                    title=_("Exceeds Available Qty"),
                )


def before_submit_job_card_drawing_entry(doc, method):
    """Enforce sequential, status-gated submission for drawing-flow Job Cards.
    # SHARED_SCO_JC: mirrors before_submit_supplier_operation_entry
    """
    if not doc.get("custom_drawing_details"):
        return  # Non-drawing-flow JCs are not restricted

    if (doc.status or "") != "Completed":
        frappe.throw(
            _("Set Status to <b>Completed</b> before submitting this Job Card."),
            title=_("Operation Not Completed"),
        )

    seq = doc.sequence_id or 0
    if seq > 1:
        pending = frappe.get_all(
            "Job Card",
            filters={
                "work_order":  doc.work_order,
                "sequence_id": ["<", seq],
                "docstatus":   0,
                "name":        ["!=", doc.name],
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


def _propagate_drawing_nos_to_next_jc(doc):
    """Push per-drawing completed_qty_nos to the next draft JC in the WO.
    # SHARED_SCO_JC: mirrors _propagate_drawing_nos_to_next
    """
    next_jc_name = frappe.db.get_value(
        "Job Card",
        {
            "work_order":  doc.work_order,
            "sequence_id": (doc.sequence_id or 0) + 1,
            "docstatus":   0,
        },
        "name",
    )
    if not next_jc_name:
        return

    drawing_nos = {
        r.drawing: flt(r.completed_qty_nos, 3)
        for r in (doc.custom_drawing_details or [])
        if r.drawing
    }
    if not drawing_nos:
        return

    next_doc = frappe.get_doc("Job Card", next_jc_name)
    changed  = False
    for row in (next_doc.custom_drawing_details or []):
        new_val = drawing_nos.get(row.drawing or "", 0.0)
        if flt(row.available_to_consume_nos, 3) != flt(new_val, 3):
            row.available_to_consume_nos = flt(new_val, 3)
            changed = True

    if changed:
        next_doc.custom_total_available_nos = flt(
            sum(flt(r.available_to_consume_nos) for r in (next_doc.custom_drawing_details or [])), 3
        )
        next_doc.flags.ignore_validate = True
        next_doc.save(ignore_permissions=True)


def _update_wo_drawing_item_completion(doc):
    """Update WO Drawing Items' completed_qty_nos from the submitted JC's drawing_details.
    # SHARED_SCO_JC: mirrors _update_sco_drawing_item_completion
    """
    drawing_nos = {
        r.drawing: flt(r.completed_qty_nos, 3)
        for r in (doc.custom_drawing_details or [])
        if r.drawing
    }
    if not drawing_nos:
        return

    for row in frappe.get_all(
        "SCO Drawing Item",
        filters={"parent": doc.work_order, "parenttype": "Work Order"},
        fields=["name", "drawing"],
    ):
        if row.drawing in drawing_nos:
            frappe.db.set_value(
                "SCO Drawing Item", row.name,
                "completed_qty_nos", drawing_nos[row.drawing],
                update_modified=False,
            )


def on_update_job_card_drawing_entry(doc, method):
    """Live propagation on save: push per-drawing Nos to next JC.
    # SHARED_SCO_JC: mirrors on_update_supplier_operation_entry
    """
    if doc.docstatus == 0 and doc.get("custom_drawing_details"):
        _propagate_drawing_nos_to_next_jc(doc)


def on_submit_job_card_drawing_entry(doc, method):
    """On submit: propagate Nos to next JC; update WO drawing completion;
    mark WO all_ops_complete if this is the last operation.
    # SHARED_SCO_JC: mirrors on_submit_supplier_operation_entry
    """
    if not doc.get("custom_drawing_details"):
        return

    _propagate_drawing_nos_to_next_jc(doc)
    _update_wo_drawing_item_completion(doc)

    # Check if all JCs for this WO are submitted
    remaining = frappe.db.count(
        "Job Card",
        filters={
            "work_order":  doc.work_order,
            "sequence_id": [">", doc.sequence_id or 0],
            "docstatus":   ["!=", 2],
        },
    )
    if remaining == 0:
        frappe.db.set_value("Work Order", doc.work_order, "custom_all_ops_complete", 1)


# ─── Private helpers (WO/JC) ─────────────────────────────────────────────────

def _build_jc_drawing_rows(wo, seq_idx):
    """Build custom_drawing_details rows for a new JC from the WO's drawing items.
    transferred_weight_kg starts at 0 — it is not yet backed by any Stock Entry —
    and is kept live afterwards by _refresh_wo_drawing_transferred_weights() on
    every transfer SE submit/cancel.
    # SHARED_SCO_JC: mirrors _build_soe_drawing_rows
    """
    rows = []
    for d in (wo.get("custom_drawing_items") or []):
        row = {
            "drawing":               d.drawing,
            "customer_drawing_number": d.customer_drawing_number or "",
            "duno_mark_no":          d.duno_mark_no or "",
            "sales_order":           d.get("sales_order") or "",
            "qty_to_manufacture":    flt(d.qty_to_manufacture, 3),
            "available_to_consume_nos": 0.0,
            "completed_qty_nos":     0.0,
            "transferred_weight_kg": 0.0,
        }
        if seq_idx == 1:
            row.update({
                "customer_provided_weight_kg": flt(d.customer_weight_kg, 3),
                "planned_weight_kg":           flt(d.total_weight_kg, 3),
            })
        else:
            row.update({
                "customer_provided_weight_kg": 0.0,
                "planned_weight_kg":           0.0,
            })
        rows.append(row)
    return rows


def _populate_jcs_for_wo(wo):
    """Populate custom_drawing_details on the Job Cards ERPNext created on WO submit.
    Idempotent — skips JCs that already have drawing detail rows.
    # SHARED_SCO_JC: mirrors _create_soes_for_sco
    """
    if not wo.get("custom_drawing_items"):
        return  # This WO was not created via the PP drawing flow — skip

    # Build operation → sequence_id map from WO operations
    wo_op_seq = {}
    for op in frappe.get_all(
        "Work Order Operation",
        filters={"parent": wo.name},
        fields=["operation", "sequence_id"],
    ):
        wo_op_seq[op.operation] = flt(op.sequence_id) or 0

    jcs = frappe.get_all(
        "Job Card",
        filters={"work_order": wo.name, "docstatus": 0},
        fields=["name", "operation", "sequence_id"],
    )
    if not jcs:
        return

    jcs_sorted = sorted(jcs, key=lambda x: (wo_op_seq.get(x.operation, 0), x.name))
    transferred_weight = flt(wo.get("custom_transferred_weight_kg") or 0)
    nos_by_drawing_from_sco = {}

    # Mixed-plan chain, reverse ordering: if a sibling SCO already finished its
    # subcontract portion before this WO's Job Cards were created, seed Op-1 from
    # ITS completion instead of this WO's own (irrelevant, likely-zero) raw-material
    # transfer. The forward ordering (SCO finishes AFTER these JCs already exist) is
    # handled live by _push_sco_completion_to_wo on the SCO's last SOE submit.
    sco_row = frappe.db.get_value(
        "Subcontracting Order",
        {"custom_production_plan": wo.production_plan, "docstatus": ["!=", 2]},
        ["name", "custom_all_ops_complete"],
        as_dict=True,
    )
    if sco_row and sco_row.custom_all_ops_complete:
        last_soe_name = frappe.db.get_value(
            "Supplier Operation Entry",
            {"subcontracting_order": sco_row.name, "docstatus": 1},
            "name", order_by="sequence_id desc",
        )
        if last_soe_name:
            last_soe = frappe.get_doc("Supplier Operation Entry", last_soe_name)
            transferred_weight = flt(last_soe.total_consumed_kg, 3)
            nos_by_drawing_from_sco = {
                r.drawing: flt(r.completed_qty_nos, 3)
                for r in (last_soe.drawing_details or []) if r.drawing
            }

    for seq_idx, jc_info in enumerate(jcs_sorted, start=1):
        jc_doc = frappe.get_doc("Job Card", jc_info.name)

        # Idempotent check
        if frappe.db.exists(
            "SOE Drawing Detail",
            {"parent": jc_info.name, "parentfield": "custom_drawing_details"},
        ):
            continue

        drawing_rows = _build_jc_drawing_rows(wo, seq_idx)
        for row in drawing_rows:
            jc_doc.append("custom_drawing_details", row)

        if seq_idx == 1:
            jc_doc.custom_available_to_consume_kg = flt(transferred_weight, 3)
            if nos_by_drawing_from_sco:
                for row in jc_doc.custom_drawing_details:
                    row.available_to_consume_nos = flt(
                        nos_by_drawing_from_sco.get(row.drawing or "", 0.0), 3
                    )

        jc_doc.custom_total_available_nos  = flt(
            sum(flt(r.available_to_consume_nos) for r in jc_doc.custom_drawing_details), 3
        )
        jc_doc.custom_total_completed_nos  = 0.0
        jc_doc.flags.ignore_validate = True
        jc_doc.save(ignore_permissions=True)
