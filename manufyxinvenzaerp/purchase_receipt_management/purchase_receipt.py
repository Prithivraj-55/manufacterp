import re
import frappe
from frappe import _
from frappe.utils import flt, now
from manufyxinvenzaerp.production_management.doctype.material_planning.material_planning import (
    _get_batch_reserved_by_others,
    _get_batch_total_stock,
)
from manufyxinvenzaerp.utils.dimension_formula import calculate_qty, calculate_sec_qty_from_qty, check_missing_fields
from manufyxinvenzaerp.utils.reference_copy import copy_reference_fields_if_blank

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
    # Excess-material-return Stock Entries (create_mip_excess_return_entry) tag
    # each item with the SCO Excess Material Item row it came from, so Excess
    # Material Mapping can trace a reservation back to it -- carry that onto
    # the batch the same way every other custom_* dimension field is copied.
    doc.custom_source_mip_excess_row = target_row.get("custom_source_mip_excess_row") or ""

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
    fields = ["custom_length", "custom_width", "custom_thickness", "custom_sec_qty", *REFERENCE_FIELDS]
    copy_reference_fields_if_blank(row, "Purchase Order Item", "purchase_order_item", fields)


def _recalculate_qty(row):
    group = row.custom_parent_item_group
    if group in ("Structurals", "Plates"):
        qty = calculate_qty(
            group, row.custom_length, row.custom_width, row.custom_thickness,
            row.custom_unit_weight, row.custom_sec_qty,
        )
        if qty is not None:
            row.qty = qty
    elif group == "Nuts and Bolts":
        sec_qty = calculate_sec_qty_from_qty(row.custom_unit_weight, row.qty)
        if sec_qty is not None:
            row.custom_sec_qty = sec_qty


def _check_missing_fields(row, throw):
    check_missing_fields(row, throw)


# ── Material Planning auto-allocation ────────────────────────────────────────

def _resolve_pr_batch_no(pr_item):
    """Purchase Receipt Items in this instance don't reliably carry batch_no
    directly (items are set to auto-create a new batch on receipt, and this
    environment leaves batch_no blank on the row) — the actual batch lives on
    the row's Serial and Batch Bundle. Resolve it from there, falling back to
    batch_no for any PR created the traditional way."""
    if pr_item.batch_no:
        return pr_item.batch_no
    bundle = pr_item.get("serial_and_batch_bundle")
    if not bundle:
        return ""
    return frappe.db.get_value("Serial and Batch Entry", {"parent": bundle}, "batch_no") or ""


@frappe.whitelist()
def get_mp_for_pr(pr_name):
    """Trace PR → PO → MR → Material Planning. Returns list of MP names linked to this PR."""
    if not frappe.has_permission("Material Planning", "read"):
        frappe.throw(_("Not permitted to view Material Planning links"), frappe.PermissionError)
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


def _pr_dimensions_match(pr_item, mp_row):
    """True when a purchased line arrived in exactly the size the requirement
    row asks for -- the same strict all-three-dimensions rule
    production_plan.get_sbb_available_qty applies when matching batches on the
    manual "check stock" path (material_planning.move_to_exact_match).

    Only such a receipt is a genuine Exact Match. Available Raw Materials
    carries a single Length/Width/Thickness precisely because the requirement
    and the batch are the same size there; a receipt in any other size has no
    field on that table to record both, so it belongs in Material Mapping.
    """
    return (
        flt(pr_item.custom_length) == flt(mp_row.length)
        and flt(pr_item.custom_width) == flt(mp_row.width)
        and flt(pr_item.custom_thickness) == flt(mp_row.thickness)
    )


