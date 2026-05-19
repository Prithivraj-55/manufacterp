"""
Validates Purchase Order creation from Material Planning Unavailable Items.

Tests:
  V1  — PO created with correct supplier and all selected items
  V2  — PO items match unavailable_items qty, uom, item_code
  V3  — purchase_order field linked back on each ordered row
  V4  — Unselected rows are NOT linked (partial selection)
  V5  — Error when no items selected
  V6  — Error when unavailable_items table is empty
  V7  — PO is created as draft (not submitted)
  V8  — Multiple POs can be created for same MP (second purchase)

Run:
  bench --site fl.local execute manufyxinvenzaerp.tests.test_purchase_order_creation.run
"""

import frappe
from frappe.utils import today, flt
import json


def get_ctx():
    company = frappe.db.sql("SELECT name FROM tabCompany LIMIT 1", as_dict=True)[0]["name"]
    warehouse = frappe.db.sql("SELECT name FROM tabWarehouse WHERE is_group=0 LIMIT 1", as_dict=True)[0]["name"]
    supplier = frappe.db.sql("SELECT name FROM tabSupplier LIMIT 1", as_dict=True)
    if not supplier:
        frappe.throw("No supplier found in DB — create one first")
    supplier = supplier[0]["name"]
    return frappe._dict(company=company, warehouse=warehouse, supplier=supplier)


def _make_test_mp(ctx):
    """Create a Material Planning with 2 unavailable items."""
    mp = frappe.new_doc("Material Planning")
    mp.company = ctx.company
    mp.posting_date = today()
    mp.for_warehouse = ctx.warehouse
    # Add a BOM row so validation passes
    bom = frappe.db.sql("SELECT name FROM tabBOM WHERE docstatus=1 LIMIT 1", as_dict=True)
    if bom:
        mp.append("bom_items", {"bom_no": bom[0]["name"]})
    # Directly populate unavailable_items
    mp.append("unavailable_items", {
        "item_code": "TEST-ANGLE-65X6",
        "item_name": "IS Angle 65×65×6mm",
        "qty": 21.9,
        "uom": "Kg",
        "bom_no": bom[0]["name"] if bom else "",
    })
    mp.append("unavailable_items", {
        "item_code": "TEST-NUT-M16",
        "item_name": "M16 Hex Nut Grade 8",
        "qty": 32,
        "uom": "Nos",
        "bom_no": bom[0]["name"] if bom else "",
    })
    mp.insert(ignore_permissions=True)
    return mp


# ── Tests ──────────────────────────────────────────────────────────────────────

def test_v1_po_created_with_correct_supplier(ctx):
    """V1: PO is created and has the correct supplier."""
    from manufyxinvenzaerp.production_management.doctype.material_planning.material_planning import make_purchase_order
    mp = _make_test_mp(ctx)
    selected = ["TEST-ANGLE-65X6", "TEST-NUT-M16"]
    po_name = make_purchase_order(mp.name, ctx.supplier, json.dumps(selected))
    assert po_name, "PO name should be returned"
    po = frappe.get_doc("Purchase Order", po_name)
    assert po.supplier == ctx.supplier, f"Supplier mismatch: {po.supplier} != {ctx.supplier}"
    assert po.company == ctx.company
    print(f"  PASS V1: PO '{po_name}' created for supplier '{ctx.supplier}'")
    return mp, po_name


def test_v2_po_items_match_unavailable_rows(ctx):
    """V2: PO items have correct item_code, qty, uom."""
    from manufyxinvenzaerp.production_management.doctype.material_planning.material_planning import make_purchase_order
    mp = _make_test_mp(ctx)
    selected = ["TEST-ANGLE-65X6", "TEST-NUT-M16"]
    po_name = make_purchase_order(mp.name, ctx.supplier, json.dumps(selected))
    po = frappe.get_doc("Purchase Order", po_name)
    assert len(po.items) == 2, f"Expected 2 PO items, got {len(po.items)}"

    po_items = {i.item_code: i for i in po.items}
    assert "TEST-ANGLE-65X6" in po_items, "ANGLE missing from PO"
    assert flt(po_items["TEST-ANGLE-65X6"].qty) == 21.9
    assert po_items["TEST-ANGLE-65X6"].uom == "Kg"
    assert "TEST-NUT-M16" in po_items, "NUT missing from PO"
    assert flt(po_items["TEST-NUT-M16"].qty) == 32.0
    assert po_items["TEST-NUT-M16"].uom == "Nos"
    print(f"  PASS V2: PO items match — ANGLE 21.9 Kg, NUT 32 Nos")
    return mp, po_name


def test_v3_po_linked_back_on_rows(ctx):
    """V3: purchase_order field is set on all ordered rows."""
    from manufyxinvenzaerp.production_management.doctype.material_planning.material_planning import make_purchase_order
    mp = _make_test_mp(ctx)
    selected = ["TEST-ANGLE-65X6", "TEST-NUT-M16"]
    po_name = make_purchase_order(mp.name, ctx.supplier, json.dumps(selected))
    mp.reload()
    for row in mp.unavailable_items:
        assert row.purchase_order == po_name, (
            f"Row {row.item_code} has purchase_order='{row.purchase_order}', expected '{po_name}'"
        )
    print(f"  PASS V3: All ordered rows linked to '{po_name}'")
    return mp, po_name


