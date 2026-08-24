"""A Cut Sheet's balance: rewritten onto the old batch, or carried into a new one.

Manufyxinvenza Settings -> "Create New Batch for Cut Sheet Stock Entry" decides which.

  off  the batch keeps its name and takes the balance dimensions -- 12000 mm becomes
       6000 mm, 1 Nos, 50 Kg. This is how every site behaves today.
  on   the batch is never rewritten. A Repack empties it and creates a NEW batch
       carrying the balance, so a document already issued against the original still
       reads true.

The case worth testing in the off mode is the piece count. Consuming the cut reduces
the batch's Sec Qty proportionally -- it lands on 0 or 0.5 depending on how the
transfer was made -- and then the balance is written over the top of it, absolutely,
so the batch ends on the balance's own 1 Nos. That the right number comes out at all
depends on those two writes happening in that order inside one submit, and nothing
else guards it.

Worked example, the client's own:

    batch  L 12000, 1 Nos, 120 Kg   (unit weight 10)
    W1     L  6000, 1 Nos,  60 Kg   consumed by the Stock Entry
    W2     L  6000, 1 Nos,  60 Kg   the balance

Self-contained: it builds its own item, batch and entries, and cancels the entries it
made on the way out. Nothing is deleted.

Run: bench --site manufact execute manufyxinvenzaerp.tests.verify_cut_sheet_new_batch.run
"""

import frappe
from frappe.utils import flt

from manufyxinvenzaerp.production_management.doctype.cut_sheet.cut_sheet import (
    apply_w2_to_batch,
    revert_w2_from_batch,
)
from manufyxinvenzaerp.production_management.stock_entry import (
    _apply_cut_sheet_w2_as_new_batch,
    _batch_stock_by_warehouse,
)

checks = []

ITEM = "ZZTEST-CS-REPACK"
PREFIX = "ZZCSR"
UNIT_WEIGHT = 10.0
SETTING = "create_new_batch_for_cut_sheet_stock_entry"


def check(label, got, want):
    ok = got == want
    checks.append(ok)
    print("  %-4s %-56s got=%r want=%r" % ("OK" if ok else "FAIL", label, got, want))


def _company(warehouse=None):
    """The company that owns the warehouse in use.

    Not whichever Company sorts first: a site restored from a backup carries test
    companies, and the first of those owns none of these warehouses -- which fails
    much later, as "Warehouse X does not belong to company Y".
    """
    if warehouse:
        owner = frappe.db.get_value("Warehouse", warehouse, "company")
        if owner:
            return owner
    return frappe.get_all("Company", pluck="name")[0]


def _warehouse(company=None):
    for name in ("Stores - MIPL", "Work In Progress - MIPL"):
        if frappe.db.exists("Warehouse", name):
            return name
    filters = {"is_group": 0}
    if company:
        filters["company"] = company
    return frappe.get_all("Warehouse", filters=filters, pluck="name")[0]


def _ensure_item():
    """A Structurals item that auto-creates its batches, like every real one here."""
    if frappe.db.exists("Item", ITEM):
        return
    # HSN is mandatory on this site (india_compliance) -- borrow the one the other
    # test items already use rather than inventing a code.
    hsn = frappe.db.get_value("Item", "ZZTEST-CUT-SHEET", "gst_hsn_code") or frappe.db.get_value(
        "Item", "ISA130", "gst_hsn_code")
    frappe.get_doc({
        "doctype": "Item",
        "item_code": ITEM,
        "gst_hsn_code": hsn,
        "item_name": "ZZTEST Cut Sheet Repack",
        "item_group": frappe.db.get_value("Item", "ZZTEST-CUT-SHEET", "item_group")
                      or frappe.get_all("Item Group", filters={"is_group": 0}, pluck="name")[0],
        "stock_uom": "Kg",
        "is_stock_item": 1,
        "has_batch_no": 1,
        "create_new_batch": 1,
        "custom_batch_prefix": PREFIX,
        "custom_parent_item_group": "Structurals",
        "custom_unit_weight": UNIT_WEIGHT,
    }).insert(ignore_permissions=True)


def _stock(batch_no):
    return flt(sum(flt(r.qty) for r in _batch_stock_by_warehouse(batch_no)), 3)


def _dims(batch_no):
    d = frappe.db.get_value(
        "Batch", batch_no, ["custom_length", "custom_sec_qty"], as_dict=True
    ) or {}
    return flt(d.get("custom_length")), flt(d.get("custom_sec_qty"))


def _make_entry(se_type, company, rows):
    se = frappe.get_doc({
        "doctype": "Stock Entry", "stock_entry_type": se_type,
        "company": company, "items": rows,
    })
    se.insert(ignore_permissions=True)
    se.submit()
    return se