def _build_mapping_row(
    mp_row,
    *,
    alloc_qty,
    ratio,
    pr_item,
    pr_name,
    purchased_item_code,
    batch_no,
    purchased_item_data,
    batch_total_qty,
    batch_reserved_qty,
):
    """Build a fully-populated Material Mapping row for a received batch that
    does not dimensionally match the requirement -- either because an alternate
    item was bought, or because the original item was bought at a different
    (typically standard stock) size via a Consolidate Item line.

    The requirement's own Length/Width/Thickness/Qty stay on the row's plain
    fields while the batch's go on the batch_* fields, so the size actually
    needed survives alongside the size actually purchased.
    """
    return {
        "item_number":             mp_row.item_number,
        "sales_order":             mp_row.sales_order,
        "item_code":               mp_row.item_code,
        "item_name":               mp_row.item_name,
        "bom_no":                  mp_row.bom_no,
        "drawing":                 mp_row.drawing,
        "duno_mark_no":            mp_row.duno_mark_no,
        "customer_drawing_number": mp_row.customer_drawing_number,
        "qty":                     mp_row.qty,
        "uom":                     mp_row.uom,
        "sec_qty":                 mp_row.sec_qty,
        "sec_uom":                 mp_row.sec_uom,
        "parent_item_group":       mp_row.parent_item_group,
        "length":                  mp_row.length,
        "width":                   mp_row.width,
        "thickness":               mp_row.thickness,
        "unit_weight":             mp_row.unit_weight,
        "batch":                   batch_no,
        "planned_item":            purchased_item_code,
        "batch_mapped":            "Mapped" if batch_no else "Not Mapped",
        "batch_parent_item_group": purchased_item_data.get("custom_parent_item_group") or "",
        "batch_length":            flt(pr_item.custom_length),
        "batch_width":             flt(pr_item.custom_width),
        "batch_thickness":         flt(pr_item.custom_thickness),
        "batch_unit_weight":       flt(purchased_item_data.get("custom_unit_weight")),
        "batch_sec_qty":           flt(flt(pr_item.custom_sec_qty) * ratio, 3),
        "batch_calc_qty":          flt(alloc_qty, 3),
        "batch_total_qty":         flt(batch_total_qty, 3),
        "batch_reserved_qty":      flt(batch_reserved_qty, 3),
        "batch_free_qty":          flt(max(0.0, batch_total_qty - batch_reserved_qty), 3),
        "purchase_receipt":        pr_name,
        # Dimensions differ by definition on this path -- reserve by weight
        # rather than requiring a dimension match, same as picking this batch by
        # hand via "Assign Batch" with that option enabled. Sec Nos is derived
        # from that weight and stays fractional; whole-piece rounding happens at
        # transfer time on the Material Issue Plan.
        "reserve_without_dimensions": 1,
    }


