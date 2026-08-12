"""Cut Sheet -- a nesting plan for one physical sheet, shared across jobs.

A plate arrives as one batch and is cut into repeated pieces (W1), leaving a
remnant (W2). Before this doctype the cut was described row by row on each
Material Planning / Material Issue Plan line, which meant re-typing the balance on
every row and gave no way for two jobs to draw from the same sheet without each
one claiming the whole thing.

Here the nesting is stated ONCE against the batch: this piece, this many of them,
this remnant. Jobs then take pieces from it the same way they reserve batch stock
-- a Sec Nos figure with an available remainder -- and the same sheet can serve
several Material Plannings.

Nothing here is physical. There is no stock ledger behind W1: the batch still
holds its own Kg and the real movement is the ordinary Material Issue Plan
transfer, which simply carries W1's dimensions instead of the batch's. What this
document owns is the arithmetic and the bookkeeping of who has claimed what.

W2 is written onto the batch when the FIRST transfer from this sheet is submitted
(the client's rule -- the sheet is physically cut at that point, whether or not
every piece has been issued yet), and taken back off if that transfer is
cancelled. See apply_w2_to_batch / revert_w2_from_batch.
"""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, now

from manufyxinvenzaerp.utils.dimension_formula import calculate_qty

# Sec Nos comparisons are made to 3 decimals everywhere else in this app; the same
# slack keeps "allocated exactly everything" from failing on a float remainder.
QTY_EPSILON = 0.001