def run():
    warehouse = _warehouse()
    company = _company(warehouse)
    original_setting = frappe.db.get_single_value("Manufyxinvenza Settings", SETTING)
    receipt = issue = mp_name = None

    try:
        _ensure_item()

        print("=== a 12000 mm plate arrives as one batch ===")
        receipt = _make_entry("Material Receipt", company, [{
            "item_code": ITEM, "qty": 120, "t_warehouse": warehouse,
            # A brand-new item has no valuation of its own; the receipt has to say
            # what the steel is worth or the ledger cannot be written.
            "basic_rate": 50,
            "custom_parent_item_group": "Structurals", "custom_unit_weight": UNIT_WEIGHT,
            "custom_length": 12000, "custom_sec_qty": 1,
        }])
        batch = frappe.db.get_value(
            "Batch", {"reference_doctype": "Stock Entry", "reference_name": receipt.name}, "name")
        check("a batch was created", bool(batch), True)
        check("named for its length", batch.startswith("%s-L12000-" % PREFIX), True)
        check("its dimensions", _dims(batch), (12000.0, 1.0))
        check("its weight", _stock(batch), 120.0)

        print()
        print("=== nested: W1 6000 x 1, balance 6000 x 1 ===")
        cs = frappe.get_doc({
            "doctype": "Cut Sheet", "company": company, "item_code": ITEM,
            "batch_no": batch, "warehouse": warehouse,
            "parent_item_group": "Structurals", "unit_weight": UNIT_WEIGHT,
            "w1_length": 6000, "w1_sec_qty": 1,
            "w2_length": 6000, "w2_sec_qty": 1,
        })
        cs.insert(ignore_permissions=True)
        check("the sheet weighs what the batch does", flt(cs.sheet_qty), 120.0)
        check("W1 total", flt(cs.w1_total_qty), 60.0)
        check("balance is derived, not typed", flt(cs.w2_calc_qty), 60.0)

        print()
        print("=== the cut is issued ===")
        issue = _make_entry("Material Issue", company, [{
            "item_code": ITEM, "qty": 60, "s_warehouse": warehouse, "batch_no": batch,
            "custom_parent_item_group": "Structurals", "custom_unit_weight": UNIT_WEIGHT,
            "custom_length": 6000, "custom_sec_qty": 1,
        }])
        check("60 Kg left the warehouse", _stock(batch), 60.0)
        check("the piece count was reduced first", _dims(batch)[1], 0.0)

        print()
        print("=== switched off: the same batch takes the balance ===")
        frappe.db.set_single_value("Manufyxinvenza Settings", SETTING, 0)
        check("the balance was applied", apply_w2_to_batch(cs.name, issue.name), True)
        check("length is now the balance's", _dims(batch)[0], 6000.0)
        check("Sec Qty is the balance's 1, not the 0 left by the issue",
              _dims(batch)[1], 1.0)
        check("and the weight agrees", _stock(batch), 60.0)

        check("cancelling puts the plate back", revert_w2_from_batch(cs.name), True)
        check("dimensions restored", _dims(batch), (12000.0, 1.0))

        print()
        print("=== a job is holding this batch ===")
        mp = frappe.get_doc({
            "doctype": "Material Planning", "company": company,
            "posting_date": frappe.utils.today(),
            "material_mapping": [{
                "item_code": ITEM, "batch": batch, "is_reserved": 1,
                "batch_sec_qty": 1, "batch_calc_qty": 60,
            }],
        })
        mp.flags.ignore_validate = True
        mp.insert(ignore_permissions=True)
        mp_name = mp.name
        mm_row = mp.material_mapping[0].name

        print()
        print("=== switched on: the balance becomes its own batch ===")
        frappe.db.set_single_value("Manufyxinvenza Settings", SETTING, 1)
        frappe.clear_messages()
        check("the balance was carried over",
              _apply_cut_sheet_w2_as_new_batch(cs.name, issue.name), True)

        cs.reload()
        if not cs.w2_batch_no:
            # It fell back to resizing in place. The reason is in the message it showed.
            print("   fell back -- reason given:")
            for m in frappe.get_message_log():
                print("     %s" % (m.get("message") if isinstance(m, dict) else m))
        new_batch = cs.w2_batch_no
        check("a new batch was made", bool(new_batch), True)
        check("named for the balance's length",
              bool(new_batch) and new_batch.startswith("%s-L6000-" % PREFIX), True)
        check("it carries the balance dimensions", _dims(new_batch), (6000.0, 1.0))
        check("and the balance weight", _stock(new_batch), 60.0)

        check("the ORIGINAL batch keeps its own dimensions", _dims(batch)[0], 12000.0)
        check("and is empty", _stock(batch), 0.0)
        check("the repack is recorded", bool(cs.w2_repack_entry), True)

        check("the job's reservation followed the steel",
              frappe.db.get_value("Material Planning Material Mapping", mm_row, "batch"),
              new_batch)

        print()
        print("=== cancelling the cut undoes the repack ===")
        repack = cs.w2_repack_entry
        check("reverted", revert_w2_from_batch(cs.name), True)
        check("the repack is cancelled",
              frappe.db.get_value("Stock Entry", repack, "docstatus"), 2)
        check("the steel is back under the original batch", _stock(batch), 60.0)
        check("the balance batch is empty", _stock(new_batch), 0.0)
        check("the reservation came back too",
              frappe.db.get_value("Material Planning Material Mapping", mm_row, "batch"),
              batch)
        check("the original was never resized", _dims(batch)[0], 12000.0)

    finally:
        frappe.db.set_single_value("Manufyxinvenza Settings", SETTING, original_setting)
        for se in (issue, receipt):
            try:
                if se and frappe.db.get_value("Stock Entry", se.name, "docstatus") == 1:
                    frappe.get_doc("Stock Entry", se.name).cancel()
            except Exception as e:
                print("   (could not cancel %s: %s)" % (se.name, e))
        frappe.db.commit()
        print()
        print("   setting put back to %r; test entries cancelled, nothing deleted" % original_setting)
        if mp_name:
            print("   left behind: %s (the holding job) and item %s" % (mp_name, ITEM))

    print()
    print("=== SUMMARY ===")
    if all(checks):
        print("ALL %d CHECKS PASSED" % len(checks))
    else:
        print("%d of %d CHECKS FAILED" % (checks.count(False), len(checks)))
