import re
import frappe
from frappe import _
from frappe.utils import flt, now

STRUCTURALS_REQUIRED = ["custom_length", "custom_unit_weight", "custom_sec_qty"]
PLATES_REQUIRED = ["custom_length", "custom_width", "custom_thickness", "custom_unit_weight", "custom_sec_qty"]
FIELD_LABELS = {
    "custom_length": "Length",
    "custom_width": "Width",
    "custom_thickness": "Thickness",
    "custom_unit_weight": "Unit Weight",
    "custom_sec_qty": "Sec Qty",
}
REFERENCE_FIELDS = ["custom_drawing", "custom_duno_mark_no", "custom_customer_drawing_number", "custom_sales_order"]


@frappe.whitelist()
def get_pr_item_uom(doctype, txt, searchfield, start, page_len, filters):
    item_code = (filters if isinstance(filters, dict) else frappe.parse_json(filters)).get("item_code")
    if not item_code:
        return []
    return frappe.db.sql(
        """
        SELECT uom FROM `tabUOM Conversion Detail`
        WHERE parent = %s AND uom LIKE %s
        UNION
        SELECT stock_uom FROM `tabItem` WHERE name = %s AND stock_uom LIKE %s
        LIMIT %s
        """,
        (item_code, f"%{txt}%", item_code, f"%{txt}%", int(page_len)),
    )


def validate_purchase_receipt(doc, method):
    for row in doc.items:
        _copy_from_po_item(row)
        _recalculate_qty(row)
        _check_missing_fields(row, throw=False)
    doc.custom_total_weight = sum(
        row.qty for row in doc.items
        if row.custom_parent_item_group in ("Structurals", "Plates")
    )


def before_submit_purchase_receipt(doc, method):
    for row in doc.items:
        _check_missing_fields(row, throw=True)


def before_insert_batch(doc, method):
    """Set custom batch name and store dimensions when batch is auto-created."""
    if doc.reference_doctype == "Purchase Receipt" and doc.reference_name:
        _setup_batch_from_purchase_receipt(doc)
    elif doc.reference_doctype == "Stock Entry" and doc.reference_name:
        _setup_batch_from_stock_entry(doc)


def _setup_batch_from_purchase_receipt(doc):
    # When multiple rows of the same item exist in the PR, count how many batches
    # have already been created for this PR + item to pick the correct row by idx.
    already_created = frappe.db.count(
        "Batch",
        filters={
            "reference_doctype": "Purchase Receipt",
            "reference_name": doc.reference_name,
            "item": doc.item,
        },
    )
    pr_items = frappe.db.get_all(
        "Purchase Receipt Item",
        filters={"parent": doc.reference_name, "item_code": doc.item},
        fields=[
            "custom_thickness", "custom_length", "custom_width", "custom_sec_qty",
            "custom_sec_uom", "custom_parent_item_group",
        ],
        order_by="idx asc",
    )
    if not pr_items:
        return
    row_index = already_created if already_created < len(pr_items) else 0
    pr_item = pr_items[row_index]

    batch_prefix = frappe.db.get_value("Item", doc.item, "custom_batch_prefix")
    if not batch_prefix:
        return

    receipt_suffix = _get_receipt_suffix(doc.reference_name)
    parts = [batch_prefix]
    if pr_item.custom_thickness:
        parts.append(f"T{int(pr_item.custom_thickness)}")
    if pr_item.custom_length:
        parts.append(f"L{int(pr_item.custom_length)}")
    if pr_item.custom_width:
        parts.append(f"W{int(pr_item.custom_width)}")
    parts.append(f"R{receipt_suffix}")

    batch_id = "-".join(parts)
    counter = 1
    base_id = batch_id
    while frappe.db.exists("Batch", batch_id):
        counter += 1
        batch_id = f"{base_id}-{counter}"

    doc.batch_id = batch_id
    doc.custom_thickness = pr_item.custom_thickness
    doc.custom_length = pr_item.custom_length
    doc.custom_width = pr_item.custom_width
    doc.custom_sec_qty = pr_item.custom_sec_qty
    doc.custom_sec_uom = pr_item.custom_sec_uom

    # Guard: Structurals/Plates batches are always Nos-tracked. A batch silently
    # created with Sec Qty 0 breaks Kg -> Nos allocation in Material Planning
    # (_alloc_sec_qty) with no visible error until someone notices downstream.
    # before_submit_purchase_receipt already requires Sec Qty > 0 on the PR line
    # itself, so landing here means the row_index match above (best-effort — there
    # is no direct back-reference from an auto-created batch to its source PR row)
    # picked up the wrong line, most likely because several rows share identical
    # dimensions. Fail loudly here rather than silently persist a corrupt batch.
    if pr_item.custom_parent_item_group in ("Structurals", "Plates") and not flt(pr_item.custom_sec_qty):
        frappe.throw(
            _(
                "Cannot create batch {0} for item {1}: Sec Qty (Nos) resolved to 0 while "
                "matching Purchase Receipt {2}. This usually means two or more rows for this "
                "item share identical Length/Width/Thickness — give them distinct dimensions "
                "(or split the receipt) so each batch can be matched to the correct row."
            ).format(batch_id, doc.item, doc.reference_name)
        )


