"""Manual verification script for Phase 1.1: Drawing customer-provided-weight
edit popup + change log + cascade. Run via:

    bench --site manufact execute manufyxinvenzaerp.tests.verify_drawing_weight_cascade.run

Looks for an existing Drawing already linked to a Sales Order DUNO Item (created
through the normal SO -> Drawing flow) and exercises update_customer_provided_weight
against it, printing before/after state. Falls back to reporting "no fixture found"
if none exists yet, rather than fabricating one (this update path only makes sense
against the real drawing->SO->downstream chain).
"""

import frappe


def run():
	rows = frappe.db.sql(
		"""select name, parent, drawing, duno_mark_no, total_weight
		   from `tabSales Order DUNO Item`
		   where drawing is not null and drawing != ''
		   limit 5""",
		as_dict=True,
	)
	print("Candidate Sales Order DUNO Item rows with a linked Drawing:", rows)

	if not rows:
		print("No existing Drawing <-> Sales Order DUNO Item link found in this site — "
			"skipping live cascade test (nothing to safely test against).")
		return

	row = rows[0]
	drawing_name = row.drawing
	print("\nUsing Drawing:", drawing_name, "| Sales Order:", row.parent, "| DUNO:", row.duno_mark_no)

	drawing = frappe.get_doc("Drawing", drawing_name)
	old_weight = drawing.customer_provided_wt
	new_weight = (old_weight or 0) + 5
	print("Drawing.customer_provided_wt before:", old_weight)

	# Show what's linked downstream, before
	pp_items_before = frappe.db.sql(
		"select name, custom_customer_weight_kg from `tabProduction Plan Item` where custom_drawing=%s",
		(drawing_name,), as_dict=True,
	)
	drawing_items_before = frappe.db.sql(
		"select name, parent, parenttype, customer_weight_kg from `tabSCO Drawing Item` where drawing=%s",
		(drawing_name,), as_dict=True,
	)
	print("Linked Production Plan Items before:", pp_items_before)
	print("Linked SCO Drawing Item rows before:", drawing_items_before)

	from manufyxinvenzaerp.drawing_management.drawing_utils import update_customer_provided_weight

	result = update_customer_provided_weight(drawing_name, new_weight)
	print("\nupdate_customer_provided_weight result:", result)

	drawing.reload()
	print("Drawing.customer_provided_wt after:", drawing.customer_provided_wt)
	print("Drawing.weight_change_log:", [
		(r.old_weight, r.new_weight, r.changed_by) for r in drawing.weight_change_log
	])

	so_row = frappe.db.get_value(
		"Sales Order DUNO Item", row.name, ["total_weight", "difference_kg"], as_dict=True
	)
	print("Sales Order DUNO Item after:", so_row)

	pp_items_after = frappe.db.sql(
		"select name, custom_customer_weight_kg from `tabProduction Plan Item` where custom_drawing=%s",
		(drawing_name,), as_dict=True,
	)
	drawing_items_after = frappe.db.sql(
		"select name, parent, parenttype, customer_weight_kg from `tabSCO Drawing Item` where drawing=%s",
		(drawing_name,), as_dict=True,
	)
	print("Linked Production Plan Items after:", pp_items_after)
	print("Linked SCO Drawing Item rows after:", drawing_items_after)

	# Revert the test change so we don't leave altered real data behind
	update_customer_provided_weight(drawing_name, old_weight)
	print("\nReverted back to original weight:", old_weight)

	frappe.db.commit()
	print("ALL CHECKS DONE")
