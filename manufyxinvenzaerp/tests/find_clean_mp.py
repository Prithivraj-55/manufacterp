import frappe

def run():
	candidates = frappe.get_all(
		"Material Planning Available Raw Material",
		filters={"batch_no": ["!=", ""], "is_reserved": 1},
		fields=["parent"], group_by="parent", limit_page_length=20,
	)
	for c in candidates:
		mp_name = c.parent
		arm_batches = set(frappe.get_all(
			"Material Planning Available Raw Material", filters={"parent": mp_name, "batch_no": ["!=", ""]}, pluck="batch_no"
		))
		mm_batches = set(frappe.get_all(
			"Material Planning Material Mapping", filters={"parent": mp_name, "batch": ["!=", ""]}, pluck="batch"
		))
		overlap = arm_batches & mm_batches
		print(mp_name, "overlap:", overlap if overlap else "none")
