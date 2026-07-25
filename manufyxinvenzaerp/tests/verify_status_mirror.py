"""Quick targeted check: an Inspection Entry with a rejected qty (>0) but
status explicitly set to Completed should make the parent Purchase Receipt's
custom_inspection_status show Completed too (the reported bug: it stayed
"Working" regardless of the entry's own status)."""

import frappe
from frappe.utils import nowdate


def run():
	pr_name = frappe.db.get_value(
		"Purchase Receipt Item", {"item_code": "ZZTEST-INSPECT-ITEM"}, "parent",
		order_by="creation desc",
	)
	pr = frappe.get_doc("Purchase Receipt", pr_name)
	print("using PR:", pr.name)

	from manufyxinvenzaerp.production_management import inspection as insp

	insp.add_inspection_call("Purchase Receipt", pr.name, call_date=nowdate())
	entry_name = insp.create_inspection_entry("Purchase Receipt", pr.name)
	entry = frappe.get_doc("Inspection Entry", entry_name)
	entry.status = "Completed"
	entry.feedback = "Not Ok"
	entry.items[0].accept_qty = 4  # partial reject, qty=10 -> reject_qty=6
	entry.items[0].remarks = "reject some, but marking round Completed anyway"
	entry.save(ignore_permissions=True)
	print("reject_qty =", entry.items[0].reject_qty, "(should be > 0)")
	entry.submit()

	pr.reload()
	print("PR custom_inspection_status =", pr.custom_inspection_status, "(should be Completed)")
	frappe.db.commit()
