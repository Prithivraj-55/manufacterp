"""The batch piece count must survive two entries touching it at once.

_reduce_batch_sec_qty read the figure, subtracted in Python, and wrote it back.
Two Stock Entries consuming the same batch in the same instant both read the same
starting value, and the second write discarded the first: 10 - 3 and 10 - 4
submitted together leave 6 instead of 3. The count then drifts permanently, and it
is what every later transfer's proportional Sec Qty and every cut sheet's sizing
are worked out from -- the piece-count equivalent of a corrupted ledger.

The arithmetic now happens inside the UPDATE, so the database serialises the two
and each subtraction lands on whatever the other left behind.

The restore path on cancel calls the same function with a negative quantity, so
both directions are exercised here.

Run: bench --site manufact execute manufyxinvenzaerp.tests.verify_batch_sec_qty_atomic.run
"""

import inspect
import threading

import frappe
from frappe.utils import flt

checks = []
SUFFIX = frappe.generate_hash(length=6).upper()
ITEM = "ZZTEST-ATOMIC-%s" % SUFFIX
BATCH = "ZZTEST-ATOMIC-BATCH-%s" % SUFFIX


def check(label, got, want):
    ok = got == want
    checks.append(ok)
    print("  %-4s %-58s got=%r want=%r" % ("OK" if ok else "FAIL", label, got, want))


def _sec_qty():
    return flt(frappe.db.get_value("Batch", BATCH, "custom_sec_qty"))


def run():
    from manufyxinvenzaerp.production_management.stock_entry import _reduce_batch_sec_qty

    print("=== the subtraction happens in the database, not in Python ===")
    src = inspect.getsource(_reduce_batch_sec_qty)
    check("no read-then-write", 'frappe.db.get_value("Batch", batch_no, "custom_sec_qty")' in src, False)
    check("arithmetic is inside the UPDATE", "custom_sec_qty = ROUND(COALESCE(custom_sec_qty, 0) - %s" in src, True)
    check("a missing value is treated as zero", "COALESCE" in src, True)
    check("still rounded to 3 as everywhere else", "ROUND(" in src, True)

    _make_fixtures()
    try:
        print()
        print("=== it subtracts and adds as before ===")
        frappe.db.set_value("Batch", BATCH, "custom_sec_qty", 10)
        frappe.db.commit()
        _reduce_batch_sec_qty(BATCH, 3)
        frappe.db.commit()
        check("10 - 3", _sec_qty(), 7.0)
        _reduce_batch_sec_qty(BATCH, 4)
        frappe.db.commit()
        check("...then - 4", _sec_qty(), 3.0)

        print()
        print("=== the cancel path adds back, through the same statement ===")
        _reduce_batch_sec_qty(BATCH, -4)
        frappe.db.commit()
        check("subtracting a negative adds", _sec_qty(), 7.0)
        _reduce_batch_sec_qty(BATCH, -3)
        frappe.db.commit()
        check("back where it started", _sec_qty(), 10.0)

        print()
        print("=== fractional pieces keep their precision ===")
        frappe.db.set_value("Batch", BATCH, "custom_sec_qty", 4.5)
        frappe.db.commit()
        _reduce_batch_sec_qty(BATCH, 1.25)
        frappe.db.commit()
        check("4.5 - 1.25", _sec_qty(), 3.25)

        print()
        print("=== two at once: the case the old code lost ===")
        frappe.db.set_value("Batch", BATCH, "custom_sec_qty", 10)
        frappe.db.commit()
        errors = []

        # The site name has to be captured out here: frappe.local is thread-local,
        # so a new thread starts with nothing set and cannot find the site on its own.
        site = frappe.local.site

        def subtract(amount):
            # Each thread opens its own connection, which is what makes this a real
            # concurrency test rather than two sequential calls on one connection.
            try:
                frappe.init(site=site)
                frappe.connect()
                _reduce_batch_sec_qty(BATCH, amount)
                frappe.db.commit()
            except Exception as e:  # noqa: BLE001 - reported, not swallowed
                errors.append("%s: %s" % (type(e).__name__, e))
            finally:
                frappe.destroy()

        threads = [threading.Thread(target=subtract, args=(a,)) for a in (3, 4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        frappe.init(site=site)
        frappe.connect()
        if errors:
            print("   (threads reported: %s)" % errors[0][:100])
        got = _sec_qty()
        check("10 - 3 - 4, both applied", got, 3.0)

        print()
        print("=== and the old approach, run the same way, to show it mattered ===")
        # The read and the write are separated deliberately so the interleaving is
        # forced rather than left to timing -- a flaky demonstration would prove
        # nothing. This is exactly what the old code did, just with the window
        # widened from microseconds to a tenth of a second.
        import time

        frappe.db.set_value("Batch", BATCH, "custom_sec_qty", 10)
        frappe.db.commit()

        def old_style(amount):
            try:
                frappe.init(site=site)
                frappe.connect()
                current = flt(frappe.db.get_value("Batch", BATCH, "custom_sec_qty"))
                time.sleep(0.1)
                frappe.db.set_value("Batch", BATCH, "custom_sec_qty",
                                    flt(current - amount, 3))
                frappe.db.commit()
            except Exception as e:  # noqa: BLE001
                errors.append("%s: %s" % (type(e).__name__, e))
            finally:
                frappe.destroy()

        threads = [threading.Thread(target=old_style, args=(a,)) for a in (3, 4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        frappe.init(site=site)
        frappe.connect()
        old_got = _sec_qty()
        check("the old way loses one of the two writes", old_got != 3.0, True)
        print("       old: %s (should have been 3.0)   new: %s" % (old_got, got))

    finally:
        _cleanup()

    print()
    print("=== SUMMARY ===")
    if all(checks):
        print("ALL %d CHECKS PASSED" % len(checks))
    else:
        print("%d of %d CHECKS FAILED" % (checks.count(False), len(checks)))


def _make_fixtures():
    if not frappe.db.exists("Item", ITEM):
        frappe.get_doc({
            "doctype": "Item", "item_code": ITEM, "item_name": ITEM,
            "item_group": "Structural child node", "stock_uom": "Kg",
            "has_batch_no": 1, "create_new_batch": 0, "is_stock_item": 1,
            "gst_hsn_code": frappe.db.get_value("GST HSN Code", {}, "name"),
            "custom_parent_item_group": "Structurals",
            "custom_unit_weight": 10,
            "custom_batch_prefix": "ZZATOM%s" % SUFFIX,
        }).insert(ignore_permissions=True)
    if not frappe.db.exists("Batch", BATCH):
        frappe.get_doc({"doctype": "Batch", "batch_id": BATCH, "item": ITEM,
                        "custom_length": 1000, "custom_sec_qty": 10}).insert(
            ignore_permissions=True)
    frappe.db.commit()
    print("fixture batch:", BATCH)


def _cleanup():
    if frappe.db.exists("Batch", BATCH):
        frappe.delete_doc("Batch", BATCH, force=1, ignore_permissions=True)
    if frappe.db.exists("Item", ITEM):
        frappe.delete_doc("Item", ITEM, force=1, ignore_permissions=True)
    frappe.db.commit()
    print()
    print("test fixtures removed")
