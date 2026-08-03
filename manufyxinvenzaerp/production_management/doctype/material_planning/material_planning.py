import json
from collections import defaultdict

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import ceil, flt, now, today


class MaterialPlanning(Document):
    def validate(self):
        self._move_skipped_arm_to_mapping()
        self.raw_materials = [r for r in (self.raw_materials or []) if r.item_code]
        self.available_raw_materials = [r for r in (self.available_raw_materials or []) if r.item_code]
        self.material_mapping = [r for r in (self.material_mapping or []) if r.item_code]
        self.unavailable_items = [r for r in (self.unavailable_items or []) if r.item_code]
        self._apply_rwd_group_allocations()
        self._validate_no_cross_table_batch_duplicate()
        if self.material_mapping and self.for_warehouse:
            self._validate_batch_calc_qty()
        if self.unavailable_items:
            self._validate_alternate_item_qty()
        self._consolidate_unavailable_items()
        self._recalculate_consolidate_items()
        self._update_weight_summary()
        _update_bom_item_weights(self)
        self._auto_update_planning_status()
        self._sync_batch_remarks()

    def _sync_batch_remarks(self):
        """Mirror each reserved/assigned row's Batch Remarks (client change
        request Phase 6.3) onto its own batch_remarks field. Synced here on
        every save -- not via fetch_from -- since batches are overwhelmingly
        assigned server-side (dialogs, reassign_batch, move_to_exact_match),
        which never triggers Frappe's client-only fetch_from auto-populate
        (the same gap already found and fixed for a different field in
        Phase 5.6). One bulk query regardless of row count."""
        batch_nos = {r.batch for r in (self.material_mapping or []) if r.batch}
        batch_nos.update(r.batch_no for r in (self.available_raw_materials or []) if r.batch_no)
        if not batch_nos:
            return
        remarks_by_batch = dict(frappe.get_all(
            "Batch", filters={"name": ["in", list(batch_nos)]},
            fields=["name", "custom_batch_remarks"], as_list=True,
        ))
        for row in (self.material_mapping or []):
            if row.batch:
                row.batch_remarks = remarks_by_batch.get(row.batch) or ""
        for row in (self.available_raw_materials or []):
            if row.batch_no:
                row.batch_remarks = remarks_by_batch.get(row.batch_no) or ""

    def _consolidate_unavailable_items(self):
        """Group unavailable_items into the Consolidate Item table by item_code
        (client change request Phase 2.4 — purchasing doesn't care which drawing
        a requirement came from). Idempotent: only rows not yet folded in
        (consolidated_into unset) are processed, so re-saving never double-counts.
        Uses item_code itself as the consolidated_into traceability key rather than
        the Consolidate Item row's own `name` — a freshly-appended child row has no
        name yet at validate() time (Frappe only assigns child names later, during
        the save flow), and item_code is already a unique key per Material Planning
        since consolidation is deduped by item_code."""
        pending = [r for r in (self.unavailable_items or []) if r.item_code and not r.consolidated_into]
        if not pending:
            return

        by_item = {r.item_code: r for r in (self.consolidate_items or [])}

        for row in pending:
            target = by_item.get(row.item_code)
            if not target:
                target = self.append("consolidate_items", {
                    "item_code": row.item_code,
                    "item_name": row.item_name,
                    "parent_item_group": row.parent_item_group,
                    "unit_weight": row.unit_weight,
                    "required_kg": 0,
                })
                by_item[row.item_code] = target
            # Nuts and Bolts reverses qty/sec_qty roles (qty = Nos, sec_qty = Kg) —
            # same reversal _verify_nos_vs_qty already accounts for.
            kg_value = flt(row.sec_qty) if row.parent_item_group == "Nuts and Bolts" else flt(row.qty)
            target.required_kg = flt(target.required_kg) + kg_value
            row.consolidated_into = row.item_code

    def _recalculate_consolidate_items(self):
        """Purchase Kg / Difference Kg on the Consolidate Item table, recomputed from
        whatever Length/Width/Thickness/Sec Qty the user has entered so far — the
        table itself is fully user-editable (client change request Phase 0.5)."""
        from manufyxinvenzaerp.production_management.doctype.material_planning_consolidate_item.material_planning_consolidate_item import (
            recalculate,
        )

        for row in (self.consolidate_items or []):
            recalculate(row)

    def _auto_update_planning_status(self):
        """Auto-set status to Working when any mapping/ARM row exists.
        Never auto-downgrade from Batch Mapping Completed."""
        if self.planning_status == "Batch Mapping Completed":
            return
        has_work = (
            any(r.item_code for r in (self.material_mapping or []))
            or any(r.item_code for r in (self.available_raw_materials or []))
        )
        self.planning_status = "Working" if has_work else "Open"

    def _validate_no_cross_table_batch_duplicate(self):
        """Block saving when the same batch is assigned in both Material Mapping
        and Exact Match (Available Raw Materials) — even if not yet reserved.
        A batch can only serve one table at a time; assigning it in both
        would cause double-counting at transfer time."""
        mm_batches = {
            r.batch: r.idx
            for r in (self.material_mapping or [])
            if r.batch
        }
        if not mm_batches:
            return
        conflicts = []
        for r in (self.available_raw_materials or []):
            if r.batch_no and r.batch_no in mm_batches:
                conflicts.append(
                    _("Batch <b>{0}</b> is assigned in both Material Mapping (Row {1}) "
                      "and Exact Match (Row {2}). Remove it from one table before saving.").format(
                        r.batch_no, mm_batches[r.batch_no], r.idx
                    )
                )
        if conflicts:
            frappe.throw("<br><br>".join(conflicts), title=_("Duplicate Batch Across Tables"))

    def _update_weight_summary(self):
        """Keep the header weight-summary fields in sync with the child tables
        on every server-side save — these 4 fields were previously ONLY ever
        recomputed client-side (material_planning.js _update_weight_summary),
        so any server-side mutation (whitelisted methods, scripts) left them
        stale, and the form showed 'Not Saved' the moment the client
        recalculated a different value on the next load."""
        total_raw = sum(
            flt(r.qty) for r in (self.raw_materials or [])
            if r.parent_item_group in ("Structurals", "Plates")
        )
        total_exact = sum(flt(r.required_qty) for r in (self.available_raw_materials or []))
        expected_mapping = sum(flt(r.qty) for r in (self.material_mapping or []))
        cross_mapped = sum(flt(r.batch_calc_qty) for r in (self.material_mapping or []))

        self.total_weight_plates_structurals = flt(total_raw, 3)
        self.weight_exact_raw_material = flt(total_exact, 3)
        self.expected_weight_material_mapping = flt(expected_mapping, 3)
        self.weight_cross_item_mapped = flt(cross_mapped, 3)

    def _apply_rwd_group_allocations(self):
        """Keep batch_sec_qty/batch_calc_qty correct for every 'Reserve stock
        without dimensions' + 'Allocate based on Sec Nos' row on EVERY save —
        not only when the Reserve button is clicked. Without this, a row can
        sit with reserve_without_dimensions checked but batch_calc_qty stuck
        at 0 (its pre-checkbox value) indefinitely, which silently corrupts
        the Difference in Kg summary and the BOM Items excess weight."""
        if not self.material_mapping:
            return
        allocations = _calc_group_rwd_allocations(self.material_mapping)
        for row in self.material_mapping:
            if row.is_reserved or not row.batch:
                continue
            if row.batch_parent_item_group not in ("Structurals", "Plates") or not row.reserve_without_dimensions:
                continue
            if row.allocate_based_on_sec_qty:
                to_reserve, sec_qty = allocations.get(row.name, (flt(row.qty), 0))
                row.batch_sec_qty = sec_qty
                row.batch_calc_qty = to_reserve
            else:
                row.batch_sec_qty = 0
                row.batch_calc_qty = 0

    def _move_skipped_arm_to_mapping(self):
        """On save, move Available Raw Material rows with skip_auto_suggest_batch
        into Material Mapping so the user can assign a batch manually."""
        keep = []
        for row in (self.available_raw_materials or []):
            if not row.get("skip_auto_suggest_batch") or row.get("is_reserved"):
                keep.append(row)
                continue
            self.append("material_mapping", {
                "item_number":             row.item_number,
                "sales_order":             row.sales_order,
                "item_code":               row.item_code,
                "item_name":               row.item_name,
                "duno_mark_no":            row.duno_mark_no,
                "customer_drawing_number": row.customer_drawing_number,
                "qty":                     row.overall_required_qty or row.required_qty,
                "uom":                     row.uom,
                "sec_qty":                 row.sec_qty,
                "sec_uom":                 row.sec_uom,
                "parent_item_group":       row.parent_item_group,
                "length":                  row.length,
                "width":                   row.width,
                "thickness":               row.thickness,
                "cnc_process":             row.cnc_process,
                "store_location":          row.store_location,
                "batch_mapped":            "Not Mapped",
            })
        self.available_raw_materials = keep

    def _validate_batch_calc_qty(self):
        mp_name = self.name or ""
        batch_allocated = {}
        shortfall_warnings = []

        # Block save if any reserved row has its qty or batch changed
        reserved_row_names = [row.name for row in self.material_mapping if row.is_reserved and row.name]
        if reserved_row_names:
            db_rows = frappe.db.get_all(
                "Material Planning Material Mapping",
                filters={"name": ["in", reserved_row_names]},
                fields=["name", "batch_sec_qty", "qty", "batch"],
            )
            db_map = {r.name: r for r in db_rows}
            reserved_modified = []
            for row in self.material_mapping:
                if not row.is_reserved or not row.name:
                    continue
                db = db_map.get(row.name)
                if not db:
                    continue
                if (
                    flt(row.batch_sec_qty) != flt(db.batch_sec_qty)
                    or flt(row.qty) != flt(db.qty)
                    or (row.batch or "") != (db.get("batch") or "")
                ):
                    reserved_modified.append(
                        _("Row {0} (<b>{1}</b>)").format(row.idx, row.item_code)
                    )
            if reserved_modified:
                frappe.throw(
                    _("Stock is already reserved for the following rows. "
                      "Unreserve the stock to update the Quantity:<br><br>")
                    + "<br>".join(reserved_modified),
                    title=_("Stock Already Reserved — Unable to Save"),
                )

        for row in self.material_mapping:
            if not row.batch:
                continue

            group = row.batch_parent_item_group or ""

            # Only validate stock coverage for Structurals/Plates
            if group not in ("Structurals", "Plates"):
                continue

            batch_stock = _get_batch_total_stock(row.batch, self.for_warehouse)
            reserved_by_others = _get_batch_reserved_by_others(row.batch, mp_name, exclude_table="material_mapping")
            allocated_so_far = batch_allocated.get(row.batch, 0.0)
            available = max(0.0, batch_stock - reserved_by_others - allocated_so_far)

            # Skip stock-coverage check when the batch has no stock in the source
            # warehouse — it was either already transferred out or not yet received.
            # Throwing here would prevent any save after a partial transfer.
            if not batch_stock:
                batch_allocated[row.batch] = allocated_so_far
                continue

            if row.reserve_without_dimensions:
                # Bypass dimension/calc check. When "Allocate based on Sec Nos"
                # is on, batch_calc_qty (freshly recomputed by
                # _apply_rwd_group_allocations just above) already holds the
                # whole-Sec-Qty-rounded Kg that will actually be reserved —
                # validate against that, not the smaller raw Required Qty,
                # or a rounding-driven shortfall would slip past this check.
                if row.allocate_based_on_sec_qty:
                    required_qty = flt(row.batch_calc_qty) or flt(row.qty)
                else:
                    required_qty = flt(row.qty)
                if required_qty > available:
                    difference = flt(required_qty - available, 3)
                    frappe.throw(
                        _("Row {0} — Batch <b>{1}</b><br>"
                          "Total available qty &nbsp;— {2} Kg<br>"
                          "Reserved by others &nbsp;&nbsp;— {3} Kg<br>"
                          "Free stock &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;— {4} Kg<br>"
                          "Required Qty &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;— {5} Kg<br>"
                          "Difference &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;— {6} Kg "
                          "(Required Qty − Free stock)").format(
                            row.idx, row.batch,
                            flt(batch_stock, 3), flt(reserved_by_others, 3),
                            flt(available, 3), flt(required_qty, 3), difference
                        ),
                        title=_("Material Mapping Quantity Difference"),
                    )
                batch_allocated[row.batch] = allocated_so_far + required_qty
                continue

            if not flt(row.batch_sec_qty):
                frappe.throw(
                    _("Row {0}: Enter Sec Qty (NOS) for batch {1} to calculate the required weight "
                      "before saving.").format(row.idx, row.batch)
                )

            batch_calc_qty = flt(row.batch_calc_qty)
            if not batch_calc_qty:
                continue

            required_qty = flt(row.qty)
            if batch_calc_qty < required_qty:
                alternate = row.planned_item or row.batch
                points = [
                    _("<b>{0}</b> needs <b>{1} Kg</b>, but alternate item <b>{2}</b> mapped only for <b>{3} Kg</b>.")
                    .format(row.item_code, flt(required_qty, 3), alternate, flt(batch_calc_qty, 3))
                ]

                if group in ("Structurals", "Plates") and flt(row.sec_qty):
                    usable_nos, usable_kg, shortfall_nos, shortfall_kg, excess_kg = _calc_usable_nos_split(
                        row.qty, row.sec_qty, batch_calc_qty
                    )
                    if usable_nos > 0:
                        points.append(
                            _("Covers <b>{0} Nos</b> ({1} Kg) — the batch will be used for {0} Nos.")
                            .format(usable_nos, usable_kg)
                        )
                        points.append(
                            _("Remaining <b>{0} Kg</b> is excess (added to Difference in Kg).")
                            .format(excess_kg)
                        )
                        points.append(
                            _("Pending <b>{0} Nos</b> ({1} Kg) will move to Unavailable Items / "
                              "Material Request when you click <b>Move to Unavailable Items</b>.")
                            .format(shortfall_nos, shortfall_kg)
                        )
                    else:
                        points.append(_("Covers <b>0 Nos</b> — this mapping is not usable."))
                        points.append(
                            _("The full <b>{0} Nos</b> ({1} Kg) needs to be purchased; "
                              "click <b>Move to Unavailable Items</b> to send it to Material Request.")
                            .format(int(flt(row.sec_qty)), flt(required_qty, 3))
                        )

                message = (
                    _("Row {0}:").format(row.idx)
                    + "<ul style='margin:4px 0 0 -18px;'>"
                    + "".join("<li>{0}</li>".format(p) for p in points)
                    + "</ul>"
                )
                shortfall_warnings.append(message)

            if batch_calc_qty > available:
                difference = flt(batch_calc_qty - available, 3)
                frappe.throw(
                    _("Row {0} — Batch <b>{1}</b><br>"
                      "Total available qty &nbsp;— {2} Kg<br>"
                      "Reserved by others &nbsp;&nbsp;— {3} Kg<br>"
                      "Free stock &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;— {4} Kg<br>"
                      "Calculated Qty &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;— {5} Kg<br>"
                      "Difference &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;— {6} Kg "
                      "(Calculated Qty − Free stock)").format(
                        row.idx, row.batch,
                        flt(batch_stock, 3), flt(reserved_by_others, 3),
                        flt(available, 3), flt(batch_calc_qty, 3), difference
                    ),
                    title=_("Material Mapping Quantity Difference"),
                )
            batch_allocated[row.batch] = allocated_so_far + batch_calc_qty

        if shortfall_warnings:
            frappe.msgprint(
                "<br>".join(shortfall_warnings),
                title=_("Batch Qty Shortfall"),
                indicator="orange",
            )

    def _validate_alternate_item_qty(self):
        """Unavailable Items row with an Alternate Item entered: the alternate's
        computed Kg (alternate_quantity, from its dimensions/Sec Qty) must cover
        the original Required Qty (qty), or the row won't have enough material
        to allocate/reserve once it's picked up in Material Mapping."""
        warnings = []
        for row in (self.unavailable_items or []):
            if not row.alternate_item:
                continue
            required_qty = flt(row.qty)
            alternate_qty = flt(row.alternate_quantity)
            if alternate_qty < required_qty:
                shortfall = flt(required_qty - alternate_qty, 3)
                points = [
                    _("<b>{0}</b> needs <b>{1} Kg</b>, but alternate item <b>{2}</b> is mapped for only <b>{3} Kg</b>.")
                    .format(row.item_code, flt(required_qty, 3), row.alternate_item, flt(alternate_qty, 3)),
                    _("Shortfall of <b>{0} Kg</b> — plan/purchase material accordingly, otherwise this "
                      "will not be enough to allocate and reserve during Material Mapping.")
                    .format(shortfall),
                ]
                warnings.append(
                    _("Row {0}:").format(row.idx)
                    + "<ul style='margin:4px 0 0 -18px;'>"
                    + "".join("<li>{0}</li>".format(p) for p in points)
                    + "</ul>"
                )

        if warnings:
            frappe.msgprint(
                "<br>".join(warnings),
                title=_("Alternate Item Quantity Shortfall"),
                indicator="orange",
            )


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def search_bom(doctype, txt, searchfield, start, page_len, filters):
    """Custom BOM search: matches name, item, item_name, or DUNO/Mark No (substring)."""
    like_txt = f"%{txt}%"
    values = {"txt": like_txt, "page_len": int(page_len), "start": int(start)}

    return frappe.db.sql(
        """
        SELECT b.name, b.item, b.item_name, b.custom_duno_mark_no
        FROM `tabBOM` b
        WHERE b.docstatus < 2
          AND b.routing = 'Standard Manufacturing Routing'
          AND (
              b.name LIKE %(txt)s
              OR b.item LIKE %(txt)s
              OR b.item_name LIKE %(txt)s
              OR CAST(b.custom_duno_mark_no AS CHAR) LIKE %(txt)s
          )
        ORDER BY b.name
        LIMIT %(page_len)s OFFSET %(start)s
        """,
        values,
    )