def _setup_batch_from_stock_entry(doc):
    """Set batch name and dimensions for batches created from Repack or Material Receipt SE."""
    se = frappe.get_doc("Stock Entry", doc.reference_name)
    if se.stock_entry_type not in ("Repack", "Material Receipt"):
        return

    matching_rows = [
        r for r in se.items
        if r.item_code == doc.item
        and (se.stock_entry_type == "Material Receipt" or r.is_finished_item)
    ]
    if not matching_rows:
        return

    # Count batches already inserted for this SE + item to pick the correct row.
    # before_insert fires before this batch is committed, so existing count = index of current row.
    already_created = frappe.db.count(
        "Batch",
        filters={
            "reference_doctype": "Stock Entry",
            "reference_name": doc.reference_name,
            "item": doc.item,
        },
    )
    row_index = already_created if already_created < len(matching_rows) else 0
    target_row = matching_rows[row_index]

    batch_prefix = frappe.db.get_value("Item", doc.item, "custom_batch_prefix")
    if not batch_prefix:
        return

    t = int(flt(target_row.custom_thickness)) if target_row.custom_thickness else None
    l = int(flt(target_row.custom_length)) if target_row.custom_length else None
    w = int(flt(target_row.custom_width)) if target_row.custom_width else None
    suffix = _get_se_suffix(se.name)

    parts = [batch_prefix]
    if t:
        parts.append(f"P{t}")
    if l:
        parts.append(f"L{l}")
    if w:
        parts.append(f"W{w}")
    parts.append(f"SR{suffix}")

    batch_id = "-".join(parts)
    counter = 1
    base_id = batch_id
    while frappe.db.exists("Batch", batch_id):
        counter += 1
        batch_id = f"{base_id}-{counter}"

    doc.batch_id = batch_id
    doc.custom_thickness = flt(target_row.custom_thickness)
    doc.custom_length = flt(target_row.custom_length)
    doc.custom_width = flt(target_row.custom_width)
    doc.custom_sec_qty = flt(target_row.custom_sec_qty)
    doc.custom_sec_uom = target_row.custom_sec_uom

    group = (target_row.get("custom_parent_item_group") or "").strip()
    if group in {"Structurals", "Plates"}:
        doc.custom_existing_supplier_invoice_no = target_row.get("custom_existing_supplier_invoice_no") or ""
        doc.custom_existing_invoice_wt = flt(target_row.get("custom_existing_invoice_wt"))
        doc.custom_existing_inward_date = target_row.get("custom_existing_inward_date")


def _get_receipt_suffix(pr_name):
    """Extract last 3 digits from the numeric part of a receipt name (e.g. MAT-PRE-2024-00010 → '010')."""
    match = re.search(r"(\d+)$", pr_name)
    if match:
        return match.group(1)[-3:].zfill(3)
    return pr_name[-3:] if pr_name else "000"


def _get_se_suffix(se_name):
    """Extract last 3 digits from the numeric part of a Stock Entry name."""
    match = re.search(r"(\d+)$", se_name)
    if match:
        return match.group(1)[-3:].zfill(3)
    return se_name[-3:] if se_name else "001"


def _copy_from_po_item(row):
    """Copy dimension + reference fields from the linked PO Item when a PR is created from a PO."""
    if not row.purchase_order_item:
        return
    fields = ["custom_length", "custom_width", "custom_thickness", "custom_sec_qty", *REFERENCE_FIELDS]
    if any(row.get(f) for f in fields):
        return
    po_item = frappe.db.get_value("Purchase Order Item", row.purchase_order_item, fields, as_dict=True)
    if not po_item:
        return
    for field in fields:
        row.set(field, po_item.get(field))


