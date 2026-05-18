"""
Test suite for Material Planning — check_stock_availability classification.

Use cases tested:
  UC1: Item with exact dimension batch match → available_raw_materials
  UC2: Item with stock but wrong dimensions  → material_mapping
  UC3: Item with zero stock                  → unavailable_items
  UC4: get_batch_item returns correct item for a batch
  UC5: check_stock_availability returns correct structure

Run with:
  bench --site fl.local execute manufyxinvenzaerp.tests.test_material_planning.run
"""

import frappe
from frappe.utils import flt
from unittest.mock import patch

_item_group = "All Item Groups"  # populated at runtime from DB
_hsn_code = ""                  # populated at runtime from DB


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_item(item_code, item_name, stock_uom="Kg", is_stock_item=1,
               has_batch_no=1, parent_item_group=None):
    if frappe.db.exists("Item", item_code):
        return item_code
    group = parent_item_group or _item_group
    doc = frappe.get_doc({
        "doctype": "Item",
        "item_code": item_code,
        "item_name": item_name,
        "item_group": group,
        "stock_uom": stock_uom,
        "is_stock_item": is_stock_item,
        "has_batch_no": has_batch_no,
        "custom_parent_item_group": group,
        "gst_hsn_code": _hsn_code,
    })
    doc.insert(ignore_permissions=True, ignore_if_duplicate=True)
    return item_code


def _make_batch(item_code, batch_id, length=0, width=0, thickness=0, sec_qty=0, sec_uom=""):
    if frappe.db.exists("Batch", batch_id):
        return batch_id
    doc = frappe.get_doc({
        "doctype": "Batch",
        "batch_id": batch_id,
        "item": item_code,
        "custom_length": length,
        "custom_width": width,
        "custom_thickness": thickness,
        "custom_sec_qty": sec_qty,
        "custom_sec_uom": sec_uom,
    })
    doc.insert(ignore_permissions=True, ignore_if_duplicate=True)
    return batch_id


def _raw_material_row(**kwargs):
    """Build a raw_materials child row dict as check_stock_availability expects."""
    defaults = {
        "item_code": "",
        "item_name": "",
        "bom_no": "BOM-TEST-001",
        "duno_mark_no": 1,
        "qty": 100.0,
        "uom": "Kg",
        "sec_qty": 2.0,
        "sec_uom": "Nos",
        "parent_item_group": "Plates",
        "length": 6000.0,
        "width": 75.0,
        "thickness": 10.0,
        "unit_weight": 5.89,
        "available_qty": 0.0,
        "shortage_qty": 100.0,
        "warehouse": "",
    }
    defaults.update(kwargs)
    return frappe._dict(defaults)


# ── Test cases ────────────────────────────────────────────────────────────────

def test_uc1_exact_match_goes_to_available(warehouse):
    """UC1: item with exact dimension batch → available_raw_materials."""
    from manufyxinvenzaerp.production_management.doctype.material_planning.material_planning import (
        check_stock_availability,
    )

    item_code = "TEST-PLATE-A"
    _make_item(item_code, "Test Plate A - Exact Match")

    # get_sbb_available_qty returns a matching batch
    matched_batches = [{"batch_no": "BATCH-A1", "qty": 120.0, "custom_sec_qty": 3, "custom_sec_uom": "Nos"}]

    doc = frappe._dict({
        "for_warehouse": warehouse,
        "raw_materials": [
            _raw_material_row(item_code=item_code, item_name="Test Plate A - Exact Match",
                              qty=100.0, length=6000.0, width=75.0, thickness=10.0),
        ],
    })

    with patch(
        "manufyxinvenzaerp.production_plan_management.production_plan.get_sbb_available_qty",
        return_value=(120.0, matched_batches),
    ):
        result = check_stock_availability(doc)

    assert len(result["available_raw_materials"]) == 1, "Expected 1 row in available_raw_materials"
    assert result["available_raw_materials"][0]["batch_no"] == "BATCH-A1"
    assert result["available_raw_materials"][0]["available_qty"] == 120.0
    assert result["material_mapping"] == [], "material_mapping should be empty"
    assert result["unavailable_items"] == [], "unavailable_items should be empty"
    # raw_materials row should have updated available_qty
    assert result["raw_materials"][0]["available_qty"] == 120.0
    assert result["raw_materials"][0]["shortage_qty"] == 0.0
    print("  PASS UC1: exact match → available_raw_materials")


