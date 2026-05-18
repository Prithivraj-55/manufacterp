"""
Creates complete test data for manual Material Planning testing.

Three scenarios in one BOM:
  Item A — TEST-PLATE-75X10   (stock with EXACT dimensions)  → Available Raw Materials
  Item B — TEST-ANGLE-50X50X5 (stock with WRONG dimensions)  → Material Mapping
  Item C — TEST-ROD-20MM      (no stock at all)              → Unavailable Items

Run:
  bench --site fl.local execute manufyxinvenzaerp.tests.create_test_data.run
"""

import frappe
from frappe.utils import today, flt, nowdate


# ── Config (auto-detected from DB) ───────────────────────────────────────────

def get_context():
    company_row = frappe.db.sql("SELECT name, abbr FROM tabCompany LIMIT 1", as_dict=True)
    if not company_row:
        frappe.throw("No company found in DB")
    company = company_row[0]["name"]
    abbr    = company_row[0]["abbr"]

    warehouse_row = frappe.db.sql(
        "SELECT name FROM tabWarehouse WHERE is_group=0 AND name LIKE %s LIMIT 1",
        (f"% - {abbr}",), as_dict=True
    )
    warehouse = warehouse_row[0]["name"] if warehouse_row else frappe.db.sql(
        "SELECT name FROM tabWarehouse WHERE is_group=0 LIMIT 1", as_dict=True
    )[0]["name"]

    ig_row = frappe.db.sql(
        "SELECT name FROM `tabItem Group` WHERE is_group=0 LIMIT 1", as_dict=True
    )
    item_group = ig_row[0]["name"] if ig_row else "All Item Groups"

    hsn_row = frappe.db.sql(
        "SELECT name FROM `tabGST HSN Code` WHERE LENGTH(name)>=6 LIMIT 1", as_dict=True
    )
    hsn = hsn_row[0]["name"] if hsn_row else ""

    return frappe._dict(
        company=company, abbr=abbr, warehouse=warehouse,
        item_group=item_group, hsn=hsn
    )


# ── Helpers ───────────────────────────────────────────────────────────────────

def make_item(ctx, item_code, item_name, stock_uom="Kg"):
    if frappe.db.exists("Item", item_code):
        print(f"  Item already exists: {item_code}")
        return item_code
    doc = frappe.get_doc({
        "doctype": "Item",
        "item_code": item_code,
        "item_name": item_name,
        "item_group": ctx.item_group,
        "stock_uom": stock_uom,
        "is_stock_item": 1,
        "has_batch_no": 1,
        "create_new_batch": 0,
        "gst_hsn_code": ctx.hsn,
        "custom_parent_item_group": ctx.item_group,
    })
    doc.insert(ignore_permissions=True)
    print(f"  Created item: {item_code}")
    return item_code


def make_fg_item(ctx, item_code, item_name):
    if frappe.db.exists("Item", item_code):
        print(f"  FG Item already exists: {item_code}")
        return item_code
    doc = frappe.get_doc({
        "doctype": "Item",
        "item_code": item_code,
        "item_name": item_name,
        "item_group": ctx.item_group,
        "stock_uom": "Nos",
        "is_stock_item": 1,
        "has_batch_no": 0,
        "gst_hsn_code": ctx.hsn,
        "custom_parent_item_group": ctx.item_group,
    })
    doc.insert(ignore_permissions=True)
    print(f"  Created FG item: {item_code}")
    return item_code


def make_batch(item_code, batch_id, length=0.0, width=0.0, thickness=0.0, sec_qty=0, sec_uom="Nos"):
    if frappe.db.exists("Batch", batch_id):
        print(f"  Batch already exists: {batch_id}")
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
    doc.insert(ignore_permissions=True)
    print(f"  Created batch: {batch_id}  (L={length}, W={width}, T={thickness})")
    return batch_id


def make_stock_entry(ctx, item_code, batch_id, qty, uom="Kg"):
    """Create a Material Receipt stock entry to put stock into the warehouse."""
    se = frappe.new_doc("Stock Entry")
    se.stock_entry_type = "Material Receipt"
    se.company = ctx.company
    se.posting_date = today()
    se.append("items", {
        "item_code": item_code,
        "qty": qty,
        "uom": uom,
        "stock_uom": uom,
        "conversion_factor": 1,
        "t_warehouse": ctx.warehouse,
        "batch_no": batch_id,
        "basic_rate": 100,
        "allow_zero_valuation_rate": 0,
    })
    se.insert(ignore_permissions=True)
    se.submit()
    print(f"  Stock entry submitted: {se.name}  ({item_code} {qty} {uom} → {ctx.warehouse})")
    return se.name


def make_bom(ctx, fg_item, bom_items_list, bom_name_hint="TEST-MP-BOM"):
    existing = frappe.db.sql(
        "SELECT name FROM tabBOM WHERE item=%s AND is_active=1 LIMIT 1",
        fg_item, as_dict=True
    )
    if existing:
        print(f"  BOM already exists: {existing[0]['name']}")
        return existing[0]["name"]

    bom = frappe.new_doc("BOM")
    bom.item = fg_item
    bom.quantity = 1
    bom.company = ctx.company
    bom.currency = frappe.db.get_value("Company", ctx.company, "default_currency") or "INR"

    for i, (item_code, qty, length, width, thickness) in enumerate(bom_items_list, 1):
        bom.append("items", {
            "item_code": item_code,
            "qty": qty,
            "uom": frappe.db.get_value("Item", item_code, "stock_uom") or "Kg",
            "stock_uom": frappe.db.get_value("Item", item_code, "stock_uom") or "Kg",
            "conversion_factor": 1,
            "custom_length": length,
            "custom_width": width,
            "custom_thickness": thickness,
            "custom_item_number": i,
        })

    bom.insert(ignore_permissions=True)
    bom.submit()
    print(f"  Created & submitted BOM: {bom.name}  (FG: {fg_item})")
    return bom.name


