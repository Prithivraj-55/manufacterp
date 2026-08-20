"""A batch must never be branded with a different item's defect remark.

The remark written onto a Batch fell back to a string built by joining EVERY
item's remarks on the inspection. So an item inspected with nothing to say
inherited its neighbour's note: a batch that passed cleanly ended up reading
"Surface rough" because a different item on the same receipt did. That text then
follows the batch into Material Planning and Stock Entry, where it reads as this
batch's own quality history.

A batch now takes its own row's remark, or the inspector's document-level Overall
Remarks, and nothing else.

The joined summary is still correct where it was always meant to be used -- the
Inspection Call Log, which describes the inspection as a whole -- so this checks
that it is still written there rather than removed along with the bug.

Run: bench --site manufact execute manufyxinvenzaerp.tests.verify_batch_remark_isolation.run
"""

import inspect

import frappe

checks = []


def check(label, got, want):
    ok = got == want
    checks.append(ok)
    print("  %-4s %-58s got=%r want=%r" % ("OK" if ok else "FAIL", label, got, want))


def run():
    from manufyxinvenzaerp.production_management import inspection

    src = inspect.getsource(inspection)

    print("=== the batch fallback no longer reaches for the joined summary ===")
    check("the old fallback is gone", "custom_batch_remarks\", row.remarks or remarks)" in src, False)
    check("a batch-only fallback exists", 'batch_fallback = doc.overall_remarks or ""' in src, True)
    check("and that is what the batch is given",
          "row.remarks or batch_fallback," in src, True)

    print()
    print("=== the document-level summary is still written to the Call Log ===")
    check("the joined summary is still built",
          '"; ".join(row.remarks for row in doc.items if row.remarks)' in src, True)
    check("...and still lands on the Call Log",
          '{"round_status": "Completed", "remarks": remarks}' in src, True)

    print()
    print("=== the rule, worked through ===")
    # Mirrors the two lines above: what each batch is given, per row.
    def batch_remark(row_remark, overall):
        return row_remark or overall or ""

    def old_batch_remark(row_remark, overall, all_rows):
        joined = overall or "; ".join(r for r in all_rows if r) or ""
        return row_remark or joined

    rows = ["Surface rough", ""]          # item 1 has a defect, item 2 is clean
    check("the flagged item keeps its own note",
          batch_remark(rows[0], ""), "Surface rough")
    check("the clean item gets nothing",
          batch_remark(rows[1], ""), "")
    check("...where before it inherited the defect",
          old_batch_remark(rows[1], "", rows), "Surface rough")
    check("the inspector's overall note is still used when there is one",
          batch_remark("", "Whole lot re-checked"), "Whole lot re-checked")
    check("a row note still wins over the overall note",
          batch_remark("Bent", "Whole lot re-checked"), "Bent")

    print()
    print("=== nothing else changed shape ===")
    check("Operation Entry still uses its own fallback",
          "remarks = doc.overall_remarks or doc.rework_remarks" in src, True)
    check("the per-item fields are untouched",
          '"custom_inspection_remarks": row.remarks or "",' in src, True)

    print()
    print("=== batches carrying a remark on this site ===")
    marked = frappe.get_all("Batch", filters={"custom_batch_remarks": ["!=", ""]},
                            fields=["name", "custom_batch_remarks"], limit_page_length=0)
    print("   %d batch(es) currently carry one" % len(marked))
    for b in marked[:5]:
        print("      %-30s %s" % (b.name, (b.custom_batch_remarks or "")[:60]))
    print("   (existing values are left alone -- this changes what future"
          " inspections write, not what is already recorded)")

    print()
    print("=== SUMMARY ===")
    if all(checks):
        print("ALL %d CHECKS PASSED" % len(checks))
    else:
        print("%d of %d CHECKS FAILED" % (checks.count(False), len(checks)))
