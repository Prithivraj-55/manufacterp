import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt

STRUCTURALS_REQUIRED = ["length", "unit_weight", "sec_qty"]
PLATES_REQUIRED = ["length", "width", "thickness", "unit_weight", "sec_qty"]
FIELD_LABELS = {
    "length": "Length",
    "width": "Width",
    "thickness": "Thickness",
    "unit_weight": "Unit Weight",
    "sec_qty": "Sec Qty",
}

BATCH_STOCK_NOTE = _(
    "Note: Select batch if stock is available, otherwise enter the dimensions manually. "
    "You can purchase it later. While making a Drawing, stock may be available, "
    "but at the time of starting work stock may not be available. "
    "Ensure stock availability while making the Production Plan."
)


class Drawing(Document):
    def before_insert(self):
        if self.amended_from:
            prev_rev = frappe.db.get_value("Drawing", self.amended_from, "rev_no") or 0
            self.rev_no = prev_rev + 1
        else:
            self.rev_no = 0
        self.status = "Working"

    def validate(self):
        self.customer_no = self.customer or ""
        self._recalculate_all()
        self._check_missing_fields(throw=False)
        self._calculate_totals()

    def before_submit(self):
        self._check_missing_fields(throw=True)
        frappe.msgprint(
            BATCH_STOCK_NOTE,
            title=_("Stock Availability Note"),
            indicator="orange",
        )

    def on_cancel(self):
        self.db_set("status", "Old Revision")

    def _recalculate_all(self):
        for row in self.items:
            _recalculate_row_qty(row)
            row.amount = flt(flt(row.rate) * flt(row.qty), 2)

    def _check_missing_fields(self, throw):
        for row in self.items:
            _check_row_missing_fields(row, throw)

    def _calculate_totals(self):
        total_cost = flt(0)
        total_weight = flt(0)
        for row in self.items:
            total_cost += flt(row.amount)
            uom = (row.uom or "").lower()
            sec_uom = (row.sec_uom or "").lower()
            if uom in ("kg", "kgs"):
                total_weight += flt(row.qty)
            elif sec_uom in ("kg", "kgs"):
                total_weight += flt(row.sec_qty)
        self.total_raw_material_cost = flt(total_cost, 2)
        self.total_weight = flt(total_weight, 3)


def _recalculate_row_qty(row):
    group = row.parent_item_group
    if group == "Structurals":
        if row.length and row.unit_weight and row.sec_qty:
            row.qty = (row.length / 1000) * row.unit_weight * row.sec_qty
    elif group == "Plates":
        if all(getattr(row, f, None) for f in PLATES_REQUIRED):
            row.qty = (
                (row.length / 1000)
                * (row.width / 1000)
                * row.thickness
                * row.unit_weight
                * row.sec_qty
            )


def _check_row_missing_fields(row, throw):
    group = row.parent_item_group
    required = {"Structurals": STRUCTURALS_REQUIRED, "Plates": PLATES_REQUIRED}.get(group)
    if not required:
        return
    missing = [FIELD_LABELS[f] for f in required if not getattr(row, f, None)]
    if not missing:
        return
    msg = _("Row {0}: Missing for {1} formula: {2}").format(
        row.idx, group, ", ".join(missing)
    )
    if throw:
        frappe.throw(msg)
    else:
        frappe.msgprint(msg, indicator="orange", title=_("Missing Fields"))
