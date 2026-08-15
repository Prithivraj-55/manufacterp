"""Verify Raw Materials must catch every value the weight formula reads.

Written after a beam (ISMB250) reached Material Planning carrying a 10 mm
Thickness typed into one line of an uploaded BOM sheet. Verification passed it:
the check only looked for values that were MISSING for the group, and for a
Structural a Thickness is not missing, it is meaningless -- the formula is
Length x Unit Weight x Sec Qty. The value was copied into the Drawing, the BOM
and Material Planning as a real requirement, and would have sent the whole
received batch to Material Mapping because Purchase Receipt matches all three
dimensions strictly.

The gate now checks, per row: the group is known and still matches the Item
master, every input the group's formula needs is present, no dimension outside
that group's formula is filled in, and the row ends up weighing something.
Header columns of each pending drawing are checked too -- a missing Total Qty
was silently replaced with 1.0.

The last section replays the real sheet from SAL-ORD-2026-00015 through the
checks, so the case that started this is proven caught rather than assumed.

Run: bench --site manufact execute manufyxinvenzaerp.tests.verify_so_raw_material_checks.run
"""

import frappe

checks = []


def check(label, got, want):
    ok = got == want
    checks.append(ok)
    print("  %-4s %-62s got=%r want=%r" % ("OK" if ok else "FAIL", label, got, want))


def _row(**kw):
    base = {"length": 0, "width": 0, "thickness": 0, "sec_qty": 0, "unit_weight": 0}
    base.update(kw)
    return frappe._dict(base)


