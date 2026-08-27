"""Material Mapping offers batches from the plan's own warehouse, and no other.

The batch field had no query on it -- literally `return {}` -- so it offered every
batch on the site. A plan built for CBE could be mapped to a batch sitting in Stores.
The reservation went through, because a reservation is paper, and the stock check then
reported the entire requirement as a shortfall:

    ISMB400 / ISA100-L12000-SR001   Required 1966.8 Kg   Batch Stock 0 Kg
    Available to Reserve 0 Kg       Shortfall 1966.8 Kg

against a batch holding 10,906.8 Kg -- in the wrong shed.

Two things this must get right, and both are checked:

  * only batches with stock in the plan's Raw Materials Warehouse are offered; and
  * the item is NOT filtered. Satisfying an ISMB400 requirement from an ISA100 bar is
    the cross-mapping this table exists for, and the batch's own item becomes the row's
    planned_item. Warehouse is the constraint that always applies; item is not.

Quantities come from ERPNext's get_batch_qty rather than a sum over the ledger's
batch_no: a batch received through a Purchase Receipt records its quantity in a Serial
and Batch Bundle and leaves that column empty, so counting it alone would report zero
for exactly the batches most likely to be picked.

Run: bench --site manufact execute manufyxinvenzaerp.tests.verify_mapping_batch_warehouse.run
"""

import frappe
from frappe.utils import flt

from manufyxinvenzaerp.production_management.doctype.material_planning.material_planning import (
    material_mapping_batch_query,
)

checks = []


def check(label, got, want):
    ok = got == want
    checks.append(ok)
    print("  %-4s %-54s got=%r want=%r" % ("OK" if ok else "FAIL", label, got, want))


def _offered(warehouse, txt=""):
    return [r[0] for r in material_mapping_batch_query("Batch", txt, "name", 0, 500,
                                                       {"warehouse": warehouse})]


def run():
    from erpnext.stock.doctype.batch.batch import get_batch_qty

    print("=== with no warehouse there is nothing to measure against ===")
    # Offering the whole site here is what caused the fault in the first place.
    check("nothing is offered", material_mapping_batch_query("Batch", "", "name", 0, 20, {}), [])

    warehouses = frappe.get_all("Warehouse", filters={"is_group": 0}, pluck="name")
    stocked, empty = None, None
    for w in warehouses:
        rows = get_batch_qty(batch_no=None, warehouse=w) or []
        if [r for r in rows if flt(r.get("qty")) > 0] and not stocked:
            stocked = w
        elif not rows and not empty:
            empty = w

    print()
    print("=== a warehouse holding no batches offers none ===")
    if not empty:
        print("   Every warehouse on this site holds batches.")
    else:
        check("%s offers nothing" % empty, _offered(empty), [])

    if not stocked:
        print()
        print("   No warehouse on this site holds a batch.")
        _wiring()
        _summary()
        return

    print()
    print("=== and one that does offers exactly what it holds ===")
    held = {r["batch_no"] for r in get_batch_qty(batch_no=None, warehouse=stocked) or []
            if flt(r.get("qty")) > 0}
    disabled = set(frappe.get_all("Batch", filters={"disabled": 1}, pluck="name"))
    offered = set(_offered(stocked))
    check("%s: every batch offered is held there" % stocked, offered - held, set())
    check("and every batch held there is offered", (held - disabled) - offered, set())
    check("disabled batches are not", offered & disabled, set())

    print()
    print("=== a batch in the wrong warehouse cannot be picked ===")
    elsewhere = [w for w in warehouses if w != stocked]
    stray = next((b for b in held), None)
    if stray and elsewhere:
        wrong = [w for w in elsewhere
                 if flt(get_batch_qty(batch_no=stray, warehouse=w,
                                      item_code=frappe.db.get_value("Batch", stray, "item")) or 0) <= 0]
        if wrong:
            check("%s is not offered in %s" % (stray, wrong[0]), stray in _offered(wrong[0]), False)
            check("but is in %s" % stocked, stray in offered, True)

    print()
    print("=== the item is deliberately not filtered ===")
    # Cross-mapping: an ISMB400 requirement satisfied by an ISA100 bar. If this query
    # ever starts filtering by the row's item, that stops being possible.
    items = {frappe.db.get_value("Batch", b, "item") for b in offered}
    if len(items) < 2:
        # Depends on what the site happens to hold, so it is stated rather than failed:
        # a warehouse with one item's batches proves nothing either way about filtering.
        print("   Only one item's batches are in %s; nothing to mix." % stocked)
    else:
        check("batches of more than one item are offered together", len(items) > 1, True)
    check("and the query never filters on item at all",
          "item_code" in open(frappe.get_app_path(
              "manufyxinvenzaerp", "production_management", "doctype", "material_planning",
              "material_planning.py")).read().split("def material_mapping_batch_query")[1]
          .split("\ndef ")[0].split("filters=")[1][:200], False)

    _wiring()
    _summary()


def _wiring():
    print()
    print("=== and the form asks for it that way ===")
    js = open(frappe.get_app_path("manufyxinvenzaerp", "production_management", "doctype",
                                  "material_planning", "material_planning.js")).read()
    check("the empty query is gone",
          'frm.set_query("batch", "material_mapping", function() {\n\t\t\treturn {};' in js, False)
    check("it calls the warehouse query", "material_mapping_batch_query" in js, True)
    check("passing the plan's own warehouse",
          "filters: { warehouse: frm.doc.for_warehouse " in js, True)
    check("and says so when that warehouse is blank",
          "Set the Raw Materials Warehouse first" in js, True)


def _summary():
    print()
    print("=== SUMMARY ===")
    if all(checks):
        print("ALL %d CHECKS PASSED" % len(checks))
    else:
        print("%d of %d CHECKS FAILED" % (checks.count(False), len(checks)))
