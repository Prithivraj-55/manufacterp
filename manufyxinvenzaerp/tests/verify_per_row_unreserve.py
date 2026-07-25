"""Verify Phase 2.2: per-row Unreserve targets exactly one row and leaves
sibling rows untouched. Builds a clean synthetic Material Planning with two
reserved Exact Match rows and two reserved Material Mapping rows, since real
site data either has no reserved rows in one table or a pre-existing
unrelated data conflict (see verify_reassign_batch_exact_match.py's findings).

Run via: bench --site manufact execute manufyxinvenzaerp.tests.verify_per_row_unreserve.run
"""

import frappe
from frappe.utils import flt
from manufyxinvenzaerp.tests.create_full_test_entry import get_ctx, ensure_item, ensure_batch


def run():
	ctx = get_ctx()
	item_a = ensure_item(ctx, "ZZTEST-UNRES-A", "Unreserve Test Item A", uom="Kg")
	item_b = ensure_item(ctx, "ZZTEST-UNRES-B", "Unreserve Test Item B", uom="Kg")
	frappe.db.set_value("Item", item_a, "custom_unit_weight", 10)
	frappe.db.set_value("Item", item_b, "custom_unit_weight", 10)
	# Distinct batches per table -- reusing the same batch in both Exact Match and
	# Material Mapping trips the app's own _validate_no_cross_table_batch_duplicate
	# guard (a real, pre-existing, unrelated validation -- not part of this feature).
	batch_arm_a = ensure_batch(item_a, "ZZTEST-UR-ARM-A", L=5000)
	batch_arm_b = ensure_batch(item_b, "ZZTEST-UR-ARM-B", L=5000)
	batch_mm_a = ensure_batch(item_a, "ZZTEST-UR-MM-A", L=5000)
	batch_mm_b = ensure_batch(item_b, "ZZTEST-UR-MM-B", L=5000)

	mp = frappe.new_doc("Material Planning")
	mp.company = ctx.company
	mp.posting_date = frappe.utils.today()
	mp.for_warehouse = ctx.warehouse

	mp.append("available_raw_materials", {
		"item_code": item_a, "batch_no": batch_arm_a, "parent_item_group": "Structurals",
		"length": 5000, "sec_qty": 2, "required_qty": 100, "overall_required_qty": 100,
		"uom": "Kg", "is_reserved": 1, "reserved_qty": 100,
	})
	mp.append("available_raw_materials", {
		"item_code": item_b, "batch_no": batch_arm_b, "parent_item_group": "Structurals",
		"length": 5000, "sec_qty": 2, "required_qty": 100, "overall_required_qty": 100,
		"uom": "Kg", "is_reserved": 1, "reserved_qty": 100,
	})
	mp.append("material_mapping", {
		"item_code": item_a, "batch": batch_mm_a, "parent_item_group": "Structurals",
		"length": 5000, "qty": 100, "uom": "Kg", "is_reserved": 1, "reserved_qty": 100,
	})
	mp.append("material_mapping", {
		"item_code": item_b, "batch": batch_mm_b, "parent_item_group": "Structurals",
		"length": 5000, "qty": 100, "uom": "Kg", "is_reserved": 1, "reserved_qty": 100,
	})
	mp.insert(ignore_permissions=True)
	print("Created test MP:", mp.name)

	arm_target, arm_sibling = mp.available_raw_materials[0], mp.available_raw_materials[1]
	mm_target, mm_sibling = mp.material_mapping[0], mp.material_mapping[1]

	from manufyxinvenzaerp.production_management.doctype.material_planning.material_planning import (
		unreserve_batches, unreserve_exact_match_batches,
	)
	import json as _json

	unreserve_exact_match_batches(mp.name, _json.dumps([arm_target.name]))
	unreserve_batches(mp.name, _json.dumps([mm_target.name]))

	mp.reload()
	arm_t = next(r for r in mp.available_raw_materials if r.name == arm_target.name)
	arm_s = next(r for r in mp.available_raw_materials if r.name == arm_sibling.name)
	mm_t = next(r for r in mp.material_mapping if r.name == mm_target.name)
	mm_s = next(r for r in mp.material_mapping if r.name == mm_sibling.name)

	print("ARM target is_reserved (expect 0):", arm_t.is_reserved)
	print("ARM sibling is_reserved (expect 1, untouched):", arm_s.is_reserved)
	print("MM target is_reserved (expect 0):", mm_t.is_reserved)
	print("MM sibling is_reserved (expect 1, untouched):", mm_s.is_reserved)

	assert not arm_t.is_reserved and arm_s.is_reserved, "ARM: only target should be unreserved"
	assert not mm_t.is_reserved and mm_s.is_reserved, "MM: only target should be unreserved"

	frappe.db.commit()
	print("\nALL CHECKS DONE — per-row unreserve correctly isolated to the target row only.")
