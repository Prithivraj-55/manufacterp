import frappe


def run():
	drawing_name = "DRW-2026-00091"
	drawing = frappe.get_doc("Drawing", drawing_name)
	old_weight = drawing.customer_provided_wt
	new_weight = (old_weight or 0) + 9
	print("Drawing:", drawing_name, "| weight before:", old_weight)

	pp_before = frappe.db.sql(
		"select name, custom_customer_weight_kg from `tabProduction Plan Item` where custom_drawing=%s",
		(drawing_name,), as_dict=True)
	sco_before = frappe.db.sql(
		"select name, parent, parenttype, customer_weight_kg from `tabSCO Drawing Item` where drawing=%s",
		(drawing_name,), as_dict=True)
	print("PP items before:", pp_before)
	print("SCO/MIP drawing rows before:", sco_before)

	sco_header_before = frappe.db.get_value("Subcontracting Order", "SC-ORD-2026-00003", "custom_customer_weight_kg")
	mip_before = frappe.db.get_value("Material Issue Plan", "MIP-2026-00001", "customer_provided_weight_kg") \
		if frappe.db.has_column("Material Issue Plan", "customer_provided_weight_kg") else None
	print("SCO header customer_weight_kg before:", sco_header_before)

	from manufyxinvenzaerp.drawing_management.drawing_utils import update_customer_provided_weight
	result = update_customer_provided_weight(drawing_name, new_weight)
	print("\nresult:", result)

	pp_after = frappe.db.sql(
		"select name, custom_customer_weight_kg from `tabProduction Plan Item` where custom_drawing=%s",
		(drawing_name,), as_dict=True)
	sco_after = frappe.db.sql(
		"select name, parent, parenttype, customer_weight_kg from `tabSCO Drawing Item` where drawing=%s",
		(drawing_name,), as_dict=True)
	print("PP items after:", pp_after)
	print("SCO/MIP drawing rows after:", sco_after)
	sco_header_after = frappe.db.get_value("Subcontracting Order", "SC-ORD-2026-00003", "custom_customer_weight_kg")
	print("SCO header customer_weight_kg after:", sco_header_after)

	# revert
	update_customer_provided_weight(drawing_name, old_weight)
	print("\nreverted to", old_weight)
	frappe.db.commit()
	print("DONE")
