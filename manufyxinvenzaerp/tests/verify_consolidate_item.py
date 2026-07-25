"""Verify Phase 0.5: Material Planning Consolidate Item child table + Purchase Kg /
Difference Kg calc (server-side, reusing _calc_batch_qty).

Run via: bench --site manufact execute manufyxinvenzaerp.tests.verify_consolidate_item.run
"""

import frappe


def run():
	mp_name = frappe.db.get_value("Material Planning", {}, "name")
	print("Using Material Planning:", mp_name)
	mp = frappe.get_doc("Material Planning", mp_name)

	# Find one Structurals/Plates item and one Nuts and Bolts item to exercise both formula branches
	structural_item = frappe.db.get_value("Item", {"custom_parent_item_group": "Structurals"}, "name")
	plate_item = frappe.db.get_value("Item", {"custom_parent_item_group": "Plates"}, "name")
	nb_item = frappe.db.get_value("Item", {"custom_parent_item_group": "Nuts and Bolts"}, "name")
	print("structural_item=", structural_item, "plate_item=", plate_item, "nb_item=", nb_item)

	before_count = len(mp.consolidate_items or [])

	if structural_item:
		mp.append("consolidate_items", {
			"item_code": structural_item, "required_kg": 100,
			"length": 6000, "sec_qty": 3,
		})
	if plate_item:
		mp.append("consolidate_items", {
			"item_code": plate_item, "required_kg": 50,
			"length": 2000, "width": 1000, "thickness": 5, "sec_qty": 2,
		})
	if nb_item:
		mp.append("consolidate_items", {
			"item_code": nb_item, "required_kg": 10,
			"sec_qty": 100,
		})

	mp.save(ignore_permissions=True)

	for row in mp.consolidate_items[before_count:]:
		print(f"item={row.item_code} group={row.parent_item_group} unit_weight={row.unit_weight} "
			f"L={row.length} W={row.width} T={row.thickness} sec_qty={row.sec_qty} "
			f"-> purchase_kg={row.purchase_kg} required_kg={row.required_kg} difference_kg={row.difference_kg}")

	# Clean up the test rows so we don't leave permanent noise
	mp.consolidate_items = (mp.consolidate_items or [])[:before_count]
	mp.save(ignore_permissions=True)
	frappe.db.commit()
	print("\nReverted test rows. ALL CHECKS DONE")