@frappe.whitelist()
def get_bom_info(bom_no):
    """Return Drawing-derived details for a BOM row (called on bom_no change in JS)."""
    bom = frappe.db.get_value(
        "BOM", bom_no,
        ["item", "item_name", "quantity", "custom_drawing", "custom_duno_mark_no",
         "custom_customer_drawing_number"],
        as_dict=True,
    )
    if not bom:
        return {}

    drawing_name = bom.custom_drawing
    duno_mark_no = bom.custom_duno_mark_no or 0
    customer_drawing_number = bom.custom_customer_drawing_number or ""

    if not drawing_name:
        stock_uom = frappe.db.get_value("Item", bom.item, "stock_uom") or "" if bom.item else ""
        return {
            "item_code": bom.item,
            "item_name": bom.item_name,
            "duno_mark_no": duno_mark_no,
            "customer_drawing_number": customer_drawing_number,
            "qty_to_manufacture": bom.quantity or 1,
            "uom": stock_uom,
        }

    d = frappe.db.get_value(
        "Drawing",
        drawing_name,
        ["fg_item_code", "fg_item_name", "duno_mark_no", "sales_order",
         "no_of_qty_to_manufacture", "customer", "customer_drawing_number"],
        as_dict=True,
    )
    if not d:
        return {}

    stock_uom = frappe.db.get_value("Item", d.fg_item_code, "stock_uom") or "" if d.fg_item_code else ""

    return {
        "drawing": drawing_name,
        "item_code": d.fg_item_code,
        "item_name": d.fg_item_name,
        "duno_mark_no": duno_mark_no or d.duno_mark_no or 0,
        "customer_drawing_number": customer_drawing_number or d.customer_drawing_number or "",
        "sales_order": d.sales_order,
        "customer": d.customer,
        "qty_to_manufacture": d.no_of_qty_to_manufacture or bom.quantity or 1,
        "uom": stock_uom,
    }


@frappe.whitelist()
def get_so_drawings_for_bom_picker(so_name, mp_name=None):
    """
    Return all drawings from a Sales Order that have a submitted BOM.
    Each result includes `already_used_in` — the name of another Material Planning
    document that already has this BOM in its bom_items table (empty if free).
    """
    so = frappe.get_doc("Sales Order", so_name)
    results = []

    for row in (so.custom_duno_items or []):
        if not row.drawing:
            continue

        bom_name = frappe.db.get_value(
            "BOM", {"custom_drawing": row.drawing, "docstatus": 1}, "name"
        )
        if not bom_name:
            continue

        # Reuse get_bom_info to build the same row structure as a manual selection
        info = get_bom_info(bom_name)
        if not info:
            continue

        info["bom_no"] = bom_name
        # Prefer duno_mark_no and customer_drawing_number from the DUNO Item row
        if not info.get("duno_mark_no"):
            info["duno_mark_no"] = row.duno_mark_no or ""
        if not info.get("customer_drawing_number"):
            info["customer_drawing_number"] = row.drawing_number or ""
        info["already_used_in"] = ""

        results.append(info)

    # Check which BOMs are already mapped in another Material Planning document
    bom_names = [r["bom_no"] for r in results]
    if bom_names:
        exclude = mp_name or "__none__"
        placeholders = ", ".join(["%s"] * len(bom_names))
        used_rows = frappe.db.sql(
            f"""
            SELECT bom_no, parent
            FROM `tabMaterial Planning BOM Item`
            WHERE bom_no IN ({placeholders})
              AND parent != %s
            ORDER BY parent
            """,
            tuple(bom_names) + (exclude,),
            as_dict=True,
        )
        # Keep only the first MP name per BOM (in case it appears in multiple)
        bom_mp_map = {}
        for u in used_rows:
            if u.bom_no not in bom_mp_map:
                bom_mp_map[u.bom_no] = u.parent

        for r in results:
            r["already_used_in"] = bom_mp_map.get(r["bom_no"], "")

    return results


def _nos_from_weight(qty, denom, tolerance=0.01):
    """Convert a weight (Kg) into a Nos count for a given per-Nos weight.

    `qty` reaching here has usually already been rounded to 3 decimals, so a
    plain ceil(qty / denom) overshoots by a whole Nos whenever that rounding
    pushes the ratio a hair above an exact integer (e.g. 4.0000077 instead of
    4.0). Round to the nearest Nos when within `tolerance`, and only ceil for
    a genuine partial-Nos shortfall/overage.
    """
    if not denom:
        return 0.0
    raw = qty / denom
    nearest = round(raw)
    if abs(raw - nearest) <= tolerance:
        return float(nearest)
    return float(ceil(raw))


def _reconcile_sec_qty_with_sales_order(rows):
    """Sec Qty is reverse-derived from an already-rounded Kg weight (see
    _nos_from_weight above), which stays inherently lossy even with the
    tolerance fix. Whenever a row traces back to a Sales Order drawing line,
    that line's Total Sec Qty is the actual source of truth for how many Nos
    are required — reconcile against it so this class of rounding drift can
    never silently diverge from what the Sales Order actually asked for.
    """
    for row in rows:
        sales_order = row.get("sales_order")
        if not sales_order:
            continue
        so_sec_qty = frappe.db.get_value(
            "Sales Order Drawing Raw Material",
            {
                "parent": sales_order,
                "material_code": row.get("item_code"),
                "item_no": row.get("item_number"),
                "customer_drawing_number": row.get("customer_drawing_number"),
            },
            "total_sec_qty",
        )
        if so_sec_qty is not None and flt(so_sec_qty) and flt(so_sec_qty) != flt(row.get("sec_qty")):
            row["sec_qty"] = flt(so_sec_qty)


@frappe.whitelist()
def get_raw_materials(doc):
    """
    Explode each BOM in bom_items and return a flat list of raw material rows
    for the raw_materials child table. Each row carries its source bom_no and
    duno_mark_no so the user can trace back to the originating BOM/Drawing.
    Rows are NOT aggregated across BOMs.
    """
    from manufyxinvenzaerp.production_plan_management.production_plan import get_exploded_items

    if isinstance(doc, str):
        doc = frappe._dict(json.loads(doc))

    company = doc.get("company")
    warehouse = doc.get("for_warehouse") or ""
    location = doc.get("store_location") or ""
    if not company:
        frappe.throw(_("Company is required before fetching raw materials."))

    rows = []

    # Collect all exploded items across every BOM first, so the per-item
    # custom_secondary_uom lookup below can be a single batched query instead
    # of one frappe.db.get_value call per row (Report 4 Finding D-03).
    exploded_by_bom = []
    all_item_codes = set()
    for bom_row in doc.get("bom_items") or []:
        bom_no = bom_row.get("bom_no")
        planned_qty = flt(bom_row.get("qty_to_manufacture")) or 1
        duno_mark_no = bom_row.get("duno_mark_no")
        customer_drawing_number = bom_row.get("customer_drawing_number") or ""
        sales_order = bom_row.get("sales_order") or ""
        drawing = bom_row.get("drawing") or ""

        if not bom_no:
            continue

        item_details = get_exploded_items({}, company, bom_no, False, planned_qty=planned_qty)
        exploded_by_bom.append((bom_no, duno_mark_no, customer_drawing_number, sales_order, drawing, item_details))
        for detail in item_details.values():
            if detail.get("item_code"):
                all_item_codes.add(detail.get("item_code"))

    sec_uom_by_item = {}
    if all_item_codes:
        for rec in frappe.get_all(
            "Item", filters={"name": ["in", list(all_item_codes)]}, fields=["name", "custom_secondary_uom"]
        ):
            sec_uom_by_item[rec.name] = rec.custom_secondary_uom or ""

    for bom_no, duno_mark_no, customer_drawing_number, sales_order, drawing, item_details in exploded_by_bom:
        for _dim_key, detail in item_details.items():
            group = detail.get("custom_parent_item_group") or ""
            length = flt(detail.get("custom_length"))
            width = flt(detail.get("custom_width"))
            thickness = flt(detail.get("custom_thickness"))
            unit_weight = flt(detail.get("custom_unit_weight"))
            qty = flt(detail.get("qty"))

            sec_qty = 0.0
            if group == "Structurals" and length and unit_weight:
                denom = (length / 1000) * unit_weight
                if denom:
                    sec_qty = _nos_from_weight(qty, denom)
            elif group == "Plates" and length and width and thickness and unit_weight:
                denom = (length / 1000) * (width / 1000) * thickness * unit_weight
                if denom:
                    sec_qty = _nos_from_weight(qty, denom)
            elif group == "Nuts and Bolts" and unit_weight:
                sec_qty = flt(qty * unit_weight, 3)

            sec_uom = sec_uom_by_item.get(detail.get("item_code"), "")

            rows.append({
                "item_number": detail.get("custom_item_number") or "",
                "sales_order": sales_order,
                "item_code": detail.get("item_code"),
                "item_name": detail.get("item_name"),
                "bom_no": bom_no,
                "drawing": drawing,
                "duno_mark_no": duno_mark_no,
                "customer_drawing_number": customer_drawing_number,
                "parent_item_group": group,
                "material_spec": "",
                "unit_weight": unit_weight,
                "thickness": thickness,
                "length": length,
                "width": width,
                "sec_qty": sec_qty,
                "sec_uom": sec_uom,
                "qty": qty,
                "uom": detail.get("stock_uom") or "",
                "available_qty": 0.0,
                "shortage_qty": qty,
                "warehouse": warehouse,
                "store_location": location,
            })

    _reconcile_sec_qty_with_sales_order(rows)
    return rows



@frappe.whitelist()
def check_stock_availability(doc):
    """
    For each row in raw_materials classify into buckets:
      Batch items:
        - available_raw_materials : exact dimension + batch match found
        - material_mapping        : no dimension-matching batch stock remaining
      Non-batch items:
        - available_raw_materials : plain stock qty >= required
        - unavailable_items       : plain stock qty < required (needs purchase)
    Also updates raw_materials rows with available_qty and shortage_qty.
    """
    from manufyxinvenzaerp.production_plan_management.production_plan import (
        get_sbb_batches_bulk,
        match_batches_by_dimension,
    )

    if isinstance(doc, str):
        doc = frappe._dict(json.loads(doc))

    warehouse = doc.get("for_warehouse")
    if not warehouse:
        frappe.throw(_("Set 'Raw Materials Warehouse' before checking stock availability."))

    location = doc.get("store_location") or None

    # Capture existing reserved rows so they survive a re-check.
    reserved_by_key = {}
    for r in doc.get("material_mapping") or []:
        if r.get("is_reserved"):
            key = (r.get("item_code"), r.get("bom_no") or "")
            reserved_by_key[key] = r

    updated_raw_materials = []
    available_raw_materials = []
    material_mapping = []
    unavailable_items = []

    # Track remaining qty per batch so the same batch is not double-counted.
    batch_remaining = {}
    # Per-batch totals (Kg and Nos) for proportional Sec Qty allocation.
    batch_total_kg = {}
    batch_total_sec = {}
    mp_name = doc.get("name") or ""
    shortfall_count = 0

    # Pre-fetch has_batch_no for all items in one query.
    all_item_codes = list({r.get("item_code") for r in doc.get("raw_materials") or [] if r.get("item_code")})
    item_batch_flag = {}
    if all_item_codes:
        for rec in frappe.get_all("Item", filters={"name": ["in", all_item_codes]}, fields=["name", "has_batch_no"]):
            item_batch_flag[rec.name] = rec.has_batch_no

    # Batch every stock/reservation lookup the per-row loop below used to make
    # individually (Report 4 Finding D-02): the SBB batch fetch, the
    # cross-MP-reservation lookup for every batch that fetch could surface,
    # and both non-batch stock/reservation lookups -- each collapsed from one
    # query per row/batch to one query (or a handful) for the whole document.
    # The loop's own row-by-row consumption logic below is unchanged; only the
    # data it reads is now looked up from these pre-fetched dicts instead of
    # triggering a fresh query.
    batch_item_codes = [ic for ic in all_item_codes if item_batch_flag.get(ic)]
    non_batch_item_codes = [ic for ic in all_item_codes if not item_batch_flag.get(ic)]

    sbb_batches_by_item = get_sbb_batches_bulk(batch_item_codes, warehouse, location=location)
    all_possible_batch_nos = {
        b["batch_no"] for batches in sbb_batches_by_item.values() for b in batches
    }
    reserved_by_others_map = _get_batch_reserved_by_others_bulk(
        all_possible_batch_nos, mp_name, exclude_table="available_raw_materials"
    )
    non_batch_stock_map = _get_non_batch_stock_bulk(non_batch_item_codes, warehouse)
    non_batch_reserved_map = _get_non_batch_reserved_by_others_bulk(non_batch_item_codes, warehouse, mp_name)

    for row in doc.get("raw_materials") or []:
        item_code = row.get("item_code")
        required_qty = flt(row.get("qty"))
        has_batch = item_batch_flag.get(item_code, 0)

        base_row = {
            "item_number": row.get("item_number") or "",
            "sales_order": row.get("sales_order") or "",
            "item_code": item_code,
            "item_name": row.get("item_name"),
            "bom_no": row.get("bom_no"),
            "drawing": row.get("drawing") or "",
            "duno_mark_no": row.get("duno_mark_no"),
            "customer_drawing_number": row.get("customer_drawing_number") or "",
            "qty": required_qty,
            "uom": row.get("uom"),
            "sec_qty": flt(row.get("sec_qty")),
            "sec_uom": row.get("sec_uom"),
            "parent_item_group": row.get("parent_item_group"),
            "length": flt(row.get("length")),
            "width": flt(row.get("width")),
            "thickness": flt(row.get("thickness")),
            "unit_weight": flt(row.get("unit_weight")),
            "alternate_item": row.get("alternate_item") or "",
            "store_location": location or "",
        }

        # Derive sec_qty from dimensions if it's 0 but all required dimensions are present.
        # This handles cases where sec_qty was not computed during get_raw_materials (e.g.,
        # a BOM item was missing a dimension at that time but has since been corrected).
        if not base_row["sec_qty"]:
            _grp = base_row.get("parent_item_group", "")
            _len = base_row.get("length", 0)
            _wid = base_row.get("width", 0)
            _thk = base_row.get("thickness", 0)
            _uwt = base_row.get("unit_weight", 0)
            _qty = base_row.get("qty", 0)
            if _grp == "Plates" and _len and _wid and _thk and _uwt and _qty:
                _denom = (_len / 1000) * (_wid / 1000) * _thk * _uwt
                if _denom:
                    base_row["sec_qty"] = _nos_from_weight(_qty, _denom)
            elif _grp == "Structurals" and _len and _uwt and _qty:
                _denom = (_len / 1000) * _uwt
                if _denom:
                    base_row["sec_qty"] = _nos_from_weight(_qty, _denom)

        if has_batch:
            # ── Batch item: match by exact dimensions via SBB ──────────────
            dimensions = {
                "custom_length": flt(row.get("length")),
                "custom_thickness": flt(row.get("thickness")),
                "custom_width": flt(row.get("width")),
            }

            _, raw_matched_batches = match_batches_by_dimension(
                sbb_batches_by_item.get(item_code, []), dimensions
            )

            # Capture each batch's TOTAL stock Kg and TOTAL Nos before any allocation —
            # needed to split Sec Qty (Nos) proportionally to the Kg each row reserves.
            for b in raw_matched_batches:
                batch_total_kg.setdefault(b["batch_no"], flt(b["qty"]))
                batch_total_sec.setdefault(b["batch_no"], flt(b.get("custom_sec_qty")))
                if b["batch_no"] not in batch_remaining:
                    reserved_by_others = reserved_by_others_map.get(b["batch_no"], 0)
                    net_qty = max(0.0, flt(b["qty"]) - reserved_by_others)
                    batch_remaining[b["batch_no"]] = net_qty

            # Sort largest batch first to minimise splits — one batch covers most items.
            matched_batches = sorted(
                [
                    {**b, "qty": batch_remaining[b["batch_no"]]}
                    for b in raw_matched_batches
                    if batch_remaining.get(b["batch_no"], 0) > 0
                ],
                key=lambda b: b["qty"],
                reverse=True,
            )

            available_qty = sum(flt(b["qty"]) for b in matched_batches)
            shortage = max(0.0, required_qty - available_qty)

            updated_row = dict(row)
            updated_row["available_qty"] = available_qty
            updated_row["shortage_qty"] = shortage
            updated_row["store_location"] = location or ""
            updated_raw_materials.append(updated_row)

            if matched_batches:
                to_consume = required_qty
                consumed_batches = []  # list of (batch, consumed_qty)
                for b in matched_batches:
                    if to_consume <= 0:
                        break
                    consumed = min(batch_remaining[b["batch_no"]], to_consume)
                    batch_remaining[b["batch_no"]] -= consumed
                    to_consume -= consumed
                    consumed_batches.append((b, consumed))

                # One ARM row per consumed batch. required_qty holds the portion
                # this batch covers so reservation never double-counts across rows.
                for b, consumed_qty in consumed_batches:
                    bn = b["batch_no"]
                    row_sec = _alloc_sec_qty(
                        consumed_qty, batch_total_kg.get(bn), batch_total_sec.get(bn)
                    )
                    available_raw_materials.append({
                        "item_number": row.get("item_number") or "",
                        "sales_order": row.get("sales_order") or "",
                        "item_code": item_code,
                        "item_name": row.get("item_name"),
                        "duno_mark_no": row.get("duno_mark_no") or "",
                        "customer_drawing_number": row.get("customer_drawing_number") or "",
                        "batch_no": bn,
                        "overall_required_qty": flt(required_qty, 3),
                        "required_qty": flt(consumed_qty, 3),
                        "available_qty": flt(b["qty"]),
                        "sec_qty": row_sec,
                        "sec_uom": b.get("custom_sec_uom") or row.get("sec_uom"),
                        "uom": row.get("uom"),
                        "length": flt(row.get("length")),
                        "thickness": flt(row.get("thickness")),
                        "width": flt(row.get("width")),
                        "warehouse": warehouse,
                        "parent_item_group": row.get("parent_item_group"),
                        "store_location": location or "",
                    })

                # Partial stock — add a shortfall row to Material Mapping so the gap
                # is visible immediately (NOS/Kg check) without waiting for reservation.
                if flt(shortage, 3) > 0:
                    # Use proportional Nos for the available Kg (same as ARM rows use
                    # _alloc_sec_qty), not the raw batch total Nos — otherwise a batch
                    # that covers all required Nos by count but not by Kg produces
                    # available_sec_qty >= required_sec_qty and shortfall_nos = 0,
                    # hiding the Nos gap in the mapping row.
                    available_sec_qty = sum(
                        _alloc_sec_qty(
                            b["qty"],
                            batch_total_kg.get(b["batch_no"]),
                            batch_total_sec.get(b["batch_no"]),
                        )
                        for b in matched_batches
                    )
                    required_sec_qty = flt(row.get("sec_qty"))
                    if not available_sec_qty and required_sec_qty and required_qty:
                        available_sec_qty = flt(available_qty / (required_qty / required_sec_qty), 0)
                    shortfall_nos = max(0.0, required_sec_qty - available_sec_qty)
                    shortfall_row = dict(base_row)
                    shortfall_row["qty"] = flt(shortage, 3)
                    shortfall_row["sec_qty"] = flt(shortfall_nos, 3)
                    shortfall_row["batch_mapped"] = "Not Mapped"
                    material_mapping.append(shortfall_row)
                    shortfall_count += 1

            else:
                # No dimension-matching batch stock — send to Material Mapping.
                existing = reserved_by_key.get((item_code, row.get("bom_no") or ""))
                if existing:
                    base_row.update({
                        "batch": existing.get("batch"),
                        "planned_item": existing.get("planned_item"),
                        "is_reserved": existing.get("is_reserved"),
                        "reserved_qty": existing.get("reserved_qty"),
                        "shortfall_qty": existing.get("shortfall_qty"),
                        "reserved_on": existing.get("reserved_on"),
                        "batch_mapped": "Mapped" if existing.get("batch") else "Not Mapped",
                        "batch_sec_qty": existing.get("batch_sec_qty"),
                        "batch_calc_qty": existing.get("batch_calc_qty"),
                        "batch_length": existing.get("batch_length"),
                        "batch_width": existing.get("batch_width"),
                        "batch_thickness": existing.get("batch_thickness"),
                        "batch_unit_weight": existing.get("batch_unit_weight"),
                        "batch_parent_item_group": existing.get("batch_parent_item_group"),
                    })
                else:
                    base_row["batch_mapped"] = "Not Mapped"
                material_mapping.append(base_row)

        else:
            # ── Non-batch item: net of cross-MP reservations ─────────────────
            total_stock = non_batch_stock_map.get(item_code, 0)
            reserved_by_others = non_batch_reserved_map.get(item_code, 0)
            available_qty = max(0.0, total_stock - reserved_by_others)
            shortage = max(0.0, required_qty - available_qty)

            updated_row = dict(row)
            updated_row["available_qty"] = min(available_qty, required_qty)
            updated_row["shortage_qty"] = shortage
            updated_row["store_location"] = location or ""
            updated_raw_materials.append(updated_row)

            if available_qty >= required_qty:
                available_raw_materials.append({
                    "item_number": row.get("item_number") or "",
                    "sales_order": row.get("sales_order") or "",
                    "item_code": item_code,
                    "item_name": row.get("item_name"),
                    "duno_mark_no": row.get("duno_mark_no") or "",
                    "customer_drawing_number": row.get("customer_drawing_number") or "",
                    "batch_no": "",
                    "overall_required_qty": flt(required_qty, 3),
                    "required_qty": required_qty,
                    "available_qty": available_qty,
                    "sec_qty": flt(row.get("sec_qty")),
                    "sec_uom": row.get("sec_uom") or "",
                    "uom": row.get("uom"),
                    "length": 0.0,
                    "thickness": 0.0,
                    "width": 0.0,
                    "warehouse": warehouse,
                    "parent_item_group": row.get("parent_item_group"),
                    "store_location": location or "",
                })
            else:
                unavailable_items.append(base_row)

    return {
        "raw_materials": updated_raw_materials,
        "available_raw_materials": available_raw_materials,
        "material_mapping": material_mapping,
        "unavailable_items": unavailable_items,
        "shortfall_mapping_count": shortfall_count,
    }