@frappe.whitelist()
def allocate_pr_stock_to_mp(pr_name, mp_name):
    """
    Allocate batches received on a PR into the linked Material Planning.
    - Received in the requirement's own dimensions → Available Raw Materials (Exact Match)
    - Received in any other size, or as an alternate item → Material Mapping (Partial Stock)

    Routing is decided per requirement row by actual dimensions
    (_pr_dimensions_match), not by whether the original or an alternate item
    code was bought: buying the right item code at a standard stock size (the
    normal outcome of a Consolidate Item purchase, e.g. ISMB400 ordered in
    4000 mm bars to cover 6936 mm requirements) is NOT an exact match, and
    recording it as one would overwrite the required size with the purchased
    one -- Available Raw Materials has only a single set of dimensions.

    "Alternate item purchased" covers both Unavailable Item's own per-row
    alternate_item AND Material Planning Consolidate Item's alternate_item
    (a bulk substitution decision made once for the whole deduped-by-item_code
    consolidated line) -- either way the purchased batch lands in Material
    Mapping against every original Unavailable Item row it substitutes for.

    The matched Unavailable Items row is removed once fully covered; if the PR
    received less than the row's required qty, the row is kept with its qty
    (and proportional Sec Qty) reduced to just the remaining shortfall.

    No item/batch/duno-keyed dedup is applied when appending Available Raw
    Materials/Material Mapping rows -- a drawing can genuinely need the SAME
    item from the SAME batch more than once (e.g. two different-length pieces
    of ISA100 on one duno), and such a key previously collapsed those into one,
    silently discarding the second Unavailable Item row (still marked
    fulfilled and removed by the reconcile step below, since _consume() runs
    before any such check) with no Available Raw Materials/Material Mapping
    row ever created for it -- a real data-loss bug found on MP-2026-00010
    (18 rows, ~132.9 Kg, across 13 duno+item combinations). Re-running this
    function for the same PR is naturally idempotent without a key anyway:
    each call rebuilds its match candidates from mp.unavailable_items as it
    currently stands, and a fully-fulfilled row is already gone from that
    table by the time any second call could happen.
    """
    pr = frappe.get_doc("Purchase Receipt", pr_name)
    mp = frappe.get_doc("Material Planning", mp_name)

    # Index MP unavailable_items two ways: precise (item_code, duno_mark_no) when the
    # PR item carries a DUNO reference, and a legacy item-code-only fallback for PRs
    # created before this reference chain existed (no custom_duno_mark_no to match on).
    by_alternate, by_alternate_any = {}, {}
    by_original, by_original_any = {}, {}
    unavail_by_item_code = {}
    for row in (mp.unavailable_items or []):
        duno = row.duno_mark_no or ""
        if row.alternate_item:
            by_alternate.setdefault((row.alternate_item, duno), []).append(row)
            by_alternate_any.setdefault(row.alternate_item, []).append(row)
        by_original.setdefault((row.item_code, duno), []).append(row)
        by_original_any.setdefault(row.item_code, []).append(row)
        unavail_by_item_code.setdefault(row.item_code, []).append(row)

    # Consolidate Item's own Alternate Item section (bulk, whole-consolidated-
    # line purchasing decision, set once rather than per original drawing row)
    # -- when set, a purchase of that alternate item must fan out across every
    # Unavailable Item row sharing the Consolidate Item row's own item_code
    # (i.e. everything that got deduped into it), the same way Unavailable
    # Item's own per-row alternate_item already does. Consolidate Item never
    # carries a DUNO (it's deduped across drawings), so this only ever
    # participates in the item-code-only ("_any"/sequential) matching below.
    by_consolidate_alt_any = {}
    for c_row in (mp.consolidate_items or []):
        if c_row.alternate_item:
            by_consolidate_alt_any.setdefault(c_row.alternate_item, []).extend(
                unavail_by_item_code.get(c_row.item_code, [])
            )

    added_exact   = 0
    added_mapping = 0
    fulfilled_row_names  = set()
    remaining_qty_by_row = {}  # row.name -> qty still short after this PR's receipts
    QTY_EPSILON = 0.001  # matches the 3-decimal rounding used throughout this table

    def _consume(mp_row, received_qty):
        remaining = flt(remaining_qty_by_row.get(mp_row.name, flt(mp_row.qty)) - received_qty, 3)
        if remaining <= QTY_EPSILON:
            fulfilled_row_names.add(mp_row.name)
            remaining_qty_by_row.pop(mp_row.name, None)
        else:
            remaining_qty_by_row[mp_row.name] = remaining

    def _split_allocation(matched_rows, received_qty, sequential):
        """Client change request Phase 2.5: a consolidated purchase line (no
        DUNO to disambiguate — e.g. one bought via a Material Planning
        Consolidate Item row that summed several drawings' requirements for
        the same item_code) matching MORE THAN ONE Unavailable Item row must
        split its received qty SEQUENTIALLY across those rows — fill the
        first (by original document order/idx) fully, then the next, and so
        on — rather than crediting the full received qty to every matched row
        independently (which double/triple-counts the same physical receipt).
        Any dimension-driven shortfall naturally lands on the last row(s) in
        the sequence, since earlier rows are always filled first. A single
        match, or a precise item+DUNO match, is unaffected — same behavior as
        before (the full received qty applies to that one row).

        Rows already filled by an EARLIER line of the same receipt are skipped.
        A supplier substituting sizes delivers one item across several PR lines
        (7000 mm unavailable, so 2 x 4000 mm plus a 6900 mm), and each line runs
        this function again over the same match list; without that skip, a row
        _consume() already completed is absent from remaining_qty_by_row and so
        falls back to its FULL original qty, silently getting a second helping
        while later rows receive nothing."""
        if not sequential or len(matched_rows) <= 1:
            return [(mp_row, flt(received_qty)) for mp_row in matched_rows]

        allocations = []
        remaining_receipt = flt(received_qty)
        for mp_row in sorted(matched_rows, key=lambda r: r.idx):
            if remaining_receipt <= QTY_EPSILON:
                break
            if mp_row.name in fulfilled_row_names:
                continue
            row_requirement = flt(remaining_qty_by_row.get(mp_row.name, mp_row.qty))
            alloc_qty = flt(min(remaining_receipt, row_requirement), 3)
            if alloc_qty <= 0:
                continue
            allocations.append((mp_row, alloc_qty))
            remaining_receipt = flt(remaining_receipt - alloc_qty, 3)
        return allocations

    # Batch-resolve the PO Item -> MR Item -> MR chain for every PR row up
    # front (3 queries total) instead of 3 frappe.db.get_value calls per row
    # (Report 4 Finding D-04) -- the loop below does the same lookups as
    # before, just against these pre-fetched dicts.
    poi_names = list({pr_item.purchase_order_item for pr_item in pr.items if pr_item.purchase_order_item})
    poi_to_mri = {}
    if poi_names:
        for rec in frappe.get_all(
            "Purchase Order Item", filters={"name": ["in", poi_names]}, fields=["name", "material_request_item"]
        ):
            poi_to_mri[rec.name] = rec.material_request_item

    mri_names = list({v for v in poi_to_mri.values() if v})
    mri_to_mr = {}
    if mri_names:
        for rec in frappe.get_all(
            "Material Request Item", filters={"name": ["in", mri_names]}, fields=["name", "parent"]
        ):
            mri_to_mr[rec.name] = rec.parent

    mr_names = list({v for v in mri_to_mr.values() if v})
    mr_to_mp = {}
    if mr_names:
        for rec in frappe.get_all(
            "Material Request", filters={"name": ["in", mr_names]}, fields=["name", "custom_material_planning"]
        ):
            mr_to_mp[rec.name] = rec.custom_material_planning

    for pr_item in pr.items:
        if not pr_item.purchase_order_item:
            continue

        # Confirm this PR item traces back to our MP
        mr_item_name = poi_to_mri.get(pr_item.purchase_order_item)
        if not mr_item_name:
            continue
        mr_name = mri_to_mr.get(mr_item_name)
        if not mr_name:
            continue
        item_mp = mr_to_mp.get(mr_name)
        if item_mp != mp_name:
            continue

        item_code = pr_item.item_code
        batch_no  = _resolve_pr_batch_no(pr_item)
        pr_duno   = pr_item.get("custom_duno_mark_no") or ""

        # When the PR item knows its DUNO, only allocate against that exact drawing's
        # row — no fallback fan-out (a miss here should surface as unallocated, not
        # mis-allocated to a different drawing's shortage). Only fall back to matching
        # by item_code alone when the PR item has no DUNO reference at all -- either an
        # in-flight PR created before this field existed, or (client change request
        # Phase 2.5) a consolidated purchase line that intentionally spans several
        # drawings' worth of the same item_code and must split sequentially across them.
        sequential = not pr_duno

        if pr_duno:
            matched_alternate = by_alternate.get((item_code, pr_duno), [])
            matched_original  = by_original.get((item_code, pr_duno), [])
        else:
            matched_alternate = list(by_alternate_any.get(item_code, []))
            matched_original  = by_original_any.get(item_code, [])
            # Merge in rows matched via a Consolidate Item row's own
            # alternate_item -- dedup by row name in case a row is ALSO
            # independently flagged with its own row-level alternate_item
            # equal to the same purchased item_code.
            if item_code in by_consolidate_alt_any:
                seen_names = {r.name for r in matched_alternate}
                for r in by_consolidate_alt_any[item_code]:
                    if r.name not in seen_names:
                        matched_alternate.append(r)
                        seen_names.add(r.name)

        if matched_alternate:
            # Alternate item purchased → Material Mapping, fully populated as
            # if the user had picked this batch by hand (batch dimensions,
            # Sec Qty/Calc Qty, Status), not left blank for a later manual fix.
            alt_item_data = frappe.db.get_value(
                "Item", item_code,
                ["custom_parent_item_group", "custom_unit_weight"],
                as_dict=True,
            ) or {}
            batch_total_qty    = _get_batch_total_stock(batch_no, mp.for_warehouse) if batch_no else 0.0
            batch_reserved_qty = _get_batch_reserved_by_others(batch_no, mp_name) if batch_no else 0.0
            received_qty = flt(pr_item.qty)

            for mp_row, alloc_qty in _split_allocation(matched_alternate, received_qty, sequential):
                _consume(mp_row, alloc_qty)
                ratio = (alloc_qty / received_qty) if received_qty else 0.0
                mp.append("material_mapping", _build_mapping_row(
                    mp_row,
                    alloc_qty=alloc_qty,
                    ratio=ratio,
                    pr_item=pr_item,
                    pr_name=pr_name,
                    purchased_item_code=item_code,
                    batch_no=batch_no,
                    purchased_item_data=alt_item_data,
                    batch_total_qty=batch_total_qty,
                    batch_reserved_qty=batch_reserved_qty,
                ))
                added_mapping += 1

        elif matched_original:
            # Original item purchased -- Exact Match only for the rows whose own
            # dimensions this receipt actually matches. A Consolidate Item line
            # bought at a standard stock size matches none of them and goes to
            # Material Mapping instead, keeping the required size on the row and
            # the purchased size on batch_* (see _pr_dimensions_match).
            item_data = frappe.db.get_value(
                "Item", item_code,
                ["stock_uom", "custom_secondary_uom",
                 "custom_parent_item_group", "custom_unit_weight"],
                as_dict=True,
            ) or {}
            batch_total_qty    = _get_batch_total_stock(batch_no, mp.for_warehouse) if batch_no else 0.0
            batch_reserved_qty = _get_batch_reserved_by_others(batch_no, mp_name) if batch_no else 0.0
            received_qty = flt(pr_item.qty)

            splits = list(_split_allocation(matched_original, received_qty, sequential))

            # ONE batch, ONE table -- decided here for the whole receipt line rather
            # than per requirement row.
            #
            # A single received batch is routinely split across several requirements,
            # and its dimensions can match some of them exactly while missing others.
            # Deciding row by row put the same batch into Material Mapping AND Exact
            # Match, which _validate_no_cross_table_batch_duplicate then refuses --
            # the plan could not be saved at all after such a receipt, and the batch
            # would have been double-counted at transfer time if it had been.
            #
            # Any mismatch sends the whole batch to Material Mapping: that table
            # carries the required size on the row and the purchased size on batch_*,
            # so it represents a matching row perfectly well, while Exact Match
            # assumes the two are the same and cannot represent a mismatch at all.
            all_dimensions_match = all(
                _pr_dimensions_match(pr_item, mp_row) for mp_row, _ in splits
            )

            for mp_row, alloc_qty in splits:
                _consume(mp_row, alloc_qty)
                ratio = (alloc_qty / received_qty) if received_qty else 0.0

                if not all_dimensions_match:
                    mp.append("material_mapping", _build_mapping_row(
                        mp_row,
                        alloc_qty=alloc_qty,
                        ratio=ratio,
                        pr_item=pr_item,
                        pr_name=pr_name,
                        purchased_item_code=item_code,
                        batch_no=batch_no,
                        purchased_item_data=item_data,
                        batch_total_qty=batch_total_qty,
                        batch_reserved_qty=batch_reserved_qty,
                    ))
                    added_mapping += 1
                    continue

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
                    "overall_required_qty":   flt(mp_row.qty, 3),
                    "required_qty":           flt(min(alloc_qty, flt(mp_row.qty)), 3),
                    "available_qty":          flt(alloc_qty, 3),
                    "sec_qty":                flt(flt(pr_item.custom_sec_qty) * ratio, 3) or mp_row.sec_qty,
                    "sec_uom":                item_data.get("custom_secondary_uom") or mp_row.sec_uom,
                    "uom":                    item_data.get("stock_uom")    or mp_row.uom,
                    "warehouse":              pr_item.warehouse or mp.for_warehouse,
                    "purchase_receipt":       pr_name,
                })
                added_exact += 1

    # Reconcile Unavailable Items. A row this receipt covered in full simply
    # goes; a row it covered only partly leaves behind its shortfall as a
    # Material Mapping row with NO batch, for someone to assign by hand.
    #
    # A short delivery means the material was ordered and arrived undersized --
    # not that nobody has tried to buy it yet. Leaving the remainder in
    # Unavailable Items would send it round the purchase loop a second time; the
    # blank-batch Mapping row instead puts it where every other "assign this
    # yourself" case already lives (move_to_exact_match uses exactly the same
    # convention when it finds no dimension match).
    if fulfilled_row_names or remaining_qty_by_row:
        kept = []
        for row in (mp.unavailable_items or []):
            if row.name in fulfilled_row_names:
                continue
            new_qty = remaining_qty_by_row.get(row.name)
            if new_qty is None:
                kept.append(row)
                continue

            old_qty = flt(row.qty)
            ratio = (new_qty / old_qty) if old_qty else 0.0
            mp.append("material_mapping", {
                "item_number":            row.item_number,
                "sales_order":            row.sales_order,
                "item_code":              row.item_code,
                "item_name":              row.item_name,
                "bom_no":                 row.bom_no,
                "drawing":                row.drawing,
                "duno_mark_no":           row.duno_mark_no,
                "customer_drawing_number": row.customer_drawing_number,
                "qty":                    flt(new_qty, 3),
                "uom":                    row.uom,
                "sec_qty":                flt(flt(row.sec_qty) * ratio, 3),
                "sec_uom":                row.sec_uom,
                "parent_item_group":      row.parent_item_group,
                "length":                 row.length,
                "width":                  row.width,
                "thickness":              row.thickness,
                "unit_weight":            row.unit_weight,
                "batch":                  "",
                "batch_mapped":           "Not Mapped",
                "purchase_receipt":       pr_name,
            })
            added_mapping += 1
        mp.unavailable_items = kept

    if added_exact or added_mapping or fulfilled_row_names or remaining_qty_by_row:
        mp.save(ignore_permissions=True)

    return {
        "added_exact": added_exact,
        "added_mapping": added_mapping,
        "fulfilled": len(fulfilled_row_names),
        "partial": len(remaining_qty_by_row),
    }