class CutSheet(Document):
    def validate(self):
        self._fetch_batch_dimensions()
        self._sync_allocations_from_rows()
        self._calculate()
        self._validate_allocations_fit()
        self._set_status()

    def _sync_allocations_from_rows(self):
        """Rebuild the Allocations table from the Material Mapping rows actually
        holding pieces of this sheet.

        The rows are the truth, not this table. A batch can be put on a Material
        Mapping row by hand through Update Batch, which never goes near
        allocate_cut_sheet -- so a table maintained only by that one path missed
        those claims entirely and the sheet reported 0 allocated while a job was
        genuinely holding pieces. Deriving it here means the figures are right no
        matter how the batch got onto the row, and the same query backs the
        availability check in material_planning._sync_cut_sheet_flag, so the two
        can no longer disagree.

        Transfer state (stock_entry / is_consumed / allocated_on) is carried over
        per source row, since that is this table's own bookkeeping and cannot be
        recovered from the mapping row."""
        if not self.name or str(self.name).startswith("new-"):
            return

        previous = {a.source_row: a for a in (self.allocations or []) if a.source_row}

        claims = frappe.get_all(
            "Material Planning Material Mapping",
            filters={"cut_sheet_ref": self.name, "is_reserved": 1},
            fields=["name", "parent", "duno_mark_no", "batch_sec_qty", "batch_calc_qty"],
            order_by="parent asc, idx asc",
        )

        self.allocations = []
        for c in claims:
            old = previous.get(c.name)
            self.append("allocations", {
                "material_planning": c.parent,
                "source_table": "Material Planning Material Mapping",
                "source_row": c.name,
                "duno_mark_no": c.duno_mark_no or "",
                "sec_qty": flt(c.batch_sec_qty),
                "qty": flt(c.batch_calc_qty),
                "allocated_on": (old.allocated_on if old else None) or now(),
                "stock_entry": old.stock_entry if old else None,
                "is_consumed": old.is_consumed if old else 0,
            })

    def on_trash(self):
        """A sheet other jobs are drawing from cannot simply vanish -- their rows
        would be left pointing at nothing, reserving pieces of a plan that no longer
        exists."""
        if self.allocations:
            frappe.throw(
                _("This Cut Sheet is in use by {0}. Release those allocations first.")
                .format(", ".join(sorted({a.material_planning for a in self.allocations if a.material_planning})))
            )

    # ── derived values ────────────────────────────────────────────────────────

    def _fetch_batch_dimensions(self):
        """The sheet's own size, read from the batch rather than typed, so the two can
        never disagree. Thickness in particular is the batch's for good: cutting
        changes Length and Width only."""
        if not self.batch_no:
            return
        batch = frappe.db.get_value(
            "Batch", self.batch_no,
            ["item", "custom_length", "custom_width", "custom_thickness", "custom_sec_qty"],
            as_dict=True,
        )
        if not batch:
            return
        if self.item_code and batch.item and batch.item != self.item_code:
            frappe.throw(
                _("Batch {0} belongs to item {1}, not {2}.")
                .format(self.batch_no, batch.item, self.item_code)
            )
        self.item_code = self.item_code or batch.item
        self.sheet_length = flt(batch.custom_length)
        self.sheet_width = flt(batch.custom_width)
        self.sheet_thickness = flt(batch.custom_thickness)
        self.sheet_sec_qty = flt(batch.custom_sec_qty)

    def _calculate(self):
        group = self.parent_item_group
        unit_weight = flt(self.unit_weight)

        self.sheet_qty = flt(calculate_qty(
            group, self.sheet_length, self.sheet_width, self.sheet_thickness,
            unit_weight, self.sheet_sec_qty or 1,
        ) or 0, 3)

        # Kg for ONE piece -- displayed, and the basis for a partial claim.
        self.w1_qty_per_nos = flt(calculate_qty(
            group, self.w1_length, self.w1_width, self.sheet_thickness, unit_weight, 1,
        ) or 0, 3)
        # Totals are computed at FULL precision from the dimensions, never as
        # (rounded per-piece x count). A 500x250x5 piece is 4.90625 Kg, which stores
        # as 4.906 -- times four that is 19.624 instead of 19.625, and one milligram
        # is enough to make a requirement of exactly 19.625 Kg look uncovered.
        self.w1_total_qty = flt(calculate_qty(
            group, self.w1_length, self.w1_width, self.sheet_thickness,
            unit_weight, self.w1_sec_qty,
        ) or 0, 3)

        # W2 is what the sheet has LEFT once W1 comes off it, not an independent
        # measurement. Calculating both halves from their own dimensions let them
        # disagree with the sheet they came from: the stock entry consumes W1, so the
        # batch is left holding (sheet - W1) while W2 claimed something else, and the
        # batch's available qty stopped matching its own W2 details. Deriving it means
        # they cannot drift apart. The W2 DIMENSIONS stay entered by hand -- they
        # describe the off-cut's shape, which cannot be inferred (a plate can be cut
        # along either edge) -- and are what gets written onto the batch.
        self.w2_calc_qty = flt(max(self.sheet_qty - self.w1_total_qty, 0.0), 3)

        self.allocated_sec_qty = flt(sum(flt(a.sec_qty) for a in (self.allocations or [])), 3)
        self.allocated_qty = flt(sum(flt(a.qty) for a in (self.allocations or [])), 3)
        self.available_sec_qty = flt(flt(self.w1_sec_qty) - self.allocated_sec_qty, 3)
        self.available_qty = flt(calculate_qty(
            group, self.w1_length, self.w1_width, self.sheet_thickness,
            unit_weight, self.available_sec_qty,
        ) or 0, 3)

    def _validate_allocations_fit(self):
        """Reducing W1 Sec Nos below what jobs have already taken would silently
        oversubscribe the sheet."""
        if self.allocated_sec_qty - flt(self.w1_sec_qty) > QTY_EPSILON:
            frappe.throw(
                _("{0} pieces are already allocated to other jobs, so W1 Sec Nos cannot be set to {1}. "
                  "Release an allocation first.")
                .format(flt(self.allocated_sec_qty, 3), flt(self.w1_sec_qty, 3))
            )

    def _set_status(self):
        if self.w2_applied:
            self.status = "Consumed"
        elif not flt(self.w1_sec_qty):
            self.status = "Draft"
        elif flt(self.available_sec_qty) <= QTY_EPSILON:
            self.status = "Fully Allocated"
        else:
            self.status = "Active"


# ── suggestion helper ─────────────────────────────────────────────────────────