def test_uc2_partial_stock_goes_to_mapping(warehouse):
    """UC2: stock exists but wrong dimensions → material_mapping."""
    from manufyxinvenzaerp.production_management.doctype.material_planning.material_planning import (
        check_stock_availability,
        _get_any_batch_qty,
    )

    item_code = "TEST-ANGLE-B"
    _make_item(item_code, "Test Angle B - Wrong Dims")

    doc = frappe._dict({
        "for_warehouse": warehouse,
        "raw_materials": [
            _raw_material_row(item_code=item_code, item_name="Test Angle B - Wrong Dims",
                              qty=50.0, parent_item_group="Structurals",
                              length=6000.0, width=50.0, thickness=5.0),
        ],
    })

    # No exact match, but there IS some stock (different dimensions)
    with patch(
        "manufyxinvenzaerp.production_plan_management.production_plan.get_sbb_available_qty",
        return_value=(0.0, []),
    ), patch(
        "manufyxinvenzaerp.production_management.doctype.material_planning.material_planning._get_any_batch_qty",
        return_value=80.0,
    ):
        result = check_stock_availability(doc)

    assert result["material_mapping"] != [], "material_mapping should have a row"
    assert result["material_mapping"][0]["item_code"] == item_code
    assert result["available_raw_materials"] == [], "available_raw_materials should be empty"
    assert result["unavailable_items"] == [], "unavailable_items should be empty"
    print("  PASS UC2: partial stock (wrong dims) → material_mapping")


def test_uc3_no_stock_goes_to_unavailable(warehouse):
    """UC3: zero stock → unavailable_items."""
    from manufyxinvenzaerp.production_management.doctype.material_planning.material_planning import (
        check_stock_availability,
    )

    item_code = "TEST-ROD-C"
    _make_item(item_code, "Test Rod C - No Stock")

    doc = frappe._dict({
        "for_warehouse": warehouse,
        "raw_materials": [
            _raw_material_row(item_code=item_code, item_name="Test Rod C - No Stock",
                              qty=30.0, parent_item_group="Structurals"),
        ],
    })

    with patch(
        "manufyxinvenzaerp.production_plan_management.production_plan.get_sbb_available_qty",
        return_value=(0.0, []),
    ), patch(
        "manufyxinvenzaerp.production_management.doctype.material_planning.material_planning._get_any_batch_qty",
        return_value=0.0,
    ):
        result = check_stock_availability(doc)

    assert result["unavailable_items"] != [], "unavailable_items should have a row"
    assert result["unavailable_items"][0]["item_code"] == item_code
    assert result["available_raw_materials"] == [], "available_raw_materials should be empty"
    assert result["material_mapping"] == [], "material_mapping should be empty"
    # shortage_qty should equal required qty
    assert result["raw_materials"][0]["shortage_qty"] == 30.0
    print("  PASS UC3: no stock → unavailable_items")


def test_uc4_get_batch_item(warehouse):
    """UC4: get_batch_item returns the item linked to a batch."""
    from manufyxinvenzaerp.production_management.doctype.material_planning.material_planning import (
        get_batch_item,
    )

    item_code = "TEST-PLATE-A"
    _make_item(item_code, "Test Plate A - Exact Match")
    batch_id = _make_batch(item_code, "BATCH-UC4-TEST")

    result = get_batch_item("BATCH-UC4-TEST")
    assert result == item_code, f"Expected {item_code}, got {result}"
    print("  PASS UC4: get_batch_item returns correct item")