def _alloc_sec_qty(consumed_kg, batch_total_kg, batch_total_sec):
    """Allocate Sec Qty (Nos) proportionally to the Kg actually reserved from a batch.

    A batch holds batch_total_sec pieces across batch_total_kg. When a row reserves
    only `consumed_kg`, it must get the matching fraction of the pieces — copying the
    full batch sec to every consuming row over-counts the Nos. Because the Kg split
    already never exceeds the batch, the proportional Nos also sum exactly to the
    batch's total and never double-count across rows or MPs.
    """
    if flt(batch_total_kg) <= 0:
        return 0.0
    return flt(flt(batch_total_sec) * (flt(consumed_kg) / flt(batch_total_kg)), 3)


def _get_non_batch_stock(item_code, warehouse):
    """Return current stock balance for a non-batch item in a warehouse via SLE."""
    result = frappe.db.sql(
        """
        SELECT COALESCE(SUM(actual_qty), 0) AS qty
        FROM `tabStock Ledger Entry`
        WHERE item_code = %s AND warehouse = %s
          AND is_cancelled = 0 AND docstatus < 2
        """,
        (item_code, warehouse),
        as_dict=True,
    )
    return flt(result[0].qty if result else 0)


def _get_non_batch_stock_bulk(item_codes, warehouse):
    """Batched variant of _get_non_batch_stock -- one query for a set of
    items instead of one query per item (Report 4 Finding D-02). Returns
    {item_code: qty}; an item with no result is simply absent (callers
    should use .get(item_code, 0), same net effect as the single-item
    function returning 0)."""
    item_codes = list({c for c in item_codes if c})
    if not item_codes:
        return {}
    ph = ", ".join(["%s"] * len(item_codes))
    rows = frappe.db.sql(
        f"""
        SELECT item_code, COALESCE(SUM(actual_qty), 0) AS qty
        FROM `tabStock Ledger Entry`
        WHERE item_code IN ({ph}) AND warehouse = %s
          AND is_cancelled = 0 AND docstatus < 2
        GROUP BY item_code
        """,
        [*item_codes, warehouse],
        as_dict=True,
    )
    return {r.item_code: flt(r.qty) for r in rows}


@frappe.whitelist()
def move_to_exact_match(doc, item_codes):
    """
    For each unavailable item, re-check stock availability:
      Batch items:
        - exact dimension batch found with free stock → matched (available_raw_materials)
        - no matching free batch                       → failed  (material_mapping, assign manually)
      Non-batch items:
        - plain stock >= required                      → matched (available_raw_materials, no batch)
        - plain stock < required                       → still_unavailable (stays in unavailable_items)
    """
    from manufyxinvenzaerp.production_plan_management.production_plan import get_sbb_available_qty

    if isinstance(doc, str):
        doc = frappe._dict(json.loads(doc))
    if isinstance(item_codes, str):
        item_codes = json.loads(item_codes)

    warehouse = doc.get("for_warehouse")
    if not warehouse:
        frappe.throw(_("Set 'Raw Materials Warehouse' before checking stock."))

    location = doc.get("store_location") or None
    mp_name = doc.get("name") or ""
    item_set = set(item_codes)
    matched = []
    failed = []
    still_unavailable = []
    batch_remaining = {}
    # Per-batch totals (Kg and Nos) for proportional Sec Qty allocation.
    batch_total_kg = {}
    batch_total_sec = {}

    # Pre-deduct stock already allocated to existing available_raw_materials rows
    # in this MP so the same batch is not double-counted across operations.
    pre_allocated = {}
    for r in doc.get("available_raw_materials") or []:
        bn = r.get("batch_no") or ""
        if bn:
            pre_allocated[bn] = pre_allocated.get(bn, 0.0) + flt(r.get("required_qty"))

    # Pre-fetch has_batch_no for all items in one query
    item_batch_flag = {}
    if item_set:
        for rec in frappe.get_all("Item", filters={"name": ["in", list(item_set)]}, fields=["name", "has_batch_no"]):
            item_batch_flag[rec.name] = rec.has_batch_no

    for row in doc.get("unavailable_items") or []:
        item_code = row.get("item_code")
        if item_code not in item_set:
            continue

        required_qty = flt(row.get("qty"))
        has_batch = item_batch_flag.get(item_code, 0)

        if has_batch:
            # ── Batch item: match by exact dimensions via SBB ──────────────
            dimensions = {
                "custom_length": flt(row.get("length")),
                "custom_thickness": flt(row.get("thickness")),
                "custom_width": flt(row.get("width")),
            }
            _available_qty, raw_batches = get_sbb_available_qty(
                item_code, warehouse, dimensions, location=location
            )

            for b in raw_batches:
                batch_total_kg.setdefault(b["batch_no"], flt(b["qty"]))
                batch_total_sec.setdefault(b["batch_no"], flt(b.get("custom_sec_qty")))
                if b["batch_no"] not in batch_remaining:
                    reserved_by_others = _get_batch_reserved_by_others(b["batch_no"], mp_name, exclude_table="available_raw_materials")
                    already_allocated  = pre_allocated.get(b["batch_no"], 0.0)
                    batch_remaining[b["batch_no"]] = max(
                        0.0, flt(b["qty"]) - reserved_by_others - already_allocated
                    )

            # Sort largest batch first so one batch covers the requirement in most cases.
            free_batches = sorted(
                [
                    {**b, "qty": batch_remaining[b["batch_no"]]}
                    for b in raw_batches
                    if batch_remaining.get(b["batch_no"], 0) > 0
                ],
                key=lambda b: b["qty"],
                reverse=True,
            )

            if free_batches:
                to_consume = required_qty
                consumed_batches = []  # list of (batch, consumed_qty)
                for b in free_batches:
                    if to_consume <= 0:
                        break
                    consumed = min(batch_remaining[b["batch_no"]], to_consume)
                    batch_remaining[b["batch_no"]] -= consumed
                    to_consume -= consumed
                    consumed_batches.append((b, consumed))

                # One matched row per consumed batch; required_qty = portion this
                # batch covers so reservation never double-counts across rows.
                for b, consumed_qty in consumed_batches:
                    bn = b["batch_no"]
                    row_sec = _alloc_sec_qty(
                        consumed_qty, batch_total_kg.get(bn), batch_total_sec.get(bn)
                    )
                    matched.append({
                        "item_number": row.get("item_number") or "",
                        "sales_order": row.get("sales_order") or "",
                        "item_code": item_code,
                        "item_name": row.get("item_name"),
                        "duno_mark_no": row.get("duno_mark_no") or "",
                        "customer_drawing_number": row.get("customer_drawing_number") or "",
                        "batch_no": bn,
                        "overall_required_qty": flt(required_qty, 3),
                        "required_qty": flt(consumed_qty, 3),
                        "available_qty": flt(b["qty"]),
                        "sec_qty": row_sec,
                        "sec_uom": b.get("custom_sec_uom") or row.get("sec_uom"),
                        "uom": row.get("uom"),
                        "length": flt(row.get("length")),
                        "thickness": flt(row.get("thickness")),
                        "width": flt(row.get("width")),
                        "warehouse": warehouse,
                        "parent_item_group": row.get("parent_item_group"),
                        "store_location": location or "",
                    })
            else:
                failed.append(item_code)

        else:
            # ── Non-batch item: check plain stock ──────────────────────────
            total_stock = _get_non_batch_stock(item_code, warehouse)
            reserved_by_others = _get_non_batch_reserved_by_others(item_code, warehouse, mp_name)
            available_qty = max(0.0, total_stock - reserved_by_others)

            if available_qty >= required_qty:
                matched.append({
                    "item_number": row.get("item_number") or "",
                    "sales_order": row.get("sales_order") or "",
                    "item_code": item_code,
                    "item_name": row.get("item_name"),
                    "duno_mark_no": row.get("duno_mark_no") or "",
                    "customer_drawing_number": row.get("customer_drawing_number") or "",
                    "batch_no": "",
                    "overall_required_qty": flt(required_qty, 3),
                    "required_qty": required_qty,
                    "available_qty": available_qty,
                    "sec_qty": flt(row.get("sec_qty")),
                    "sec_uom": row.get("sec_uom") or "",
                    "uom": row.get("uom"),
                    "length": 0.0,
                    "thickness": 0.0,
                    "width": 0.0,
                    "warehouse": warehouse,
                    "parent_item_group": row.get("parent_item_group"),
                    "store_location": location or "",
                })
            else:
                still_unavailable.append(item_code)

    return {"matched": matched, "failed": failed, "still_unavailable": still_unavailable}


@frappe.whitelist()
def finalize_mapping(doc):
    """
    Scan the material_mapping table:
      - Rows WITHOUT a batch                              → move to unavailable_items
      - Rows WITH a batch, fully covering the requirement  → stay in material_mapping
      - Rows WITH a batch that under-covers (Structurals/
        Plates only — a partial piece isn't usable) and
        are NOT already reserved                           → SPLIT:
          - shrink the kept row's qty/sec_qty down to just what the batch
            can actually fulfil (whole Nos only), so the existing
            batch_calc_qty − qty diff formula correctly shows the leftover
            as excess instead of understating a phantom shortfall
          - the remaining shortfall, for the ORIGINAL item (not the
            alternate), moves to unavailable_items so it flows into the
            existing Material Request / Purchase pipeline
          - if the batch can't even cover ONE whole Nos, the mapping is
            unusable — drop the batch entirely and move the FULL original
            requirement to unavailable_items
      - Rows WITH a batch already reserved                 → left untouched
        (splitting a committed reservation needs an explicit unreserve
        first, not a silent qty rewrite)
    Returns updated material_mapping and unavailable_items lists, plus a
    split_details list describing what happened to any split/dropped row.
    """
    if not frappe.has_permission("Material Planning", "write"):
        frappe.throw(_("Not permitted to finalize Material Planning mapping"), frappe.PermissionError)

    if isinstance(doc, str):
        doc = frappe._dict(json.loads(doc))

    mapped = []
    unavailable = []
    split_details = []

    for row in doc.get("material_mapping") or []:
        base = {
            "item_number": row.get("item_number") or "",
            "sales_order": row.get("sales_order") or "",
            "item_code": row.get("item_code"),
            "item_name": row.get("item_name"),
            "bom_no": row.get("bom_no"),
            "drawing": row.get("drawing") or "",
            "duno_mark_no": row.get("duno_mark_no"),
            "customer_drawing_number": row.get("customer_drawing_number") or "",
            "qty": flt(row.get("qty")),
            "uom": row.get("uom"),
            "sec_qty": flt(row.get("sec_qty")),
            "sec_uom": row.get("sec_uom"),
            "parent_item_group": row.get("parent_item_group"),
            "length": flt(row.get("length")),
            "width": flt(row.get("width")),
            "thickness": flt(row.get("thickness")),
            "unit_weight": flt(row.get("unit_weight")),
            # Material Mapping calls this field "planned_item"; Unavailable
            # Items calls the same concept "alternate_item" — translate when
            # a no-batch row moves back so the alternate isn't lost.
            "alternate_item": row.get("alternate_item") or row.get("planned_item") or "",
        }

        batch = row.get("batch")
        if not batch:
            unavailable.append(base)
            continue

        mapped_extra = dict(
            batch=batch,
            planned_item=row.get("planned_item"),
            batch_mapped="Mapped",
            batch_parent_item_group=row.get("batch_parent_item_group") or "",
            batch_length=flt(row.get("batch_length")),
            batch_width=flt(row.get("batch_width")),
            batch_thickness=flt(row.get("batch_thickness")),
            batch_unit_weight=flt(row.get("batch_unit_weight")),
            batch_sec_qty=flt(row.get("batch_sec_qty")),
            batch_calc_qty=flt(row.get("batch_calc_qty")),
            batch_total_qty=flt(row.get("batch_total_qty")),
            batch_reserved_qty=flt(row.get("batch_reserved_qty")),
            batch_free_qty=flt(row.get("batch_free_qty")),
            is_reserved=row.get("is_reserved") or 0,
            reserved_qty=flt(row.get("reserved_qty")),
            shortfall_qty=flt(row.get("shortfall_qty")),
            reserved_on=row.get("reserved_on") or "",
            store_location=row.get("store_location") or "",
        )

        group = row.get("parent_item_group") or ""
        qty = flt(row.get("qty"))
        sec_qty = flt(row.get("sec_qty"))
        batch_calc_qty = flt(row.get("batch_calc_qty"))
        is_reserved = bool(row.get("is_reserved"))
        under_covers = group in ("Structurals", "Plates") and sec_qty and batch_calc_qty < qty

        if under_covers and not is_reserved:
            usable_nos, usable_kg, shortfall_nos, shortfall_kg, excess_kg = _calc_usable_nos_split(
                qty, sec_qty, batch_calc_qty
            )
            if usable_nos > 0:
                mapped.append(dict(base, qty=usable_kg, sec_qty=usable_nos, **mapped_extra))
                unavailable.append(dict(base, qty=shortfall_kg, sec_qty=shortfall_nos))
                split_details.append({
                    "idx": row.get("idx"), "item_code": row.get("item_code"),
                    "duno_mark_no": row.get("duno_mark_no") or "", "alternate": row.get("planned_item") or batch,
                    "usable_nos": usable_nos, "usable_kg": usable_kg,
                    "excess_kg": excess_kg,
                    "shortfall_nos": shortfall_nos, "shortfall_kg": shortfall_kg,
                    "dropped": False,
                })
            else:
                unavailable.append(base)
                split_details.append({
                    "idx": row.get("idx"), "item_code": row.get("item_code"),
                    "duno_mark_no": row.get("duno_mark_no") or "", "alternate": row.get("planned_item") or batch,
                    "usable_nos": 0, "usable_kg": 0.0,
                    "excess_kg": 0.0,
                    "shortfall_nos": int(sec_qty), "shortfall_kg": flt(qty, 3),
                    "dropped": True,
                })
            continue

        mapped.append(dict(base, **mapped_extra))

    return {
        "material_mapping": mapped,
        "unavailable_items": unavailable,
        "split_details": split_details,
    }