# ── Main ──────────────────────────────────────────────────────────────────────

def run():
    frappe.set_user("Administrator")
    ctx = get_context()

    print(f"\n{'='*55}")
    print(f"Company  : {ctx.company}")
    print(f"Warehouse: {ctx.warehouse}")
    print(f"Item Group: {ctx.item_group}")
    print(f"{'='*55}\n")

    # ── 1. Items ──────────────────────────────────────────────────────────────
    print("[1] Creating Items...")
    ITEM_A = "TEST-PLATE-75X10"
    ITEM_B = "TEST-ANGLE-50X50X5"
    ITEM_C = "TEST-ROD-20MM"
    ITEM_FG = "TEST-FABRICATED-FRAME"

    make_item(ctx, ITEM_A, "Test MS Plate 75x10mm")
    make_item(ctx, ITEM_B, "Test MS Angle 50x50x5mm")
    make_item(ctx, ITEM_C, "Test MS Round Rod 20mm")
    make_fg_item(ctx, ITEM_FG, "Test Fabricated Frame Assembly")
    frappe.db.commit()

    # ── 2. Batches ────────────────────────────────────────────────────────────
    print("\n[2] Creating Batches...")

    # Item A: Batch with EXACT dimensions (L=6000, W=75, T=10)
    BATCH_A = "TEST-BATCH-PLATE-EXACT"
    make_batch(ITEM_A, BATCH_A, length=6000.0, width=75.0, thickness=10.0, sec_qty=5, sec_uom="Nos")

    # Item B: Batch with DIFFERENT dimensions (L=3000 instead of 6000)
    BATCH_B = "TEST-BATCH-ANGLE-WRONG"
    make_batch(ITEM_B, BATCH_B, length=3000.0, width=50.0, thickness=5.0, sec_qty=3, sec_uom="Nos")

    # Item C: No batch / no stock
    frappe.db.commit()

    # ── 3. Stock Entries ──────────────────────────────────────────────────────
    print("\n[3] Creating Stock Entries (Material Receipt)...")
    try:
        make_stock_entry(ctx, ITEM_A, BATCH_A, qty=354.0)   # 354 Kg = 5 pcs × 6m × ~11.8 kg/m
    except Exception as e:
        print(f"  WARN Stock entry for {ITEM_A}: {e}")

    try:
        make_stock_entry(ctx, ITEM_B, BATCH_B, qty=90.0)    # wrong-dim stock
    except Exception as e:
        print(f"  WARN Stock entry for {ITEM_B}: {e}")

    # Item C intentionally has NO stock
    frappe.db.commit()

    # ── 4. BOM ────────────────────────────────────────────────────────────────
    print("\n[4] Creating BOM...")
    # BOM items: (item_code, qty, length, width, thickness)
    # BOM dimensions must MATCH the batch dims for Item A (exact match test)
    bom_items = [
        (ITEM_A, 70.8,  6000.0, 75.0,  10.0),   # exact match with BATCH_A
        (ITEM_B, 45.0,  6000.0, 50.0,  5.0),    # stock exists but BATCH_B is L=3000 → wrong dim
        (ITEM_C, 25.0,  0.0,    20.0,  0.0),    # no stock
    ]
    bom_name = make_bom(ctx, ITEM_FG, bom_items)
    frappe.db.commit()

    # ── Summary ───────────────────────────────────────────────────────────────
    print(f"\n{'='*55}")
    print("TEST DATA CREATED SUCCESSFULLY")
    print(f"{'='*55}")
    print(f"\nBOM to use   : {bom_name}")
    print(f"Warehouse    : {ctx.warehouse}")
    print(f"\nExpected results after 'Check Stock Availability':")
    print(f"  Available Raw Materials : {ITEM_A} (exact L/W/T match with {BATCH_A})")
    print(f"  Material Mapping        : {ITEM_B} (stock exists, different length)")
    print(f"  Unavailable Items       : {ITEM_C} (no stock at all)")
    print(f"\n{'='*55}")
    print("PROCEDURE TO TEST IN UI")
    print(f"{'='*55}")
    print("""
Step 1 — Open Material Planning
  Manufacturing → Material Planning → New

Step 2 — Fill Details tab
  • Company    : {company}
  • Date       : Today
  • Warehouse  : {warehouse}

Step 3 — Go to 'Selected BOMs' tab
  • Add Row → BOM No : {bom}
  • The Item Code, Qty, etc. auto-fill from the Drawing

Step 4 — Click 'Get Raw Materials' button
  → Raw Materials tab populates with 3 rows (Items A, B, C)

Step 5 — Go to 'Stock Analysis' tab → Click 'Check Stock Availability'
  → Available Raw Materials : {item_a} with batch {batch_a}
  → Material Mapping        : {item_b} (pick any batch manually)
  → Unavailable Items       : {item_c}

Step 6 — In Material Mapping, click on a row → 'Assign Batch'
  → Type in search, item name shows alongside batch ID
  → On selecting a batch, 'Planned Item' auto-fills

Step 7 — Save → Submit
  → Stock Analysis tab stays visible even after submit

Step 8 — After submit, click Create → Production Plan
  → Production Plan is created with the BOM items
""".format(
        company=ctx.company,
        warehouse=ctx.warehouse,
        bom=bom_name,
        item_a=ITEM_A,
        item_b=ITEM_B,
        item_c=ITEM_C,
        batch_a=BATCH_A,
    ))
