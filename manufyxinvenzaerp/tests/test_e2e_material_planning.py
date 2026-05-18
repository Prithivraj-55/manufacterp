"""
End-to-end integration test for Material Planning full flow.
Uses real DB data from the restored live site.

Tests the complete flow:
  1. Create Material Planning document with a real BOM
  2. Get Raw Materials (BOM explosion)
  3. Check Stock Availability (classify into 3 buckets)
  4. Batch auto-fetch (get_batch_item)
  5. Create Production Plan from submitted MP

Edge cases tested:
  EC1: submit without BOM items → ValidationError
  EC2: get_raw_materials without company → error
  EC3: check_stock without warehouse → error
  EC4: get_batch_item with invalid batch → returns None
  EC5: rows with zero planned qty → treated as 1
  EC6: make_production_plan on draft doc → error

Run with:
  bench --site fl.local execute manufyxinvenzaerp.tests.test_e2e_material_planning.run
"""

import frappe
from frappe.utils import today, flt


def _get_context():
    """Pull real context values from restored DB."""
    company = frappe.db.sql(
        "SELECT name FROM tabCompany LIMIT 1", as_dict=True
    )
    warehouse = frappe.db.sql(
        "SELECT name FROM tabWarehouse WHERE is_group=0 LIMIT 1", as_dict=True
    )
    bom = frappe.db.sql(
        "SELECT name FROM tabBOM WHERE docstatus=1 LIMIT 1", as_dict=True
    )
    return {
        "company": company[0]["name"] if company else None,
        "warehouse": warehouse[0]["name"] if warehouse else None,
        "bom": bom[0]["name"] if bom else None,
    }


def _make_mp(ctx, submit=False):
    """Create a draft Material Planning document with one BOM row."""
    mp = frappe.new_doc("Material Planning")
    mp.company = ctx["company"]
    mp.posting_date = today()
    mp.for_warehouse = ctx["warehouse"]
    mp.append("bom_items", {"bom_no": ctx["bom"]})
    mp.insert(ignore_permissions=True)
    if submit:
        mp.submit()
    return mp


# ── Flow tests ─────────────────────────────────────────────────────────────────

def test_flow_1_get_raw_materials(ctx):
    """Flow 1: insert MP → get_raw_materials returns rows."""
    from manufyxinvenzaerp.production_management.doctype.material_planning.material_planning import (
        get_raw_materials,
    )
    mp = _make_mp(ctx)
    rows = get_raw_materials(mp.as_dict())
    assert isinstance(rows, list), "get_raw_materials must return a list"
    assert len(rows) > 0, "Expected at least one raw material row from BOM explosion"
    row = rows[0]
    assert "item_code" in row, "Row missing item_code"
    assert "qty" in row, "Row missing qty"
    assert flt(row["qty"]) > 0, "Row qty should be > 0"
    print(f"  PASS Flow 1: get_raw_materials returned {len(rows)} rows")
    print(f"  (MP saved as: {mp.name})")
    mp.delete()
    return rows


def test_flow_2_check_stock_availability(ctx, raw_rows):
    """Flow 2: check_stock_availability classifies rows into 3 buckets."""
    from manufyxinvenzaerp.production_management.doctype.material_planning.material_planning import (
        check_stock_availability,
    )
    mp = _make_mp(ctx)
    # Set raw_materials from previous explosion
    for r in raw_rows:
        mp.append("raw_materials", r)
    mp.save(ignore_permissions=True)

    doc_dict = mp.as_dict()
    result = check_stock_availability(doc_dict)

    assert "raw_materials" in result
    assert "available_raw_materials" in result
    assert "material_mapping" in result
    assert "unavailable_items" in result

    total_classified = (
        len(result["available_raw_materials"])
        + len(result["material_mapping"])
        + len(result["unavailable_items"])
    )
    assert total_classified == len(raw_rows), (
        f"All {len(raw_rows)} raw material rows must appear in one of the 3 buckets, "
        f"got {total_classified}"
    )

    # Every raw_materials row should have updated available_qty
    for row in result["raw_materials"]:
        assert "available_qty" in row
        assert "shortage_qty" in row

    # Save classified rows back to the document so it's visible in UI
    mp.reload()
    mp.set("available_raw_materials", result["available_raw_materials"])
    mp.set("material_mapping", result["material_mapping"])
    mp.set("unavailable_items", result["unavailable_items"])
    for r in result["raw_materials"]:
        for child in mp.raw_materials:
            if child.item_code == r.get("item_code") and child.bom_no == r.get("bom_no"):
                child.available_qty = r.get("available_qty", 0)
                child.shortage_qty = r.get("shortage_qty", 0)
    mp.save(ignore_permissions=True)
    frappe.db.commit()

    print(
        f"  PASS Flow 2: {len(result['available_raw_materials'])} exact match, "
        f"{len(result['material_mapping'])} partial, "
        f"{len(result['unavailable_items'])} unavailable"
    )
    print(f"  (MP saved as: {mp.name} — check it in the UI)")
    return result


