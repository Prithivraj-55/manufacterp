import frappe


def run():
	pp = frappe.db.sql(
		"select custom_drawing, count(*) c from `tabProduction Plan Item` "
		"where custom_drawing is not null and custom_drawing != '' group by custom_drawing limit 5",
		as_dict=True,
	)
	print("Drawings with Production Plan Item links:", pp)

	sco = frappe.db.sql(
		"select drawing, parent, parenttype, count(*) c from `tabSCO Drawing Item` "
		"where drawing is not null and drawing != '' group by drawing, parent, parenttype limit 5",
		as_dict=True,
	)
	print("Drawings with SCO Drawing Item links:", sco)
