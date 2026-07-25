"""Verify the multi-supplier consolidated-purchase workflow: after a Material
Planning's Consolidate Item table has a requirement, the user may need to
split the purchase across several suppliers by creating SEPARATE Material
Requests manually (via the standard Material Request form, not the
Create-Material-Request-from-Consolidate button) -- each one tagged with
`custom_material_planning` so its eventual Purchase Receipt still
auto-allocates back into this Material Planning.

This requires custom_material_planning on Material Request to be editable
(it was previously read_only, settable only by the app's own whitelisted
functions) -- confirms the fix, then proves the existing PR auto-allocation
mechanism (on_submit_purchase_receipt -> allocate_pr_stock_to_mp) already
composes correctly across TWO entirely separate MR -> PO -> PR chains
against the SAME Material Planning, with different suppliers, without any
further backend changes.

Run via: bench --site manufact execute manufyxinvenzaerp.tests.verify_manual_mr_multi_supplier.run
"""

import frappe
from frappe.utils import flt, today
from manufyxinvenzaerp.tests.create_full_test_entry import get_ctx, ensure_item


def run():
    ctx = get_ctx()
    item = ensure_item(ctx, "ZZTEST-MULTI-SUPPLIER", "Multi Supplier Split Test Item", uom="Kg")
    frappe.db.set_value("Item", item, "custom_parent_item_group", "Structurals")
    frappe.db.set_value("Item", item, "custom_unit_weight", 10)
    frappe.db.set_value("Item", item, "create_new_batch", 1)
    frappe.db.set_value("Item", item, "custom_batch_prefix", "ZZMULTISUP")

    suppliers = frappe.get_all("Supplier", limit=2, pluck="name")
    if len(suppliers) < 2:
        frappe.throw("Need at least 2 suppliers in this site to run this test.")
    supplier_a, supplier_b = suppliers[0], suppliers[1]
    print("Suppliers:", supplier_a, supplier_b)

    # 0. Schema check: the field must be editable now.
    meta = frappe.get_meta("Material Request")
    f = meta.get_field("custom_material_planning")
    print("custom_material_planning read_only (expect 0):", f.read_only)
    assert not f.read_only, "custom_material_planning must be editable for manual multi-supplier MRs"

    # 1. Material Planning with one Unavailable Item needing 60 Kg total.
    mp = frappe.new_doc("Material Planning")
    mp.company = ctx.company
    mp.posting_date = today()
    mp.for_warehouse = ctx.warehouse
    mp.append("unavailable_items", {
        "item_code": item, "item_name": "Multi Supplier Split Test Item",
        "parent_item_group": "Structurals", "unit_weight": 10,
        "qty": 60, "uom": "Kg", "sec_qty": 6, "sec_uom": "Nos",
        "duno_mark_no": "DUNO-MULTI-SUPPLIER",
    })
    mp.insert(ignore_permissions=True)
    print("Created MP:", mp.name)

    mp.reload()
    consol_row = next(r for r in mp.consolidate_items if r.item_code == item)
    assert flt(consol_row.required_kg) == 60

    stock_uom = "Kg"

    def _make_manual_mr(qty, supplier_label):
        """Simulates a user creating a standalone Material Request by hand
        (NOT via make_material_request_from_consolidate) and manually setting
        the Material Planning field, which is the whole point of this fix."""
        mr = frappe.new_doc("Material Request")
        mr.material_request_type = "Purchase"
        mr.company = ctx.company
        mr.transaction_date = today()
        mr.schedule_date = today()
        mr.custom_material_planning = mp.name  # <-- the field this phase made editable
        mr.append("items", {
            "item_code": item,
            "qty": qty,
            "uom": stock_uom,
            "schedule_date": today(),
            "warehouse": ctx.warehouse,
            "custom_parent_item_group": "Structurals",
            "custom_unit_weight": 10,
            "custom_length": 5000,
            "custom_sec_qty": qty / (5 * 10),  # (L/1000)*UW*secqty = qty
        })
        mr.insert(ignore_permissions=True)
        mr.submit()
        print(f"Created + submitted MR for {supplier_label}: {mr.name} (qty={mr.items[0].qty})")
        assert mr.custom_material_planning == mp.name
        return mr

    mr_a = _make_manual_mr(40, "Supplier A")
    mr_b = _make_manual_mr(20, "Supplier B")

    from erpnext.stock.doctype.material_request.material_request import make_purchase_order
    from erpnext.buying.doctype.purchase_order.purchase_order import make_purchase_receipt

    def _po_pr(mr, supplier, label):
        po = make_purchase_order(mr.name)
        po.supplier = supplier
        for row in po.items:
            row.rate = 80
        po.insert(ignore_permissions=True)
        po.submit()
        print(f"  PO for {label}: {po.name} (supplier={po.supplier})")

        pr = make_purchase_receipt(po.name)
        for row in pr.items:
            row.allow_zero_valuation_rate = 1
            row.use_serial_batch_fields = 1
        pr.insert(ignore_permissions=True)
        pr.submit()
        print(f"  PR for {label}: {pr.name} (qty={pr.items[0].qty})")
        return po, pr

    po_a, pr_a = _po_pr(mr_a, supplier_a, "Supplier A")
    po_b, pr_b = _po_pr(mr_b, supplier_b, "Supplier B")

    # Both PR submits already triggered allocate_pr_stock_to_mp automatically.
    mp.reload()
    print("\nAvailable Raw Material rows after both receipts:")
    total_available = 0.0
    for r in mp.available_raw_materials:
        print(" ", r.item_code, "batch=", r.batch_no, "available_qty=", r.available_qty, "purchase_receipt=", r.purchase_receipt)
        total_available += flt(r.available_qty)
    print("Remaining Unavailable Item rows:", [(r.duno_mark_no, r.qty) for r in mp.unavailable_items])

    assert flt(total_available, 3) == 60, f"Expected 60 Kg total available across both receipts, got {total_available}"
    remaining = [r for r in mp.unavailable_items if r.duno_mark_no == "DUNO-MULTI-SUPPLIER"]
    assert not remaining, "Unavailable Item row should be fully covered and removed after both receipts"

    # Confirm each PR traced back to the correct MP independently.
    from manufyxinvenzaerp.purchase_receipt_management.purchase_receipt import get_mp_for_pr
    assert get_mp_for_pr(pr_a.name) == [mp.name]
    assert get_mp_for_pr(pr_b.name) == [mp.name]

    frappe.db.commit()
    print("\nALL CHECKS DONE — two independently-created Material Requests (different suppliers, "
          "same Material Planning) both correctly auto-allocated their receipts back into the "
          "shared Unavailable Item requirement, fully covering it.")
    print("Test data left in place:", mp.name, mr_a.name, mr_b.name, po_a.name, po_b.name, pr_a.name, pr_b.name)