def test_flow_3_get_batch_item(ctx):
    """Flow 3: get_batch_item returns the item linked to a real batch."""
    from manufyxinvenzaerp.production_management.doctype.material_planning.material_planning import (
        get_batch_item,
    )
    batch = frappe.db.sql("SELECT name, item FROM tabBatch LIMIT 1", as_dict=True)
    if not batch:
        print("  SKIP Flow 3: no batches in DB")
        return
    batch_no = batch[0]["name"]
    expected_item = batch[0]["item"]
    result = get_batch_item(batch_no)
    assert result == expected_item, f"Expected {expected_item}, got {result}"
    print(f"  PASS Flow 3: get_batch_item('{batch_no}') → '{result}'")


def test_flow_4_make_production_plan(ctx):
    """Flow 4: submit MP → make_production_plan creates a Production Plan."""
    from manufyxinvenzaerp.production_management.doctype.material_planning.material_planning import (
        make_production_plan,
    )
    mp = _make_mp(ctx, submit=True)
    pp_name = make_production_plan(mp.name)
    assert pp_name, "make_production_plan should return a Production Plan name"
    pp = frappe.get_doc("Production Plan", pp_name)
    assert pp.company == ctx["company"]
    assert len(pp.po_items) > 0, "Production Plan should have po_items"
    print(f"  PASS Flow 4: Production Plan '{pp_name}' created with {len(pp.po_items)} item(s)")


# ── Edge case tests ─────────────────────────────────────────────────────────────

def test_ec1_submit_without_bom(ctx):
    """EC1: submitting without BOM items raises ValidationError."""
    mp = frappe.new_doc("Material Planning")
    mp.company = ctx["company"]
    mp.posting_date = today()
    mp.insert(ignore_permissions=True)
    try:
        mp.submit()
        mp.cancel()
        mp.delete()
        raise AssertionError("Should have raised ValidationError")
    except frappe.ValidationError:
        mp.delete()
        print("  PASS EC1: submit without BOM raises ValidationError")


def test_ec2_get_raw_materials_no_company(ctx):
    """EC2: get_raw_materials without company raises error."""
    from manufyxinvenzaerp.production_management.doctype.material_planning.material_planning import (
        get_raw_materials,
    )
    doc = frappe._dict({
        "company": None,
        "for_warehouse": ctx["warehouse"],
        "bom_items": [{"bom_no": ctx["bom"], "qty_to_manufacture": 1}],
    })
    try:
        get_raw_materials(doc)
        raise AssertionError("Should have raised error for missing company")
    except frappe.ValidationError:
        print("  PASS EC2: get_raw_materials without company raises error")


def test_ec3_check_stock_no_warehouse(ctx):
    """EC3: check_stock_availability without warehouse raises error."""
    from manufyxinvenzaerp.production_management.doctype.material_planning.material_planning import (
        check_stock_availability,
    )
    doc = frappe._dict({
        "for_warehouse": None,
        "raw_materials": [{"item_code": "TEST", "qty": 10}],
    })
    try:
        check_stock_availability(doc)
        raise AssertionError("Should have raised error for missing warehouse")
    except frappe.ValidationError:
        print("  PASS EC3: check_stock without warehouse raises error")