def _recalculate_qty(row):
    group = row.custom_parent_item_group
    if group == "Structurals":
        if row.custom_length and row.custom_unit_weight and row.custom_sec_qty:
            row.qty = (row.custom_length / 1000) * row.custom_unit_weight * row.custom_sec_qty
    elif group == "Plates":
        if all(getattr(row, f, None) for f in PLATES_REQUIRED):
            row.qty = (
                (row.custom_length / 1000)
                * (row.custom_width / 1000)
                * row.custom_thickness
                * row.custom_unit_weight
                * row.custom_sec_qty
            )
    elif group == "Nuts and Bolts":
        if row.qty and row.custom_unit_weight:
            row.custom_sec_qty = row.qty * row.custom_unit_weight


def _check_missing_fields(row, throw):
    group = row.custom_parent_item_group
    if group == "Structurals":
        required = STRUCTURALS_REQUIRED
    elif group == "Plates":
        required = PLATES_REQUIRED
    else:
        return
    missing = [FIELD_LABELS[f] for f in required if not getattr(row, f, None)]
    if missing:
        msg = _("Row {0}: {1} required for {2} formula").format(
            row.idx, ", ".join(missing), group
        )
        if throw:
            frappe.throw(msg)
        else:
            frappe.msgprint(msg, indicator="orange", title=_("Missing Fields"))


# ── Material Planning auto-allocation ────────────────────────────────────────

@frappe.whitelist()
def get_mp_for_pr(pr_name):
    """Trace PR → PO → MR → Material Planning. Returns list of MP names linked to this PR."""
    rows = frappe.db.sql(
        """
        SELECT DISTINCT mr.custom_material_planning
        FROM `tabPurchase Receipt Item`  pri
        JOIN `tabPurchase Order Item`    poi ON poi.name  = pri.purchase_order_item
        JOIN `tabMaterial Request Item`  mri ON mri.name  = poi.material_request_item
        JOIN `tabMaterial Request`       mr  ON mr.name   = mri.parent
        WHERE pri.parent = %(pr)s
          AND mr.custom_material_planning IS NOT NULL
          AND mr.custom_material_planning != ''
        """,
        {"pr": pr_name},
    )
    return [r[0] for r in rows if r[0]]


