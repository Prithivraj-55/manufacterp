"""Read a Material Planning back and say whether it hangs together.

Not a unit test -- a health check for one real document, for when the question is
simply "is this plan alright?". Every check is against the ledger and the other
plans on the site, not against the document's own opinion of itself.

    bench --site manufact execute \\
        manufyxinvenzaerp.tests.verify_material_planning_health.run \\
        --kwargs "{'mp_name': 'MP-2026-00012'}"

With no name it takes the most recently modified plan.

What it looks at:

  reservations   a row reserving a batch that does not exist, or holds no stock in
                 the plan's own warehouse
  over-booking   the sum of every reservation against one batch, including OTHER
                 plans' reservations, against what that batch actually holds. One
                 batch legitimately serves several rows here, so a per-row check
                 says nothing -- only the total does
  purchase size  a consolidated line bought too small, or too thin, to yield the
                 biggest piece it was consolidated for
  coverage       demand with no purchase line behind it, and purchase lines with no
                 demand in front of them
"""

import frappe
from collections import defaultdict
from frappe.utils import flt

FINDINGS = []


def _note(severity, text):
    FINDINGS.append((severity, text))


def _stock_in(batch_no, warehouse):
    row = frappe.db.sql(
        """
        SELECT COALESCE(SUM(sbe.qty), 0)
        FROM `tabSerial and Batch Entry` sbe
        JOIN `tabSerial and Batch Bundle` sbb ON sbb.name = sbe.parent
        WHERE sbe.batch_no = %s AND sbb.docstatus = 1 AND sbe.warehouse = %s
        """,
        (batch_no, warehouse),
    )
    return flt(row[0][0]) if row else 0.0


def _reserved_elsewhere(batch_no, this_plan):
    total = 0.0
    for table, field in (
        ("Material Planning Material Mapping", "batch"),
        ("Material Planning Available Raw Material", "batch_no"),
    ):
        row = frappe.db.sql(
            "SELECT COALESCE(SUM(reserved_qty), 0) FROM `tab%s` "
            "WHERE %s = %%s AND is_reserved = 1 AND parent != %%s" % (table, field),
            (batch_no, this_plan),
        )
        total += flt(row[0][0]) if row else 0.0
    return total


def _check_reservations(doc):
    held = defaultdict(float)
    where = defaultdict(list)

    for label, table, field in (
        ("Material Mapping", "material_mapping", "batch"),
        ("Exact Match", "available_raw_materials", "batch_no"),
    ):
        for row in (doc.get(table) or []):
            batch = row.get(field)
            if row.is_reserved and not batch:
                _note("ISSUE", "%s row %s (%s) is reserved but names no batch"
                      % (label, row.idx, row.item_code))
                continue
            if not batch:
                continue
            if not frappe.db.exists("Batch", batch):
                _note("ISSUE", "%s row %s names batch %s, which does not exist"
                      % (label, row.idx, batch))
                continue
            if row.is_reserved:
                held[batch] += flt(row.reserved_qty)
                where[batch].append("%s #%s" % (label, row.idx))

    for batch in sorted(held):
        stock = _stock_in(batch, doc.for_warehouse)
        mine = flt(held[batch], 3)
        others = flt(_reserved_elsewhere(batch, doc.name), 3)
        print("   %-30s stock %10.3f   this plan %9.3f   other plans %8.3f"
              % (batch, stock, mine, others))
        if mine + others - stock > 0.001:
            _note("ISSUE",
                  "batch %s is over-booked: %.3f reserved (%.3f here across %s, %.3f "
                  "elsewhere) against %.3f in %s"
                  % (batch, mine + others, mine, ", ".join(where[batch]), others,
                     stock, doc.for_warehouse))
    return held


def _check_purchase_sizes(doc):
    need = {}
    for row in (doc.unavailable_items or []):
        if not row.item_code:
            continue
        agg = need.setdefault(row.item_code,
                              {"length": 0.0, "width": 0.0, "thickness": set(), "qty": 0.0,
                               "group": row.parent_item_group, "rows": 0})
        agg["length"] = max(agg["length"], flt(row.length))
        agg["qty"] += flt(row.qty)
        agg["rows"] += 1
        if (row.parent_item_group or "").strip() != "Plates":
            continue
        agg["width"] = max(agg["width"], flt(row.width))
        if flt(row.thickness):
            agg["thickness"].add(flt(row.thickness))

    lines = {c.item_code: c for c in (doc.consolidate_items or [])}
    for code, agg in sorted(need.items()):
        line = lines.get(code)
        if not line:
            _note("ISSUE", "%s is needed (%d rows, %.3f Kg) but has no purchase line"
                  % (code, agg["rows"], agg["qty"]))
            continue
        if line.get("alternate_item"):
            print("   %-12s bought as %s — sizes not compared" % (code, line.alternate_item))
            continue
        problems = []
        if flt(line.length) and flt(line.length) < agg["length"]:
            problems.append("Length %.0f is under the longest piece %.0f"
                            % (flt(line.length), agg["length"]))
        if not flt(line.length):
            problems.append("no purchase Length")
        if agg["group"] == "Plates":
            if flt(line.width) and flt(line.width) < agg["width"]:
                problems.append("Width %.0f is under the widest piece %.0f"
                                % (flt(line.width), agg["width"]))
            if agg["thickness"] and flt(line.thickness) not in agg["thickness"]:
                problems.append("Thickness %.1f is not one of %s"
                                % (flt(line.thickness), sorted(agg["thickness"])))
        if not flt(line.sec_qty):
            problems.append("no Sec Qty to buy")
        bought = flt(line.get("purchase_kg") or line.get("qty"))
        print("   %-12s %-11s %2d rows   need %9.3f   buying %9.3f   %s"
              % (code, agg["group"], agg["rows"], agg["qty"], bought,
                 "; ".join(problems) or "ok"))
        for p in problems:
            _note("ISSUE", "%s — %s" % (code, p))
        if bought and bought + 0.001 < agg["qty"]:
            _note("ISSUE", "%s — buying %.3f Kg against %.3f Kg of demand"
                  % (code, bought, agg["qty"]))

    for code in lines:
        if code not in need:
            _note("LOOK", "purchase line for %s has no demand behind it" % code)


def run(mp_name=None):
    del FINDINGS[:]
    if not mp_name:
        mp_name = frappe.get_all("Material Planning", pluck="name",
                                 order_by="modified desc", limit=1)[0]
    doc = frappe.get_doc("Material Planning", mp_name)

    print("=== %s ===" % mp_name)
    print("   status %s · docstatus %s · warehouse %s"
          % (doc.get("planning_status"), doc.docstatus, doc.for_warehouse))
    print("   %d in Exact Match · %d in Material Mapping · %d unavailable · %d purchase lines"
          % (len(doc.get("available_raw_materials") or []),
             len(doc.get("material_mapping") or []),
             len(doc.get("unavailable_items") or []),
             len(doc.get("consolidate_items") or [])))

    print()
    print("=== reserved batches, against what is actually in the warehouse ===")
    held = _check_reservations(doc)
    if not held:
        print("   (nothing reserved)")

    print()
    print("=== purchase lines, against the pieces they must yield ===")
    _check_purchase_sizes(doc)

    print()
    print("=== VERDICT ===")
    issues = [t for s, t in FINDINGS if s == "ISSUE"]
    looks = [t for s, t in FINDINGS if s == "LOOK"]
    if not issues and not looks:
        print("   Nothing wrong found.")
    for t in issues:
        print("   ISSUE  %s" % t)
    for t in looks:
        print("   LOOK   %s" % t)
    return {"issues": issues, "worth_a_look": looks}
