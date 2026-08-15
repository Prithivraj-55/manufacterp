"""Every View All popup in Material Planning filters on the same four fields.

The popup is how anyone reads a table past the grid's page size -- 100 raw
material rows on one plan is ordinary -- and it offered two filters, both about
the drawing. Finding one item code among a hundred rows meant scrolling.

All four child tables carry item_code, item_name, duno_mark_no and
customer_drawing_number, so all four filters are offered on all four tables, and
the two drawing columns are now shown in the three popups that were filtering on
values the reader could not see.

Guards the configuration rather than the DOM: the filtering itself is a few lines
of client-side string matching, but a column quietly dropped from a config would
take its filter with it and nothing else would notice.

Run: bench --site manufact execute manufyxinvenzaerp.tests.verify_mp_view_all_filters.run
"""

import os
import re

import frappe

checks = []

FILTERED_FIELDS = ["item_code", "item_name", "duno_mark_no", "customer_drawing_number"]

TABLE_DOCTYPES = {
    "raw_materials": "Material Planning Raw Material",
    "available_raw_materials": "Material Planning Available Raw Material",
    "material_mapping": "Material Planning Material Mapping",
    "unavailable_items": "Material Planning Unavailable Item",
}


def check(label, got, want):
    ok = got == want
    checks.append(ok)
    print("  %-4s %-58s got=%r want=%r" % ("OK" if ok else "FAIL", label, got, want))


def _js():
    path = os.path.join(
        frappe.get_app_path("manufyxinvenzaerp"),
        "production_management", "doctype", "material_planning", "material_planning.js",
    )
    with open(path) as f:
        return f.read()


def run():
    js = _js()

    print("=== the filter list ===")
    block = re.search(r"const _VIEW_FILTERS = \[(.*?)\n\];", js, re.S)
    check("_VIEW_FILTERS is defined", bool(block), True)
    declared = re.findall(r'fieldname:\s*"([^"]+)"', block.group(1)) if block else []
    check("it offers exactly the four asked for", declared, FILTERED_FIELDS)

    print()
    print("=== the child doctypes can answer all four ===")
    for fieldname, doctype in TABLE_DOCTYPES.items():
        meta = frappe.get_meta(doctype)
        missing = [f for f in FILTERED_FIELDS if not meta.get_field(f)]
        check("%s has every filtered field" % fieldname, missing, [])

    print()
    print("=== every popup shows the columns it filters on ===")
    cfg_block = re.search(r"const _TABLE_VIEW_CONFIG = \{(.*?)\n\};", js, re.S)
    check("_TABLE_VIEW_CONFIG is defined", bool(cfg_block), True)
    body = cfg_block.group(1) if cfg_block else ""
    # Split the config into its per-table sections, in declaration order.
    starts = [(m.start(), m.group(1)) for m in re.finditer(r"\n\t(\w+):\s*\{", body)]
    sections = {}
    for i, (pos, name) in enumerate(starts):
        end = starts[i + 1][0] if i + 1 < len(starts) else len(body)
        sections[name] = body[pos:end]
    check("all four tables are configured", sorted(sections), sorted(TABLE_DOCTYPES))
    for name in TABLE_DOCTYPES:
        cols = re.findall(r'fieldname:\s*"([^"]+)"', sections.get(name, ""))
        missing = [f for f in FILTERED_FIELDS if f not in cols]
        check("%s shows them as columns" % name, missing, [])

    print()
    print("=== the filters combine, and empty ones are ignored ===")
    # Mirrors _apply_filter: collect the boxes with something in them, and keep a
    # row only when it matches every one of them.
    def apply(rows, queries):
        active = [(k, v.strip().lower()) for k, v in queries.items() if v.strip()]
        if not active:
            return rows
        return [
            r for r in rows
            if all(str(r.get(k) or "").lower().find(q) >= 0 for k, q in active)
        ]

    rows = [
        {"item_code": "ISMB250", "item_name": "ISMB250", "duno_mark_no": "1B16",
         "customer_drawing_number": "BEAM-1B16 -SHT-16 OF 291"},
        {"item_code": "ISMB250", "item_name": "ISMB250", "duno_mark_no": "1B13",
         "customer_drawing_number": "BEAM-1B13 -SHT-13 OF 291"},
        {"item_code": "PLATE10", "item_name": "PLATE10", "duno_mark_no": "1B16",
         "customer_drawing_number": "BEAM-1B16 -SHT-16 OF 291"},
    ]
    check("no filter returns everything", len(apply(rows, {})), 3)
    check("blank boxes are ignored", len(apply(rows, {"item_code": "   "})), 3)
    check("item code alone", len(apply(rows, {"item_code": "ISMB250"})), 2)
    check("mark no alone", len(apply(rows, {"duno_mark_no": "1B16"})), 2)
    check("both together narrow further",
          len(apply(rows, {"item_code": "ISMB250", "duno_mark_no": "1B16"})), 1)
    check("case does not matter", len(apply(rows, {"item_code": "ismb"})), 2)
    check("partial drawing number matches",
          len(apply(rows, {"customer_drawing_number": "SHT-13"})), 1)
    check("no match returns nothing, not everything",
          len(apply(rows, {"item_code": "NOTHING"})), 0)

    print()
    print("=== SUMMARY ===")
    if all(checks):
        print("ALL %d CHECKS PASSED" % len(checks))
    else:
        print("%d of %d CHECKS FAILED" % (checks.count(False), len(checks)))