def _verify_nos_vs_qty(rows):
    """Cross-check each row's Sec Qty (Nos) against its Qty (Kg) using the
    same weight formula the rest of the app uses, and — for rows that trace
    back to a Sales Order drawing line — against that line's Total Sec Qty
    too. Surfaces exactly the class of mismatch behind the ISMB250/BEAM-1B10
    case (Sec Qty silently inflated by a rounding-driven ceil() overshoot).
    """
    issues = []
    for row in rows:
        group = row.get("parent_item_group") or ""
        length = flt(row.get("length"))
        width = flt(row.get("width"))
        thickness = flt(row.get("thickness"))
        unit_weight = flt(row.get("unit_weight"))
        qty = flt(row.get("qty"))
        sec_qty = flt(row.get("sec_qty"))

        # Nuts and Bolts reverses the roles: qty holds Nos, sec_qty holds Kg
        # (see setup.py's Nuts and Bolts qty handler) — everywhere else qty
        # is Kg and sec_qty is Nos.
        expected = None
        checked_field = None
        if group == "Structurals" and length and unit_weight:
            expected = flt((length / 1000) * unit_weight * sec_qty, 3)
            checked_field, actual = "qty", qty
        elif group == "Plates" and length and width and thickness and unit_weight:
            expected = flt((length / 1000) * (width / 1000) * thickness * unit_weight * sec_qty, 3)
            checked_field, actual = "qty", qty
        elif group == "Nuts and Bolts" and unit_weight:
            expected = flt(unit_weight * qty, 3)
            checked_field, actual = "sec_qty", sec_qty

        formula_ok = expected is None or abs(expected - actual) <= 0.01

        so_expected_sec_qty = None
        so_ok = True
        sales_order = row.get("sales_order")
        if sales_order:
            so_expected_sec_qty = frappe.db.get_value(
                "Sales Order Drawing Raw Material",
                {
                    "parent": sales_order,
                    "material_code": row.get("item_code"),
                    "item_no": row.get("item_number"),
                    "customer_drawing_number": row.get("customer_drawing_number"),
                },
                "total_sec_qty",
            )
            if so_expected_sec_qty is not None:
                so_ok = abs(flt(so_expected_sec_qty) - sec_qty) <= 0.01

        if not formula_ok or not so_ok:
            issues.append({
                "idx": row.get("idx"),
                "item_code": row.get("item_code"),
                "item_number": row.get("item_number") or "",
                "customer_drawing_number": row.get("customer_drawing_number") or "",
                "parent_item_group": group,
                "qty": qty,
                "sec_qty": sec_qty,
                "checked_field": checked_field,
                "formula_expected": expected,
                "formula_ok": formula_ok,
                "so_expected_sec_qty": flt(so_expected_sec_qty) if so_expected_sec_qty is not None else None,
                "so_ok": so_ok,
            })

    return issues


@frappe.whitelist()
def verify_raw_materials(doc):
    """Verify the raw_materials table — run right after Get Raw Materials,
    before Check Stock Availability creates any batch/reservation state, so
    a Nos/Qty mismatch is caught at the earliest possible point.
    """
    if isinstance(doc, str):
        doc = frappe._dict(json.loads(doc))

    rows = doc.get("raw_materials") or []
    return {
        "checked": len(rows),
        "issues": _verify_nos_vs_qty(rows),
    }


@frappe.whitelist()
def get_batch_reservation_summary(batch_no):
    """Return all active reservations for a batch, enriched with SO customer and project."""
    if not frappe.has_permission("Material Planning", "read"):
        frappe.throw(_("Not permitted to view Material Planning reservations"), frappe.PermissionError)
    rows = frappe.db.sql(
        """
        SELECT mm.parent AS mp_name, mm.sales_order, mm.reserved_qty, mm.item_code, mm.item_name
        FROM `tabMaterial Planning Material Mapping` mm
        WHERE mm.batch = %s AND mm.is_reserved = 1

        UNION ALL

        SELECT arm.parent AS mp_name, arm.sales_order, arm.reserved_qty, arm.item_code, arm.item_name
        FROM `tabMaterial Planning Available Raw Material` arm
        WHERE arm.batch_no = %s AND arm.is_reserved = 1
        """,
        (batch_no, batch_no),
        as_dict=True,
    )

    so_cache = {}
    for row in rows:
        so = row.get("sales_order") or ""
        if so and so not in so_cache:
            so_data = frappe.db.get_value(
                "Sales Order", so, ["customer", "project"], as_dict=True
            ) or {}
            so_cache[so] = so_data
        d = so_cache.get(so) or {}
        row["customer"] = d.get("customer") or ""
        row["project"] = d.get("project") or ""

    return rows


@frappe.whitelist()
def get_batch_item(batch_no):
    """Return item_code linked to a batch (for auto-fill on Material Mapping batch select)."""
    if not batch_no:
        return None
    return frappe.db.get_value("Batch", batch_no, "item")


@frappe.whitelist()
def get_batch_stock_summary(batch_no, warehouse, mp_name=""):
    """Return total, reserved-by-others, and free qty for a batch in a warehouse."""
    total_qty = _get_batch_total_stock(batch_no, warehouse)
    reserved_qty = _get_batch_reserved_by_others(batch_no, mp_name)
    free_qty = max(0.0, total_qty - reserved_qty)
    return {
        "total_qty": flt(total_qty, 3),
        "reserved_qty": flt(reserved_qty, 3),
        "free_qty": flt(free_qty, 3),
    }


def _get_batch_inspection_block_reason(batch_no):
    """Client change request Phase 6.2: block reserving a batch until its
    source Purchase Receipt's inspection is Completed -- but ONLY when the
    item actually requires inspection (Item.custom_inspection_required) AND
    the batch traces back to a Purchase Receipt at all.

    Returns None (not blocked) if the item doesn't require inspection, or if
    the batch has no traceable source Purchase Receipt -- e.g. an
    excess-return recovery batch (Phase 2.3/5.6, created via a plain Material
    Receipt Stock Entry, never a Purchase Receipt) or a batch that predates
    this app's PR->Batch linkage. There is no Purchase Receipt inspection to
    check in either case, so nothing here to gate against; failing open
    matches the plan's own framing ("... or the item never required
    inspection") rather than blocking material that was never subject to
    this gate in the first place.

    Otherwise returns a human-readable reason string if the source PR's
    custom_inspection_status isn't yet "Completed", or None if it is.
    """
    if not batch_no:
        return None

    batch = frappe.db.get_value(
        "Batch", batch_no, ["item", "reference_doctype", "reference_name"], as_dict=True
    )
    if not batch or not batch.item:
        return None
    if not frappe.db.get_value("Item", batch.item, "custom_inspection_required"):
        return None
    if batch.reference_doctype != "Purchase Receipt" or not batch.reference_name:
        return None

    status = frappe.db.get_value("Purchase Receipt", batch.reference_name, "custom_inspection_status")
    if status == "Completed":
        return None
    return _(
        "Item {0} requires inspection -- batch {1}'s source Purchase Receipt {2} "
        "has inspection status \"{3}\", not yet Completed."
    ).format(batch.item, batch_no, batch.reference_name, status or "Open")


def _get_batch_total_stock(batch_no, warehouse):
    """Return net stock qty for a batch in the given warehouse (submitted SBBs only)."""
    result = frappe.db.sql(
        """
        SELECT COALESCE(SUM(sbe.qty), 0) AS qty
        FROM `tabSerial and Batch Entry` sbe
        INNER JOIN `tabSerial and Batch Bundle` sbb ON sbb.name = sbe.parent
        WHERE sbe.batch_no = %s AND sbb.warehouse = %s AND sbb.docstatus = 1
        """,
        (batch_no, warehouse),
        as_dict=True,
    )
    return flt(result[0].qty) if result else 0.0


def _get_batch_reserved_by_others(batch_no, exclude_mp, exclude_table=None):
    """Return total reserved_qty committed to other Material Planning docs for this batch.

    Checks both material_mapping (field: batch) and available_raw_materials
    (field: batch_no) so reservations in either table are counted.

    exclude_table: "material_mapping" or "available_raw_materials".
      When set, only that table applies the same-MP exclusion; the OTHER
      table counts ALL MPs including the current one, so intra-MP
      cross-table double-reservation is detected at reservation time.
      When None (default), both tables exclude the current MP (legacy behaviour,
      used for display-only helpers where the calling table is unknown).
    """
    exclude_mm = exclude_table in (None, "material_mapping")
    exclude_arm = exclude_table in (None, "available_raw_materials")

    if exclude_mm:
        mm = frappe.db.sql(
            """
            SELECT COALESCE(SUM(reserved_qty), 0) AS total
            FROM `tabMaterial Planning Material Mapping`
            WHERE batch = %s AND is_reserved = 1 AND parent != %s
            """,
            (batch_no, exclude_mp),
            as_dict=True,
        )
    else:
        mm = frappe.db.sql(
            """
            SELECT COALESCE(SUM(reserved_qty), 0) AS total
            FROM `tabMaterial Planning Material Mapping`
            WHERE batch = %s AND is_reserved = 1
            """,
            (batch_no,),
            as_dict=True,
        )

    if exclude_arm:
        arm = frappe.db.sql(
            """
            SELECT COALESCE(SUM(reserved_qty), 0) AS total
            FROM `tabMaterial Planning Available Raw Material`
            WHERE batch_no = %s AND is_reserved = 1 AND parent != %s
            """,
            (batch_no, exclude_mp),
            as_dict=True,
        )
    else:
        arm = frappe.db.sql(
            """
            SELECT COALESCE(SUM(reserved_qty), 0) AS total
            FROM `tabMaterial Planning Available Raw Material`
            WHERE batch_no = %s AND is_reserved = 1
            """,
            (batch_no,),
            as_dict=True,
        )

    return flt(mm[0].total if mm else 0) + flt(arm[0].total if arm else 0)


def _get_batch_reserved_by_others_bulk(batch_nos, exclude_mp, exclude_table=None):
    """Batched variant of _get_batch_reserved_by_others -- 2 queries total for
    a set of batches instead of 2 queries per batch (Report 4 Finding D-02).
    Same exclude_table semantics as the single-batch function. Returns
    {batch_no: reserved_qty}; a batch with no reservation is simply absent
    (callers should use .get(batch_no, 0))."""
    batch_nos = list({b for b in batch_nos if b})
    if not batch_nos:
        return {}

    exclude_mm = exclude_table in (None, "material_mapping")
    exclude_arm = exclude_table in (None, "available_raw_materials")
    ph = ", ".join(["%s"] * len(batch_nos))
    totals = defaultdict(float)

    if exclude_mm:
        mm_rows = frappe.db.sql(
            f"""
            SELECT batch, COALESCE(SUM(reserved_qty), 0) AS total
            FROM `tabMaterial Planning Material Mapping`
            WHERE batch IN ({ph}) AND is_reserved = 1 AND parent != %s
            GROUP BY batch
            """,
            [*batch_nos, exclude_mp],
            as_dict=True,
        )
    else:
        mm_rows = frappe.db.sql(
            f"""
            SELECT batch, COALESCE(SUM(reserved_qty), 0) AS total
            FROM `tabMaterial Planning Material Mapping`
            WHERE batch IN ({ph}) AND is_reserved = 1
            GROUP BY batch
            """,
            batch_nos,
            as_dict=True,
        )
    for r in mm_rows:
        totals[r.batch] += flt(r.total)

    if exclude_arm:
        arm_rows = frappe.db.sql(
            f"""
            SELECT batch_no, COALESCE(SUM(reserved_qty), 0) AS total
            FROM `tabMaterial Planning Available Raw Material`
            WHERE batch_no IN ({ph}) AND is_reserved = 1 AND parent != %s
            GROUP BY batch_no
            """,
            [*batch_nos, exclude_mp],
            as_dict=True,
        )
    else:
        arm_rows = frappe.db.sql(
            f"""
            SELECT batch_no, COALESCE(SUM(reserved_qty), 0) AS total
            FROM `tabMaterial Planning Available Raw Material`
            WHERE batch_no IN ({ph}) AND is_reserved = 1
            GROUP BY batch_no
            """,
            batch_nos,
            as_dict=True,
        )
    for r in arm_rows:
        totals[r.batch_no] += flt(r.total)

    return dict(totals)


def _get_non_batch_reserved_by_others(item_code, warehouse, exclude_mp):
    """Return total reserved_qty committed to other MPs for a non-batch item in a warehouse."""
    result = frappe.db.sql(
        """
        SELECT COALESCE(SUM(reserved_qty), 0) AS total
        FROM `tabMaterial Planning Available Raw Material`
        WHERE item_code = %s AND warehouse = %s
          AND (batch_no IS NULL OR batch_no = '')
          AND is_reserved = 1 AND parent != %s
        """,
        (item_code, warehouse, exclude_mp),
        as_dict=True,
    )
    return flt(result[0].total if result else 0)


def _get_non_batch_reserved_by_others_bulk(item_codes, warehouse, exclude_mp):
    """Batched variant of _get_non_batch_reserved_by_others -- one query for a
    set of items instead of one query per item (Report 4 Finding D-02).
    Returns {item_code: reserved_qty}; an item with no reservation is simply
    absent (callers should use .get(item_code, 0))."""
    item_codes = list({c for c in item_codes if c})
    if not item_codes:
        return {}
    ph = ", ".join(["%s"] * len(item_codes))
    rows = frappe.db.sql(
        f"""
        SELECT item_code, COALESCE(SUM(reserved_qty), 0) AS total
        FROM `tabMaterial Planning Available Raw Material`
        WHERE item_code IN ({ph}) AND warehouse = %s
          AND (batch_no IS NULL OR batch_no = '')
          AND is_reserved = 1 AND parent != %s
        GROUP BY item_code
        """,
        [*item_codes, warehouse, exclude_mp],
        as_dict=True,
    )
    return {r.item_code: flt(r.total) for r in rows}


@frappe.whitelist()
def get_batch_cross_table_usage(batch_no, mp_name, warehouse):
    """Return the full per-table allocation picture for a batch within one MP.

    Called by the JS batch-selection handler to build the detailed conflict
    popup before allowing the batch to be committed to a row.
    """
    if not frappe.has_permission("Material Planning", "read"):
        frappe.throw(_("Not permitted to view Material Planning reservations"), frappe.PermissionError)
    total_qty = _get_batch_total_stock(batch_no, warehouse)
    reserved_by_others = _get_batch_reserved_by_others(batch_no, mp_name)

    mm_rows = frappe.db.sql(
        """
        SELECT idx, item_code,
               CASE WHEN is_reserved = 1 THEN reserved_qty
                    WHEN batch_calc_qty > 0 THEN batch_calc_qty
                    ELSE qty END AS qty,
               is_reserved
        FROM `tabMaterial Planning Material Mapping`
        WHERE parent = %s AND batch = %s
        ORDER BY idx
        """,
        (mp_name, batch_no),
        as_dict=True,
    )
    arm_rows = frappe.db.sql(
        """
        SELECT idx, item_code,
               CASE WHEN is_reserved = 1 THEN reserved_qty ELSE required_qty END AS qty,
               is_reserved
        FROM `tabMaterial Planning Available Raw Material`
        WHERE parent = %s AND batch_no = %s
        ORDER BY idx
        """,
        (mp_name, batch_no),
        as_dict=True,
    )

    mm_total  = sum(flt(r.qty) for r in mm_rows)
    arm_total = sum(flt(r.qty) for r in arm_rows)
    available_qty = max(0.0, flt(total_qty) - flt(reserved_by_others) - mm_total - arm_total)

    return {
        "total_qty":         flt(total_qty, 3),
        "reserved_by_others": flt(reserved_by_others, 3),
        "mm_rows":  [{"idx": r.idx, "item_code": r.item_code, "qty": flt(r.qty, 3), "is_reserved": r.is_reserved} for r in mm_rows],
        "arm_rows": [{"idx": r.idx, "item_code": r.item_code, "qty": flt(r.qty, 3), "is_reserved": r.is_reserved} for r in arm_rows],
        "mm_total":       flt(mm_total, 3),
        "arm_total":      flt(arm_total, 3),
        "available_qty":  flt(available_qty, 3),
    }