def test_uc5_mixed_items_all_three_buckets(warehouse):
    """UC5: three items in one call → all three output tables populated."""
    from manufyxinvenzaerp.production_management.doctype.material_planning.material_planning import (
        check_stock_availability,
    )

    item_a = "TEST-PLATE-A"
    item_b = "TEST-ANGLE-B"
    item_c = "TEST-ROD-C"

    _make_item(item_a, "Test Plate A")
    _make_item(item_b, "Test Angle B")
    _make_item(item_c, "Test Rod C")

    doc = frappe._dict({
        "for_warehouse": warehouse,
        "raw_materials": [
            _raw_material_row(item_code=item_a, item_name="Test Plate A", qty=100.0),
            _raw_material_row(item_code=item_b, item_name="Test Angle B", qty=50.0),
            _raw_material_row(item_code=item_c, item_name="Test Rod C", qty=30.0),
        ],
    })

    def mock_sbb(item_code, warehouse, dimensions):
        if item_code == item_a:
            return 120.0, [{"batch_no": "B-A", "qty": 120.0, "custom_sec_qty": 2, "custom_sec_uom": "Nos"}]
        return 0.0, []

    def mock_any(item_code, warehouse):
        return 80.0 if item_code == item_b else 0.0

    with patch(
        "manufyxinvenzaerp.production_plan_management.production_plan.get_sbb_available_qty",
        side_effect=mock_sbb,
    ), patch(
        "manufyxinvenzaerp.production_management.doctype.material_planning.material_planning._get_any_batch_qty",
        side_effect=mock_any,
    ):
        result = check_stock_availability(doc)

    assert len(result["raw_materials"]) == 3
    assert len(result["available_raw_materials"]) == 1
    assert len(result["material_mapping"]) == 1
    assert len(result["unavailable_items"]) == 1
    assert result["available_raw_materials"][0]["item_code"] == item_a
    assert result["material_mapping"][0]["item_code"] == item_b
    assert result["unavailable_items"][0]["item_code"] == item_c
    print("  PASS UC5: mixed items → all three tables populated correctly")


# ── Runner ────────────────────────────────────────────────────────────────────

def run():
    frappe.set_user("Administrator")

    # Get any leaf warehouse from DB
    warehouse = frappe.db.sql(
        "SELECT name FROM tabWarehouse WHERE is_group=0 LIMIT 1", as_dict=True
    )
    if not warehouse:
        print("ERROR: No warehouse found in DB — cannot run tests.")
        return
    warehouse = warehouse[0]["name"]

    # Get a valid leaf item group
    global _item_group, _hsn_code
    ig = frappe.db.sql(
        "SELECT name FROM `tabItem Group` WHERE is_group=0 LIMIT 1", as_dict=True
    )
    _item_group = ig[0]["name"] if ig else "All Item Groups"

    hsn = frappe.db.sql(
        "SELECT name FROM `tabGST HSN Code` WHERE LENGTH(name) >= 6 LIMIT 1", as_dict=True
    )
    _hsn_code = hsn[0]["name"] if hsn else ""

    print(f"\nRunning Material Planning tests against warehouse: {warehouse}\n")

    tests = [
        test_uc1_exact_match_goes_to_available,
        test_uc2_partial_stock_goes_to_mapping,
        test_uc3_no_stock_goes_to_unavailable,
        test_uc4_get_batch_item,
        test_uc5_mixed_items_all_three_buckets,
    ]

    passed = 0
    failed = 0
    for test in tests:
        try:
            test(warehouse)
            passed += 1
        except Exception as e:
            print(f"  FAIL {test.__name__}: {e}")
            failed += 1

    print(f"\nResults: {passed} passed, {failed} failed out of {len(tests)} tests")
    frappe.db.rollback()  # Don't persist test items
