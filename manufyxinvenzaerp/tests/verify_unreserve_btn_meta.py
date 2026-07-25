import frappe

def run():
	for dt in ("Material Planning Available Raw Material", "Material Planning Material Mapping"):
		meta = frappe.get_meta(dt)
		f = meta.get_field("unreserve_btn")
		print(dt, "-> fieldtype:", f.fieldtype, "depends_on:", f.depends_on, "in_list_view:", f.in_list_view)