def _update_bom_item_weights(mp):
    """Compute per-drawing customer_provided_weight_kg, planned_weight_kg, and
    excess_weight_kg and store them on each bom_items row. Runs on every save
    (from validate()) so the excess split by drawing is always current — not
    only after reserve_batches / reserve_exact_match_batches succeed.
    """
    from manufyxinvenzaerp.subcontracting_management.subcontracting import (
        _get_mp_excess_by_duno,
        _get_mp_mapped_weight_by_duno,
    )
    if not mp.bom_items:
        return

    mapped_by_duno = _get_mp_mapped_weight_by_duno(mp.name)
    excess_by_duno = _get_mp_excess_by_duno(mp.name)

    for bom_item in (mp.bom_items or []):
        duno = bom_item.duno_mark_no or ""
        bom_item.planned_weight_kg = flt(mapped_by_duno.get(duno, 0.0), 3)
        bom_item.excess_weight_kg = flt(excess_by_duno.get(duno, 0.0), 3)
        if bom_item.sales_order and duno:
            so_wt = frappe.db.get_value(
                "Sales Order DUNO Item",
                {"parent": bom_item.sales_order, "duno_mark_no": duno},
                "total_weight",
            ) or 0.0
            bom_item.customer_provided_weight_kg = flt(so_wt, 3)


def _calc_kg_per_nos(group, length, width, thickness, unit_weight):
    """Kg represented by ONE Sec Qty (Nos) piece of the given dimensions/group."""
    length, width, thickness, unit_weight = flt(length), flt(width), flt(thickness), flt(unit_weight)
    if group == "Structurals" and length and unit_weight:
        return (length / 1000) * unit_weight
    if group == "Plates" and length and width and thickness and unit_weight:
        return (length / 1000) * (width / 1000) * thickness * unit_weight
    if group == "Nuts and Bolts" and unit_weight:
        return unit_weight
    return 0.0


def _calc_usable_nos_split(qty, sec_qty, batch_calc_qty):
    """For a Material Mapping row (Structurals/Plates only — Nuts and Bolts
    shortfalls never reach this table) whose mapped batch under-covers the
    requirement: work out how many whole Sec Qty (Nos) of the ORIGINAL item
    the mapped batch_calc_qty can actually fulfil. A partial piece isn't
    usable — a structural length or plate either exists whole or it doesn't —
    so this always rounds DOWN, never up.

    Returns (usable_nos, usable_kg, shortfall_nos, shortfall_kg, excess_kg):
      - usable_nos/usable_kg   — the whole pieces this mapping actually covers.
      - shortfall_nos/shortfall_kg — the remaining pieces of the ORIGINAL item
        still needed — these move to Unavailable Items / purchase.
      - excess_kg              — batch_calc_qty beyond what usable_kg needed;
        this is weight already drawn from the batch that doesn't correspond
        to a complete piece, so it's tracked as Difference in Kg, not thrown away.
    """
    qty, sec_qty, batch_calc_qty = flt(qty), flt(sec_qty), flt(batch_calc_qty)
    if not sec_qty:
        return 0, 0.0, 0, flt(qty, 3), 0.0

    kg_per_nos = qty / sec_qty
    if not kg_per_nos:
        return 0, 0.0, 0, flt(qty, 3), 0.0

    usable_nos = int(round(batch_calc_qty / kg_per_nos, 9))
    usable_nos = max(0, min(usable_nos, int(sec_qty)))
    usable_kg = flt(usable_nos * kg_per_nos, 3)
    shortfall_nos = int(sec_qty) - usable_nos
    shortfall_kg = flt(shortfall_nos * kg_per_nos, 3)
    excess_kg = flt(batch_calc_qty - usable_kg, 3)
    return usable_nos, usable_kg, shortfall_nos, shortfall_kg, excess_kg


def _row_get(row, key, default=None):
    return row.get(key, default) if isinstance(row, dict) else getattr(row, key, default)


def _calc_group_rwd_allocations(rows):
    """
    Group not-yet-reserved "Reserve stock without dimensions" rows (with
    "Allocate based on Sec Nos" enabled) by the batch they share, round the
    GROUP's *combined* required Kg up to the nearest whole Sec Qty (Nos) of
    that batch, then split the rounded total back across the group's rows
    proportional to each row's own required-Kg share — mirrors
    _alloc_sec_qty()'s proportional-split pattern.

    Rounding must happen on the combined total, not per row: 4 rows each
    needing a fraction of a sheet can add up to needing whole sheets between
    them, and rounding each row up independently would over-reserve an extra
    sheet per row instead of one extra sheet for the whole group.

    Returns {row.name: (to_reserve_kg, sec_qty)} for every row in such a group.
    """
    groups = {}
    for row in rows:
        batch = _row_get(row, "batch")
        if _row_get(row, "is_reserved") or not batch:
            continue
        if not (_row_get(row, "reserve_without_dimensions") and _row_get(row, "allocate_based_on_sec_qty")):
            continue
        group = _row_get(row, "batch_parent_item_group") or ""
        if group not in ("Structurals", "Plates"):
            continue
        groups.setdefault(batch, []).append(row)

    allocations = {}
    for batch, group_rows in groups.items():
        r0 = group_rows[0]
        group = _row_get(r0, "batch_parent_item_group") or ""
        kg_per_nos = _calc_kg_per_nos(
            group, _row_get(r0, "batch_length"), _row_get(r0, "batch_width"),
            _row_get(r0, "batch_thickness"), _row_get(r0, "batch_unit_weight"),
        )
        group_required = sum(flt(_row_get(r, "qty")) for r in group_rows)

        if not kg_per_nos or not group_required:
            for r in group_rows:
                allocations[_row_get(r, "name")] = (flt(_row_get(r, "qty"), 3), 0)
            continue

        sec_qty_needed = int(_nos_from_weight(group_required, kg_per_nos))
        group_kg_to_reserve = flt(sec_qty_needed * kg_per_nos, 3)

        for r in group_rows:
            share = flt(_row_get(r, "qty")) / group_required
            row_kg = flt(share * group_kg_to_reserve, 3)
            row_sec = flt(row_kg / kg_per_nos, 3)
            allocations[_row_get(r, "name")] = (row_kg, row_sec)

    return allocations


@frappe.whitelist()
def reserve_batches(material_planning_name):
    """
    Reserve batches in material_mapping with partial-stock awareness.
    For each row:
      - Computes available qty = batch_stock - already_reserved_by_other_MPs
      - reserved_qty = min(required_qty, available)
      - shortfall_qty = required_qty - reserved_qty
    Returns updated rows + list of partially reserved items for JS warning.
    """
    mp = frappe.get_doc("Material Planning", material_planning_name)
    if not frappe.has_permission("Material Planning", "write", doc=mp):
        frappe.throw(_("Not permitted to reserve batches on this Material Planning"), frappe.PermissionError)
    if not mp.material_mapping:
        frappe.throw(_("No items in Material Mapping to reserve."))
    if not mp.for_warehouse:
        frappe.throw(_("Set 'Raw Materials Warehouse' on the Material Planning before reserving."))

    reserved_count = 0
    partial_rows = []
    blocked_rows = []
    # Track qty allocated within this doc so the same batch used in multiple
    # rows is not double-counted against available stock.
    batch_allocated_here = {}

    # Rows sharing a batch under "Reserve stock without dimensions" + "Allocate
    # based on Sec Nos" must be rounded up to whole Sec Qty as a GROUP (not
    # independently per row) — see _calc_group_rwd_allocations for why.
    rwd_allocations = _calc_group_rwd_allocations(mp.material_mapping)

    for row in mp.material_mapping:
        if not row.batch:
            continue
        if row.is_reserved:
            # Count already-reserved rows toward intra-doc tracking so
            # subsequent new rows see a realistic remaining balance.
            batch_allocated_here[row.batch] = (
                batch_allocated_here.get(row.batch, 0.0) + flt(row.reserved_qty)
            )
            continue

        block_reason = _get_batch_inspection_block_reason(row.batch)
        if block_reason:
            blocked_rows.append({
                "item_code": row.item_code, "item_name": row.item_name or "",
                "batch": row.batch, "reason": block_reason,
            })
            continue

        batch_calc_qty = flt(row.batch_calc_qty)
        required_qty = flt(row.qty)

        if row.reserve_without_dimensions and row.batch_parent_item_group in ("Structurals", "Plates"):
            if row.allocate_based_on_sec_qty:
                # Stock can't be physically transferred as a fractional Kg
                # amount — reserve this row's proportional share of the
                # group's whole-Sec-Qty rounded-up total instead.
                to_reserve, sec_qty = rwd_allocations.get(row.name, (required_qty, 0))
                row.batch_sec_qty = sec_qty
                row.batch_calc_qty = to_reserve
            else:
                # Opted out — reserve the exact Required Qty; Sec Qty is
                # entered manually later, at transfer time.
                to_reserve = required_qty
                row.batch_sec_qty = 0
                row.batch_calc_qty = 0
        elif batch_calc_qty > 0 and row.batch_parent_item_group in ("Structurals", "Plates"):
            # When a different-dimension batch is assigned, batch_calc_qty is the
            # Kg we actually take from that batch (Structurals/Plates only).
            if batch_calc_qty < required_qty:
                frappe.throw(
                    _("Row {0}: Calculated Qty ({1} Kg) is less than Required Qty ({2} Kg) for item {3}. "
                      "Increase Sec Qty so the allocated batch material covers the requirement.").format(
                        row.idx, flt(batch_calc_qty, 3), required_qty, row.item_code
                    )
                )
            to_reserve = batch_calc_qty
        else:
            to_reserve = required_qty

        batch_stock = _get_batch_total_stock(row.batch, mp.for_warehouse)
        reserved_by_others = _get_batch_reserved_by_others(row.batch, material_planning_name, exclude_table="material_mapping")
        allocated_here = batch_allocated_here.get(row.batch, 0.0)
        available = max(0.0, flt(batch_stock) - flt(reserved_by_others) - allocated_here)

        # Round reserved_qty first so shortfall is computed on the same precision
        # as the displayed value — avoids floating-point near-zero false positives.
        reserved_qty = flt(min(to_reserve, available), 3)
        shortfall_qty = flt(max(0.0, flt(to_reserve, 3) - reserved_qty), 3)

        row.is_reserved = 1
        row.reserved_qty = reserved_qty
        row.shortfall_qty = shortfall_qty
        row.reserved_on = now()
        batch_allocated_here[row.batch] = allocated_here + reserved_qty
        reserved_count += 1

        if shortfall_qty > 0:
            partial_rows.append({
                "item_code": row.item_code,
                "item_name": row.item_name or "",
                "batch": row.batch,
                "required_qty": flt(to_reserve, 3),
                "reserved_qty": reserved_qty,
                "shortfall_qty": shortfall_qty,
                "uom": row.uom or "",
                "batch_stock": flt(batch_stock, 3),
                "reserved_by_others": flt(reserved_by_others + allocated_here, 3),
            })

    if not reserved_count:
        if blocked_rows:
            frappe.throw(
                _("All remaining rows with a batch are blocked pending inspection completion. {0}").format(
                    "; ".join(b["reason"] for b in blocked_rows)
                )
            )
        frappe.throw(_("All rows with a batch are already reserved."))

    _update_bom_item_weights(mp)
    mp.save(ignore_permissions=True)
    frappe.db.commit()

    return {
        "rows": [
            {
                "name": row.name,
                "item_code": row.item_code,
                "batch": row.batch,
                "is_reserved": row.is_reserved,
                "reserved_qty": flt(row.reserved_qty, 3),
                "shortfall_qty": flt(row.shortfall_qty, 3),
                "reserved_on": str(row.reserved_on) if row.reserved_on else "",
            }
            for row in mp.material_mapping
        ],
        "partial": partial_rows,
        "blocked": blocked_rows,
    }


def _get_batch_reserved_by_self(batch_no, mp_name):
    """Sum reserved_qty already committed to batch_no WITHIN this same
    Material Planning (both tables) — the inverse of
    _get_batch_reserved_by_others, which deliberately excludes the current
    MP's own reservations. get_available_excess_batches needs both: stock
    already claimed by OTHER MPs, and stock this SAME MP already claimed
    from a previous mapping of this batch, so a fully-claimed batch stops
    showing up as "still free" once this MP has taken all of it."""
    mm = frappe.db.sql(
        """
        SELECT COALESCE(SUM(reserved_qty), 0) AS total
        FROM `tabMaterial Planning Material Mapping`
        WHERE batch = %s AND is_reserved = 1 AND parent = %s
        """,
        (batch_no, mp_name),
    )[0][0]
    arm = frappe.db.sql(
        """
        SELECT COALESCE(SUM(reserved_qty), 0) AS total
        FROM `tabMaterial Planning Available Raw Material`
        WHERE batch_no = %s AND is_reserved = 1 AND parent = %s
        """,
        (batch_no, mp_name),
    )[0][0]
    return flt(mm) + flt(arm)


@frappe.whitelist()
def get_available_excess_batches(mp_name, item_code=None):
    """List batches recovered via the excess-material-return flow
    (create_mip_excess_return_entry in material_issue_plan_transfer.py) that
    still have free stock in THIS Material Planning's own warehouse -- i.e.,
    off-cuts left over from one job that can be manually reused here instead
    of buying fresh raw material (client change request Phase 2.3). A batch
    counts as "excess-return" if it was created by a submitted Material
    Receipt Stock Entry that carries a custom_mip_ref (the tag every
    excess-return entry sets)."""
    mp = frappe.get_doc("Material Planning", mp_name)
    if not mp.for_warehouse:
        frappe.throw(_("Set 'Raw Materials Warehouse' on the Material Planning first."))

    se_names = frappe.get_all(
        "Stock Entry",
        filters={"stock_entry_type": "Material Receipt", "custom_mip_ref": ["is", "set"], "docstatus": 1},
        pluck="name",
    )
    if not se_names:
        return []

    batch_filters = {"reference_doctype": "Stock Entry", "reference_name": ["in", se_names]}
    if item_code:
        batch_filters["item"] = item_code
    batches = frappe.get_all(
        "Batch",
        filters=batch_filters,
        fields=["name", "item", "custom_length", "custom_width", "custom_thickness",
                "custom_sec_qty", "custom_sec_uom"],
    )
    if not batches:
        return []

    item_codes = list({b.item for b in batches})
    item_data = {
        r.name: r for r in frappe.get_all(
            "Item", filters={"name": ["in", item_codes]},
            fields=["name", "item_name", "custom_parent_item_group", "custom_unit_weight"],
        )
    }

    result = []
    for b in batches:
        summary = get_batch_stock_summary(b.name, mp.for_warehouse, mp_name)
        already_by_self = _get_batch_reserved_by_self(b.name, mp_name)
        free_qty = flt(max(0.0, flt(summary.get("free_qty")) - already_by_self), 3)
        if free_qty <= 0:
            continue
        item = item_data.get(b.item, frappe._dict())
        result.append({
            "batch_no": b.name,
            "item_code": b.item,
            "item_name": item.get("item_name") or b.item,
            "parent_item_group": item.get("custom_parent_item_group") or "",
            "unit_weight": flt(item.get("custom_unit_weight")),
            "length": flt(b.custom_length),
            "width": flt(b.custom_width),
            "thickness": flt(b.custom_thickness),
            "batch_sec_qty": flt(b.custom_sec_qty),
            "sec_uom": b.custom_sec_uom or "",
            "free_qty": free_qty,
        })
    return result