def test_v4_partial_selection_only_links_selected(ctx):
    """V4: Only selected items are linked; unselected rows stay blank."""
    from manufyxinvenzaerp.production_management.doctype.material_planning.material_planning import make_purchase_order
    mp = _make_test_mp(ctx)
    # Only order ANGLE, not NUT
    selected = ["TEST-ANGLE-65X6"]
    po_name = make_purchase_order(mp.name, ctx.supplier, json.dumps(selected))
    po = frappe.get_doc("Purchase Order", po_name)
    assert len(po.items) == 1, f"Expected 1 PO item, got {len(po.items)}"
    mp.reload()
    linked = {r.item_code: r.purchase_order for r in mp.unavailable_items}
    assert linked["TEST-ANGLE-65X6"] == po_name, "ANGLE should be linked"
    assert not linked.get("TEST-NUT-M16"), "NUT should NOT be linked"
    print(f"  PASS V4: Partial selection — ANGLE linked, NUT unlinked")
    return mp, po_name


def test_v5_error_when_no_items_selected(ctx):
    """V5: Raises error when selected_items is empty list."""
    from manufyxinvenzaerp.production_management.doctype.material_planning.material_planning import make_purchase_order
    mp = _make_test_mp(ctx)
    try:
        make_purchase_order(mp.name, ctx.supplier, json.dumps([]))
        raise AssertionError("Should have raised ValidationError")
    except frappe.ValidationError:
        print("  PASS V5: Empty selection raises ValidationError")
    return mp


def test_v6_error_when_no_unavailable_items(ctx):
    """V6: Raises error when unavailable_items table is empty."""
    from manufyxinvenzaerp.production_management.doctype.material_planning.material_planning import make_purchase_order
    mp = frappe.new_doc("Material Planning")
    mp.company = ctx.company
    mp.posting_date = today()
    mp.for_warehouse = ctx.warehouse
    bom = frappe.db.sql("SELECT name FROM tabBOM WHERE docstatus=1 LIMIT 1", as_dict=True)
    if bom:
        mp.append("bom_items", {"bom_no": bom[0]["name"]})
    mp.insert(ignore_permissions=True)
    try:
        make_purchase_order(mp.name, ctx.supplier, json.dumps(["TEST-ANGLE-65X6"]))
        raise AssertionError("Should have raised ValidationError")
    except frappe.ValidationError:
        print("  PASS V6: Empty unavailable_items raises ValidationError")
    return mp


def test_v7_po_is_draft(ctx):
    """V7: Created PO is in draft state (docstatus=0)."""
    from manufyxinvenzaerp.production_management.doctype.material_planning.material_planning import make_purchase_order
    mp = _make_test_mp(ctx)
    po_name = make_purchase_order(mp.name, ctx.supplier, json.dumps(["TEST-ANGLE-65X6"]))
    po = frappe.get_doc("Purchase Order", po_name)
    assert po.docstatus == 0, f"PO should be draft (docstatus=0), got {po.docstatus}"
    print(f"  PASS V7: PO '{po_name}' is in Draft state")
    return mp, po_name


def test_v8_multiple_pos_for_same_mp(ctx):
    """V8: Can create a second PO for remaining items after first purchase."""
    from manufyxinvenzaerp.production_management.doctype.material_planning.material_planning import make_purchase_order
    mp = _make_test_mp(ctx)
    # First PO: order only ANGLE
    po1 = make_purchase_order(mp.name, ctx.supplier, json.dumps(["TEST-ANGLE-65X6"]))
    # Second PO: order NUT separately (different supplier/batch)
    po2 = make_purchase_order(mp.name, ctx.supplier, json.dumps(["TEST-NUT-M16"]))
    assert po1 != po2, "Two different POs should be created"
    mp.reload()
    linked = {r.item_code: r.purchase_order for r in mp.unavailable_items}
    assert linked["TEST-ANGLE-65X6"] == po1
    assert linked["TEST-NUT-M16"] == po2
    print(f"  PASS V8: Two POs created — ANGLE→{po1}, NUT→{po2}")
    return mp, po1, po2


# ── Runner ────────────────────────────────────────────────────────────────────

def run():
    frappe.set_user("Administrator")
    ctx = get_ctx()

    print(f"\nPurchase Order Creation Validation")
    print(f"  Supplier  : {ctx.supplier}")
    print(f"  Warehouse : {ctx.warehouse}")
    print()

    tests = [
        ("V1 — PO created with correct supplier",      lambda: test_v1_po_created_with_correct_supplier(ctx)),
        ("V2 — PO items match unavailable rows",       lambda: test_v2_po_items_match_unavailable_rows(ctx)),
        ("V3 — PO linked back on rows",                lambda: test_v3_po_linked_back_on_rows(ctx)),
        ("V4 — Partial selection only links selected", lambda: test_v4_partial_selection_only_links_selected(ctx)),
        ("V5 — Error when no items selected",          lambda: test_v5_error_when_no_items_selected(ctx)),
        ("V6 — Error when no unavailable items",       lambda: test_v6_error_when_no_unavailable_items(ctx)),
        ("V7 — PO is created as draft",                lambda: test_v7_po_is_draft(ctx)),
        ("V8 — Multiple POs for same MP",              lambda: test_v8_multiple_pos_for_same_mp(ctx)),
    ]

    passed = failed = 0
    for label, fn in tests:
        try:
            fn()
            passed += 1
        except Exception as e:
            print(f"  FAIL {label}: {e}")
            failed += 1

    print(f"\nResults: {passed} passed, {failed} failed out of {passed + failed} tests")
    frappe.db.rollback()
