import frappe


def run():
	for dt in ("Work Order", "Job Card"):
		meta = frappe.get_meta(dt)
		custom_fields = [f.fieldname for f in meta.fields if f.fieldname.startswith("custom_")]
		print(dt, "-> remaining custom_ fields:", custom_fields)

	print("\nJob Card in doctype_js hook:",
		"Job Card" in frappe.get_hooks("doctype_js"))
	print("Work Order doc_events registered:", bool(frappe.get_hooks("doc_events")))
	de = frappe.get_hooks("doc_events")
	print("Work Order in doc_events:", any("Work Order" in d for d in de if isinstance(d, dict)) if False else ("Work Order" in [k for hook in de.values() for k in ([hook] if isinstance(hook, str) else [])]))