@frappe.whitelist()
def add_excess_material_mapping(mp_name, batch_no, sec_qty, unavailable_item_row=None):
    """Add a Material Mapping row sourced from a recovered excess-return
    batch, auto-fetching its dimensions, validating the requested Sec Qty
    against the batch's free stock, then reserving it via the same
    reserve_batches() logic used everywhere else (client change request
    Phase 2.3). If unavailable_item_row is given, traceability (item
    number/DUNO/SO/drawing) is copied from that Unavailable Item row and it
    is shrunk/removed by the amount covered -- same reconciliation pattern
    allocate_pr_stock_to_mp uses; otherwise the new row is added standalone
    with no traceability (an opportunistic reuse not tied to a specific
    planned requirement)."""
    mp = frappe.get_doc("Material Planning", mp_name)
    if not frappe.has_permission("Material Planning", "write", doc=mp):
        frappe.throw(_("Not permitted to modify this Material Planning"), frappe.PermissionError)
    if not mp.for_warehouse:
        frappe.throw(_("Set 'Raw Materials Warehouse' on the Material Planning first."))

    sec_qty = flt(sec_qty)
    if sec_qty <= 0:
        frappe.throw(_("Enter a Sec Qty greater than 0."))

    batch = frappe.db.get_value(
        "Batch", batch_no,
        ["item", "custom_length", "custom_width", "custom_thickness", "custom_sec_uom"],
        as_dict=True,
    )
    if not batch:
        frappe.throw(_("Batch {0} not found.").format(batch_no))

    item_code = batch.item
    item = frappe.db.get_value(
        "Item", item_code,
        ["item_name", "custom_parent_item_group", "custom_unit_weight"],
        as_dict=True,
    ) or {}
    group = item.get("custom_parent_item_group") or ""
    unit_weight = flt(item.get("custom_unit_weight"))

    calc_qty = _calc_batch_qty(group, batch.custom_length, batch.custom_width, batch.custom_thickness, sec_qty, unit_weight)
    if not calc_qty:
        frappe.throw(_("Could not calculate a Kg quantity for this Sec Qty — check the item's Unit Weight and the batch's dimensions."))

    free_qty = flt(get_batch_stock_summary(batch_no, mp.for_warehouse, mp_name).get("free_qty"))
    free_qty = flt(max(0.0, free_qty - _get_batch_reserved_by_self(batch_no, mp_name)), 3)
    if calc_qty > free_qty:
        frappe.throw(
            _("Requested Sec Qty needs {0} Kg, but only {1} Kg is free in batch {2}.")
            .format(flt(calc_qty, 3), free_qty, batch_no)
        )

    base = {
        "item_number": "", "sales_order": "", "item_code": item_code,
        "item_name": item.get("item_name") or item_code, "bom_no": "", "drawing": "",
        "duno_mark_no": "", "customer_drawing_number": "",
    }

    if unavailable_item_row:
        src = next((r for r in (mp.unavailable_items or []) if r.name == unavailable_item_row), None)
        if not src:
            frappe.throw(_("Unavailable Item row {0} not found.").format(unavailable_item_row))
        if src.item_code != item_code:
            frappe.throw(
                _("Selected batch's item ({0}) does not match the Unavailable Item row's item ({1}).")
                .format(item_code, src.item_code)
            )
        base.update({
            "item_number": src.item_number, "sales_order": src.sales_order,
            "bom_no": src.bom_no, "drawing": src.drawing,
            "duno_mark_no": src.duno_mark_no, "customer_drawing_number": src.customer_drawing_number,
        })
        old_qty = flt(src.qty)
        remaining = flt(old_qty - calc_qty, 3)
        if remaining <= 0.001:
            mp.unavailable_items = [r for r in mp.unavailable_items if r.name != unavailable_item_row]
        else:
            ratio = (remaining / old_qty) if old_qty else 0.0
            src.qty = remaining
            src.sec_qty = flt(flt(src.sec_qty) * ratio, 3)

    mp.append("material_mapping", dict(base,
        qty=flt(calc_qty, 3), uom="Kg", sec_qty=sec_qty, sec_uom=batch.custom_sec_uom or "",
        parent_item_group=group, length=flt(batch.custom_length), width=flt(batch.custom_width),
        thickness=flt(batch.custom_thickness), unit_weight=unit_weight,
        batch=batch_no, planned_item=item_code, batch_mapped="Mapped",
        batch_parent_item_group=group, batch_length=flt(batch.custom_length),
        batch_width=flt(batch.custom_width), batch_thickness=flt(batch.custom_thickness),
        batch_unit_weight=unit_weight, batch_sec_qty=sec_qty, batch_calc_qty=flt(calc_qty, 3),
    ))

    mp.save(ignore_permissions=True)
    return reserve_batches(mp_name)


@frappe.whitelist()
def reserve_exact_match_batches(material_planning_name):
    """
    Reserve batches in available_raw_materials (Exact Match) with partial-stock awareness.
    Mirrors reserve_batches logic but targets the available_raw_materials table and uses
    the batch_no / required_qty field names used by that child doctype.
    """
    mp = frappe.get_doc("Material Planning", material_planning_name)
    if not mp.available_raw_materials:
        frappe.throw(_("No items in Available Raw Materials to reserve."))
    if not mp.for_warehouse:
        frappe.throw(_("Set 'Raw Materials Warehouse' on the Material Planning before reserving."))

    reserved_count = 0
    partial_rows = []
    blocked_rows = []
    batch_allocated_here = {}
    nonbatch_allocated = {}  # (item_code, warehouse) → qty allocated within this doc

    for row in mp.available_raw_materials:
        if row.is_reserved:
            if row.batch_no:
                batch_allocated_here[row.batch_no] = (
                    batch_allocated_here.get(row.batch_no, 0.0) + flt(row.reserved_qty)
                )
            else:
                key = (row.item_code, row.warehouse or mp.for_warehouse)
                nonbatch_allocated[key] = nonbatch_allocated.get(key, 0.0) + flt(row.reserved_qty)
            continue

        required_qty = flt(row.required_qty)

        if row.batch_no:
            # ── Batch item ──────────────────────────────────────────────────
            block_reason = _get_batch_inspection_block_reason(row.batch_no)
            if block_reason:
                blocked_rows.append({
                    "item_code": row.item_code, "item_name": row.item_name or "",
                    "batch": row.batch_no, "reason": block_reason,
                })
                continue

            batch_stock = _get_batch_total_stock(row.batch_no, mp.for_warehouse)
            reserved_by_others = _get_batch_reserved_by_others(row.batch_no, material_planning_name, exclude_table="available_raw_materials")
            allocated_here = batch_allocated_here.get(row.batch_no, 0.0)
            available = max(0.0, flt(batch_stock) - flt(reserved_by_others) - allocated_here)

            reserved_qty = flt(min(required_qty, available), 3)
            shortfall_qty = flt(max(0.0, flt(required_qty, 3) - reserved_qty), 3)

            row.is_reserved = 1
            row.reserved_qty = reserved_qty
            row.shortfall_qty = shortfall_qty
            row.reserved_on = now()
            batch_allocated_here[row.batch_no] = allocated_here + reserved_qty
            reserved_count += 1

            if shortfall_qty > 0:
                partial_rows.append({
                    "item_code": row.item_code,
                    "item_name": row.item_name or "",
                    "batch": row.batch_no,
                    "required_qty": flt(required_qty, 3),
                    "reserved_qty": reserved_qty,
                    "shortfall_qty": shortfall_qty,
                    "uom": row.uom or "",
                    "batch_stock": flt(batch_stock, 3),
                    "reserved_by_others": flt(reserved_by_others + allocated_here, 3),
                })

        else:
            # ── Non-batch item ───────────────────────────────────────────────
            wh = row.warehouse or mp.for_warehouse
            key = (row.item_code, wh)
            stock = _get_non_batch_stock(row.item_code, wh)
            reserved_by_others = _get_non_batch_reserved_by_others(row.item_code, wh, material_planning_name)
            allocated_here = nonbatch_allocated.get(key, 0.0)
            available = max(0.0, stock - reserved_by_others - allocated_here)

            reserved_qty = flt(min(required_qty, available), 3)
            shortfall_qty = flt(max(0.0, flt(required_qty, 3) - reserved_qty), 3)

            row.is_reserved = 1
            row.reserved_qty = reserved_qty
            row.shortfall_qty = shortfall_qty
            row.reserved_on = now()
            nonbatch_allocated[key] = allocated_here + reserved_qty
            reserved_count += 1

            if shortfall_qty > 0:
                partial_rows.append({
                    "item_code": row.item_code,
                    "item_name": row.item_name or "",
                    "batch": "",
                    "required_qty": flt(required_qty, 3),
                    "reserved_qty": reserved_qty,
                    "shortfall_qty": shortfall_qty,
                    "uom": row.uom or "",
                    "batch_stock": flt(stock, 3),
                    "reserved_by_others": flt(reserved_by_others + allocated_here, 3),
                })

    if not reserved_count:
        if blocked_rows:
            frappe.throw(
                _("All remaining rows are blocked pending inspection completion. {0}").format(
                    "; ".join(b["reason"] for b in blocked_rows)
                )
            )
        frappe.throw(_("All rows are already reserved."))

    _update_bom_item_weights(mp)
    mp.save(ignore_permissions=True)
    frappe.db.commit()

    return {
        "rows": [
            {
                "name": row.name,
                "item_code": row.item_code,
                "batch_no": row.batch_no,
                "is_reserved": row.is_reserved,
                "reserved_qty": flt(row.reserved_qty, 3),
                "shortfall_qty": flt(row.shortfall_qty, 3),
                "reserved_on": str(row.reserved_on) if row.reserved_on else "",
            }
            for row in mp.available_raw_materials
        ],
        "partial": partial_rows,
        "blocked": blocked_rows,
    }


@frappe.whitelist()
def unreserve_exact_match_batches(material_planning_name, row_names):
    """
    Clear reservation on specified available_raw_materials rows (by child row name).
    row_names: JSON list of child row names to unreserve.
    """
    if isinstance(row_names, str):
        row_names = json.loads(row_names)

    mp = frappe.get_doc("Material Planning", material_planning_name)
    target = set(row_names)
    unreserved_count = 0

    for row in mp.available_raw_materials:
        if row.name in target:
            row.is_reserved = 0
            row.reserved_qty = 0
            row.shortfall_qty = 0
            row.reserved_on = None
            unreserved_count += 1

    if not unreserved_count:
        frappe.throw(_("No matching reserved rows found."))

    mp.save(ignore_permissions=True)
    frappe.db.commit()

    return [
        {
            "name": row.name,
            "item_code": row.item_code,
            "batch_no": row.batch_no,
            "is_reserved": row.is_reserved,
            "reserved_qty": flt(row.reserved_qty, 3),
            "shortfall_qty": flt(row.shortfall_qty, 3),
            "reserved_on": str(row.reserved_on) if row.reserved_on else "",
        }
        for row in mp.available_raw_materials
    ]


@frappe.whitelist()
def check_mapping_batch_availability(doc):
    """
    For every Material Mapping row that has a batch assigned, compute how much
    stock is actually available to reserve (considering other MPs and intra-doc
    same-batch rows).  Returns a list of rows where a shortfall would occur so
    the JS can show a warning popup before/after save.
    """
    if isinstance(doc, str):
        doc = frappe._dict(json.loads(doc))

    warehouse = doc.get("for_warehouse")
    if not warehouse:
        return []

    mp_name = doc.get("name") or ""
    warnings = []
    batch_allocated_here = {}

    # Rows sharing a batch under "Reserve stock without dimensions" + "Allocate
    # based on Sec Nos" round up to whole Sec Qty as a GROUP, not per row —
    # see _calc_group_rwd_allocations.
    rwd_allocations = _calc_group_rwd_allocations(doc.get("material_mapping") or [])

    for row in doc.get("material_mapping") or []:
        batch = row.get("batch") if isinstance(row, dict) else getattr(row, "batch", None)
        if not batch:
            continue

        base_qty = flt(row.get("qty") if isinstance(row, dict) else row.qty)
        batch_calc_qty = flt(row.get("batch_calc_qty") if isinstance(row, dict) else getattr(row, "batch_calc_qty", 0))
        group = (row.get("batch_parent_item_group") if isinstance(row, dict) else getattr(row, "batch_parent_item_group", "")) or ""
        reserve_without_dim = int(row.get("reserve_without_dimensions") if isinstance(row, dict) else getattr(row, "reserve_without_dimensions", 0))
        if reserve_without_dim and group in ("Structurals", "Plates"):
            row_name = row.get("name") if isinstance(row, dict) else getattr(row, "name", None)
            required_qty, _ = rwd_allocations.get(row_name, (base_qty, 0))
        else:
            required_qty = batch_calc_qty if (batch_calc_qty > 0 and group in ("Structurals", "Plates")) else base_qty

        batch_stock = _get_batch_total_stock(batch, warehouse)
        reserved_by_others = _get_batch_reserved_by_others(batch, mp_name, exclude_table="material_mapping")
        allocated_here = batch_allocated_here.get(batch, 0.0)
        available = max(0.0, flt(batch_stock) - flt(reserved_by_others) - allocated_here)

        can_reserve = min(required_qty, available)
        shortfall = max(0.0, required_qty - can_reserve)

        if shortfall > 0:
            item_code = row.get("item_code") if isinstance(row, dict) else row.item_code
            warnings.append({
                "idx": (row.get("idx") if isinstance(row, dict) else getattr(row, "idx", "")) or "",
                "item_code": item_code,
                "item_name": (row.get("item_name") if isinstance(row, dict) else row.item_name) or "",
                "batch": batch,
                "required_qty": flt(required_qty, 3),
                "batch_stock": flt(batch_stock, 3),
                "available_to_reserve": flt(can_reserve, 3),
                "shortfall_qty": flt(shortfall, 3),
                "uom": (row.get("uom") if isinstance(row, dict) else row.uom) or "",
            })

        batch_allocated_here[batch] = allocated_here + can_reserve

    return warnings


@frappe.whitelist()
def unreserve_batches(material_planning_name, row_names):
    """
    Clear reservation on specified material_mapping rows (by child row name).
    row_names: JSON list of child row names to unreserve.
    """
    if isinstance(row_names, str):
        row_names = json.loads(row_names)

    mp = frappe.get_doc("Material Planning", material_planning_name)
    target = set(row_names)
    unreserved_count = 0

    for row in mp.material_mapping:
        if row.name in target:
            row.is_reserved = 0
            row.reserved_qty = 0
            row.shortfall_qty = 0
            row.reserved_on = None
            unreserved_count += 1

    if not unreserved_count:
        frappe.throw(_("No matching reserved rows found."))

    mp.save(ignore_permissions=True)
    frappe.db.commit()

    return [
        {
            "name": row.name,
            "item_code": row.item_code,
            "batch": row.batch,
            "is_reserved": row.is_reserved,
            "reserved_qty": flt(row.reserved_qty, 3),
            "shortfall_qty": flt(row.shortfall_qty, 3),
            "reserved_on": str(row.reserved_on) if row.reserved_on else "",
        }
        for row in mp.material_mapping
    ]


def _get_batch_dims(batch_no):
    """(length, width, thickness) recorded on a Batch record itself."""
    d = frappe.db.get_value(
        "Batch", batch_no, ["custom_length", "custom_width", "custom_thickness"], as_dict=True
    ) or {}
    return flt(d.get("custom_length")), flt(d.get("custom_width")), flt(d.get("custom_thickness"))


def _calc_batch_qty(group, length, width, thickness, sec_qty, unit_weight):
    """Kg for a given item group + dimensions + Sec Qty (Nos) + unit weight.
    Single source of truth for the formula mirrored from material_planning.js's
    _recalc_batch_qty/_kg_per_nos — used both to apply a batch and to preview a
    prospective allocation before anything is mutated."""
    L, W, T, S, UW = flt(length), flt(width), flt(thickness), flt(sec_qty), flt(unit_weight)
    if group == "Structurals" and L and UW and S:
        return flt((L / 1000) * UW * S, 3)
    if group == "Plates" and L and W and T and UW and S:
        return flt((L / 1000) * (W / 1000) * T * UW * S, 3)
    if group == "Nuts and Bolts" and S and UW:
        return flt(S * UW, 3)
    return 0.0


def _precheck_batch_reassignment(mp, item_code, new_batch_no, group, length, width, thickness, sec_qty, unit_weight, required_qty):
    """Non-blocking pre-checks run BEFORE a batch is unreserved/applied/reserved:
    (1) does the new batch have enough free stock in the MP's warehouse, (2) does
    the qty the new allocation computes to match what this row actually requires.
    Both only warn (never frappe.throw) — same posture as the existing
    check_mapping_batch_availability dry run this complements."""
    warnings = []
    if not new_batch_no or not mp.for_warehouse:
        return warnings

    # Client change request Phase 6.2: warn immediately if the new batch is
    # blocked pending inspection -- the reassignment still goes through (the
    # user is allowed to pick a real batch ahead of time), but reservation
    # will actually be skipped a few steps later, so surface it here too
    # rather than only as a warning buried at the very end of the call.
    block_reason = _get_batch_inspection_block_reason(new_batch_no)
    if block_reason:
        warnings.append({"item_code": item_code or "", "batch": new_batch_no, "reason": block_reason})

    free_qty = flt(get_batch_stock_summary(new_batch_no, mp.for_warehouse, mp.name or "").get("free_qty"))
    prospective_qty = _calc_batch_qty(group, length, width, thickness, sec_qty, unit_weight)

    if prospective_qty and free_qty < prospective_qty:
        warnings.append({
            "item_code": item_code or "",
            "batch": new_batch_no,
            "shortfall_qty": flt(prospective_qty - free_qty, 3),
            "reason": _("Batch {0} has only {1} Kg free stock in {2}, less than the {3} Kg this allocation needs.")
                .format(new_batch_no, free_qty, mp.for_warehouse, prospective_qty),
        })

    if prospective_qty and required_qty and abs(flt(prospective_qty - required_qty, 3)) > 0.001:
        warnings.append({
            "item_code": item_code or "",
            "batch": new_batch_no,
            "shortfall_qty": flt(required_qty - prospective_qty, 3),
            "reason": _("New allocation for batch {0} computes to {1} Kg, which does not match the required {2} Kg for this row.")
                .format(new_batch_no, prospective_qty, required_qty),
        })
    return warnings


def _batch_change_remarks(item_code, old_batch, new_batch_no, material_issue_plan):
    text = _("Batch changed from {0} to {1} for {2}").format(
        old_batch or _("(none)"), new_batch_no or _("(none)"), item_code
    )
    if material_issue_plan:
        text += _(" via Material Issue Plan {0}").format(material_issue_plan)
    return text


