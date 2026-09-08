"""One plan may cover several Sales Orders, so DUNO/Mark No must be unique inside it.

A DUNO is a mark off the customer's drawing -- "1B1", "TYPE 2". Nothing makes it
unique across Sales Orders (`unique` is 0 on Drawing and on Sales Order DUNO Item),
and it did not need to be while one Material Planning covered exactly one order.

Grouping several orders into one plan changes that, because about ten places key
per-drawing figures on the DUNO alone WITHIN a plan -- planned weight, mapped weight,
excess to return, which batches belong to a job, and the transfer scope. Two rows
sharing a mark collapse into one key: weights double-count, and the transfer offers
another Sales Order's reserved batches for shipment to this job's supplier. That is
steel going to the wrong place.

The guard is two-strength on purpose, and both halves are tested here:

  Material Planning + Production Plan  THROW. This is where the damage happens.
  Sales Order + Drawing               WARN.  A mark is the customer's; two unrelated
                                             customers both sending "TYPE 1" is
                                             ordinary and must not block an import.

Run: bench --site manufact execute manufyxinvenzaerp.tests.verify_duno_uniqueness.run
"""

import frappe

checks = []


def check(label, got, want):
    ok = got == want
    checks.append(ok)
    print("  %-4s %-62s got=%r want=%r" % ("OK" if ok else "FAIL", label, got, want))


def _throws(fn):
    try:
        fn()
        return False
    except frappe.ValidationError:
        return True