def _archive_consolidate_items(mp_name, pr_name):
    """Once a receipt has landed, the Consolidate Item table has done its job:
    write it out to a comment on the Material Planning -- every row plus the
    Material Request / Purchase Order / Purchase Receipt it turned into -- and
    empty the table.

    Keeping the purchasing lines around after they have been bought invites
    someone to raise a second Material Request for material that is already in
    the warehouse. The comment preserves exactly what was ordered, so the
    history survives even though the table no longer offers it for purchase.
    """
    mp = frappe.get_doc("Material Planning", mp_name)
    if not mp.consolidate_items:
        return 0

    # Trace this receipt back to the PO and MR it came from, for the record.
    po_names, mr_names = set(), set()
    pr = frappe.get_doc("Purchase Receipt", pr_name)
    for pr_item in pr.items:
        if pr_item.purchase_order:
            po_names.add(pr_item.purchase_order)
        if pr_item.purchase_order_item:
            mri = frappe.db.get_value(
                "Purchase Order Item", pr_item.purchase_order_item, "material_request_item")
            if mri:
                mr = frappe.db.get_value("Material Request Item", mri, "parent")
                if mr:
                    mr_names.add(mr)

    header = "".join("<th style='padding:4px 8px'>%s</th>" % h for h in (
        _("Item"), _("Alternate Item"), _("Required Kg"), _("Length"), _("Width"),
        _("Thickness"), _("Sec Qty"), _("Purchase Kg"), _("Difference Kg")))
    body = ""
    for c in mp.consolidate_items:
        body += "<tr>" + "".join("<td style='padding:4px 8px'>%s</td>" % v for v in (
            frappe.utils.escape_html(c.item_code or ""),
            frappe.utils.escape_html(c.alternate_item or "-"),
            flt(c.required_kg, 3), flt(c.length, 3), flt(c.width, 3),
            flt(c.thickness, 3), flt(c.sec_qty, 3), flt(c.purchase_kg, 3),
            flt(c.difference_kg, 3),
        )) + "</tr>"

    comment = _("<b>Consolidate Items purchased and archived</b><br>") + "{0}: {1}<br>{2}: {3}<br>{4}: {5}<br><br>".format(
        _("Material Request"), ", ".join(sorted(mr_names)) or "-",
        _("Purchase Order"), ", ".join(sorted(po_names)) or "-",
        _("Purchase Receipt"), pr_name,
    ) + (
        "<table border='1' style='border-collapse:collapse;font-size:12px'>"
        "<thead><tr>" + header + "</tr></thead><tbody>" + body + "</tbody></table>"
    )

    archived = len(mp.consolidate_items)
    mp.add_comment("Comment", comment)

    # Clear the table, and release the rows that fed it so a later requirement
    # for the same item consolidates cleanly instead of being treated as already
    # folded in (_consolidate_unavailable_items keys off consolidated_into).
    mp.consolidate_items = []
    for row in (mp.unavailable_items or []):
        row.consolidated_into = ""
    mp.save(ignore_permissions=True)
    return archived


