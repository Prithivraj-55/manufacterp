import frappe


def run():
	de = frappe.get_hooks("doc_events")
	print("Work Order in doc_events keys:", "Work Order" in de)
	print("Job Card in doc_events keys:", "Job Card" in de)
	print("Stock Entry before_submit handlers:", de.get("Stock Entry", {}).get("before_submit"))
