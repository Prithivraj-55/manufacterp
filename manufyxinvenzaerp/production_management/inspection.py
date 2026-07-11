"""Inspection Call / QC workflow shared by Job Card and Supplier Operation Entry
for the two QC checkpoint operations: "Fitup Inspection" and "Final Inspection".

Manufacturing logs an Inspection Call Date on the Job Card/SOE (round-tracked in
the `custom_inspection_call_log` child table); QC records the actual result on a
separate "Inspection Entry" document. Unresolved (rework) qty keeps the parent's
`custom_inspection_status` at "Working" until a later round fully clears it.
# SHARED_JC_SOE_INSPECTION: every function below treats Job Card and Supplier
# Operation Entry identically, per their shared 1:1 operation-per-document shape.
"""

import frappe
from frappe import _
from frappe.utils import flt

INSPECTION_OPERATIONS = ("Fitup Inspection", "Final Inspection")


# ─── Job Card / SOE hooks ────────────────────────────────────────────────────

def validate_job_card_inspection(doc, method):
	_validate_inspection_call_log(doc)


def validate_soe_inspection(doc, method):
	_validate_inspection_call_log(doc)


def _validate_inspection_call_log(doc):
	if doc.operation not in INSPECTION_OPERATIONS:
		return
	for idx, row in enumerate(doc.get("custom_inspection_call_log") or [], start=1):
		if not row.round_no:
			row.round_no = idx


def before_submit_job_card_inspection_gate(doc, method):
	_before_submit_inspection_gate(doc)


def before_submit_soe_inspection_gate(doc, method):
	_before_submit_inspection_gate(doc)


def _before_submit_inspection_gate(doc):
	if doc.operation not in INSPECTION_OPERATIONS:
		return
	if (doc.custom_inspection_status or "") != "Completed":
		frappe.throw(
			_("Inspection Status must be <b>Completed</b> before submitting this {0} for the "
			  "<b>{1}</b> operation.").format(doc.doctype, doc.operation),
			title=_("Inspection Not Completed"),
		)


# ─── Whitelisted API (called from job_card.js / supplier_operation_entry.js) ─

@frappe.whitelist()
def add_inspection_call(source_doctype, source_name):
	"""Log a new inspection call round from the source doc's
	`custom_inspection_call_date` field. Blocked while a round is already
	pending (i.e. its Inspection Entry hasn't been submitted yet)."""
	doc = _get_source_doc(source_doctype, source_name)

	if not doc.custom_inspection_call_date:
		frappe.throw(_("Set an Inspection Call Date first."))

	existing = doc.get("custom_inspection_call_log") or []
	if any(row.round_status == "Pending" for row in existing):
		frappe.throw(
			_("An inspection round is already pending. Create and submit its Inspection "
			  "Entry before logging a new call.")
		)

	doc.append("custom_inspection_call_log", {
		"round_no": len(existing) + 1,
		"call_date": doc.custom_inspection_call_date,
		"round_status": "Pending",
	})
	if doc.custom_inspection_status == "Open":
		doc.custom_inspection_status = "Working"
	doc.save()

	return doc.name


@frappe.whitelist()
def create_inspection_entry(source_doctype, source_name):
	"""Create a draft Inspection Entry prefilled from the latest pending
	inspection call round, and link it back onto that round. Returns the new
	Inspection Entry name for the client to route to."""
	doc = _get_source_doc(source_doctype, source_name)

	pending_row = None
	for row in reversed(doc.get("custom_inspection_call_log") or []):
		if row.round_status == "Pending" and not row.inspection_entry:
			pending_row = row
			break
	if not pending_row:
		frappe.throw(
			_("Set an Inspection Call Date and click <b>Add Inspection Call</b> before "
			  "creating an Inspection Entry.")
		)

	sales_order, customer = _resolve_traceability(doc)

	if source_doctype == "Job Card":
		work_order = doc.work_order
		production_plan = frappe.db.get_value("Work Order", work_order, "production_plan") if work_order else ""
		subcontracting_order = ""
		supplier = ""
	else:
		work_order = doc.work_order
		production_plan = doc.production_plan
		subcontracting_order = doc.subcontracting_order
		supplier = doc.supplier

	entry = frappe.get_doc({
		"doctype": "Inspection Entry",
		"source_doctype": source_doctype,
		"job_card": source_name if source_doctype == "Job Card" else None,
		"supplier_operation_entry": source_name if source_doctype == "Supplier Operation Entry" else None,
		"operation": doc.operation,
		"round_no": pending_row.round_no,
		"call_date": pending_row.call_date,
		"work_order": work_order,
		"subcontracting_order": subcontracting_order,
		"production_plan": production_plan,
		"sales_order": sales_order,
		"customer": customer,
		"supplier": supplier,
	}).insert(ignore_mandatory=True)

	frappe.db.set_value("Inspection Call Log", pending_row.name, "inspection_entry", entry.name)

	return entry.name


def on_submit_inspection_entry(doc, method):
	"""Propagate the QC result back to the parent Job Card/SOE: mark the
	round Completed and set the overall Inspection Status — Completed once
	fully cleared, otherwise Working (awaiting the next call/round)."""
	parent_doctype = doc.source_doctype
	parent_name = doc.job_card if parent_doctype == "Job Card" else doc.supplier_operation_entry
	if not parent_name:
		return

	rows = frappe.get_all(
		"Inspection Call Log",
		filters={"parenttype": parent_doctype, "parent": parent_name, "inspection_entry": doc.name},
		fields=["name"],
		limit=1,
	)
	if not rows:
		return

	frappe.db.set_value(
		"Inspection Call Log",
		rows[0].name,
		{"round_status": "Completed", "remarks": doc.rework_remarks or ""},
	)
	new_status = "Working" if flt(doc.rework_qty) > 0 else "Completed"
	frappe.db.set_value(parent_doctype, parent_name, "custom_inspection_status", new_status)


# ─── Private helpers ─────────────────────────────────────────────────────────

def _get_source_doc(source_doctype, source_name):
	if source_doctype not in ("Job Card", "Supplier Operation Entry"):
		frappe.throw(_("Invalid source doctype {0}").format(source_doctype))

	doc = frappe.get_doc(source_doctype, source_name)
	if doc.operation not in INSPECTION_OPERATIONS:
		frappe.throw(
			_("This action is only available for the <b>Fitup Inspection</b> and "
			  "<b>Final Inspection</b> operations.")
		)
	return doc


def _resolve_traceability(doc):
	"""Sales Order + Customer for a Job Card/SOE, via its drawing details
	(both already carry a per-row `sales_order`), falling back to the linked
	Work Order's `sales_order` field."""
	drawing_rows = doc.get("custom_drawing_details") or doc.get("drawing_details") or []
	sales_order = ""
	for row in drawing_rows:
		if row.get("sales_order"):
			sales_order = row.sales_order
			break
	if not sales_order and doc.get("work_order"):
		sales_order = frappe.db.get_value("Work Order", doc.work_order, "sales_order") or ""

	customer = frappe.db.get_value("Sales Order", sales_order, "customer") if sales_order else ""
	return sales_order, customer
