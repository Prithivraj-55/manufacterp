import frappe


def run():
	meta = frappe.get_meta("Material Planning")
	f = meta.get_field("consolidate_items")
	print("consolidate_items field: read_only=", f.read_only, "options=", f.options)

	umeta = frappe.get_meta("Material Planning Unavailable Item")
	cf = umeta.get_field("consolidated_into")
	print("consolidated_into present:", bool(cf), "hidden=", cf.hidden if cf else None)
