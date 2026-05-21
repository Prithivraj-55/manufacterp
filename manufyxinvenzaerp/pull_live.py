"""
Pull all data from live site via Frappe REST API and restore to fl.local.
Run with: bench --site fl.local execute manufyxinvenzaerp.pull_live.run
"""
import frappe
from frappe.utils import flt, cint
import requests

LIVE_URL = "https://erp.manufyx.co.in"
LIVE_USER = "Administrator"
LIVE_PASS = "M@nufYx@0154"

# ── Helpers ──────────────────────────────────────────────────────────────────

def get_session():
    s = requests.Session()
    r = s.post(f"{LIVE_URL}/api/method/login",
               json={"usr": LIVE_USER, "pwd": LIVE_PASS})
    r.raise_for_status()
    print("  Logged in to live site.")
    return s

def fetch_list(session, doctype, fields=None, filters=None, limit=500):
    params = {"limit": limit, "limit_start": 0}
    if fields:
        import json
        params["fields"] = json.dumps(fields)
    if filters:
        import json
        params["filters"] = json.dumps(filters)
    all_records = []
    while True:
        r = session.get(f"{LIVE_URL}/api/resource/{doctype}", params=params)
        data = r.json().get("data", [])
        if not data:
            break
        all_records.extend(data)
        if len(data) < limit:
            break
        params["limit_start"] += limit
    return all_records

def fetch_doc(session, doctype, name):
    r = session.get(f"{LIVE_URL}/api/resource/{doctype}/{requests.utils.quote(name, safe='')}")
    if r.status_code == 200:
        return r.json().get("data", {})
    return {}

def upsert(doctype, data, ignore_fields=None):
    """Insert or update a document, skipping meta/system fields."""
    skip = {"creation","modified","modified_by","owner","docstatus_original",
            "idx","__islocal","__unsaved","__run_link_triggers"}
    if ignore_fields:
        skip.update(ignore_fields)
    clean = {k: v for k, v in data.items() if k not in skip and not k.startswith("__")}
    name = clean.get("name")
    if not name:
        return
    if frappe.db.exists(doctype, name):
        try:
            doc = frappe.get_doc(doctype, name)
            doc.update(clean)
            doc.save(ignore_permissions=True)
        except Exception as e:
            print(f"    WARN update {doctype} {name}: {e}")
    else:
        try:
            doc = frappe.get_doc({"doctype": doctype, **clean})
            doc.insert(ignore_permissions=True, ignore_if_duplicate=True)
        except Exception as e:
            print(f"    WARN insert {doctype} {name}: {e}")

# ── Sync functions ────────────────────────────────────────────────────────────

def sync_singles(session, doctypes):
    for dt in doctypes:
        try:
            r = session.get(f"{LIVE_URL}/api/resource/{dt}/{dt}")
            if r.status_code == 200:
                data = r.json().get("data", {})
                if data:
                    doc = frappe.get_single(dt)
                    for k, v in data.items():
                        if not k.startswith("__") and hasattr(doc, k):
                            setattr(doc, k, v)
                    doc.save(ignore_permissions=True)
                    print(f"  Synced single: {dt}")
        except Exception as e:
            print(f"  WARN single {dt}: {e}")

def sync_doctype(session, doctype, fields=None, filters=None, skip_submit=False, batch_size=200):
    records = fetch_list(session, doctype, fields=["name"], filters=filters, limit=batch_size)
    print(f"  {doctype}: {len(records)} records")
    for rec in records:
        doc = fetch_doc(session, doctype, rec["name"])
        if not doc:
            continue
        # Handle submittable docs — insert as draft then submit
        docstatus = cint(doc.get("docstatus", 0))
        doc["docstatus"] = 0
        upsert(doctype, doc)
        if docstatus == 1 and not skip_submit:
            try:
                local = frappe.get_doc(doctype, doc["name"])
                if local.docstatus == 0:
                    local.submit()
            except Exception as e:
                print(f"    WARN submit {doctype} {doc['name']}: {e}")
    frappe.db.commit()

# ── Main ─────────────────────────────────────────────────────────────────────

