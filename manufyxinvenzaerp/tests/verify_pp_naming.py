"""Quick check for Phase 0.3: Production Plan Type field + naming series."""

import frappe


def run():
	company = frappe.db.get_value("Company", {}, "name")
	for ptype in ["Internal Job", "Supplier Job", "Supplier with Material"]:
		pp = frappe.new_doc("Production Plan")
		pp.custom_type = ptype
		pp.company = company
		pp.posting_date = frappe.utils.today()
		pp.get_items_from = ""
		pp.insert(ignore_permissions=True, ignore_mandatory=True)
		print(ptype, "->", pp.name)

	# Missing Type should throw
	try:
		pp2 = frappe.new_doc("Production Plan")
		pp2.company = company
		pp2.posting_date = frappe.utils.today()
		pp2.get_items_from = ""
		pp2.insert(ignore_permissions=True, ignore_mandatory=True)
		print("ERROR: should have thrown for missing Type")
	except frappe.exceptions.ValidationError as e:
		print("OK blocked missing Type:", str(e)[:100])

	frappe.db.commit()
