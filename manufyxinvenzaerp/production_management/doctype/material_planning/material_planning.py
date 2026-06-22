import json

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import ceil, flt, now, today


class MaterialPlanning(Document):
    def validate(self):
        self.raw_materials = [r for r in (self.raw_materials or []) if r.item_code]
        self.available_raw_materials = [r for r in (self.available_raw_materials or []) if r.item_code]
        self.material_mapping = [r for r in (self.material_mapping or []) if r.item_code]
        self.unavailable_items = [r for r in (self.unavailable_items or []) if r.item_code]
        if self.material_mapping and self.for_warehouse:
            self._validate_batch_calc_qty()

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
            reserved_by_others = _get_batch_reserved_by_others(row.batch, mp_name)
            allocated_so_far = batch_allocated.get(row.batch, 0.0)
            available = max(0.0, batch_stock - reserved_by_others - allocated_so_far)

            if row.reserve_without_dimensions:
                # Bypass dimension/calc check — validate Required Qty directly
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
                shortfall_warnings.append(
                    _("Row {0}: <b>{1}</b> needs <b>{2} Kg</b>, "
                      "but alternate item <b>{3}</b> mapped only for <b>{4} Kg</b>.").format(
                        row.idx, row.item_code,
                        flt(required_qty, 3), alternate, flt(batch_calc_qty, 3)
                    )
                )

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

    for bom_row in doc.get("bom_items") or []:
        bom_no = bom_row.get("bom_no")
        planned_qty = flt(bom_row.get("qty_to_manufacture")) or 1
        duno_mark_no = bom_row.get("duno_mark_no")
        customer_drawing_number = bom_row.get("customer_drawing_number") or ""
        sales_order = bom_row.get("sales_order") or ""

        if not bom_no:
            continue

        item_details = get_exploded_items({}, company, bom_no, False, planned_qty=planned_qty)

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
                    sec_qty = ceil(round(qty / denom, 9))
            elif group == "Plates" and length and width and thickness and unit_weight:
                denom = (length / 1000) * (width / 1000) * thickness * unit_weight
                if denom:
                    sec_qty = ceil(round(qty / denom, 9))
            elif group == "Nuts and Bolts" and unit_weight:
                sec_qty = flt(qty * unit_weight, 3)

            sec_uom = (
                frappe.db.get_value("Item", detail.get("item_code"), "custom_secondary_uom") or ""
            )

            rows.append({
                "item_number": detail.get("custom_item_number") or "",
                "sales_order": sales_order,
                "item_code": detail.get("item_code"),
                "item_name": detail.get("item_name"),
                "bom_no": bom_no,
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
    from manufyxinvenzaerp.production_plan_management.production_plan import get_sbb_available_qty

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
                    base_row["sec_qty"] = ceil(round(_qty / _denom, 9))
            elif _grp == "Structurals" and _len and _uwt and _qty:
                _denom = (_len / 1000) * _uwt
                if _denom:
                    base_row["sec_qty"] = ceil(round(_qty / _denom, 9))

        if has_batch:
            # ── Batch item: match by exact dimensions via SBB ──────────────
            dimensions = {
                "custom_length": flt(row.get("length")),
                "custom_thickness": flt(row.get("thickness")),
                "custom_width": flt(row.get("width")),
            }

            _, raw_matched_batches = get_sbb_available_qty(item_code, warehouse, dimensions, location=location)

            # Capture each batch's TOTAL stock Kg and TOTAL Nos before any allocation —
            # needed to split Sec Qty (Nos) proportionally to the Kg each row reserves.
            for b in raw_matched_batches:
                batch_total_kg.setdefault(b["batch_no"], flt(b["qty"]))
                batch_total_sec.setdefault(b["batch_no"], flt(b.get("custom_sec_qty")))
                if b["batch_no"] not in batch_remaining:
                    reserved_by_others = _get_batch_reserved_by_others(b["batch_no"], mp_name)
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
                        "batch_no": bn,
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
                if shortage > 0:
                    available_sec_qty = sum(flt(b.get("custom_sec_qty")) for b in matched_batches)
                    required_sec_qty = flt(row.get("sec_qty"))
                    if not available_sec_qty and required_sec_qty and required_qty:
                        # batch has no custom_sec_qty — derive NOS from Kg ratio
                        # use flt(..., 0) (round to nearest) to avoid ceil float over-count
                        available_sec_qty = flt(available_qty / (required_qty / required_sec_qty), 0)
                    shortfall_nos = max(0.0, required_sec_qty - available_sec_qty)
                    shortfall_row = dict(base_row)
                    shortfall_row["qty"] = flt(shortage, 3)
                    shortfall_row["sec_qty"] = flt(shortfall_nos)
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
            total_stock = _get_non_batch_stock(item_code, warehouse)
            reserved_by_others = _get_non_batch_reserved_by_others(item_code, warehouse, mp_name)
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
                    "batch_no": "",
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
                    reserved_by_others = _get_batch_reserved_by_others(b["batch_no"], mp_name)
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
                        "batch_no": bn,
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
                    "batch_no": "",
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
      - Rows WITH a batch assigned  → stay in material_mapping
      - Rows WITHOUT a batch        → move to unavailable_items
    Returns updated material_mapping and unavailable_items lists.
    """
    if isinstance(doc, str):
        doc = frappe._dict(json.loads(doc))

    mapped = []
    unavailable = []

    for row in doc.get("material_mapping") or []:
        base = {
            "item_number": row.get("item_number") or "",
            "sales_order": row.get("sales_order") or "",
            "item_code": row.get("item_code"),
            "item_name": row.get("item_name"),
            "bom_no": row.get("bom_no"),
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
            "alternate_item": row.get("alternate_item") or "",
        }
        if row.get("batch"):
            mapped.append(dict(
                base,
                batch=row.get("batch"),
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
            ))
        else:
            unavailable.append(base)

    return {
        "material_mapping": mapped,
        "unavailable_items": unavailable,
    }


@frappe.whitelist()
def get_batch_reservation_summary(batch_no):
    """Return all active reservations for a batch, enriched with SO customer and project."""
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


def _get_batch_reserved_by_others(batch_no, exclude_mp):
    """Return total reserved_qty committed to other Material Planning docs for this batch.

    Checks both material_mapping (field: batch) and available_raw_materials
    (field: batch_no) so reservations in either table are counted.
    """
    mm = frappe.db.sql(
        """
        SELECT COALESCE(SUM(reserved_qty), 0) AS total
        FROM `tabMaterial Planning Material Mapping`
        WHERE batch = %s AND is_reserved = 1 AND parent != %s
        """,
        (batch_no, exclude_mp),
        as_dict=True,
    )
    arm = frappe.db.sql(
        """
        SELECT COALESCE(SUM(reserved_qty), 0) AS total
        FROM `tabMaterial Planning Available Raw Material`
        WHERE batch_no = %s AND is_reserved = 1 AND parent != %s
        """,
        (batch_no, exclude_mp),
        as_dict=True,
    )
    return flt(mm[0].total if mm else 0) + flt(arm[0].total if arm else 0)


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
    if not mp.material_mapping:
        frappe.throw(_("No items in Material Mapping to reserve."))
    if not mp.for_warehouse:
        frappe.throw(_("Set 'Raw Materials Warehouse' on the Material Planning before reserving."))

    reserved_count = 0
    partial_rows = []
    # Track qty allocated within this doc so the same batch used in multiple
    # rows is not double-counted against available stock.
    batch_allocated_here = {}

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

        batch_calc_qty = flt(row.batch_calc_qty)
        required_qty = flt(row.qty)

        if row.reserve_without_dimensions and row.batch_parent_item_group in ("Structurals", "Plates"):
            # Skip dimension-based calc; reserve Required Qty directly
            to_reserve = required_qty
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
        reserved_by_others = _get_batch_reserved_by_others(row.batch, material_planning_name)
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
        frappe.throw(_("All rows with a batch are already reserved."))

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
    }


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
            batch_stock = _get_batch_total_stock(row.batch_no, mp.for_warehouse)
            reserved_by_others = _get_batch_reserved_by_others(row.batch_no, material_planning_name)
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
        frappe.throw(_("All rows are already reserved."))

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

    for row in doc.get("material_mapping") or []:
        batch = row.get("batch") if isinstance(row, dict) else getattr(row, "batch", None)
        if not batch:
            continue

        base_qty = flt(row.get("qty") if isinstance(row, dict) else row.qty)
        batch_calc_qty = flt(row.get("batch_calc_qty") if isinstance(row, dict) else getattr(row, "batch_calc_qty", 0))
        group = (row.get("batch_parent_item_group") if isinstance(row, dict) else getattr(row, "batch_parent_item_group", "")) or ""
        reserve_without_dim = int(row.get("reserve_without_dimensions") if isinstance(row, dict) else getattr(row, "reserve_without_dimensions", 0))
        if reserve_without_dim and group in ("Structurals", "Plates"):
            required_qty = base_qty
        else:
            required_qty = batch_calc_qty if (batch_calc_qty > 0 and group in ("Structurals", "Plates")) else base_qty

        batch_stock = _get_batch_total_stock(batch, warehouse)
        reserved_by_others = _get_batch_reserved_by_others(batch, mp_name)
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

    # Block if any active MR already exists for this Material Planning
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
                    use_sec_qty = ceil(round(_qty / _denom, 9))
            elif group == "Structurals" and use_length and use_unit_weight and _qty:
                _denom = (use_length / 1000) * use_unit_weight
                if _denom:
                    use_sec_qty = ceil(round(_qty / _denom, 9))

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
        })

    mr.custom_material_planning = material_planning_name
    mr.insert(ignore_permissions=True)
    return mr.name


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
        # Sum diff across ALL MPs for this (SO, duno) so the value is always complete
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
            updated += 1

    frappe.db.commit()
    return {"updated": updated}


def unlink_material_request_on_cancel(doc, method=None):
    """Clear the Material Planning link when an MR is cancelled or deleted."""
    if doc.get("custom_material_planning"):
        frappe.db.set_value("Material Request", doc.name, "custom_material_planning", "")