@frappe.whitelist()
def reassign_batch(material_planning_name, source_table, row_name, new_batch_no,
                    dimensions=None, sec_qty=None, reserve_without_dimensions=0,
                    allocate_based_on_sec_qty=1, material_issue_plan=None):
    """Change the batch (and optionally dimensions/Sec Qty) already assigned to a
    Material Mapping / Available Raw Material row, in three explicit steps:
    (1) verify the new batch's stock and required-qty match (warn only), (2) unreserve
    the old assignment, (3) apply the new batch, re-validate availability, and
    re-reserve — delegating to Material Planning's own existing reservation functions
    throughout so this stays the single source of truth for reservation bookkeeping.
    Every reassignment is appended to batch_change_log for audit. Used by Material
    Issue Plan's "Update Batch" action; Material Planning's own grid keeps working
    unchanged alongside it."""
    if isinstance(dimensions, str):
        dimensions = json.loads(dimensions) if dimensions else {}
    dimensions = dimensions or {}
    reserve_without_dimensions = int(reserve_without_dimensions)
    allocate_based_on_sec_qty = int(allocate_based_on_sec_qty)

    if source_table not in ("Material Planning Material Mapping", "Material Planning Available Raw Material"):
        frappe.throw(_("Unsupported source table for batch reassignment: {0}").format(source_table))

    new_item = get_batch_item(new_batch_no) if new_batch_no else None
    new_item_data = (
        frappe.db.get_value("Item", new_item, ["custom_unit_weight", "custom_parent_item_group"], as_dict=True) or {}
        if new_item else {}
    )
    new_unit_weight = flt(new_item_data.get("custom_unit_weight"))

    mp = frappe.get_doc("Material Planning", material_planning_name)
    warnings = []

    if source_table == "Material Planning Material Mapping":
        row = next((r for r in mp.material_mapping if r.name == row_name), None)
        if not row:
            frappe.throw(_("Row not found in Material Mapping."))

        old_batch, old_sec_qty, old_qty = row.batch, flt(row.batch_sec_qty), flt(row.batch_calc_qty)

        # Step 1 — batch dims come from the Batch record itself (not user input);
        # Step 2 — compare against this row's own required qty.
        if new_batch_no:
            b_length, b_width, b_thickness = _get_batch_dims(new_batch_no)
            group = new_item_data.get("custom_parent_item_group") or row.parent_item_group
            precheck_sec_qty = flt(sec_qty) if sec_qty is not None else old_sec_qty
            warnings.extend(_precheck_batch_reassignment(
                mp, new_item or row.item_code, new_batch_no, group, b_length, b_width, b_thickness,
                precheck_sec_qty, new_unit_weight, flt(row.qty),
            ))

        if row.is_reserved:
            unreserve_batches(material_planning_name, json.dumps([row_name]))
            mp = frappe.get_doc("Material Planning", material_planning_name)
            row = next(r for r in mp.material_mapping if r.name == row_name)

        _apply_batch_to_mapping_row(row, new_batch_no, new_item, dimensions, sec_qty, reserve_without_dimensions,
                                     allocate_based_on_sec_qty)

        mp.append("batch_change_log", {
            "material_issue_plan": material_issue_plan or "",
            "source_table": source_table,
            "source_row": row_name,
            "item_code": row.item_code,
            "planned_item": row.planned_item if row.planned_item and row.planned_item != row.item_code else "",
            "old_batch": old_batch,
            "new_batch": new_batch_no or "",
            "old_sec_qty": old_sec_qty,
            "new_sec_qty": flt(row.batch_sec_qty),
            "old_qty": old_qty,
            "new_qty": flt(row.batch_calc_qty),
            "remarks": _batch_change_remarks(row.item_code, old_batch, new_batch_no, material_issue_plan),
        })
        mp.save(ignore_permissions=True)

    else:
        row = next((r for r in mp.available_raw_materials if r.name == row_name), None)
        if not row:
            frappe.throw(_("Row not found in Available Raw Materials."))

        old_batch, old_sec_qty, old_qty = row.batch_no, flt(row.sec_qty), flt(row.required_qty)
        item_code = row.item_code

        if new_batch_no:
            group = new_item_data.get("custom_parent_item_group") or row.parent_item_group
            length = flt(dimensions.get("length")) if dimensions.get("length") is not None else flt(row.length)
            width = flt(dimensions.get("width")) if dimensions.get("width") is not None else flt(row.width)
            thickness = flt(dimensions.get("thickness")) if dimensions.get("thickness") is not None else flt(row.thickness)
            precheck_sec_qty = flt(sec_qty) if sec_qty is not None else old_sec_qty
            warnings.extend(_precheck_batch_reassignment(
                mp, new_item or row.item_code, new_batch_no, group, length, width, thickness,
                precheck_sec_qty, new_unit_weight, flt(row.overall_required_qty or row.required_qty),
            ))

        if row.is_reserved:
            unreserve_exact_match_batches(material_planning_name, json.dumps([row_name]))
            mp = frappe.get_doc("Material Planning", material_planning_name)
            row = next(r for r in mp.available_raw_materials if r.name == row_name)

        planned_item_for_log = ""
        if new_item and new_item != row.item_code:
            # Cross-item substitution — an exact-match row can't represent "batch is a
            # different item", so it moves to Material Mapping, where planned_item
            # (the established alternate-item mechanism) records the substitution.
            mp.available_raw_materials = [r for r in mp.available_raw_materials if r.name != row_name]
            new_row = mp.append("material_mapping", {
                "item_number": row.item_number,
                "sales_order": row.sales_order,
                "item_code": row.item_code,
                "item_name": row.item_name,
                "duno_mark_no": row.duno_mark_no,
                "customer_drawing_number": row.customer_drawing_number,
                "qty": row.overall_required_qty or row.required_qty,
                "uom": row.uom,
                "sec_qty": row.sec_qty,
                "sec_uom": row.sec_uom,
                "parent_item_group": row.parent_item_group,
                "length": row.length,
                "width": row.width,
                "thickness": row.thickness,
            })
            _apply_batch_to_mapping_row(new_row, new_batch_no, new_item, dimensions, sec_qty, reserve_without_dimensions,
                                         allocate_based_on_sec_qty)
            new_sec_qty, new_qty = flt(new_row.batch_sec_qty), flt(new_row.batch_calc_qty)
            planned_item_for_log = new_item
        else:
            row.batch_no = new_batch_no or ""
            if dimensions.get("length") is not None:
                row.length = flt(dimensions.get("length"))
            if dimensions.get("width") is not None:
                row.width = flt(dimensions.get("width"))
            if dimensions.get("thickness") is not None:
                row.thickness = flt(dimensions.get("thickness"))
            if sec_qty is not None:
                row.sec_qty = flt(sec_qty)
            new_sec_qty, new_qty = flt(row.sec_qty), flt(row.required_qty)

        mp.append("batch_change_log", {
            "material_issue_plan": material_issue_plan or "",
            "source_table": source_table,
            "source_row": row_name,
            "item_code": item_code,
            "planned_item": planned_item_for_log,
            "old_batch": old_batch,
            "new_batch": new_batch_no or "",
            "old_sec_qty": old_sec_qty,
            "new_sec_qty": new_sec_qty,
            "old_qty": old_qty,
            "new_qty": new_qty,
            "remarks": _batch_change_remarks(item_code, old_batch, new_batch_no, material_issue_plan),
        })
        mp.save(ignore_permissions=True)

    # Dry-run validation — the same check the JS already runs before/after save.
    mp = frappe.get_doc("Material Planning", material_planning_name)
    warnings.extend(check_mapping_batch_availability(mp.as_dict()))

    # Finalize the new reservation via the existing bulk reserve functions — both
    # only ever touch currently-unreserved rows that carry a batch, so calling them
    # broadly here is safe and won't disturb any other already-reserved row.
    #
    # If every remaining unreserved row is blocked pending inspection (Phase 6.2),
    # reserve_batches/reserve_exact_match_batches throw rather than silently no-op
    # — downgrade THAT specific throw to a warning instead of letting it abort this
    # whole call. The batch reassignment itself (dimensions/batch already applied
    # and saved above) must still succeed; the user picked a real batch, it just
    # can't be reserved yet -- that's a warning to surface, not a failure to roll
    # back. Any OTHER validation error (e.g. missing warehouse) still propagates
    # normally, unchanged from before this phase.
    if any(not r.is_reserved and r.batch for r in mp.material_mapping):
        try:
            reserve_batches(material_planning_name)
        except frappe.ValidationError as e:
            if "blocked pending inspection completion" not in str(e):
                raise
            warnings.append({"reason": str(e)})
        mp = frappe.get_doc("Material Planning", material_planning_name)
    if any(not r.is_reserved and r.batch_no for r in mp.available_raw_materials):
        try:
            reserve_exact_match_batches(material_planning_name)
        except frappe.ValidationError as e:
            if "blocked pending inspection completion" not in str(e):
                raise
            warnings.append({"reason": str(e)})

    return {"warnings": warnings}


def _apply_batch_to_mapping_row(row, new_batch_no, new_item, dimensions, sec_qty, reserve_without_dimensions,
                                 allocate_based_on_sec_qty=1):
    """Set a Material Planning Material Mapping row's batch + recompute its
    batch_calc_qty, mirroring material_planning.js's _recalc_batch_qty formula."""
    row.batch = new_batch_no or ""
    row.planned_item = new_item or ""
    row.batch_mapped = "Mapped" if new_batch_no else "Not Mapped"
    row.reserve_without_dimensions = reserve_without_dimensions
    row.allocate_based_on_sec_qty = allocate_based_on_sec_qty

    if dimensions.get("length") is not None:
        row.length = flt(dimensions.get("length"))
    if dimensions.get("width") is not None:
        row.width = flt(dimensions.get("width"))
    if dimensions.get("thickness") is not None:
        row.thickness = flt(dimensions.get("thickness"))
    if sec_qty is not None:
        row.sec_qty = flt(sec_qty)

    if not new_batch_no:
        row.batch_length = row.batch_width = row.batch_thickness = 0.0
        row.batch_unit_weight = 0.0
        row.batch_parent_item_group = ""
        row.batch_sec_qty = 0.0
        row.batch_calc_qty = 0.0
        return

    row.batch_length, row.batch_width, row.batch_thickness = _get_batch_dims(new_batch_no)

    item_data = (
        frappe.db.get_value("Item", new_item, ["custom_unit_weight", "custom_parent_item_group"], as_dict=True) or {}
        if new_item else {}
    )
    row.batch_unit_weight = flt(item_data.get("custom_unit_weight"))
    row.batch_parent_item_group = item_data.get("custom_parent_item_group") or ""
    row.batch_sec_qty = flt(sec_qty) if sec_qty is not None else flt(row.batch_sec_qty)

    row.batch_calc_qty = _calc_batch_qty(
        row.batch_parent_item_group, row.batch_length, row.batch_width, row.batch_thickness,
        row.batch_sec_qty, row.batch_unit_weight,
    )


@frappe.whitelist()
def _test_simulate_se_release(batch_nos, se_type="Material Issue"):
    """Test helper: simulate a Stock Entry submit that consumes the given batch(es)."""
    from manufyxinvenzaerp.production_management.stock_entry import _release_material_planning_reservations
    if isinstance(batch_nos, str):
        batch_nos = json.loads(batch_nos)

    class _FakeRow:
        def __init__(self, b): self.batch_no = b; self.is_finished_item = False
        def get(self, k, d=None): return getattr(self, k, d)

    class _FakeSE:
        def __init__(self, t, bs): self.stock_entry_type = t; self.items = [_FakeRow(b) for b in bs]

    _release_material_planning_reservations(_FakeSE(se_type, batch_nos))
    frappe.db.commit()
    return "OK"


@frappe.whitelist()
def make_production_plan(material_planning_name):
    """Create a draft Production Plan from a Material Planning document."""
    mp = frappe.get_doc("Material Planning", material_planning_name)
    if mp.docstatus == 2:
        frappe.throw(_("Cannot create a Production Plan from a cancelled Material Planning."))
    if not mp.bom_items:
        frappe.throw(_("No BOM items found on this Material Planning."))

    if mp.production_plan and frappe.db.exists("Production Plan", mp.production_plan):
        frappe.throw(
            _("Production Plan {0} already exists for this Material Planning. "
              "Open it or clear the link before creating a new one.").format(mp.production_plan)
        )

    pp = frappe.new_doc("Production Plan")
    pp.custom_type = "Internal Job"
    pp.company = mp.company
    pp.posting_date = today()
    pp.for_warehouse = mp.for_warehouse
    pp.get_items_from = "Sales Order"

    from manufyxinvenzaerp.production_management.production_utils import get_routing_operations_for_bom

    for row in mp.bom_items:
        item_code = row.item_code or frappe.db.get_value("BOM", row.bom_no, "item")
        item_name = row.item_name or frappe.db.get_value("Item", item_code, "item_name") or item_code
        stock_uom = frappe.db.get_value("Item", item_code, "stock_uom") or "Nos"
        planned_qty = flt(row.qty_to_manufacture) or 1
        pp.append("po_items", {
            "item_code": item_code,
            "item_name": item_name,
            "bom_no": row.bom_no,
            "planned_qty": planned_qty,
            "stock_uom": stock_uom,
            "sales_order": row.sales_order or "",
            "custom_customer": row.customer or "",
            "warehouse": mp.for_warehouse or "",
            "custom_drawing": row.drawing or "",
            "custom_duno_mark_no": row.duno_mark_no or 0,
            "custom_material_planning": material_planning_name,
            "custom_customer_drawing_number": row.customer_drawing_number or "",
        })

    # Populate Process Planning from the first BOM's operations
    if mp.bom_items:
        first_bom = mp.bom_items[0].bom_no
        if first_bom:
            for op in get_routing_operations_for_bom(first_bom):
                pp.append("custom_process_planning", {
                    "operation_name": op.get("operation"),
                    "work_type": "Internal Jobcard",
                })

    pp.insert(ignore_permissions=True)
    frappe.db.set_value("Material Planning", material_planning_name, "production_plan", pp.name)
    return pp.name


@frappe.whitelist()
def make_material_request(material_planning_name, selected_items):
    """Create a draft Material Request for selected unavailable items."""
    mp = frappe.get_doc("Material Planning", material_planning_name)
    if not mp.unavailable_items:
        frappe.throw(_("No unavailable items found on this Material Planning."))

    if isinstance(selected_items, str):
        selected_items = json.loads(selected_items)

    selected_set = set(selected_items)
    rows_to_request = [r for r in mp.unavailable_items if r.item_code in selected_set]

    if not rows_to_request:
        frappe.throw(_("Select at least one item to create a Material Request."))

    # Block if any active MR already exists for this Material Planning -- lists
    # ALL of them in the message, not just the first found (a Material Planning
    # can have more than one, e.g. from the separate multi-supplier manual MR
    # flow, even though this specific auto-create path only ever makes one).
    existing_mrs = frappe.get_all(
        "Material Request",
        filters={
            "custom_material_planning": material_planning_name,
            "status": ["not in", ["Cancelled", "Stopped"]],
        },
        fields=["name", "status"],
    )
    if existing_mrs:
        frappe.throw(
            _("You already have {0} active Material Request(s) linked to this plan: {1}. "
              "Cancel them first before creating a new one.").format(
                len(existing_mrs),
                ", ".join(f"{r.name} ({r.status})" for r in existing_mrs),
            )
        )

    mr = frappe.new_doc("Material Request")
    mr.material_request_type = "Purchase"
    mr.company = mp.company
    mr.transaction_date = today()
    mr.schedule_date = today()
    mr.set("items", [])

    for row in rows_to_request:
        order_item = row.alternate_item or row.item_code
        item_data = frappe.db.get_value(
            "Item", order_item,
            ["item_name", "stock_uom", "custom_parent_item_group", "custom_unit_weight"],
            as_dict=True,
        ) or {}

        order_item_name = item_data.get("item_name") or order_item
        uom             = item_data.get("stock_uom") or row.uom or "Nos"
        group           = item_data.get("custom_parent_item_group") or ""

        # Dimensions — alternate item values take priority
        if row.alternate_item:
            use_length      = flt(row.alternate_length)
            use_width       = flt(row.alternate_width)
            use_thickness   = flt(row.alternate_thickness)
            use_sec_qty     = flt(row.alternate_sec_qty) or flt(row.sec_qty)
            use_unit_weight = flt(row.alternate_unit_weight) or flt(item_data.get("custom_unit_weight"))
        else:
            use_length      = flt(row.length)
            use_width       = flt(row.width)
            use_thickness   = flt(row.thickness)
            use_sec_qty     = flt(row.sec_qty)
            use_unit_weight = flt(row.unit_weight)

        # Derive sec_qty from dimensions+weight if it's 0 but all other dimensions are
        # present — handles stale unavailable_items rows saved before dimensions were complete.
        if not use_sec_qty:
            _qty = flt(row.qty)
            if group == "Plates" and use_length and use_width and use_thickness and use_unit_weight and _qty:
                _denom = (use_length / 1000) * (use_width / 1000) * use_thickness * use_unit_weight
                if _denom:
                    use_sec_qty = _nos_from_weight(_qty, _denom)
            elif group == "Structurals" and use_length and use_unit_weight and _qty:
                _denom = (use_length / 1000) * use_unit_weight
                if _denom:
                    use_sec_qty = _nos_from_weight(_qty, _denom)

        # Validate mandatory dimensions by parent item group
        if group == "Structurals":
            missing = []
            if not use_length:      missing.append("Length")
            if not use_sec_qty:     missing.append("Sec Qty")
            if not use_unit_weight: missing.append("Unit Weight")
            if missing:
                frappe.throw(
                    _("Item {0}: {1} required for Structurals formula.").format(
                        order_item, ", ".join(missing)
                    )
                )
        elif group == "Plates":
            missing = []
            if not use_length:      missing.append("Length")
            if not use_width:       missing.append("Width")
            if not use_thickness:   missing.append("Thickness")
            if not use_sec_qty:     missing.append("Sec Qty")
            if not use_unit_weight: missing.append("Unit Weight")
            if missing:
                frappe.throw(
                    _("Item {0}: {1} required for Plates formula.").format(
                        order_item, ", ".join(missing)
                    )
                )

        # Calculate qty using the same formula as Purchase Order
        qty = flt(row.qty) or 1
        if group == "Structurals" and use_length and use_unit_weight and use_sec_qty:
            qty = (use_length / 1000) * use_unit_weight * use_sec_qty
        elif group == "Plates" and all([use_length, use_width, use_thickness, use_unit_weight, use_sec_qty]):
            qty = (use_length / 1000) * (use_width / 1000) * use_thickness * use_unit_weight * use_sec_qty
        elif group == "Nuts and Bolts" and use_unit_weight and qty:
            use_sec_qty = flt(qty * use_unit_weight, 3)

        dim_parts = []
        if use_length:    dim_parts.append(f"L={use_length}mm")
        if use_width:     dim_parts.append(f"W={use_width}mm")
        if use_thickness: dim_parts.append(f"T={use_thickness}mm")
        dim_str = ", ".join(dim_parts)
        description = f"{order_item_name}" + (f" ({dim_str})" if dim_str else "")
        if row.alternate_item:
            description += f" [Alt for {row.item_code}]"

        mr.append("items", {
            "item_code":                order_item,
            "item_name":                order_item_name,
            "qty":                      qty,
            "uom":                      uom,
            "stock_uom":                uom,
            "conversion_factor":        1,
            "schedule_date":            today(),
            "warehouse":                mp.for_warehouse or "",
            "description":              description,
            "custom_length":            use_length,
            "custom_width":             use_width,
            "custom_thickness":         use_thickness,
            "custom_unit_weight":       use_unit_weight,
            "custom_sec_qty":           use_sec_qty,
            "custom_parent_item_group": group,
            "custom_drawing":                 row.drawing or "",
            "custom_duno_mark_no":            row.duno_mark_no or "",
            "custom_customer_drawing_number": row.customer_drawing_number or "",
            "custom_sales_order":             row.sales_order or "",
        })

    mr.custom_material_planning = material_planning_name
    mr.insert(ignore_permissions=True)
    return mr.name


