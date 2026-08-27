"""Material Planning does not offer to create a Production Plan.

The button took every BOM on the plan and raised a Production Plan from the lot. That
is rarely what is wanted: a plan covers a whole Sales Order's drawings, while a job is
raised against a handful of them. The Production Plan is now raised by hand and picks
its own drawings through its own picker -- which still reads from Material Planning, so
nothing about the order of work changes.

It was the only button in the Create group, so the group goes with it.

The server method it called, make_production_plan, is deliberately left in place: it is
whitelisted, covered by test_e2e_material_planning, and is what the button would be
rebuilt on if it is ever wanted back. This checks it still works -- a withdrawn button
should not quietly become a broken API.

Run: bench --site manufact execute manufyxinvenzaerp.tests.verify_no_create_production_plan_button.run
"""

import frappe

checks = []


def check(label, got, want):
    ok = got == want
    checks.append(ok)
    print("  %-4s %-54s got=%r want=%r" % ("OK" if ok else "FAIL", label, got, want))


def run():
    js = open(frappe.get_app_path("manufyxinvenzaerp", "production_management", "doctype",
                                  "material_planning", "material_planning.js")).read()

    print("=== the button is gone ===")
    check("no Production Plan button", 'add_custom_button(__("Production Plan")' in js, False)
    check("and the Create group goes with it", '__("Create"))' in js, False)
    check("nothing calls the method from the form",
          "material_planning.make_production_plan" in js, False)
    check("with a note saying why, and how to put it back",
          '"Create → Production Plan" was here' in js, True)

    print()
    print("=== the buttons that remain ===")
    # Batch Mapping Completed and Reopen Mapping were listed here too, until d4c983f
    # made the status follow the reservations and removed both. This assertion was not
    # re-run then and went on demanding buttons the app had deliberately dropped -- so
    # it is now the one place that records which buttons the form is supposed to have.
    for label in ("Check Mapping", "Validate Stock"):
        check("%s is still there" % label,
              'add_custom_button(__("%s")' % label in js, True)
    for label in ("Batch Mapping Completed", "Reopen Mapping"):
        check("%s is gone, with the status it used to set" % label,
              'add_custom_button(__("%s")' % label in js, False)

    print()
    print("=== but the method behind it still works ===")
    # A withdrawn button must not leave a broken API behind it: it is whitelisted, it is
    # tested elsewhere, and it is what a rebuild would stand on.
    from manufyxinvenzaerp.production_management.doctype.material_planning import (
        material_planning as mp_module,
    )
    fn = getattr(mp_module, "make_production_plan", None)
    check("it still exists", callable(fn), True)
    check("and is still whitelisted",
          getattr(fn, "__name__", None) and fn in frappe.whitelisted, True)

    print()
    print("=== and the manual no longer sends anybody to it ===")
    manual = open(frappe.get_app_path("manufyxinvenzaerp", "production_management", "page",
                                      "erp_manual", "erp_manual.js")).read()
    check("no step tells you to press it",
          "<b>Create → Production Plan</b> — hands this plan on" in manual, False)
    check("no button entry lists it",
          '{ name: "Create → Production Plan"' in manual, False)
    check("and it says the plan is raised by hand now",
          "There is no Create → Production Plan button any more" in manual, True)

    print()
    print("=== SUMMARY ===")
    if all(checks):
        print("ALL %d CHECKS PASSED" % len(checks))
    else:
        print("%d of %d CHECKS FAILED" % (checks.count(False), len(checks)))
