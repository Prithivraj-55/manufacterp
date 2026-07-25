"""Verify Phase 2.1: Reassign Batch on Material Planning's Available Raw
Materials (Exact Match) table, using a clean synthetic Material Planning
document (the one real MP with Exact Match data on this site has a
pre-existing unrelated data conflict -- see verify_reassign_batch_exact_match.py's
run output). Covers both the same-item swap and the cross-item substitution
path (row should move into Material Mapping).

Run via: bench --site manufact execute manufyxinvenzaerp.tests.verify_reassign_batch_exact_match2.run
"""

import frappe
from frappe.utils import flt
from manufyxinvenzaerp.tests.create_full_test_entry import get_ctx, ensure_item, ensure_batch


def run():
	ctx = get_ctx()

	item_a = ensure_item(ctx, "ZZTEST-REASSIGN-A", "Reassign Test Item A", uom="Kg")
	item_b = ensure_item(ctx, "ZZTEST-REASSIGN-B", "Reassign Test Item B", uom="Kg")
	frappe.db.set_value("Item", item_a, "custom_unit_weight", 10)
	frappe.db.set_value("Item", item_b, "custom_unit_weight", 20)

	batch1 = ensure_batch(item_a, "ZZTEST-RA-BATCH1", L=5000)
	batch2 = ensure_batch(item_a, "ZZTEST-RA-BATCH2", L=6000)
	batch3 = ensure_batch(item_b, "ZZTEST-RB-BATCH3", L=4000)

	mp = frappe.new_doc("Material Planning")
	mp.company = ctx.company
	mp.posting_date = frappe.utils.today()
	mp.for_warehouse = ctx.warehouse
	mp.append("available_raw_materials", {
		"item_code": item_a, "batch_no": batch1, "parent_item_group": "Structurals",
		"length": 5000, "sec_qty": 2, "required_qty": 100, "overall_required_qty": 100,
		"uom": "Kg", "is_reserved": 0,
	})
	mp.insert(ignore_permissions=True)
	row_name = mp.available_raw_materials[0].name
	print("Created test MP:", mp.name, "row:", row_name)

	from manufyxinvenzaerp.production_management.doctype.material_planning.material_planning import (
		reassign_batch,
	)

	# 1) Same-item swap: batch1 -> batch2. Dimensions are the CALLER's
	# responsibility to fetch from the new batch and pass through (the JS
	# dialog's _fetch_batch_dims_and_item does exactly this) -- reassign_batch
	# does not auto-derive them for the Available Raw Material same-item case.
	result = reassign_batch(
		material_planning_name=mp.name,
		source_table="Material Planning Available Raw Material",
		row_name=row_name,
		new_batch_no=batch2,
		dimensions=frappe.as_json({"length": 6000, "width": 0, "thickness": 0}),
		sec_qty=3,
	)
	print("same-item reassign warnings:", result.get("warnings"))

	mp.reload()
	row = next(r for r in mp.available_raw_materials if r.name == row_name)
	print("after same-item swap: batch_no=", row.batch_no, "length=", row.length, "sec_qty=", row.sec_qty)
	assert row.batch_no == batch2, "batch_no should now be batch2"
	assert flt(row.length) == 6000, "length should be fetched from batch2 (6000)"

	log_rows = [r for r in mp.batch_change_log if r.source_row == row_name]
	print("batch_change_log entries for this row:", [(r.old_batch, r.new_batch) for r in log_rows])
	assert log_rows and log_rows[-1].old_batch == batch1 and log_rows[-1].new_batch == batch2

	# 2) Cross-item substitution: batch2 (item A) -> batch3 (item B) -- should move
	# the row OUT of available_raw_materials and INTO material_mapping.
	result2 = reassign_batch(
		material_planning_name=mp.name,
		source_table="Material Planning Available Raw Material",
		row_name=row_name,
		new_batch_no=batch3,
		dimensions=frappe.as_json({"length": 4000, "width": 0, "thickness": 0}),
		sec_qty=1,
	)
	print("cross-item reassign warnings:", result2.get("warnings"))

	mp.reload()
	still_in_arm = next((r for r in mp.available_raw_materials if r.name == row_name), None)
	print("row still in Exact Match after cross-item swap:", bool(still_in_arm), "(expected: False)")
	assert not still_in_arm, "row should have moved out of Available Raw Materials"

	mm_row = next((r for r in mp.material_mapping if r.batch == batch3), None)
	print("new Material Mapping row:", mm_row.item_code if mm_row else None,
		"planned_item=", mm_row.planned_item if mm_row else None)
	assert mm_row is not None, "a new Material Mapping row with batch3 should exist"
	assert mm_row.planned_item == item_b, "planned_item should record the substituted item"

	mm_log = [r for r in mp.batch_change_log if r.planned_item == item_b]
	print("batch_change_log entries recording the substitution:", len(mm_log))
	assert mm_log, "batch_change_log should have an entry with planned_item set"

	frappe.db.commit()
	print("\nALL CHECKS DONE — both same-item and cross-item reassignment paths verified correctly.")
