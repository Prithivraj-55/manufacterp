"""Consumable Entry: issuing consumables against a job, not moving the job's steel.

Welding rods, paint and gas are consumed by a job but are not the job's own material.
Ticking **Consumable Entry** on a Stock Entry says so, and asks the one question that
decides whose cost they land on: which job.

The three fields are a chain, and each step narrows the next:

    Sales Order  →  Production Plan  →  Job Work Order

Only the first is chosen freely. The plans offered are the ones raised against that
order -- which cannot be a link filter, because a plan's Sales Order lives on its child
rows and not on the plan. Choosing a plan fills in its Job Work Order, and that is what
every weight rollup downstream already keys on.

Each step also clears what sits below it, and the server refuses a mismatched pair
outright. A Stock Entry naming a plan that belongs to a different order would put its
consumables on the wrong job's cost, and nothing on the screen would show it.

Ticking the box also marks every item row as a consumable -- the rows already there,
and any added afterwards. Unticking leaves the rows alone: a row may have been ticked
deliberately, and clearing somebody's rows because a header field changed is not a
decision this should make.

Run: bench --site manufact execute manufyxinvenzaerp.tests.verify_consumable_entry.run
"""

import re

import frappe

from manufyxinvenzaerp.production_management.stock_entry import (
    get_job_work_order_for_production_plan,
    get_production_plans_for_sales_order,
    production_plan_query,
)

checks = []


def check(label, got, want):
    ok = got == want
    checks.append(ok)
    print("  %-4s %-54s got=%r want=%r" % ("OK" if ok else "FAIL", label, got, want))


def _client_script():
    src = open(frappe.get_app_path("manufyxinvenzaerp", "setup.py")).read()
    m = re.search(r'STOCK_ENTRY_CLIENT_SCRIPT = """(.*?)\n"""', src, re.S)
    return m.group(1).encode().decode("unicode_escape")


def run():
    meta = frappe.get_meta("Stock Entry")
    js = _client_script()

    print("=== the three fields, and when each appears ===")
    tick = meta.get_field("custom_consumable_entry")
    check("the tick exists", bool(tick), True)
    check("next to Inspection Required",
          frappe.db.get_value("Custom Field", "Stock Entry-custom_consumable_entry",
                              "insert_after"), "inspection_required")
    check("Sales Order shows only when ticked",
          meta.get_field("custom_consumable_sales_order").depends_on,
          "eval:doc.custom_consumable_entry")
    check("Production Plan shows only once an order is chosen",
          meta.get_field("custom_consumable_production_plan").depends_on,
          "eval:doc.custom_consumable_entry && doc.custom_consumable_sales_order")

    print()
    print("=== one Job Work Order field on the form, not two ===")
    check("the app's duplicate is hidden", meta.get_field("custom_sco_ref").hidden, 1)
    check("ERPNext's own field stays", meta.get_field("subcontracting_order").hidden, 0)
    check("but the hidden one is still written",
          "frm.doc.custom_sco_ref = found.job_work_order;" in js, True)

    print()
    print("=== the chain, against real documents ===")
    pair = frappe.db.sql(
        """
        SELECT ppi.sales_order, ppi.parent AS plan, sco.name AS job_work_order
        FROM `tabProduction Plan Item` ppi
        JOIN `tabSubcontracting Order` sco ON sco.custom_production_plan = ppi.parent
        WHERE ppi.sales_order IS NOT NULL AND ppi.sales_order != ''
        LIMIT 1
        """,
        as_dict=True,
    )
    if not pair:
        print("   No Sales Order on this site has a plan with a Job Work Order behind it.")
    else:
        p = pair[0]
        plans = [r["name"] for r in get_production_plans_for_sales_order(p.sales_order)]
        check("the order's plans are found", p.plan in plans, True)
        check("the plan's job work order is found",
              get_job_work_order_for_production_plan(p.plan).get("job_work_order"),
              p.job_work_order)
        found = production_plan_query("Production Plan", "", "name", 0, 20,
                                      {"sales_order": p.sales_order})
        check("and the link search offers it", p.plan in [row[0] for row in found], True)

    print()
    print("=== with no order chosen, nothing is offered ===")
    # Offering every plan on the site would invite exactly the mismatch the server
    # then refuses, which is a worse experience than an empty list.
    check("the search returns nothing",
          production_plan_query("Production Plan", "", "name", 0, 20, {}), [])
    check("and so does the plan lookup", get_production_plans_for_sales_order(None), [])

    print()
    print("=== a mismatched pair is refused, not saved ===")
    src = open(frappe.get_app_path("manufyxinvenzaerp", "production_management",
                                   "stock_entry.py")).read()
    check("the guard exists", "def validate_consumable_entry(doc):" in src, True)
    check("and runs on every save", "validate_consumable_entry(doc)" in src, True)
    check("checking the plan really is against that order",
          '"Production Plan Item", {"parent": plan, "sales_order": sales_order}' in src, True)

    print()
    print("=== the item rows ===")
    check("ticking the box marks the rows already there",
          "function _se_mark_rows_consumable(frm)" in js, True)
    check("a row added afterwards arrives ticked",
          'frappe.model.set_value(cdt, cdn, "custom_is_consumable", 1)' in js, True)
    check("unticking does not clear anybody's rows",
          "_se_unmark_rows" in js, False)
    check("each step clears what sits below it",
          'custom_consumable_sales_order(frm) {\n    frm.set_value("custom_consumable_production_plan", null);' in js,
          True)

    print()
    print("=== picking a plan does not set off ERPNext's own transfer fetch ===")
    # ERPNext's subcontracting_order handler calls make_rm_stock_entry, which throws
    # "No item available for transfer." for an order with no supplied_items -- which
    # is every PP-flow order. Writing the field with set_value fired it on every pick.
    check("the Job Work Order is assigned, not set_value'd",
          'frm.set_value("subcontracting_order", found.job_work_order)' in js, False)
    check("written straight to the document instead",
          "frm.doc.subcontracting_order = found.job_work_order;" in js, True)
    check("and the form still knows it changed", "frm.dirty();" in js, True)

    print()
    print("=== Material Consumption for Manufacture answers its own question ===")
    check("one place decides it", "function _se_apply_consumption_type(frm)" in js, True)
    check("applied when the type changes", "stock_entry_type(frm) {" in js, True)
    check("and when the form is reopened", "_se_apply_consumption_type(frm);\n  },\n\n  stock_entry_type" in js, True)
    check("Work Order is hidden for it",
          'frm.set_df_property("work_order", "hidden", is_consumption ? 1 : 0)' in js, True)
    check("Consumable Entry is ticked",
          'frm.set_value("custom_consumable_entry", 1)' in js, True)
    check("and locked, since there is only one right answer",
          'frm.set_df_property("custom_consumable_entry", "read_only", is_consumption ? 1 : 0)' in js, True)

    print()
    print("=== SUMMARY ===")
    if all(checks):
        print("ALL %d CHECKS PASSED" % len(checks))
    else:
        print("%d of %d CHECKS FAILED" % (checks.count(False), len(checks)))