def run():
    from manufyxinvenzaerp.drawing_management.so_drawing_import import (
        _check_row_required,
        _check_unused_dimensions,
        _check_drawing_headers,
        verify_raw_materials,
        GROUP_DIMENSIONS,
    )

    print("=== the reported case: a Structural carrying a Thickness ===")
    beam = _row(length=879.1, thickness=10.0, sec_qty=1, unit_weight=37.3)
    check("Thickness on a Structural is reported",
          _check_unused_dimensions(beam, "Structurals"), ["Thickness"])
    check("...and nothing is reported as missing",
          _check_row_required(beam, "Structurals"), [])
    check("a Width would be caught the same way",
          _check_unused_dimensions(_row(length=100, width=50, sec_qty=1, unit_weight=1), "Structurals"),
          ["Width"])
    check("a clean Structural passes both checks",
          (_check_unused_dimensions(_row(length=879.1, sec_qty=1, unit_weight=37.3), "Structurals"),
           _check_row_required(_row(length=879.1, sec_qty=1, unit_weight=37.3), "Structurals")),
          ([], []))

    print()
    print("=== Plates legitimately use all three dimensions ===")
    plate = _row(length=210.81, width=201.0, thickness=10.0, sec_qty=1, unit_weight=7.85)
    check("nothing unused on a plate", _check_unused_dimensions(plate, "Plates"), [])
    check("nothing missing on a plate", _check_row_required(plate, "Plates"), [])
    check("a plate with no Thickness IS missing one",
          _check_row_required(_row(length=200, width=100, sec_qty=1, unit_weight=7.85), "Plates"),
          ["Thickness"])

    print()
    print("=== Sec Qty -- the input that was never checked ===")
    check("Structural without Reqd Raw Material Qty",
          _check_row_required(_row(length=879.1, unit_weight=37.3), "Structurals"),
          ["Reqd Raw Material Qty"])
    check("Plate without it too",
          _check_row_required(_row(length=200, width=100, thickness=10, unit_weight=7.85), "Plates"),
          ["Reqd Raw Material Qty"])
    print("       (a blank column here used to stage the row weighing zero, silently)")

    print()
    print("=== Unit Weight comes from the Item master ===")
    got = _check_row_required(_row(length=879.1, sec_qty=1), "Structurals")
    check("missing Unit Weight is named", len(got), 1)
    check("...and points at the Item master", "Item master" in (got[0] if got else ""), True)

    print()
    print("=== Nuts and Bolts use no dimensions at all ===")
    check("group is known", "Nuts and Bolts" in GROUP_DIMENSIONS, True)
    check("a Length on a bolt is reported",
          _check_unused_dimensions(_row(length=50, sec_qty=4, unit_weight=0.5), "Nuts and Bolts"),
          ["Length"])
    check("Sec Qty and Unit Weight are still required",
          _check_row_required(_row(), "Nuts and Bolts"),
          ["Reqd Raw Material Qty", "Unit Weight (set it on the Item master)"])

    print()
    print("=== drawing header columns ===")
    real_fg = frappe.db.get_value("Item", {"custom_parent_item_group": "Finished Goods"}, "name") \
        or frappe.db.get_value("Item", {}, "name")
    so = frappe._dict(custom_duno_items=[
        frappe._dict(drawing_number="CDN-OK", duno_mark_no="M1", item=real_fg, total_quantity=2, drawing=None),
        frappe._dict(drawing_number="CDN-NOFG", duno_mark_no="M2", item="", total_quantity=1, drawing=None),
        frappe._dict(drawing_number="CDN-BADFG", duno_mark_no="M3", item="NOT-AN-ITEM-XYZ", total_quantity=1, drawing=None),
        frappe._dict(drawing_number="CDN-NOQTY", duno_mark_no="M4", item=real_fg, total_quantity=0, drawing=None),
        frappe._dict(drawing_number="CDN-NOMARK", duno_mark_no="", item=real_fg, total_quantity=1, drawing=None),
        frappe._dict(drawing_number="CDN-DONE", duno_mark_no="", item="", total_quantity=0, drawing="DRW-EXISTING"),
    ])
    so.get = lambda f, *a, **k: so[f] if f in so else None
    issues = _check_drawing_headers(so)
    joined = " | ".join(frappe.utils.strip_html(i) for i in issues)
    check("blank FG Item caught", "CDN-NOFG" in joined, True)
    check("FG Item not in master caught", "CDN-BADFG" in joined, True)
    check("Total Qty of 0 caught", "CDN-NOQTY" in joined, True)
    check("blank Mark No caught", "CDN-NOMARK" in joined, True)
    check("the good drawing is left alone", "CDN-OK" in joined, False)
    check("a drawing already created is not re-checked", "CDN-DONE" in joined, False)

    print()
    print("=== replay of the real sheet: SAL-ORD-2026-00015 ===")
    rows = frappe.db.sql(
        """SELECT rm.customer_drawing_number, rm.item_no, rm.material_code,
                  rm.length, rm.width, rm.thickness, rm.sec_qty, rm.unit_weight,
                  i.custom_parent_item_group AS grp
           FROM `tabSales Order Drawing Raw Material` rm
           JOIN `tabItem` i ON i.name = rm.material_code
           WHERE rm.parent = 'SAL-ORD-2026-00015'""",
        as_dict=True,
    )
    if not rows:
        print("   (sales order not on this site -- skipped)")
    else:
        flagged = []
        for r in rows:
            for text in _check_unused_dimensions(r, r.grp):
                flagged.append((r.customer_drawing_number, r.item_no, r.material_code, text))
            if _check_row_required(r, r.grp):
                flagged.append((r.customer_drawing_number, r.item_no, r.material_code, "missing input"))
        print("   %d staged rows, %d flagged" % (len(rows), len(flagged)))
        for f in flagged:
            print("     %s / %s / %s -> %s" % f)
        check("exactly one row is flagged", len(flagged), 1)
        check("it is the ISMB250 that picked up a Thickness",
              [f[2] for f in flagged], ["ISMB250"])
        check("named as Thickness", [f[3] for f in flagged], ["Thickness"])
        check("every other row passes", len(rows) - len(flagged), len(rows) - 1)

    print()
    print("=== locked rows are recognised as locked ===")
    # frappe's Document class defines is_locked as a property reporting whether
    # a FILE LOCK is held, and it shadows the field of the same name -- the
    # attribute reads False whatever the column holds. Every backend read has
    # to go through .get(). Nothing on the client side is affected: JS reads
    # the raw payload.
    from frappe.model.document import Document
    check("frappe.Document really does define is_locked",
          isinstance(getattr(Document, "is_locked", None), property), True)

    if frappe.db.exists("Sales Order", "SAL-ORD-2026-00015"):
        so_doc = frappe.get_doc("Sales Order", "SAL-ORD-2026-00015")
        srm = so_doc.custom_so_raw_materials or []
        db_locked = frappe.db.sql(
            """SELECT COUNT(*) FROM `tabSales Order Drawing Raw Material`
               WHERE parent='SAL-ORD-2026-00015' AND is_locked=1""")[0][0]
        check("the column says these rows are locked", db_locked, len(srm))
        check("the attribute would have called every one of them unlocked",
              len([r for r in srm if not r.is_locked]), len(srm))
        check("...but .get() reads them correctly",
              len([r for r in srm if not r.get("is_locked")]), 0)

        res = verify_raw_materials("SAL-ORD-2026-00015")
        check("a fully processed order verifies clean", res["verified"], True)
        check("no issues raised against its locked rows", res["issues"], [])
    else:
        print("   (sales order not on this site -- skipped)")

    print()
    print("=== SUMMARY ===")
    if all(checks):
        print("ALL %d CHECKS PASSED" % len(checks))
    else:
        print("%d of %d CHECKS FAILED" % (checks.count(False), len(checks)))