def run():
    from manufyxinvenzaerp.drawing_management import duno_uniqueness as du

    print("=== 1. find_duplicates ===")
    rows = [
        {"idx": 1, "duno_mark_no": "1B1", "sales_order": "SO-A"},
        {"idx": 2, "duno_mark_no": "1B2", "sales_order": "SO-A"},
        {"idx": 3, "duno_mark_no": "1B1", "sales_order": "SO-B"},
    ]
    dupes = du.find_duplicates(rows)
    check("the clashing mark is found", sorted(dupes), ["1B1"])
    check("both sides are reported", len(dupes["1B1"]), 2)
    check("a unique mark is not reported", "1B2" in dupes, False)

    # A mark pasted from a spreadsheet cell often carries trailing space. Treating
    # "1B1 " as a different drawing would let the exact collision this guards
    # against walk straight through.
    check("whitespace is not a different mark",
          sorted(du.find_duplicates([
              {"idx": 1, "duno_mark_no": "1B1 ", "sales_order": "SO-A"},
              {"idx": 2, "duno_mark_no": "1B1", "sales_order": "SO-B"},
          ])), ["1B1"])
    check("blank marks are ignored here",
          du.find_duplicates([
              {"idx": 1, "duno_mark_no": "", "sales_order": "SO-A"},
              {"idx": 2, "duno_mark_no": None, "sales_order": "SO-B"},
          ]), {})

    print()
    print("=== 2. assert_unique throws, and says enough to fix it ===")
    check("a clash throws", _throws(lambda: du.assert_unique(rows, "BOM Items")), True)
    check("a clean set does not",
          _throws(lambda: du.assert_unique(rows[:2], "BOM Items")), False)
    try:
        du.assert_unique(rows, "BOM Items")
        message = ""
    except frappe.ValidationError:
        message = frappe.message_log[-1].get("message") if frappe.message_log else ""
        frappe.clear_messages()
    check("the message names the mark", "1B1" in message, True)
    check("the message names both Sales Orders",
          "SO-A" in message and "SO-B" in message, True)

    print()
    print("=== 3. normalise() reads each table's own spelling ===")
    # Material Planning BOM Item and Production Plan Item spell these differently.
    # Getting it wrong would silently read nothing and pass everything.
    pp_row = frappe._dict({
        "idx": 4, "custom_duno_mark_no": "2C1", "sales_order": "SO-C",
        "custom_customer_drawing_number": "CDN-9", "custom_drawing": "DRW-9",
    })
    n = du.normalise(pp_row, duno_field="custom_duno_mark_no",
                     cdn_field="custom_customer_drawing_number",
                     drawing_field="custom_drawing")
    check("Production Plan Item spelling is read", n["duno_mark_no"], "2C1")
    check("and its drawing number too", n["customer_drawing_number"], "CDN-9")
    mp_row = frappe._dict({"idx": 5, "duno_mark_no": "3D1", "sales_order": "SO-D"})
    check("Material Planning BOM Item spelling is read",
          du.normalise(mp_row)["duno_mark_no"], "3D1")

    print()
    print("=== 4. Material Planning refuses to save a duplicate ===")
    mp = frappe.new_doc("Material Planning")
    mp.company = frappe.defaults.get_user_default("Company") or frappe.db.get_value("Company", {}, "name")
    for duno, so in (("1B1", "SO-A"), ("1B1", "SO-B")):
        mp.append("bom_items", {"duno_mark_no": duno, "sales_order": so, "item_code": None})
    check("save is refused", _throws(lambda: mp._validate_unique_dunos()), True)
    frappe.clear_messages()

    mp.set("bom_items", [])
    for duno, so in (("1B1", "SO-A"), ("2C1", "SO-B")):
        mp.append("bom_items", {"duno_mark_no": duno, "sales_order": so, "item_code": None})
    check("two Sales Orders with distinct marks are allowed",
          _throws(lambda: mp._validate_unique_dunos()), False)

    print()
    print("=== 5. Production Plan refuses one too ===")
    from manufyxinvenzaerp.production_plan_management.production_plan import (
        validate_duno_uniqueness,
    )
    dup_pp = frappe._dict({"po_items": [
        frappe._dict({"idx": 1, "custom_duno_mark_no": "1B1", "sales_order": "SO-A"}),
        frappe._dict({"idx": 2, "custom_duno_mark_no": "1B1", "sales_order": "SO-B"}),
    ]})
    ok_pp = frappe._dict({"po_items": [
        frappe._dict({"idx": 1, "custom_duno_mark_no": "1B1", "sales_order": "SO-A"}),
        frappe._dict({"idx": 2, "custom_duno_mark_no": "2C1", "sales_order": "SO-B"}),
    ]})
    check("duplicate is refused", _throws(lambda: validate_duno_uniqueness(dup_pp, None)), True)
    frappe.clear_messages()
    check("distinct marks are allowed",
          _throws(lambda: validate_duno_uniqueness(ok_pp, None)), False)
    check("a plan with no drawings at all is fine",
          _throws(lambda: validate_duno_uniqueness(frappe._dict({"po_items": []}), None)), False)

    print()
    print("=== 6. The Sales Order side WARNS, it does not block ===")
    real = frappe.db.sql("""
        SELECT name, sales_order, duno_mark_no FROM `tabDrawing`
        WHERE IFNULL(duno_mark_no,'')!='' AND IFNULL(sales_order,'')!='' AND docstatus!=2
        LIMIT 1
    """, as_dict=True)
    if not real:
        print("  (no submitted drawing with a DUNO on this site -- lookup checks skipped)")
    else:
        d0 = real[0]
        # Seen from a DIFFERENT order, this mark is a clash.
        clashes = du.find_clashes_on_other_sales_orders("SOME-OTHER-SO", [d0.duno_mark_no])
        check("a mark used elsewhere is reported",
              d0.duno_mark_no in clashes, True)
        check("and it names the order using it",
              d0.sales_order in clashes.get(d0.duno_mark_no, []), True)
        # Seen from its OWN order it is not a clash -- otherwise every drawing would
        # warn about itself.
        #
        # Asserted as "my own order is not in the answer", not "the answer is empty":
        # another Sales Order may legitimately share this mark (the test suite itself
        # creates such a case), and that is a real clash which SHOULD be reported.
        # An empty-result assertion passes only while the site happens to be free of
        # duplicates, and fails the moment the feature has something to find.
        own = du.find_clashes_on_other_sales_orders(d0.sales_order, [d0.duno_mark_no])
        check("a drawing does not clash with itself",
              d0.sales_order in own.get(d0.duno_mark_no, []), False)
        check("the warning text is written as information, not an error",
              "allowed" in " ".join(du.warn_text_for_clashes(clashes)), True)

    check("an unused mark clashes with nothing",
          du.find_clashes_on_other_sales_orders("SO-X", ["NO-SUCH-MARK-XYZ"]), {})
    check("no marks in, nothing out",
          du.find_clashes_on_other_sales_orders("SO-X", []), {})

    print()
    print("=== 7. Cancelled drawings are ignored, so a revision never self-reports ===")
    # This site has no cancelled drawing to read, so one is made by cancelling a real
    # one in-transaction and rolling back. Worth the intrusion: create_revision works
    # by cancelling the old drawing and inserting a new one with the SAME mark, so if
    # cancelled drawings were counted, every revision would warn about the drawing it
    # replaced -- on the one flow where the warning is guaranteed to be wrong.
    if not real:
        print("  (no drawing to exercise this with -- skipped)")
    else:
        d0 = real[0]
        before = du.find_clashes_on_other_sales_orders("SOME-OTHER-SO", [d0.duno_mark_no])
        check("live drawing is reported before cancelling", d0.duno_mark_no in before, True)

        frappe.db.set_value("Drawing", d0.name, "docstatus", 2, update_modified=False)
        after = du.find_clashes_on_other_sales_orders("SOME-OTHER-SO", [d0.duno_mark_no])
        still_live = frappe.db.exists("Drawing", {
            "duno_mark_no": d0.duno_mark_no, "docstatus": ["!=", 2],
            "sales_order": ["not in", ["SOME-OTHER-SO"]],
        })
        check("cancelled drawing is not reported",
              d0.duno_mark_no in after, bool(still_live))
        frappe.db.set_value("Drawing", d0.name, "docstatus", 1, update_modified=False)

    print()
    print("=== 8. The Sales Order picker takes several orders ===")
    from manufyxinvenzaerp.production_management.doctype.material_planning.material_planning import (
        get_so_drawings_for_bom_picker,
    )
    import inspect, json as _json
    src = inspect.getsource(get_so_drawings_for_bom_picker)
    check("it accepts a JSON list", "json.loads" in src, True)
    sos = frappe.get_all("Sales Order", filters={"docstatus": 1}, limit=2, pluck="name")
    if len(sos) < 2:
        print("  (fewer than two submitted Sales Orders -- multi-order call skipped)")
    else:
        one = get_so_drawings_for_bom_picker(sos[0])
        both = get_so_drawings_for_bom_picker(_json.dumps(sos))
        check("a single name still works (unchanged callers)", isinstance(one, list), True)
        check("two orders return at least as many rows", len(both) >= len(one), True)
        check("every row carries its own Sales Order",
              all(r.get("sales_order") for r in both), True)

    print()
    print("=== 9. so_bom_import is hidden, not deleted ===")
    frappe.clear_cache(doctype="Material Planning")
    meta = frappe.get_meta("Material Planning")
    df = meta.get_field("so_bom_import")
    check("the field still exists", bool(df), True)
    check("and is hidden", bool(df and df.hidden), True)
    btn = meta.get_field("show_drawings_btn")
    check("the button is relabelled", btn and btn.label, "Add Sales Order")

    print()
    print("=== 10. The setting gates the WARNINGS only, never the blocks ===")
    # The whole risk of a switch like this is somebody turning it off believing they
    # have turned off DUNO checking, and quietly losing the ledger protection. So the
    # test that matters is the second half: blocks still throw with it off.
    SETTING = "warn_on_duplicate_duno"
    original = frappe.db.get_single_value("Manufyxinvenza Settings", SETTING)

    df = frappe.get_meta("Manufyxinvenza Settings").get_field(SETTING)
    check("the setting exists", bool(df), True)
    check("and defaults to on", df and df.default, "1")
    check("its description says the blocks are unaffected",
          bool(df and "REFUSE" in (df.description or "")), True)

    frappe.db.set_single_value("Manufyxinvenza Settings", SETTING, 1)
    frappe.clear_document_cache("Manufyxinvenza Settings", "Manufyxinvenza Settings")
    check("enabled -> warnings on", du.warnings_enabled(), True)

    frappe.db.set_single_value("Manufyxinvenza Settings", SETTING, 0)
    frappe.clear_document_cache("Manufyxinvenza Settings", "Manufyxinvenza Settings")
    check("disabled -> warnings off", du.warnings_enabled(), False)

    # ...and with it OFF, both hard blocks must still refuse.
    off_mp = frappe.new_doc("Material Planning")
    for duno, so in (("1B1", "SO-A"), ("1B1", "SO-B")):
        off_mp.append("bom_items", {"duno_mark_no": duno, "sales_order": so, "item_code": None})
    check("Material Planning STILL refuses with the warning off",
          _throws(lambda: off_mp._validate_unique_dunos()), True)
    frappe.clear_messages()
    check("Production Plan STILL refuses with the warning off",
          _throws(lambda: validate_duno_uniqueness(dup_pp, None)), True)
    frappe.clear_messages()

    # The Sales Order side goes quiet, and does so without running the lookup.
    from manufyxinvenzaerp.drawing_management.so_drawing_import import _check_duno_reuse
    if real:
        so_stub = frappe._dict({
            "name": "SOME-OTHER-SO",
            "custom_duno_items": [frappe._dict({"duno_mark_no": real[0].duno_mark_no})],
        })
        check("Sales Order warning is silent when disabled", _check_duno_reuse(so_stub), [])
        frappe.db.set_single_value("Manufyxinvenza Settings", SETTING, 1)
        frappe.clear_document_cache("Manufyxinvenza Settings", "Manufyxinvenza Settings")
        check("and speaks again when enabled", len(_check_duno_reuse(so_stub)) > 0, True)

    if original is not None:
        frappe.db.set_single_value("Manufyxinvenza Settings", SETTING, original)

    print()
    print("=== 11. No document already on this site is broken by the block ===")
    # The block runs on EVERY save of every Material Planning and Production Plan,
    # including ones created long before it existed. A plan that can no longer be
    # saved is not a validation, it is an outage -- so this walks the real data
    # rather than trusting that duplicates "shouldn't" exist.
    refused = []
    for name in frappe.get_all("Material Planning", pluck="name"):
        doc = frappe.get_doc("Material Planning", name)
        try:
            du.assert_unique([du.normalise(r) for r in (doc.bom_items or [])], "BOM Items")
        except frappe.ValidationError:
            refused.append(("Material Planning", name))
            frappe.clear_messages()
    for name in frappe.get_all("Production Plan", pluck="name"):
        doc = frappe.get_doc("Production Plan", name)
        rows = [
            du.normalise(r, duno_field="custom_duno_mark_no",
                         cdn_field="custom_customer_drawing_number",
                         drawing_field="custom_drawing")
            for r in (doc.po_items or [])
        ]
        try:
            du.assert_unique(rows, "Items to Manufacture")
        except frappe.ValidationError:
            refused.append(("Production Plan", name))
            frappe.clear_messages()

    print("  scanned %d Material Planning(s) and %d Production Plan(s)" % (
        frappe.db.count("Material Planning"), frappe.db.count("Production Plan")))
    check("no existing document would be refused", refused, [])

    frappe.db.rollback()
    total, failed = len(checks), checks.count(False)
    print()
    if failed:
        print("%d of %d CHECKS FAILED" % (failed, total))
    else:
        print("ALL %d CHECKS PASSED" % total)