def run():
    frappe.set_user("Administrator")
    session = get_session()

    # ── 1. Master Data ──────────────────────────────────────────────────────
    print("\n[1] Syncing master data...")

    COMPANY = "Manufyx Invenza Private Limited"

    # UOM
    print("  UOMs...")
    for rec in fetch_list(session, "UOM", fields=["name"]):
        if not frappe.db.exists("UOM", rec["name"]):
            try:
                frappe.get_doc({"doctype": "UOM", "uom_name": rec["name"]}).insert(ignore_permissions=True)
            except Exception:
                pass
    frappe.db.commit()

    # Accounts — update existing ones from live (COA already created by company setup)
    print("  Accounts (update from live)...")
    accs = fetch_list(session, "Account", fields=["name","parent_account","is_group","account_type","root_type"], limit=500)
    for rec in accs:
        live_name = rec["name"]
        # Map live account name (- MIPL) to local account name (- MIPL)
        if frappe.db.exists("Account", live_name):
            try:
                doc = fetch_doc(session, "Account", live_name)
                local = frappe.get_doc("Account", live_name)
                for f in ["account_type","root_type","account_currency","tax_rate"]:
                    if doc.get(f):
                        setattr(local, f, doc[f])
                local.save(ignore_permissions=True)
            except Exception:
                pass
        else:
            try:
                doc = fetch_doc(session, "Account", live_name)
                if doc:
                    upsert("Account", doc)
            except Exception:
                pass
    frappe.db.commit()

    # Warehouses
    print("  Warehouses...")
    whs = fetch_list(session, "Warehouse", fields=["name","parent_warehouse","is_group"])
    roots = [w for w in whs if not w.get("parent_warehouse")]
    children = [w for w in whs if w.get("parent_warehouse")]
    for rec in roots + children:
        if not frappe.db.exists("Warehouse", rec["name"]):
            doc = fetch_doc(session, "Warehouse", rec["name"])
            if doc:
                upsert("Warehouse", doc)
        else:
            # update warehouse type
            doc = fetch_doc(session, "Warehouse", rec["name"])
            if doc and doc.get("warehouse_type"):
                frappe.db.set_value("Warehouse", rec["name"], "warehouse_type", doc["warehouse_type"])
    frappe.db.commit()

    # Item Groups
    print("  Item Groups...")
    igs = fetch_list(session, "Item Group", fields=["name","parent_item_group","is_group"])
    roots = [i for i in igs if not i.get("parent_item_group")]
    children = [i for i in igs if i.get("parent_item_group")]
    for rec in roots + children:
        doc = fetch_doc(session, "Item Group", rec["name"])
        if doc:
            upsert("Item Group", doc)
    frappe.db.commit()

    # Customer/Supplier Groups + Territory
    for dt in ["Customer Group", "Supplier Group", "Territory", "Sales Person"]:
        print(f"  {dt}...")
        recs = fetch_list(session, dt, fields=["name"])
        for rec in recs:
            doc = fetch_doc(session, dt, rec["name"])
            if doc:
                upsert(dt, doc)
        frappe.db.commit()

    # Price Lists
    print("  Price Lists...")
    for rec in fetch_list(session, "Price List", fields=["name"]):
        doc = fetch_doc(session, "Price List", rec["name"])
        if doc:
            upsert("Price List", doc)
    frappe.db.commit()

    # GST HSN Codes
    print("  GST HSN Codes...")
    for rec in fetch_list(session, "GST HSN Code", fields=["name"], limit=500):
        doc = fetch_doc(session, "GST HSN Code", rec["name"])
        if doc:
            upsert("GST HSN Code", doc)
    frappe.db.commit()

    # ── 2. Items ─────────────────────────────────────────────────────────────
    print("\n[2] Syncing Items...")
    sync_doctype(session, "Item", skip_submit=True)
    sync_doctype(session, "Item Price", skip_submit=True)

    # ── 3. Parties ───────────────────────────────────────────────────────────
    print("\n[3] Syncing Customers & Suppliers...")
    sync_doctype(session, "Customer", skip_submit=True)
    sync_doctype(session, "Supplier", skip_submit=True)
    sync_doctype(session, "Address", skip_submit=True)
    sync_doctype(session, "Contact", skip_submit=True)

    # ── 4. Operations & Routing ──────────────────────────────────────────────
    print("\n[4] Syncing Manufacturing Masters...")
    sync_doctype(session, "Operation", skip_submit=True)
    sync_doctype(session, "Workstation", skip_submit=True)
    sync_doctype(session, "Routing", skip_submit=True)

    # ── 5. Batch & Stock ─────────────────────────────────────────────────────
    print("\n[5] Syncing Batches...")
    sync_doctype(session, "Batch", skip_submit=True)

    # ── 6. BOM ───────────────────────────────────────────────────────────────
    print("\n[6] Syncing BOMs...")
    sync_doctype(session, "BOM", skip_submit=False)

    # ── 7. Custom Doctypes ───────────────────────────────────────────────────
    print("\n[7] Syncing Custom Doctypes...")
    sync_doctype(session, "Drawing", skip_submit=False)
    sync_doctype(session, "Material Planning", skip_submit=False)
    sync_doctype(session, "Supplier Operation Entry", skip_submit=False)

    # ── 8. Transactions ──────────────────────────────────────────────────────
    print("\n[8] Syncing Transactions...")
    sync_doctype(session, "Sales Order", skip_submit=False)
    sync_doctype(session, "Purchase Order", skip_submit=False)
    sync_doctype(session, "Material Request", skip_submit=False)
    sync_doctype(session, "Request for Quotation", skip_submit=False)
    sync_doctype(session, "Supplier Quotation", skip_submit=False)
    sync_doctype(session, "Purchase Receipt", skip_submit=False)
    sync_doctype(session, "Purchase Invoice", skip_submit=False)
    sync_doctype(session, "Sales Invoice", skip_submit=False)
    sync_doctype(session, "Delivery Note", skip_submit=False)
    sync_doctype(session, "Stock Entry", skip_submit=False)
    sync_doctype(session, "Production Plan", skip_submit=False)
    sync_doctype(session, "Work Order", skip_submit=False)
    sync_doctype(session, "Job Card", skip_submit=False)
    sync_doctype(session, "Subcontracting Order", skip_submit=False)

    frappe.db.commit()
    print("\n✅ Live data pull complete!")
    # Summary
    for dt in ["Item","Customer","Supplier","Sales Order","Purchase Order",
               "Drawing","BOM","Production Plan","Stock Entry","Batch"]:
        cnt = frappe.db.count(dt)
        print(f"   {dt}: {cnt}")
