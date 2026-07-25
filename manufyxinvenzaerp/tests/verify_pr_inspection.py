"""Manual verification script for the Purchase Receipt Inspection Call workflow
(Phase 6.1 of the client change request, revised per client feedback: no stored
call-date field, popup-driven "Create Inspection" combining add_inspection_call
+ create_inspection_entry, an "Update Inspection Call Date" action, a visible
status field on Inspection Entry regardless of source, and inspection_complete_date
stamped on submit). Run via:

    bench --site manufact execute manufyxinvenzaerp.tests.verify_pr_inspection.run

Creates a throwaway Item (ZZTEST-INSPECT-ITEM) and one Purchase Receipt against
existing Company/Warehouse/Supplier records, then exercises the full round trip
and prints the results for manual inspection. Does not delete anything it creates.
"""

import frappe
from frappe.utils import nowdate


def run():
	company = frappe.db.get_value("Company", {}, "name")
	warehouse = frappe.db.get_value("Warehouse", {"company": company, "is_group": 0}, "name")
	supplier = frappe.db.get_value("Supplier", {}, "name")
	print("company=", company, "warehouse=", warehouse, "supplier=", supplier)

	item_code = "ZZTEST-INSPECT-ITEM"
	if not frappe.db.exists("Item", item_code):
		item_group = frappe.db.get_value("Item Group", {"is_group": 0}, "name")
		it = frappe.get_doc({
			"doctype": "Item",
			"item_code": item_code,
			"item_name": item_code,
			"item_group": item_group,
			"stock_uom": "Nos",
			"is_stock_item": 1,
			"gst_hsn_code": frappe.db.get_value("GST HSN Code", {}, "name"),
			"custom_parent_item_group": "Nuts and Bolts",
			"custom_inspection_required": 1,
		}).insert(ignore_permissions=True)
	else:
		it = frappe.get_doc("Item", item_code)
		it.custom_inspection_required = 1
		it.save(ignore_permissions=True)
	print("item ok, custom_inspection_required=", it.custom_inspection_required)

	pr = frappe.get_doc({
		"doctype": "Purchase Receipt",
		"supplier": supplier,
		"company": company,
		"set_warehouse": warehouse,
		"items": [
			{"item_code": item_code, "qty": 10, "rate": 1, "warehouse": warehouse},
		],
	})
	pr.insert(ignore_permissions=True)
	pr.submit()
	print("PR created+submitted:", pr.name, "pr_item row name:", pr.items[0].name)

	from manufyxinvenzaerp.production_management import inspection as insp

	# Round 1: "Create Inspection" popup flow, passing call_date directly (no stored field)
	insp.add_inspection_call("Purchase Receipt", pr.name, call_date=nowdate())
	print("after add_inspection_call, status=",
		frappe.db.get_value("Purchase Receipt", pr.name, "custom_inspection_status"))

	try:
		insp.add_inspection_call("Purchase Receipt", pr.name, call_date=nowdate())
		print("ERROR: second add_inspection_call should have been blocked!")
	except frappe.exceptions.ValidationError as e:
		print("OK blocked second call while in progress:", str(e)[:120])

	# Update Inspection Call Date button, before the entry is created
	insp.update_inspection_call_date("Purchase Receipt", pr.name, "2026-01-15")
	pr.reload()
	print("call date after update (pre-entry):", pr.custom_inspection_call_log[-1].call_date)

	entry_name = insp.create_inspection_entry("Purchase Receipt", pr.name)
	print("created Inspection Entry:", entry_name)

	entry = frappe.get_doc("Inspection Entry", entry_name)
	print("entry.status field present:", "status" in entry.as_dict())
	print("entry.items:", [(r.item_code, r.qty, r.accept_qty, r.reject_qty) for r in entry.items])
	entry.status = "Working"  # deliberately still in progress, despite a partial reject
	entry.feedback = "Not Ok"
	entry.overall_remarks = "round 1 overall remarks"
	entry.items[0].accept_qty = 7
	entry.items[0].remarks = "test partial reject"
	entry.save(ignore_permissions=True)
	print("after save, reject_qty auto-calc =", entry.items[0].reject_qty)
	entry.submit()
	print("entry submitted, inspection_complete_date =", entry.inspection_complete_date)

	pr.reload()
	row = pr.items[0]
	print("PR item after propagation: accepted=", row.custom_inspection_accepted_qty,
		"rejected=", row.custom_inspection_rejected_qty,
		"remarks=", row.custom_inspection_remarks)
	print("PR custom_inspection_status =", pr.custom_inspection_status)

	log = pr.custom_inspection_call_log
	print("call log rounds:", [(r.round_no, r.round_status, r.inspection_entry, r.call_date) for r in log])

	# Update Inspection Call Date button after round 1 is Completed (should still work + propagate to entry)
	insp.update_inspection_call_date("Purchase Receipt", pr.name, "2026-01-20")
	entry.reload()
	print("entry.call_date after update:", entry.call_date)

	# Round 2: full acceptance -> status should flip to Completed
	insp.add_inspection_call("Purchase Receipt", pr.name, call_date=nowdate())
	entry2_name = insp.create_inspection_entry("Purchase Receipt", pr.name)
	entry2 = frappe.get_doc("Inspection Entry", entry2_name)
	entry2.status = "Completed"
	entry2.feedback = "Ok"
	entry2.items[0].accept_qty = entry2.items[0].qty
	entry2.save(ignore_permissions=True)
	print("round 2 reject_qty =", entry2.items[0].reject_qty)
	entry2.submit()
	print("round 2 inspection_complete_date =", entry2.inspection_complete_date)

	pr.reload()
	print("PR custom_inspection_status after round 2 =", pr.custom_inspection_status)
	print("call log rounds after round 2:",
		[(r.round_no, r.round_status, r.inspection_entry) for r in pr.custom_inspection_call_log])

	frappe.db.commit()
	print("ALL CHECKS DONE")