def on_submit_purchase_receipt(doc, method):
    """Auto-allocate received batches back to every Material Planning this PR traces to,
    then refresh any Material Issue Plans that link to those MPs so their raw-material
    snapshot stays current for the transfer popup."""
    from manufyxinvenzaerp.subcontracting_management.doctype.material_issue_plan.material_issue_plan import (
        refresh_mip_raw_materials,
    )

    affected_mps = get_mp_for_pr(doc.name)
    for mp_name in affected_mps:
        try:
            allocate_pr_stock_to_mp(doc.name, mp_name)
            _archive_consolidate_items(mp_name, doc.name)
        except Exception:
            frappe.log_error(
                title=f"Material Planning auto-allocation failed for {doc.name} -> {mp_name}",
                message=frappe.get_traceback(),
            )
            # Report 3 Finding H-01 / Phase 1 HP-04: this failure previously
            # had zero user-visible signal -- the PR submit still succeeds
            # (intentionally, so a downstream planning-sync problem never
            # blocks the stock-affecting document), but the submitting user
            # now sees that the automatic allocation into mp_name did not
            # happen, instead of only discovering it much later when
            # Material Planning still shows the item as unavailable.
            frappe.msgprint(
                _(
                    "Automatic batch allocation into Material Planning {0} failed for this "
                    "receipt. The Purchase Receipt has still been submitted; a Manufacturing "
                    "Manager will need to check the Error Log and, if appropriate, retry the "
                    "allocation manually from the Material Planning document."
                ).format(mp_name),
                indicator="orange",
                title=_("Material Planning Allocation Failed"),
            )

    # Refresh MIP raw-material snapshots for any MIPs linked to affected MPs
    if affected_mps:
        mip_rows = frappe.db.get_all(
            "SCO Drawing Item",
            filters={"material_planning": ("in", affected_mps)},
            fields=["parent"],
            distinct=True,
        )
        for row in mip_rows:
            try:
                refresh_mip_raw_materials(row.parent)
            except Exception:
                frappe.log_error(
                    title=f"MIP raw-material refresh failed for {row.parent} after {doc.name}",
                    message=frappe.get_traceback(),
                )
                # Report 3 Finding H-01 / Phase 1 HP-04: same "surface it, don't
                # just log it" treatment as the allocation failure above.
                frappe.msgprint(
                    _(
                        "Refreshing the raw-material snapshot for Material Issue Plan {0} failed "
                        "after this receipt. Its displayed transferred/allocated weight may be "
                        "stale until it is manually refreshed."
                    ).format(row.parent),
                    indicator="orange",
                    title=_("Material Issue Plan Refresh Failed"),
                )


