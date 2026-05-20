import json

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import ceil, flt, today


class MaterialPlanning(Document):
    def before_submit(self):
        if not self.bom_items:
            frappe.throw(_("Add at least one BOM before submitting."))
        for row in self.bom_items:
            if not row.bom_no:
                frappe.throw(_("Row {0}: BOM No is required.").format(row.idx))

    def on_submit(self):
        self.db_set("status", "Submitted")

    def on_cancel(self):
        self.db_set("status", "Cancelled")


@frappe.whitelist()
def get_bom_info(bom_no):
    """Return Drawing-derived details for a BOM row (called on bom_no change in JS)."""
    drawing_name = frappe.db.get_value("BOM", bom_no, "custom_drawing")
    if not drawing_name:
        return {}

    d = frappe.db.get_value(
        "Drawing",
        drawing_name,
        ["fg_item_code", "fg_item_name", "duno_mark_no", "sales_order",
         "no_of_qty_to_manufacture", "customer"],
        as_dict=True,
    )
    if not d:
        return {}

    bom_qty = frappe.db.get_value("BOM", bom_no, "quantity") or 1
    stock_uom = ""
    if d.fg_item_code:
        stock_uom = frappe.db.get_value("Item", d.fg_item_code, "stock_uom") or ""

    return {
        "drawing": drawing_name,
        "item_code": d.fg_item_code,
        "item_name": d.fg_item_name,
        "duno_mark_no": d.duno_mark_no,
        "sales_order": d.sales_order,
        "customer": d.customer,
        "qty_to_manufacture": d.no_of_qty_to_manufacture or bom_qty,
        "uom": stock_uom,
    }


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
    if not company:
        frappe.throw(_("Company is required before fetching raw materials."))

    rows = []
    for bom_row in doc.get("bom_items") or []:
        bom_no = bom_row.get("bom_no")
        planned_qty = flt(bom_row.get("qty_to_manufacture")) or 1
        duno_mark_no = bom_row.get("duno_mark_no")

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
                    sec_qty = ceil(qty / denom)
            elif group == "Plates" and length and width and thickness and unit_weight:
                denom = (length / 1000) * (width / 1000) * thickness * unit_weight
                if denom:
                    sec_qty = ceil(qty / denom)

            sec_uom = (
                frappe.db.get_value("Item", detail.get("item_code"), "custom_secondary_uom") or ""
            )

            rows.append({
                "item_code": detail.get("item_code"),
                "item_name": detail.get("item_name"),
                "bom_no": bom_no,
                "duno_mark_no": duno_mark_no,
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
            })

    return rows


@frappe.whitelist()
def check_stock_availability(doc):
    """
    For each row in raw_materials, look up available qty via Serial and Batch Bundle
    and compute shortage_qty. Returns the updated rows list.
    """
    from manufyxinvenzaerp.production_plan_management.production_plan import get_sbb_available_qty

    if isinstance(doc, str):
        doc = frappe._dict(json.loads(doc))

    warehouse = doc.get("for_warehouse")
    if not warehouse:
        frappe.throw(_("Set 'Raw Materials Warehouse' before checking stock availability."))

    updated_rows = []
    for row in doc.get("raw_materials") or []:
        item_code = row.get("item_code")
        required_qty = flt(row.get("qty"))
        dimensions = {
            "custom_length": flt(row.get("length")),
            "custom_thickness": flt(row.get("thickness")),
            "custom_width": flt(row.get("width")),
        }
        available_qty, _ = get_sbb_available_qty(item_code, warehouse, dimensions)
        shortage = max(0.0, required_qty - available_qty)
        updated_row = dict(row)
        updated_row["available_qty"] = available_qty
        updated_row["shortage_qty"] = shortage
        updated_rows.append(updated_row)

    return updated_rows


@frappe.whitelist()
def make_production_plan(material_planning_name):
    """Create a draft Production Plan from a Material Planning document."""
    mp = frappe.get_doc("Material Planning", material_planning_name)
    if mp.docstatus == 2:
        frappe.throw(_("Cannot create a Production Plan from a cancelled Material Planning."))
    if not mp.bom_items:
        frappe.throw(_("No BOM items found on this Material Planning."))

    pp = frappe.new_doc("Production Plan")
    pp.company = mp.company
    pp.posting_date = today()
    pp.for_warehouse = mp.for_warehouse
    pp.ignore_existing_ordered_qty = mp.ignore_existing_ordered_qty
    pp.get_items_from = "Sales Order"

    for row in mp.bom_items:
<<<<<<< Updated upstream
        stock_uom = frappe.db.get_value("Item", row.item_code, "stock_uom") or ""
        pp.append("po_items", {
            "item_code": row.item_code,
            "item_name": row.item_name,
            "bom_no": row.bom_no,
            "planned_qty": flt(row.qty_to_manufacture),
=======
        item_code = row.item_code or frappe.db.get_value("BOM", row.bom_no, "item")
        item_name = row.item_name or frappe.db.get_value("Item", item_code, "item_name") or item_code
        stock_uom = frappe.db.get_value("Item", item_code, "stock_uom") or "Nos"
        planned_qty = flt(row.qty_to_manufacture) or 1
        pp.append("po_items", {
            "item_code": item_code,
            "custom_item_name": item_name,
            "bom_no": row.bom_no,
            "custom_duno_mark_no": row.duno_mark_no or 0,
            "custom_drawing": row.drawing or "",
            "planned_qty": planned_qty,
>>>>>>> Stashed changes
            "stock_uom": stock_uom,
            "sales_order": row.sales_order or "",
            "custom_customer": row.customer or "",
            "warehouse": mp.for_warehouse or "",
        })

    pp.insert(ignore_permissions=True)
    return pp.name
