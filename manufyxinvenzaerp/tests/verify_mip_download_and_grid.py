"""Material Issue Plan: the Download menu, the locked Raw Materials grid, and the
View All button's new home.

The Add Row check is the one that matters, and it is subtler than it looks.
material_issue_plan.json has carried `"cannot_add_rows": 1` on raw_materials for a
while and it never did anything: that key is NOT a property of the DocField doctype
in Frappe v15.116.0, so syncing the doctype discards it and the grid never sees it.
It survives only as a runtime flag the browser reads off the grid object. So the
assertion here is deliberately about the CLIENT SCRIPT, not the doctype -- checking
the JSON would pass while Add Row sat on screen, which is exactly the state this
change was made to fix.

Run: bench --site manufact execute manufyxinvenzaerp.tests.verify_mip_download_and_grid.run
"""

import os
import re

import frappe

checks = []


def check(label, got, want):
    ok = got == want
    checks.append(ok)
    print("  %-4s %-62s got=%r want=%r" % ("OK" if ok else "FAIL", label, got, want))


def _source(relative_path):
    path = os.path.join(frappe.get_app_path("manufyxinvenzaerp"), relative_path)
    with open(path) as f:
        return f.read()


def run():
    mip_js = _source("subcontracting_management/doctype/material_issue_plan/material_issue_plan.js")

    print("=== Add Row is off the Raw Materials grid ===")
    check("the flag is set on the grid object, which is what grid.js reads",
          bool(re.search(r"grid\.cannot_add_rows\s*=\s*true", mip_js)), True)
    check("and the grid is refreshed so the footer redraws",
          bool(re.search(r"grid\.cannot_add_rows\s*=\s*true;\s*\n[^\n]*\n[^\n]*\n[^\n]*grid\.refresh\(\)",
                         mip_js, re.S)), True)
    check("it is called from refresh", "_lock_raw_materials_row_adding(frm)" in mip_js, True)
    # Deliberately asserted as still-useless rather than removed: it states the
    # intent on the doctype, and someone will otherwise re-add it thinking it works.
    doctype_json = _source("subcontracting_management/doctype/material_issue_plan/material_issue_plan.json")
    check("the doctype key is still there (documented as insufficient)",
          '"cannot_add_rows": 1' in doctype_json, True)
    check("cannot_add_rows really is not a DocField property in this Frappe",
          bool(frappe.get_meta("DocField").get_field("cannot_add_rows")), False)

    print()
    print("=== View All moved to the grid's top toolbar, beside Update Batch ===")
    # Anchored on the FUNCTION, not on the icon name. A first version of this keyed
    # off frappe.utils.icon("eye"...) and broke the moment that icon was corrected --
    # reporting a placement failure when placement had not changed at all.
    add_view_all = re.search(
        r'function _add_view_all_raw_materials_button\(frm\)\s*\{.*?\n\}',
        mip_js, re.S)
    check("the View All helper exists", bool(add_view_all), True)
    # The body holds exactly one add_custom_button call, so the presence of the
    # "top" argument anywhere in it is unambiguous -- and does not depend on how
    # the arguments happen to be spread across lines.
    body = add_view_all.group(0) if add_view_all else ""
    check("it adds exactly one grid button", body.count("add_custom_button("), 1)
    check("and places it in the 'top' toolbar", '"top"' in body, True)
    check("Update Batch is still 'top' too",
          bool(re.search(r'__\("Update Batch"\).*?"top"', mip_js, re.S)), True)
    # Order of the two calls decides which sits where, so pin it.
    check("Update Batch is added before View All",
          mip_js.index("_add_update_batch_button(frm);") < mip_js.index("_add_view_all_raw_materials_button(frm);"),
          True)

    print()
    print("=== Download offers both plans ===")
    check("Batch wise PDF is in the Download group",
          bool(re.search(r'__\("Batch wise PDF"\).*?__\("Download"\)', mip_js, re.S)), True)
    check("Consolidate item wise PDF is too",
          bool(re.search(r'__\("Consolidate item wise PDF"\).*?__\("Download"\)', mip_js, re.S)), True)
    check("the old standalone PDF button is gone", '__("PDF")' in mip_js, False)

    print()
    print("=== Load Drawings is hidden ===")
    # after_insert already calls populate_from_production_plan, so a plan arrives
    # with its drawings loaded and the button only ever repeated work already done.
    frappe.clear_cache(doctype="Material Issue Plan")
    df = frappe.get_meta("Material Issue Plan").get_field("load_drawings_btn")
    check("the button still exists", bool(df), True)
    check("and is hidden", bool(df and df.hidden), True)

    print()
    print("=== Icons referenced actually exist in Frappe's set ===")
    # "eye" and "filetype" are not in the icon set (verified live against the
    # injected sprite -- 179 symbols, neither present), so they rendered as an
    # empty box. Nothing in Frappe complains; the button just looks broken.
    for dead in ('icon("eye"', 'icon("filetype"'):
        check("no reference to %s" % dead, dead in mip_js, False)

    from manufyxinvenzaerp.subcontracting_management.doctype.material_issue_plan import (
        material_issue_plan as mip_py,
    )
    # frappe.whitelisted holds the actual function objects @frappe.whitelist()
    # registered. Checking membership there is the only thing that proves the
    # button's frappe.call will not answer "Method Not Allowed" -- the decorator is
    # exactly what goes missing when a helper is pasted in above a function.
    for method in ("get_mip_batch_plan_html", "download_mip_batch_plan_pdf",
                   "get_mip_consolidate_plan_html", "download_mip_consolidate_plan_pdf"):
        fn = getattr(mip_py, method, None)
        check("%s is whitelisted" % method, bool(fn) and fn in frappe.whitelisted, True)

    print()
    print("=== the consolidated plan renders against real data ===")
    mip_name = frappe.db.get_value(
        "Material Issue Plan Consolidate Item", {"batch_no": ["!=", ""]}, "parent")
    if not mip_name:
        print("  (no plan with consolidated rows on this site -- render check skipped)")
    else:
        html = mip_py.get_mip_consolidate_plan_html(mip_name)
        doc = frappe.get_doc("Material Issue Plan", mip_name)
        check("names the plan", mip_name in html, True)
        check("one table row per consolidate line",
              html.count('<td class="num pending">'), len(doc.consolidate_items))
        check("carries a totals row", 'class="totals"' in html, True)
        check("every consolidate item appears",
              all(r.item_code in html for r in doc.consolidate_items), True)
        # The store picks against this sheet, so a CNC row must say so on the line.
        if any(r.cnc_process for r in doc.consolidate_items):
            check("CNC rows are marked", 'class="cnc"' in html, True)

    print()
    print("=== the shared button palette is loaded app-wide ===")
    bundle = _source("public/js/manufyxinvenzaerp.bundle.js")
    check("mfx_buttons.js is in the bundle", 'import "./mfx_buttons.js";' in bundle, True)
    check("rate_schedule.js is in the bundle", 'import "./rate_schedule.js";' in bundle, True)
    buttons_js = _source("public/js/mfx_buttons.js")
    for fn in ("mfx_paint_button", "mfx_paint_group", "mfx_paint_grid",
               "mfx_paint_field", "mfx_paint_el"):
        check("%s is exported on window" % fn, "window.%s =" % fn in buttons_js, True)
    check("Material Planning no longer carries its own copy of the CSS",
          "_MFX_BTN_CSS" in _source(
              "production_management/doctype/material_planning/material_planning.js"), False)

    total, failed = len(checks), checks.count(False)
    print()
    if failed:
        print("%d of %d CHECKS FAILED" % (failed, total))
    else:
        print("ALL %d CHECKS PASSED" % total)