@frappe.whitelist()
def allocate_pr_stock_to_mp(pr_name, mp_name):
    """
    Allocate batches received on a PR into the linked Material Planning.
    - Original item purchased  → Available Raw Materials (Exact Match)
    - Alternate item purchased → Material Mapping (Partial Stock)
    """
    pr = frappe.get_doc("Purchase Receipt", pr_name)
    mp = frappe.get_doc("Material Planning", mp_name)

    # Index MP unavailable_items two ways: precise (item_code, duno_mark_no) when the
    # PR item carries a DUNO reference, and a legacy item-code-only fallback for PRs
    # created before this reference chain existed (no custom_duno_mark_no to match on).
    by_alternate, by_alternate_any = {}, {}
    by_original, by_original_any = {}, {}
    for row in (mp.unavailable_items or []):
        duno = row.duno_mark_no or ""
        if row.alternate_item:
            by_alternate.setdefault((row.alternate_item, duno), []).append(row)
            by_alternate_any.setdefault(row.alternate_item, []).append(row)
        by_original.setdefault((row.item_code, duno), []).append(row)
        by_original_any.setdefault(row.item_code, []).append(row)

    # Existing allocations — avoid duplicates
    existing_exact   = {(r.item_code, r.batch_no)           for r in (mp.available_raw_materials or [])}
    existing_mapping = {(r.item_code, r.batch or "")        for r in (mp.material_mapping       or [])}

    added_exact   = 0
    added_mapping = 0

    for pr_item in pr.items:
        if not pr_item.purchase_order_item:
            continue

        # Confirm this PR item traces back to our MP
        mr_item_name = frappe.db.get_value(
            "Purchase Order Item", pr_item.purchase_order_item, "material_request_item"
        )
        if not mr_item_name:
            continue
        mr_name = frappe.db.get_value("Material Request Item", mr_item_name, "parent")
        if not mr_name:
            continue
        item_mp = frappe.db.get_value("Material Request", mr_name, "custom_material_planning")
        if item_mp != mp_name:
            continue

        item_code = pr_item.item_code
        batch_no  = pr_item.batch_no or ""
        pr_duno   = pr_item.get("custom_duno_mark_no") or ""

        # When the PR item knows its DUNO, only allocate against that exact drawing's
        # row — no fallback fan-out (a miss here should surface as unallocated, not
        # mis-allocated to a different drawing's shortage). Only fall back to matching
        # by item_code alone when the PR item has no DUNO reference at all (in-flight
        # PRs created before this field existed).
        if pr_duno:
            matched_alternate = by_alternate.get((item_code, pr_duno), [])
            matched_original  = by_original.get((item_code, pr_duno), [])
        else:
            matched_alternate = by_alternate_any.get(item_code, [])
            matched_original  = by_original_any.get(item_code, [])

        if matched_alternate:
            # Alternate item purchased → Material Mapping
            for mp_row in matched_alternate:
                key = (mp_row.item_code, batch_no)
                if key in existing_mapping:
                    continue
                existing_mapping.add(key)
                mp.append("material_mapping", {
                    "item_number":            mp_row.item_number,
                    "sales_order":            mp_row.sales_order,
                    "item_code":              mp_row.item_code,
                    "item_name":              mp_row.item_name,
                    "bom_no":                 mp_row.bom_no,
                    "drawing":                mp_row.drawing,
                    "duno_mark_no":           mp_row.duno_mark_no,
                    "customer_drawing_number": mp_row.customer_drawing_number,
                    "qty":                    mp_row.qty,
                    "uom":                    mp_row.uom,
                    "sec_qty":                flt(pr_item.custom_sec_qty) or mp_row.sec_qty,
                    "sec_uom":                mp_row.sec_uom,
                    "parent_item_group":      mp_row.parent_item_group,
                    "length":                 flt(pr_item.custom_length)    or mp_row.length,
                    "width":                  flt(pr_item.custom_width)     or mp_row.width,
                    "thickness":              flt(pr_item.custom_thickness) or mp_row.thickness,
                    "unit_weight":            mp_row.unit_weight,
                    "batch":                  batch_no,
                    "planned_item":           item_code,
                })
                added_mapping += 1

        elif matched_original:
            # Original item purchased → Available Raw Materials (Exact Match)
            item_data = frappe.db.get_value(
                "Item", item_code,
                ["stock_uom", "custom_secondary_uom"],
                as_dict=True,
            ) or {}
            for mp_row in matched_original:
                key = (item_code, batch_no)
                if key in existing_exact:
                    continue
                existing_exact.add(key)
                mp.append("available_raw_materials", {
                    "item_number":            mp_row.item_number,
                    "sales_order":            mp_row.sales_order,
                    "item_code":              item_code,
                    "item_name":              pr_item.item_name or mp_row.item_name,
                    "duno_mark_no":           mp_row.duno_mark_no,
                    "customer_drawing_number": mp_row.customer_drawing_number,
                    "batch_no":               batch_no,
                    "parent_item_group":      mp_row.parent_item_group,
                    "length":                 flt(pr_item.custom_length)    or mp_row.length,
                    "width":                  flt(pr_item.custom_width)     or mp_row.width,
                    "thickness":              flt(pr_item.custom_thickness) or mp_row.thickness,
                    "required_qty":           mp_row.qty,
                    "available_qty":          pr_item.qty,
                    "sec_qty":                flt(pr_item.custom_sec_qty)   or mp_row.sec_qty,
                    "sec_uom":                item_data.get("custom_secondary_uom") or mp_row.sec_uom,
                    "uom":                    item_data.get("stock_uom")    or mp_row.uom,
                    "warehouse":              pr_item.warehouse or mp.for_warehouse,
                })
                added_exact += 1

    if added_exact or added_mapping:
        mp.save(ignore_permissions=True)

    return {"added_exact": added_exact, "added_mapping": added_mapping}


def on_submit_purchase_receipt(doc, method):
    """Auto-allocate received batches back to every Material Planning this PR traces to."""
    for mp_name in get_mp_for_pr(doc.name):
        try:
            allocate_pr_stock_to_mp(doc.name, mp_name)
        except Exception:
            frappe.log_error(
                title=f"Material Planning auto-allocation failed for {doc.name} -> {mp_name}",
                message=frappe.get_traceback(),
            )
