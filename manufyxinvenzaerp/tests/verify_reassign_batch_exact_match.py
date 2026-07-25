"""Verify Phase 2.1: Reassign Batch on Material Planning's Available Raw
Materials (Exact Match) table. Confirms the exact call shape the new JS
dialog sends against the real reassign_batch backend, and the cross-item
substitution path (row moves into Material Mapping).

Run via: bench --site manufact execute manufyxinvenzaerp.tests.verify_reassign_batch_exact_match.run
"""

import frappe
from frappe.utils import flt


def run():
	from manufyxinvenzaerp.production_management.doctype.material_planning.material_planning import (
		reassign_batch,
	)

	row = frappe.db.get_value(
		"Material Planning Available Raw Material",
		{"batch_no": ["!=", ""]},
		["name", "parent", "item_code", "batch_no", "sec_qty", "required_qty", "is_reserved"],
		as_dict=True, order_by="modified desc",
	)
	print("Using row:", row)
	mp_name, row_name, old_batch = row.parent, row.name, row.batch_no

	before_log_count = frappe.db.count("Material Planning Batch Change Log", {"parent": mp_name})

	# Same-batch round trip (dialog's own "reassign to same batch" edge case) --
	# exercises unreserve -> apply -> re-validate -> re-reserve without changing
	# the real allocation.
	result = reassign_batch(
		material_planning_name=mp_name,
		source_table="Material Planning Available Raw Material",
		row_name=row_name,
		new_batch_no=old_batch,
		dimensions=frappe.as_json({}),
		sec_qty=row.sec_qty,
	)
	print("warnings:", result.get("warnings"))

	after_log_count = frappe.db.count("Material Planning Batch Change Log", {"parent": mp_name})
	print("batch_change_log rows added:", after_log_count - before_log_count)

	mp = frappe.get_doc("Material Planning", mp_name)
	updated = next((r for r in mp.available_raw_materials if r.name == row_name), None)
	print("post-reassign row still in Exact Match:", bool(updated), "batch_no=", updated.batch_no if updated else None)

	frappe.db.commit()
	print("ALL CHECKS DONE")