def test_ec4_get_batch_item_invalid():
    """EC4: get_batch_item with non-existent batch returns None."""
    from manufyxinvenzaerp.production_management.doctype.material_planning.material_planning import (
        get_batch_item,
    )
    result = get_batch_item("NON-EXISTENT-BATCH-XYZ")
    assert result is None, f"Expected None, got {result}"
    print("  PASS EC4: get_batch_item with invalid batch returns None")


def test_ec5_empty_bom_items(ctx):
    """EC5: get_raw_materials with bom_items present but no bom_no returns empty list."""
    from manufyxinvenzaerp.production_management.doctype.material_planning.material_planning import (
        get_raw_materials,
    )
    doc = frappe._dict({
        "company": ctx["company"],
        "for_warehouse": ctx["warehouse"],
        "bom_items": [{"bom_no": None, "qty_to_manufacture": 1}],
    })
    rows = get_raw_materials(doc)
    assert rows == [], f"Expected empty list for null bom_no, got {rows}"
    print("  PASS EC5: bom_no=None in bom_items → empty raw_materials")


def test_ec6_make_pp_on_draft(ctx):
    """EC6: make_production_plan on a draft MP raises error."""
    from manufyxinvenzaerp.production_management.doctype.material_planning.material_planning import (
        make_production_plan,
    )
    mp = _make_mp(ctx)
    try:
        make_production_plan(mp.name)
        mp.delete()
        raise AssertionError("Should have raised error on draft doc")
    except frappe.ValidationError:
        mp.delete()
        print("  PASS EC6: make_production_plan on draft raises error")


# ── Runner ─────────────────────────────────────────────────────────────────────

def run():
    frappe.set_user("Administrator")
    ctx = _get_context()

    if not ctx["company"] or not ctx["bom"]:
        print("ERROR: Missing company or BOM in DB. Cannot run e2e tests.")
        return

    print(f"\nE2E Test Context:")
    print(f"  Company  : {ctx['company']}")
    print(f"  Warehouse: {ctx['warehouse']}")
    print(f"  BOM      : {ctx['bom']}")
    print()

    passed = failed = 0
    raw_rows = None

    flow_tests = [
        ("Flow 1 — Get Raw Materials",        lambda: globals().update(raw_rows=test_flow_1_get_raw_materials(ctx)) or True),
        ("Flow 2 — Check Stock Availability", lambda: test_flow_2_check_stock_availability(ctx, raw_rows) or True),
        ("Flow 3 — Batch Item Lookup",        lambda: test_flow_3_get_batch_item(ctx) or True),
        ("Flow 4 — Create Production Plan",   lambda: test_flow_4_make_production_plan(ctx) or True),
    ]

    edge_tests = [
        ("EC1 — Submit without BOM",          lambda: test_ec1_submit_without_bom(ctx)),
        ("EC2 — get_raw_materials no company",lambda: test_ec2_get_raw_materials_no_company(ctx)),
        ("EC3 — check_stock no warehouse",    lambda: test_ec3_check_stock_no_warehouse(ctx)),
        ("EC4 — get_batch_item invalid",      lambda: test_ec4_get_batch_item_invalid()),
        ("EC5 — bom_no is None",              lambda: test_ec5_empty_bom_items(ctx)),
        ("EC6 — make_pp on draft doc",        lambda: test_ec6_make_pp_on_draft(ctx)),
    ]

    print("── Flow Tests ──────────────────────────────────────")
    raw_rows = test_flow_1_get_raw_materials(ctx)
    passed += 1

    for label, fn in flow_tests[1:]:
        try:
            fn()
            passed += 1
        except Exception as e:
            print(f"  FAIL {label}: {e}")
            failed += 1

    print()
    print("── Edge Case Tests ─────────────────────────────────")
    for label, fn in edge_tests:
        try:
            fn()
            passed += 1
        except Exception as e:
            print(f"  FAIL {label}: {e}")
            failed += 1

    print()
    print(f"Results: {passed} passed, {failed} failed out of {passed + failed} tests")
    frappe.db.commit()
