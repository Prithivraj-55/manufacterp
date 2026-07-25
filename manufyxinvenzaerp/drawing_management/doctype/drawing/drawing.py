import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt
from manufyxinvenzaerp.utils.dimension_formula import calculate_qty

STRUCTURALS_REQUIRED = ["length", "unit_weight", "sec_qty"]
PLATES_REQUIRED = ["length", "width", "thickness", "unit_weight", "sec_qty"]
NUTS_AND_BOLTS_REQUIRED = ["qty"]
FIELD_LABELS = {
    "length": "Length",
    "width": "Width",
    "thickness": "Thickness",
    "unit_weight": "Unit Weight",
    "sec_qty": "Sec Qty",
    "qty": "Primary Qty",
}

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

    def on_cancel(self):
        self.db_set("status", "Old Revision")

    def _recalculate_all(self):
        no_of_qty = flt(self.no_of_qty_to_manufacture)
        for row in self.items:
            _recalculate_row_qty(row)
            _recalculate_row_totals(row, no_of_qty)

    def _check_missing_fields(self, throw):
        for row in self.items:
            _check_row_missing_fields(row, throw)

    def _calculate_totals(self):
        total_weight = flt(0)
        for row in self.items:
            uom = (row.uom or "").lower()
            sec_uom = (row.sec_uom or "").lower()
            if uom in ("kg", "kgs"):
                total_weight += flt(row.qty)
            elif sec_uom in ("kg", "kgs"):
                total_weight += flt(row.sec_qty)
        self.total_weight = flt(total_weight, 3)


def _recalculate_row_qty(row):
    group = row.parent_item_group
    if group in ("Structurals", "Plates"):
        qty = calculate_qty(group, row.length, row.width, row.thickness, row.unit_weight, row.sec_qty)
        if qty is not None:
            row.qty = qty
    elif group == "Nuts and Bolts":
        if row.qty and row.unit_weight:
            row.sec_qty = flt(row.qty * row.unit_weight, 3)


def _recalculate_row_totals(row, no_of_qty):
    group = row.parent_item_group
    if group == "Nuts and Bolts":
        row.total_qty = flt(flt(row.qty) * no_of_qty, 3)
        row.total_sec_qty = flt(row.total_qty * flt(row.unit_weight), 3)
        return
    row.total_sec_qty = flt(row.sec_qty) * no_of_qty
    if group in ("Structurals", "Plates"):
        total_qty = calculate_qty(group, row.length, row.width, row.thickness, row.unit_weight, row.total_sec_qty)
        row.total_qty = flt(total_qty, 3) if total_qty is not None else 0
    else:
        row.total_qty = 0


def _check_row_missing_fields(row, throw):
    group = row.parent_item_group
    required = {
        "Structurals": STRUCTURALS_REQUIRED,
        "Plates": PLATES_REQUIRED,
        "Nuts and Bolts": NUTS_AND_BOLTS_REQUIRED,
    }.get(group)
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


@frappe.whitelist()
def check_existing_bom(drawing_name):
    return bool(frappe.get_all(
        "BOM",
        filters={
            "custom_drawing": drawing_name,
            "docstatus": ["in", [0, 1]]
        },
        limit=1
    ))