def _get_batch_from_bundle(sbb_name):
    """Resolve a Serial and Batch Bundle to its batch_no -- Frappe v15 items using
    use_serial_batch_fields can end up with the PR item's own batch_no blank and
    the batch reference living only in its serial_and_batch_bundle instead. Was
    previously called here but never defined (a latent NameError -- this crashed
    get_pr_mp_allocations for any PR whose items went through the bundle path)."""
    if not sbb_name:
        return None
    return frappe.db.get_value("Serial and Batch Entry", {"parent": sbb_name}, "batch_no")


@frappe.whitelist()
def get_pr_mp_allocations(pr_name):
    """Return which Material Planning documents have batches from this PR allocated,
    so the client can show a post-submit popup pointing the user at them.

    Deliberately NOT filtered to is_reserved=1: allocate_pr_stock_to_mp only places
    the received batch into Available Raw Materials / Material Mapping -- it never
    sets is_reserved itself, that's still a separate, manual Reserve step on the
    Material Planning. Filtering by is_reserved here would make this popup fire
    almost never (nothing is reserved yet right after a normal receipt) and, worse,
    would let a stale "already reserved" message go out even though a reserve step
    still needs to happen before the batch can be transferred via a Material Issue
    Plan (client change request: no transfer for anything not purchased AND
    reserved -- see _get_mp_reserved_batches's is_reserved=1 filter, which is what
    actually enforces that)."""
    if not frappe.has_permission("Material Planning", "read"):
        frappe.throw(_("Not permitted to view Material Planning allocations"), frappe.PermissionError)
    pr = frappe.get_doc("Purchase Receipt", pr_name)
    pr_batches = {}
    for item in (pr.items or []):
        batch_no = item.batch_no
        if not batch_no:
            # Try to get batch from serial_and_batch_bundle
            batch_no = _get_batch_from_bundle(item.serial_and_batch_bundle or "")
        if batch_no:
            pr_batches.setdefault(batch_no, []).append({
                "item_code": item.item_code,
                "qty": flt(item.qty, 3),
            })

    if not pr_batches:
        return []

    batch_list = list(pr_batches.keys())
    ph = ", ".join(["%s"] * len(batch_list))

    mm_rows = frappe.db.sql(
        f"SELECT parent AS mp, batch AS batch_no, item_code, is_reserved, "
        f"       SUM(CASE WHEN is_reserved = 1 THEN reserved_qty ELSE qty END) AS qty "
        f"FROM `tabMaterial Planning Material Mapping` "
        f"WHERE batch IN ({ph}) "
        f"GROUP BY parent, batch, item_code, is_reserved",
        batch_list, as_dict=True,
    )

    arm_rows = frappe.db.sql(
        f"SELECT parent AS mp, batch_no, item_code, is_reserved, "
        f"       SUM(CASE WHEN is_reserved = 1 THEN reserved_qty ELSE required_qty END) AS qty "
        f"FROM `tabMaterial Planning Available Raw Material` "
        f"WHERE batch_no IN ({ph}) "
        f"GROUP BY parent, batch_no, item_code, is_reserved",
        batch_list, as_dict=True,
    )

    result = []
    for r in (list(mm_rows) + list(arm_rows)):
        result.append({
            "material_planning": r.mp,
            "batch_no": r.batch_no,
            "item_code": r.item_code,
            "qty": flt(r.qty, 3),
            "is_reserved": bool(r.is_reserved),
        })

    return result