@frappe.whitelist()
def make_material_request_from_consolidate(material_planning_name, selected_items):
    """Create a draft Material Request from selected Consolidate Item rows (client
    change request Phase 2.4) — Consolidate Item is now the purchasing-facing table,
    deduped by item_code across every drawing/sales order that needed it. Simpler
    than make_material_request: purchase_kg is already the auto-calculated Kg
    quantity (Material Planning Consolidate Item.recalculate), so no need to
    re-derive it from Length/Width/Thickness/Sec Qty here.

    Consolidate Item's own Alternate Item section (mirrors Unavailable Item's,
    added so a bulk purchasing decision can be made once for the whole
    consolidated line): when set, the MR line orders the ALTERNATE item, not
    the original item_code. Unlike Unavailable Item, there are no separate
    alternate_* dimension fields -- the row's own Length/Width/Thickness/Sec
    Qty are reused (reinterpreted as describing the alternate item), only the
    Unit Weight/Parent Item Group are looked up separately since the
    alternate item can differ from the original on those. allocate_pr_stock_to_mp
    fans the received batch back out across every original Unavailable Item
    row this line was consolidated from once that MR is fulfilled."""
    mp = frappe.get_doc("Material Planning", material_planning_name)
    if not mp.consolidate_items:
        frappe.throw(_("No consolidated items found on this Material Planning."))

    if isinstance(selected_items, str):
        selected_items = json.loads(selected_items)

    selected_set = set(selected_items)
    rows_to_request = [r for r in mp.consolidate_items if r.item_code in selected_set]

    if not rows_to_request:
        frappe.throw(_("Select at least one item to create a Material Request."))

    existing_mr = frappe.db.get_value(
        "Material Request",
        {
            "custom_material_planning": material_planning_name,
            "status": ["not in", ["Cancelled", "Stopped"]],
        },
        ["name", "status"],
        as_dict=True,
    )
    if existing_mr:
        frappe.throw(
            _("You already have an active Material Request {0} ({1}) linked to this plan. "
              "Cancel it first before creating a new one.").format(
                existing_mr.name, existing_mr.status
            )
        )

    mr = frappe.new_doc("Material Request")
    mr.material_request_type = "Purchase"
    mr.company = mp.company
    mr.transaction_date = today()
    mr.schedule_date = today()
    mr.set("items", [])

    for row in rows_to_request:
        order_item = row.alternate_item or row.item_code
        item_data = frappe.db.get_value(
            "Item", order_item, ["item_name", "stock_uom"], as_dict=True
        ) or {}
        order_item_name = item_data.get("item_name") or row.item_name or order_item
        uom = item_data.get("stock_uom") or row.sec_uom or "Nos"

        use_length, use_width, use_thickness = flt(row.length), flt(row.width), flt(row.thickness)
        use_sec_qty = flt(row.sec_qty)
        qty = flt(row.purchase_kg) or flt(row.required_kg) or 1
        if row.alternate_item:
            use_unit_weight = flt(row.alternate_unit_weight)
            group = row.alternate_parent_item_group or ""
        else:
            use_unit_weight = flt(row.unit_weight)
            group = row.parent_item_group or ""

        dim_parts = []
        if use_length:    dim_parts.append(f"L={use_length}mm")
        if use_width:     dim_parts.append(f"W={use_width}mm")
        if use_thickness: dim_parts.append(f"T={use_thickness}mm")
        dim_str = ", ".join(dim_parts)
        description = f"{order_item_name}" + (f" ({dim_str})" if dim_str else "")
        if row.alternate_item:
            description += f" [Alt for {row.item_code}]"

        mr.append("items", {
            "item_code":                order_item,
            "item_name":                order_item_name,
            "qty":                      qty,
            "uom":                      uom,
            "stock_uom":                uom,
            "conversion_factor":        1,
            "schedule_date":            today(),
            "warehouse":                mp.for_warehouse or "",
            "description":              description,
            "custom_length":            use_length,
            "custom_width":             use_width,
            "custom_thickness":         use_thickness,
            "custom_unit_weight":       use_unit_weight,
            "custom_sec_qty":           use_sec_qty,
            "custom_parent_item_group": group,
        })

    mr.custom_material_planning = material_planning_name
    mr.insert(ignore_permissions=True)
    return mr.name


def _update_so_difference_kg_for_pair(sales_order, duno_mark_no):
    """Sum (batch_calc_qty - qty) across ALL Material Planning Material Mapping rows for this
    (sales_order, duno_mark_no) pair, and write it into Difference Kg on every matching Sales
    Order DUNO Item row. Returns the number of DUNO rows updated. Shared by the MP-triggered
    `update_so_difference_kg` button and Drawing's customer-weight-edit cascade."""
    rows = frappe.db.get_all(
        "Material Planning Material Mapping",
        filters={
            "sales_order": sales_order,
            "duno_mark_no": duno_mark_no,
            "batch_mapped": "Mapped",
        },
        fields=["batch_calc_qty", "qty"],
    )
    diff_kg = flt(sum(flt(r.batch_calc_qty) - flt(r.qty) for r in rows), 3)

    duno_rows = frappe.db.get_all(
        "Sales Order DUNO Item",
        filters={"parent": sales_order, "duno_mark_no": duno_mark_no},
        fields=["name"],
    )
    for duno_row in duno_rows:
        frappe.db.set_value(
            "Sales Order DUNO Item",
            duno_row.name,
            "difference_kg",
            diff_kg,
            update_modified=False,
        )
    return len(duno_rows)


@frappe.whitelist()
def update_so_difference_kg(mp_name):
    """Sum (batch_calc_qty - qty) per (sales_order, duno_mark_no) across ALL Material Planning
    documents and write the result into the Difference Kg field on Sales Order DUNO Item rows.
    Called from the 'Update Difference Kg in Sales Order' button."""
    mp = frappe.get_doc("Material Planning", mp_name)

    # Collect unique (sales_order, duno_mark_no) pairs touched by this MP
    pairs = set()
    for row in (mp.material_mapping or []):
        if row.sales_order and row.duno_mark_no:
            pairs.add((row.sales_order, row.duno_mark_no))

    if not pairs:
        frappe.throw(_("No Material Mapping rows with Sales Order and DUNO/Mark No found."))

    updated = 0
    for sales_order, duno_mark_no in pairs:
        updated += _update_so_difference_kg_for_pair(sales_order, duno_mark_no)

    frappe.db.commit()
    return {"updated": updated}


def unlink_material_request_on_cancel(doc, method=None):
    """Clear the Material Planning link when an MR is cancelled or deleted."""
    if doc.get("custom_material_planning"):
        frappe.db.set_value("Material Request", doc.name, "custom_material_planning", "")


@frappe.whitelist()
def auto_purchase_from_mp(material_planning_name):
    """One-click MR → submit → PO → submit → PR → submit for all consolidated items.
    Reads custom_auto_purchase_supplier and for_warehouse from the MP.

    Sources from consolidate_items (not unavailable_items) -- same move already made
    for the "Create Material Request" button (client change request Phase 2.4):
    Consolidate Item is the purchasing-facing table, deduped by item_code across
    every drawing/sales order that needed it.
    """
    from frappe.utils import today
    from erpnext.stock.doctype.material_request.material_request import (
        make_purchase_order as _mr_to_po,
    )
    from erpnext.buying.doctype.purchase_order.purchase_order import (
        make_purchase_receipt as _po_to_pr,
    )

    mp = frappe.get_doc("Material Planning", material_planning_name)
    if not frappe.has_permission("Material Planning", "write", doc=mp):
        frappe.throw(_("Not permitted to run Auto Purchase on this Material Planning"), frappe.PermissionError)

    supplier  = mp.get("custom_auto_purchase_supplier")
    warehouse = mp.get("for_warehouse")

    if not supplier:
        frappe.throw(_("Please set the Supplier for Auto Purchase on this Material Planning."))
    if not warehouse:
        frappe.throw(_("Please set the Raw Materials Warehouse on this Material Planning."))
    if not mp.consolidate_items:
        frappe.throw(_("No consolidated items found. Run stock check first."))

    # Step 1 — Create Material Request (draft) for all consolidated items, then submit
    all_item_codes = list({r.item_code for r in mp.consolidate_items})
    mr_name = make_material_request_from_consolidate(material_planning_name, json.dumps(all_item_codes))
    mr = frappe.get_doc("Material Request", mr_name)
    mr.submit()
    frappe.db.commit()

    # Step 2 — Map MR → PO (ERPNext mapper), set supplier, insert, submit
    po = _mr_to_po(mr_name)
    po.supplier        = supplier
    po.schedule_date   = today()
    po.transaction_date = today()
    po.insert(ignore_permissions=True)
    frappe.db.commit()
    po.submit()
    frappe.db.commit()

    # Step 3 — Map PO → PR (ERPNext mapper), override warehouse, insert, submit
    pr = _po_to_pr(po.name)
    for item in pr.get("items") or []:
        item.warehouse = warehouse
    pr.insert(ignore_permissions=True)
    frappe.db.commit()
    pr.submit()
    frappe.db.commit()

    return {"mr": mr_name, "po": po.name, "pr": pr.name}


# ---------------------------------------------------------------------------
# Batch Mapping Completed validation
# ---------------------------------------------------------------------------

def _collect_batch_mapping_issues(mp):
    """Return a list of human-readable issue strings for the given MP doc.
    Empty list = everything is clean and the mapping can be marked complete."""
    issues = []
    warehouse = mp.for_warehouse or ""

    # 1. Items in Material Mapping with no batch selected
    for r in (mp.material_mapping or []):
        if r.item_code and not r.batch:
            issues.append(
                _("Material Mapping Row {0} ({1} — {2}): No batch selected.").format(
                    r.idx, r.item_code, r.duno_mark_no or "-"
                )
            )

    # 2. Items in Exact Match with no batch selected
    for r in (mp.available_raw_materials or []):
        if r.item_code and not r.batch_no:
            issues.append(
                _("Exact Match Row {0} ({1} — {2}): No batch selected.").format(
                    r.idx, r.item_code, r.duno_mark_no or "-"
                )
            )

    # 3. Cross-table duplicate batches
    mm_batches = {r.batch: r.idx for r in (mp.material_mapping or []) if r.batch}
    for r in (mp.available_raw_materials or []):
        if r.batch_no and r.batch_no in mm_batches:
            issues.append(
                _("Batch <b>{0}</b> appears in both Material Mapping (Row {1}) and Exact Match (Row {2}). "
                  "Remove it from one table.").format(r.batch_no, mm_batches[r.batch_no], r.idx)
            )

    # 4. Material Mapping rows with batch but not reserved
    for r in (mp.material_mapping or []):
        if r.batch and not r.is_reserved:
            issues.append(
                _("Material Mapping Row {0} — Batch <b>{1}</b> ({2}): Batch selected but not reserved. "
                  "Run <b>Reserve Batches</b> first.").format(r.idx, r.batch, r.item_code)
            )

    # 5. Exact Match rows with batch but not reserved
    for r in (mp.available_raw_materials or []):
        if r.batch_no and not r.is_reserved:
            issues.append(
                _("Exact Match Row {0} — Batch <b>{1}</b> ({2}): Batch selected but not reserved. "
                  "Run <b>Reserve Exact Match Batches</b> first.").format(r.idx, r.batch_no, r.item_code)
            )

    # 6. Over-allocation: total reserved across ALL MPs vs actual stock
    if warehouse:
        seen_batches = set()
        for r in (mp.material_mapping or []):
            if r.batch and r.is_reserved:
                seen_batches.add(r.batch)
        for r in (mp.available_raw_materials or []):
            if r.batch_no and r.is_reserved:
                seen_batches.add(r.batch_no)

        for batch_no in seen_batches:
            stock = _get_batch_total_stock(batch_no, warehouse)
            mm_res = flt(frappe.db.sql(
                "SELECT COALESCE(SUM(reserved_qty),0) FROM `tabMaterial Planning Material Mapping` "
                "WHERE batch = %s AND is_reserved = 1", batch_no
            )[0][0])
            arm_res = flt(frappe.db.sql(
                "SELECT COALESCE(SUM(reserved_qty),0) FROM `tabMaterial Planning Available Raw Material` "
                "WHERE batch_no = %s AND is_reserved = 1", batch_no
            )[0][0])
            total_res = flt(mm_res + arm_res, 3)
            if flt(total_res, 3) > flt(stock, 3):
                over = flt(total_res - stock, 3)
                issues.append(
                    _("Batch <b>{0}</b>: Over-allocated by <b>{1} Kg</b> "
                      "(Stock: {2} Kg, Total Reserved across all plans: {3} Kg).").format(
                        batch_no, over, flt(stock, 3), total_res
                    )
                )

        # 7. Reserve-without-dimensions Nos check: batch_sec_qty must cover sec_qty per row
        for r in (mp.material_mapping or []):
            if (r.batch and r.is_reserved and r.reserve_without_dimensions
                    and r.batch_parent_item_group in ("Structurals", "Plates")):
                batch_total_nos = flt(frappe.db.get_value("Batch", r.batch, "custom_sec_qty") or 0)
                if batch_total_nos and flt(r.batch_sec_qty, 3) > flt(batch_total_nos, 3):
                    issues.append(
                        _("Material Mapping Row {0} — Batch <b>{1}</b> ({2}): "
                          "Allocated Nos ({3}) exceeds batch stock Nos ({4}).").format(
                            r.idx, r.batch, r.item_code,
                            flt(r.batch_sec_qty, 3), batch_total_nos
                        )
                    )

    # 8. Items with no stock at all (unavailable_items)
    unavail = [r for r in (mp.unavailable_items or []) if r.item_code]
    if unavail:
        item_list = ", ".join(
            f"{r.item_code} (Row {r.idx})" for r in unavail[:10]
        )
        if len(unavail) > 10:
            item_list += _(" … and {0} more").format(len(unavail) - 10)
        issues.append(
            _("{0} item(s) in <b>Unavailable Items</b> have no stock assigned: {1}. "
              "Purchase and map them before completing.").format(len(unavail), item_list)
        )

    return issues


@frappe.whitelist()
def complete_batch_mapping(mp_name):
    """Validate all mapping conditions and, if clean, set status to
    'Batch Mapping Completed'. Returns {status, issues} to the client."""
    mp = frappe.get_doc("Material Planning", mp_name)
    issues = _collect_batch_mapping_issues(mp)
    if not issues:
        frappe.db.set_value("Material Planning", mp_name, "planning_status", "Batch Mapping Completed")
        return {"status": "ok", "issues": []}
    return {"status": "issues", "issues": issues}