@frappe.whitelist()
def suggest_w1_sec_qty(cut_sheet_name=None, sheet_length=None, sheet_width=None,
                       w1_length=None, w1_width=None):
    """How many W1 pieces the sheet could yield, purely geometrically.

    Offered as a starting point only -- the real answer depends on the nesting and
    the saw, so the client's rule is that the user types the figure. Deliberately
    NOT derived from Kg: a 1800x6300 sheet is 2.1 times the weight of a 1800x3000
    piece, but it yields 2 of them, and a Kg-based figure would over-issue on every
    sheet."""
    if cut_sheet_name:
        cs = frappe.db.get_value(
            "Cut Sheet", cut_sheet_name,
            ["sheet_length", "sheet_width", "w1_length", "w1_width"], as_dict=True,
        ) or {}
        sheet_length = sheet_length or cs.get("sheet_length")
        sheet_width = sheet_width or cs.get("sheet_width")
        w1_length = w1_length or cs.get("w1_length")
        w1_width = w1_width or cs.get("w1_width")

    sheet_length, sheet_width = flt(sheet_length), flt(sheet_width)
    w1_length, w1_width = flt(w1_length), flt(w1_width)
    if not (sheet_length and w1_length):
        return 0

    # Plates nest in two directions; a structural section only runs along its length.
    if sheet_width and w1_width:
        along = int(sheet_length // w1_length) * int(sheet_width // w1_width)
        rotated = int(sheet_length // w1_width) * int(sheet_width // w1_length)
        return max(along, rotated)
    return int(sheet_length // w1_length)


# ── allocation ────────────────────────────────────────────────────────────────
#
# A cut allocation is deliberately shaped like an ordinary batch reservation: the
# Material Mapping row keeps the REAL batch (so the stock ledger and every transfer
# path work untouched) and carries W1's dimensions in its batch_* fields. That is
# the whole trick -- downstream code never needs to know a Cut Sheet exists, it just
# sees a row reserving so many Kg of a batch at these dimensions.

@frappe.whitelist()
def get_available_cut_sheets(mp_name, item_code=None):
    """Cut Sheets with pieces still free, for the mapping picker. Filtered to the
    Material Planning's own company, and to one item when the picker is opened from
    a row that already knows what it needs."""
    mp = frappe.db.get_value("Material Planning", mp_name, ["company", "for_warehouse"], as_dict=True)
    if not mp:
        frappe.throw(_("Material Planning {0} not found.").format(mp_name))

    filters = {"company": mp.company, "w2_applied": 0}
    if item_code:
        filters["item_code"] = item_code

    rows = frappe.get_all(
        "Cut Sheet", filters=filters,
        fields=["name", "item_code", "item_name", "parent_item_group", "unit_weight",
                "batch_no", "warehouse", "sheet_length", "sheet_width", "sheet_thickness",
                "w1_length", "w1_width", "w1_sec_qty", "w1_qty_per_nos",
                "available_sec_qty", "available_qty", "status"],
        order_by="modified desc",
    )
    return [r for r in rows if flt(r.available_sec_qty) > QTY_EPSILON]


@frappe.whitelist()
def get_cut_sheet_for_batch(batch_no, exclude_row=None):
    """The nesting plan against a batch, if it has one, for the moment a batch is
    picked on a Material Mapping row.

    The server-side sync only runs on save, which left the user selecting a batch and
    seeing nothing about the cut until they saved -- so this answers the same question
    immediately, and the row can show W1's size and the free piece count straight
    away. exclude_row keeps the row's own claim from counting against itself."""
    if not batch_no:
        return None
    cs = frappe.db.get_value(
        "Cut Sheet", {"batch_no": batch_no},
        ["name", "item_code", "parent_item_group", "unit_weight", "status",
         "sheet_length", "sheet_width", "sheet_thickness",
         "w1_length", "w1_width", "w1_sec_qty", "w1_qty_per_nos",
         "w2_length", "w2_width", "w2_sec_qty", "w2_calc_qty", "w2_applied"],
        as_dict=True,
    )
    if not cs:
        return None

    taken_by_others = flt(sum(
        flt(c.batch_sec_qty) for c in frappe.get_all(
            "Material Planning Material Mapping",
            filters={"cut_sheet_ref": cs.name, "is_reserved": 1},
            fields=["name", "batch_sec_qty"])
        if c.name != exclude_row
    ), 3)
    cs["available_sec_qty"] = flt(flt(cs.w1_sec_qty) - taken_by_others, 3)
    cs["allocated_sec_qty"] = taken_by_others
    return cs


@frappe.whitelist()
def allocate_cut_sheet(mp_name, cut_sheet_name, sec_qty, row_name=None, unavailable_item_row=None):
    """Take `sec_qty` pieces off a Cut Sheet and reserve them into a Material Mapping
    row -- either an existing row, or a new one covering an Unavailable Item.

    Partial by design: 10 pieces on the sheet can go 2 to this plan, 2 to the next,
    and the rest stay free. What is taken here is recorded on the Cut Sheet itself,
    so the sheet is the one place that knows who holds what."""
    from manufyxinvenzaerp.production_management.doctype.material_planning.material_planning import (
        BATCH_CUT_SHEET_MAPPED, _release_row_pool_claims,
    )

    mp = frappe.get_doc("Material Planning", mp_name)
    if not frappe.has_permission("Material Planning", "write", doc=mp):
        frappe.throw(_("Not permitted to modify this Material Planning"), frappe.PermissionError)

    sec_qty = flt(sec_qty)
    if sec_qty <= 0:
        frappe.throw(_("Enter how many pieces to take (Sec Nos greater than 0)."))

    cs = frappe.get_doc("Cut Sheet", cut_sheet_name)
    if cs.w2_applied:
        frappe.throw(_("This sheet has already been cut and its balance written back to batch {0}.")
                     .format(cs.batch_no))
    if sec_qty - flt(cs.available_sec_qty) > QTY_EPSILON:
        frappe.throw(
            _("Only {0} piece(s) are still free on this Cut Sheet — {1} requested.")
            .format(flt(cs.available_sec_qty, 3), flt(sec_qty, 3))
        )

    # Full precision, not sec_qty x the rounded per-piece figure -- see _calculate.
    qty = flt(calculate_qty(
        cs.parent_item_group, cs.w1_length, cs.w1_width, cs.sheet_thickness,
        flt(cs.unit_weight), sec_qty,
    ) or 0, 3)

    if row_name:
        row = next((r for r in mp.material_mapping if r.name == row_name), None)
        if not row:
            frappe.throw(_("Row {0} not found.").format(row_name))
        if row.item_code and row.item_code != cs.item_code:
            frappe.throw(
                _("This Cut Sheet is for <b>{0}</b>, but row {1} is planned for <b>{2}</b>.")
                .format(cs.item_code, row.idx, row.item_code)
            )
        # Whatever this row was drawing from before -- another cut sheet, an excess
        # claim -- is handed back before it takes something new, or the old pool would
        # go on believing this row still holds its pieces.
        _release_row_pool_claims(row)
        row.is_reserved = 0
        row.reserved_qty = 0
        row.shortfall_qty = 0
        row.reserved_on = None
    else:
        base = {
            "item_number": "", "sales_order": "", "item_code": cs.item_code,
            "item_name": cs.item_name or cs.item_code, "bom_no": "", "drawing": "",
            "duno_mark_no": "", "customer_drawing_number": "",
        }
        if unavailable_item_row:
            src = next((r for r in (mp.unavailable_items or []) if r.name == unavailable_item_row), None)
            if not src:
                frappe.throw(_("Unavailable Item row {0} not found.").format(unavailable_item_row))
            if src.item_code != cs.item_code:
                frappe.throw(
                    _("This Cut Sheet is for {0}, which does not match the Unavailable Item row's {1}.")
                    .format(cs.item_code, src.item_code)
                )
            base.update({
                "item_number": src.item_number, "sales_order": src.sales_order,
                "bom_no": src.bom_no, "drawing": src.drawing,
                "duno_mark_no": src.duno_mark_no,
                "customer_drawing_number": src.customer_drawing_number,
            })
            old_qty = flt(src.qty)
            remaining = flt(old_qty - qty, 3)
            if remaining <= QTY_EPSILON:
                mp.unavailable_items = [r for r in mp.unavailable_items if r.name != unavailable_item_row]
            else:
                ratio = (remaining / old_qty) if old_qty else 0.0
                src.qty = remaining
                src.sec_qty = flt(flt(src.sec_qty) * ratio, 3)
        row = mp.append("material_mapping", base)

    # The REAL batch, carrying W1's dimensions -- so the row describes the piece it
    # will actually receive, and the ordinary dimensional checks hold.
    #
    # reserve_without_dimensions is deliberately OFF. It means the reverse of a cut:
    # "Kg is what was asked for, Sec Nos is that weight expressed as a fraction of the
    # batch". Here the piece COUNT is what the user chose and the Kg follows from it,
    # so leaving the flag on had reserve_batches recompute Sec Nos back out of the
    # requirement's weight and quietly replace the count.
    row.batch = cs.batch_no
    row.planned_item = cs.item_code
    row.batch_mapped = BATCH_CUT_SHEET_MAPPED
    row.reserve_without_dimensions = 0
    row.cut_sheet = 1
    row.cut_sheet_ref = cs.name
    row.batch_parent_item_group = cs.parent_item_group or ""
    row.batch_length = flt(cs.w1_length)
    row.batch_width = flt(cs.w1_width)
    row.batch_thickness = flt(cs.sheet_thickness)
    row.batch_unit_weight = flt(cs.unit_weight)
    row.batch_sec_qty = sec_qty
    row.batch_calc_qty = qty

    # is_reserved is flipped after the save, not in it: _validate_batch_calc_qty
    # refuses a save that changes a reserved row's qty or batch.
    mp.save(ignore_permissions=True)

    frappe.db.set_value(
        "Material Planning Material Mapping", row.name,
        {"is_reserved": 1, "reserved_qty": qty, "shortfall_qty": 0, "reserved_on": now()},
        update_modified=False,
    )

    # No manual append: the row is reserved in the database by now, and the sheet
    # derives its Allocations from the rows holding it (_sync_allocations_from_rows).
    # Appending here as well would double-count this claim.
    refresh_cut_sheet_allocations(cs.name)
    frappe.db.commit()
    return {"row_name": row.name, "cut_sheet": cs.name, "sec_qty": sec_qty, "qty": qty}


def refresh_cut_sheet_allocations(cut_sheet_name):
    """Re-derive a sheet's Allocations table and its Allocated/Available figures.

    Called whenever a Material Mapping row starts or stops holding pieces, so the
    sheet is correct immediately rather than only after someone opens and saves it.
    A plain save is enough -- validate() does the rebuild -- but it is wrapped here
    so callers do not need to know that, and so a failure to refresh can never take
    down the reservation that triggered it."""
    if not cut_sheet_name or not frappe.db.exists("Cut Sheet", cut_sheet_name):
        return
    try:
        frappe.get_doc("Cut Sheet", cut_sheet_name).save(ignore_permissions=True)
    except Exception:
        frappe.log_error(
            title="Cut Sheet allocation refresh failed",
            message=frappe.get_traceback(),
        )


def release_cut_sheet_allocation(row):
    """Hand a row's pieces back to its Cut Sheet. Caller saves the Material Planning.

    The row's own markers are cleared in the database FIRST, because the sheet now
    rebuilds its Allocations from whatever rows still point at it -- refreshing
    before the row was released would simply find it again and put it straight
    back."""
    if not row.get("cut_sheet_ref"):
        return
    cs_name = row.cut_sheet_ref

    if row.name and not str(row.name).startswith("new-"):
        frappe.db.set_value(
            "Material Planning Material Mapping", row.name,
            {"cut_sheet": 0, "cut_sheet_ref": "", "cut_sheet_avail_sec_qty": 0},
            update_modified=False,
        )
    row.cut_sheet = 0
    row.cut_sheet_ref = ""
    row.cut_sheet_avail_sec_qty = 0

    refresh_cut_sheet_allocations(cs_name)


# ── W2 write-back ─────────────────────────────────────────────────────────────

def apply_w2_to_batch(cut_sheet_name, stock_entry):
    """Write the balance onto the batch, on the FIRST transfer taken from this sheet.

    The client's rule, and it is about the physical world rather than the paperwork:
    the moment anyone cuts a piece out, the sheet in the rack IS the remnant --
    whether or not the other jobs have collected their pieces yet. Waiting until
    every piece had shipped would leave the batch advertising a full sheet that no
    longer exists.

    The batch KEEPS its original name, which still spells out the original
    dimensions. The client is aware and has chosen to live with it for now."""
    cs = frappe.get_doc("Cut Sheet", cut_sheet_name)
    if cs.w2_applied or not cs.batch_no:
        return False
    if not (flt(cs.w2_length) or flt(cs.w2_width) or flt(cs.w2_sec_qty)):
        # No balance was planned -- the sheet is used up rather than leaving a remnant.
        return False

    frappe.db.set_value("Batch", cs.batch_no, {
        "custom_length": flt(cs.w2_length),
        "custom_width": flt(cs.w2_width),
        "custom_sec_qty": flt(cs.w2_sec_qty),
    })
    frappe.db.set_value("Cut Sheet", cs.name, {
        "w2_applied": 1,
        "w2_applied_stock_entry": stock_entry,
        "w2_applied_on": now(),
        "status": "Consumed",
    }, update_modified=False)
    return True


def revert_w2_from_batch(cut_sheet_name):
    """Undo the write-back when the transfer that triggered it is cancelled -- the
    steel is back in the rack uncut, so the batch has to say so again."""
    cs = frappe.get_doc("Cut Sheet", cut_sheet_name)
    if not cs.w2_applied:
        return False
    frappe.db.set_value("Batch", cs.batch_no, {
        "custom_length": flt(cs.sheet_length),
        "custom_width": flt(cs.sheet_width),
        "custom_sec_qty": flt(cs.sheet_sec_qty),
    })
    frappe.db.set_value("Cut Sheet", cs.name, {
        "w2_applied": 0, "w2_applied_stock_entry": "", "w2_applied_on": None,
        "status": "Fully Allocated" if flt(cs.available_sec_qty) <= QTY_EPSILON else "Active",
    }, update_modified=False)
    return True
