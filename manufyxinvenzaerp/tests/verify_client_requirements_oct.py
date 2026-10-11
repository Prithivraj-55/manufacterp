"""The client's October 2026 change list, checked against a copy of live data.

  1. BOM template in the client's column order; Description and the two Rate Schedule
     columns read by the import.
  3. MRS No. / Cutting Plan No. typed in the Material Issue Plan popups reach the
     Stock Entry (and are left off the leg into CNC).
  4. Painting Rate Schedule travels Drawing <-> BOM <-> Production Plan like the
     Fabrication one, without touching it.
  7. Inspection Entry: Ok / Not Ok gone, Partly Completed read off the quantities.
  8/9. Operation Entry: list columns, Status read-only.
  11. Packing Slip from a Delivery Note: Qty in Nos, Net Weight per piece, header Net
     Weight = the note's Kg, and the note still submits (packed Kg = its Kg).
  13/14. Return Excess Entry: received into the Excess Return Warehouse with a Return
     Slip No.; scrap lines leave the job's material at the supplier (never counted
     twice), are costed from what left for them, and are logged on the plan.

Everything that writes runs inside one transaction that is rolled back at the end --
the code under test commits mid-request, so frappe.db.commit is stubbed out while it
runs. Nothing is left on the site.

Run: bench --site manufactv16 execute manufyxinvenzaerp.tests.verify_client_requirements_oct.run
"""

import io
import os
import tempfile

import frappe
from frappe.utils import flt

checks = []


def check(label, got, want):
	ok = got == want
	checks.append(ok)
	print("  %-4s %-66s got=%r want=%r" % ("OK" if ok else "FAIL", label, got, want))


def _throws(fn, needle=None):
	frappe.db.savepoint("mfx_throw")
	try:
		fn()
	except frappe.ValidationError as e:
		frappe.db.rollback(save_point="mfx_throw")
		frappe.clear_last_message()
		return needle in str(e) if needle else True
	return False


def run():
	real_commit = frappe.db.commit
	frappe.db.commit = lambda *a, **k: None
	try:
		_bom_template()
		_slip_numbers()
		_painting_rate_schedule()
		_inspection_entry()
		_operation_entry()
		_packing_slip()
		_excess_and_scrap()
	finally:
		frappe.db.rollback()
		frappe.db.commit = real_commit
	print()
	print("ALL %d CHECKS PASSED" % len(checks) if all(checks) else "%d of %d CHECKS FAILED" % (checks.count(False), len(checks)))


# ── 1. BOM template ──────────────────────────────────────────────────────────────


def _bom_template():
	import openpyxl

	from manufyxinvenzaerp.drawing_management import so_drawing_import as imp

	print("=== 1. BOM template ===")
	imp.download_bom_template()
	wb = openpyxl.load_workbook(io.BytesIO(frappe.response["filecontent"]))
	headers = [c.value for c in wb.active[1]]
	client = ["Assembly Group", "Customer Drawing Number", "Description", "FG Item", "DUNO/Mark No",
	          "Item No", "Material Code", "Thickness", "Width", "Length", "Reqd Raw Material Qty", "Grade",
	          "Total Qty", "Cust Weight (per Nos)", "Cust Weight (Total)"]
	check("client's columns keep their order", [h for h in headers if h in client], client)
	check("Nature of Work, Fabrication, Painting follow FG Item",
	      headers[headers.index("FG Item") + 1: headers.index("FG Item") + 4],
	      ["Nature of Work", "Fabrication Rate Schedule", "Painting Rate Schedule"])
	frappe.response.pop("filecontent", None)

	ws_path = os.path.join(tempfile.mkdtemp(), "bom.xlsx")
	wb.save(ws_path)
	drawings = imp._parse_excel(ws_path)
	d = next(iter(drawings.values()))
	check("Description read", d["description"], "Beam")
	check("Painting Rate Schedule read", bool(d["painting_rate_schedule"]), True)
	check("Fabrication read from its new header", d["rate_schedule"], d["painting_rate_schedule"])


# ── 3. Slip numbers ──────────────────────────────────────────────────────────────


def _slip_numbers():
	import inspect

	from manufyxinvenzaerp.subcontracting_management import material_issue_plan_transfer as t

	print("=== 3. MRS / Cutting Plan / Return Slip ===")
	check("blank slips set nothing", t._slip_numbers(custom_mrs_number=" ", custom_cutting_plan_no=None), {})
	check("typed slips are trimmed", t._slip_numbers(custom_mrs_number=" MRS-1 "), {"custom_mrs_number": "MRS-1"})
	for fn in (t.create_mip_partial_transfer, t.create_mip_cnc_partial_forward):
		params = inspect.signature(fn).parameters
		check("%s takes both slips" % fn.__name__, "mrs_number" in params and "cutting_plan_no" in params, True)
	src = inspect.getsource(t.create_mip_partial_transfer)
	check("leg into CNC carries no slips", 'if transfer_type != "cnc" else {}' in src, True)
	for f in ("custom_mrs_number", "custom_cutting_plan_no", "custom_return_slip_no"):
		df = frappe.get_meta("Stock Entry").get_field(f)
		check("Stock Entry has %s, editable" % f, bool(df) and not df.read_only, True)


# ── 4. Painting Rate Schedule ────────────────────────────────────────────────────


def _painting_rate_schedule():
	from manufyxinvenzaerp.drawing_management import rate_schedule_sync as rss

	print("=== 4. Painting Rate Schedule ===")
	for dt, f in (("Drawing", "painting_rate_schedule"), ("BOM", "custom_painting_rate_schedule"),
	              ("Production Plan Item", "custom_painting_rate_schedule"),
	              ("Sales Order DUNO Item", "painting_rate_schedule")):
		check("%s has the Painting link" % dt, bool(frappe.get_meta(dt).get_field(f)), True)
	check("Fabrication label", frappe.get_meta("Drawing").get_field("rate_schedule").label, "Fabrication Rate Schedule")

	row = frappe.db.sql(
		"""SELECT b.custom_drawing AS drawing FROM `tabBOM` b
		   JOIN `tabProduction Plan Item` p ON p.custom_drawing = b.custom_drawing AND p.docstatus < 2
		   WHERE b.docstatus < 2 AND IFNULL(b.custom_drawing, '') != '' LIMIT 1""", as_dict=True)
	schedules = frappe.get_all("Rate Schedule", fields=["name", "rate_per_kg"], limit=2)
	if not row or not schedules:
		print("  (no drawing with a BOM and plan row, or no Rate Schedule -- propagation not exercised)")
		return
	drawing = row[0].drawing
	fab_before = frappe.db.get_value("Drawing", drawing, "rate_schedule")
	paint = schedules[-1]
	doc = frappe.get_doc("Drawing", drawing)
	doc.painting_rate_schedule = paint.name
	doc.flags.ignore_validate_update_after_submit = True
	doc.save(ignore_permissions=True)
	frappe.clear_messages()
	boms = frappe.get_all("BOM", filters={"custom_drawing": drawing, "docstatus": ["<", 2]},
	                      fields=["custom_painting_rate_schedule", "custom_prs_rate_per_kg", "custom_rate_schedule"])
	pps = frappe.get_all("Production Plan Item", filters={"custom_drawing": drawing, "docstatus": ["<", 2]},
	                     fields=["custom_painting_rate_schedule", "custom_prs_rate_per_kg"])
	check("BOM follows the Drawing's Painting schedule",
	      {b.custom_painting_rate_schedule for b in boms}, {paint.name})
	check("BOM carries its Rate/KG", {flt(b.custom_prs_rate_per_kg) for b in boms}, {flt(paint.rate_per_kg)})
	check("plan rows follow", {p.custom_painting_rate_schedule for p in pps}, {paint.name})
	check("Fabrication untouched on the Drawing", frappe.db.get_value("Drawing", drawing, "rate_schedule"), fab_before)
	conflict = rss.get_rate_schedule_conflict(drawing, "", kind="painting")
	check("conflict question asks about Painting", conflict["current"], paint.name)

	# The Sales Order's Drawing List row is the fourth place: an edit there reaches
	# the Drawing, and the Drawing's edit (above) reached the row.
	so_row = frappe.db.get_value("Sales Order DUNO Item", {"drawing": drawing, "docstatus": ["<", 2]},
	                             ["name", "parent"], as_dict=True)
	if so_row:
		check("Drawing's Painting schedule reached its Sales Order row",
		      frappe.db.get_value("Sales Order DUNO Item", so_row.name, "painting_rate_schedule"), paint.name)
		so = frappe.get_doc("Sales Order", so_row.parent)
		row = next(r for r in so.custom_duno_items if r.name == so_row.name)
		fab = schedules[0]
		row.rate_schedule = fab.name
		row.nature_of_work = frappe.db.get_value("Nature of Work", {}, "name") or ""
		so.flags.ignore_validate_update_after_submit = True
		so.save(ignore_permissions=True) if so.docstatus == 0 else so.save()
		frappe.clear_messages()
		check("Sales Order row's Fabrication schedule reached the Drawing",
		      frappe.db.get_value("Drawing", drawing, ["rate_schedule", "rs_rate_per_kg"]),
		      (fab.name, flt(fab.rate_per_kg)))
		check("and its Nature of Work",
		      frappe.db.get_value("Drawing", drawing, "nature_of_work"), row.nature_of_work)
		check("and the BOM", {b.custom_rate_schedule for b in frappe.get_all(
		      "BOM", filters={"custom_drawing": drawing, "docstatus": ["<", 2]}, fields=["custom_rate_schedule"])},
		      {fab.name})


# ── 7. Inspection Entry ──────────────────────────────────────────────────────────


def _inspection_entry():
	print("=== 7. Inspection Entry ===")
	for dt in ("Inspection Entry", "Inspection Entry Item", "SOE Inspection Item"):
		check("%s has no Ok / Not Ok" % dt, bool(frappe.get_meta(dt).get_field("feedback")), False)
	meta = frappe.get_meta("Inspection Entry")
	check("Partly Completed is a status", "Partly Completed" in meta.get_field("status").options.split("\n"), True)
	order = [f.fieldname for f in meta.fields]
	check("3rd column: Status, Complete Date, Remarks",
	      order[order.index("column_break_status") + 1: order.index("column_break_status") + 4],
	      ["status", "inspection_complete_date", "overall_remarks"])
	check("Sales Order sits after Production Plan", order.index("sales_order") == order.index("production_plan") + 1, True)

	doc = frappe.new_doc("Inspection Entry")
	doc.source_doctype = "Purchase Receipt"
	doc.status = "Working"
	doc.append("items", {"qty": 10, "accept_qty": 4})
	doc._set_partly_completed()
	check("some cleared -> Partly Completed", doc.status, "Partly Completed")
	doc.items[0].accept_qty = 10
	doc._set_partly_completed()
	check("all cleared -> back to Working (Completed is the inspector's)", doc.status, "Working")
	doc.items[0].accept_qty = 0
	doc.status = "Open"
	doc._set_partly_completed()
	check("nothing cleared stays Open", doc.status, "Open")


# ── 8/9. Operation Entry ─────────────────────────────────────────────────────────


def _operation_entry():
	print("=== 8/9. Operation Entry ===")
	meta = frappe.get_meta("Supplier Operation Entry")
	in_list = [f.fieldname for f in meta.fields if f.in_list_view]
	check("Work Order not in the list", "work_order" in in_list, False)
	check("Job Work Order, Operation, Supplier/Contractor listed",
	      all(f in in_list for f in ("subcontracting_order", "operation", "supplier", "contractor")), True)
	check("Job Work Order labelled as such", meta.get_field("subcontracting_order").label, "Job Work Order")
	check("Status is read-only", meta.get_field("status").read_only, 1)
	script = frappe.db.get_value("Client Script", "Supplier Operation Entry-client", "script") or ""
	if not script:
		script = "".join(frappe.get_all("Client Script", filters={"dt": "Supplier Operation Entry"}, pluck="script"))
	check("Mark as Complete button installed", "Mark as Complete" in script, True)


# ── 11. Packing Slip ─────────────────────────────────────────────────────────────


def _packing_slip():
	from manufyxinvenzaerp.selling_management.packing_slip import make_packing_slip

	print("=== 11. Packing Slip ===")
	dn_name = frappe.db.get_value("Delivery Note Item", {"docstatus": 0, "custom_sec_qty": [">", 0]}, "parent")
	if not dn_name:
		print("  (no draft Delivery Note with Nos -- not exercised)")
		return
	dn = frappe.get_doc("Delivery Note", dn_name)
	ps = make_packing_slip(dn_name)
	by_row = {r.name: r for r in dn.items}
	rows_ok = all(
		abs(flt(r.qty) - flt(by_row[r.dn_detail].custom_sec_qty)) < 0.001
		and abs(flt(r.net_weight) - flt(by_row[r.dn_detail].qty) / flt(by_row[r.dn_detail].custom_sec_qty)) < 0.001
		for r in ps.items if flt(by_row[r.dn_detail].custom_sec_qty)
	)
	check("Qty = Nos, Net Weight = Kg per piece", rows_ok, True)
	kg = sum(flt(r.qty) for r in dn.items if r.name in {p.dn_detail for p in ps.items})
	check("header Net Weight = the note's Kg", abs(flt(ps.net_weight_pkg) - kg) < 0.05, True)
	ps.insert(ignore_permissions=True)
	ps.submit()
	packed = {r.name: flt(r.packed_qty, 3) for r in frappe.get_all(
		"Delivery Note Item", filters={"parent": dn_name}, fields=["name", "packed_qty"])}
	check("note's Packed Qty = its Kg on every packed row",
	      all(abs(packed[p.dn_detail] - flt(by_row[p.dn_detail].qty, 3)) < 0.001 for p in ps.items), True)
	dn.reload()
	check("the note would still submit (packed = qty)", _throws(dn.validate_packed_qty), False)
	ps2 = make_packing_slip(dn_name)
	check("a second slip finds nothing left to pack", len(ps2.items), 0)


# ── 13/14. Excess return and scrap ───────────────────────────────────────────────


SCRAP = "ZZTEST-SCRAP-STEEL"


def _hsn():
	"""India Compliance refuses an Item without one; borrow any the site already uses."""
	return frappe.db.get_value("Item", {"gst_hsn_code": ["is", "set"]}, "gst_hsn_code")


def _scrap_item():
	from manufyxinvenzaerp.tests.fixtures import ensure_test_item_group

	if not frappe.db.exists("Item", SCRAP):
		frappe.get_doc({
			"doctype": "Item", "item_code": SCRAP, "item_name": "ZZTEST Steel Scrap",
			"item_group": ensure_test_item_group(), "custom_parent_item_group": "All Item Groups",
			"stock_uom": "Kg", "is_stock_item": 1, "has_batch_no": 0, "custom_is_scrap": 1,
			"gst_hsn_code": _hsn(),
		}).insert(ignore_permissions=True)
	return SCRAP


def _excess_and_scrap():
	from manufyxinvenzaerp.subcontracting_management import material_issue_plan_transfer as t

	print("=== 13/14. Excess return warehouse, Return Slip, Scrap ===")
	check("scrap item must not be batch-tracked", _throws(lambda: frappe.get_doc({
		"doctype": "Item", "item_code": "ZZTEST-SCRAP-BAD", "item_group": "All Item Groups",
		"custom_parent_item_group": "All Item Groups", "stock_uom": "Kg", "is_stock_item": 1,
		"has_batch_no": 1, "custom_is_scrap": 1, "gst_hsn_code": _hsn(),
	}).insert(ignore_permissions=True), "Has Batch No"), True)

	mip_name = None
	for m in frappe.get_all("Material Issue Plan", filters={"docstatus": ["!=", 2]},
	                        fields=["name", "supplier_warehouse", "subcontracting_order"], order_by="creation desc"):
		if m.supplier_warehouse and m.subcontracting_order:
			stock = t._job_stock_at_supplier(frappe.get_doc("Material Issue Plan", m.name))
			if sum(stock.values()) > 50:
				mip_name = m.name
				break
	if not mip_name:
		print("  (no plan with material at a supplier -- not exercised)")
		return
	from manufyxinvenzaerp.stock_management import storage_location as sl

	scrap = _scrap_item()
	mip = frappe.get_doc("Material Issue Plan", mip_name)
	target = mip.source_warehouse
	# Where the warehouse needs a location, everything received there names one.
	loc = (sl.warehouse_locations(target) or [None])[0] if sl.location_applicable(target) else None
	frappe.db.set_value("Material Issue Plan", mip_name,
	                    {"excess_material_warehouse": target, "excess_material_storage_location": loc})
	check("plan saves without an Excess Return location (asked for at return)",
	      _throws(lambda: frappe.get_doc("Material Issue Plan", mip_name).update(
	          {"excess_material_storage_location": None}).save(ignore_permissions=True)), False)
	frappe.db.set_value("Material Issue Plan", mip_name, "excess_material_storage_location", loc)
	before = t._job_stock_at_supplier(mip)
	print("  plan %s, %.3f Kg at %s, returning to %s" % (mip_name, sum(before.values()), mip.supplier_warehouse, target))

	check("not a scrap item -> refused", _throws(lambda: t.create_mip_excess_return_entry(
		mip_name, scrap_json=[{"item_code": next(iter(before))[0], "qty": 1, "warehouse": target, "storage_location": loc}]),
		"not a scrap item"), True)
	check("more scrap than is left -> refused", _throws(lambda: t.create_mip_excess_return_entry(
		mip_name, scrap_json=[{"item_code": scrap, "qty": sum(before.values()) + 100, "warehouse": target, "storage_location": loc}]),
		"short"), True)

	# One off-cut and one scrap line together: two incoming groups, each costed
	# from what left the supplier for it.
	item, batch = max(before, key=lambda k: before[k])
	mip = frappe.get_doc("Material Issue Plan", mip_name)
	mip.append("excess_return_items", {
		"item_code": item, "qty": 5, "enter_weight_instead_of_pieces": 1, "return_reason": "ZZTEST",
		"parent_item_group": frappe.db.get_value("Item", item, "custom_parent_item_group"),
		"unit_weight": frappe.db.get_value("Item", item, "custom_unit_weight"), "length": 100, "sec_qty": 1,
	})
	mip.flags.ignore_validate_update_after_submit = True
	mip.save(ignore_permissions=True)

	se_name = t.create_mip_excess_return_entry(
		mip_name, return_slip_no=" RS-77 ",
		scrap_json=[{"item_code": scrap, "qty": 7.5, "warehouse": target, "storage_location": loc}],
	)
	se = frappe.get_doc("Stock Entry", se_name)
	out = [r for r in se.items if r.s_warehouse]
	inc = {r.item_code: r for r in se.items if r.t_warehouse}
	check("a Repack", se.stock_entry_type, "Repack")
	check("Return Slip No. on the entry", se.custom_return_slip_no, "RS-77")
	check("off-cut lands in the Excess Return Warehouse", inc[item].t_warehouse, target)
	check("scrap row received as typed", (inc[scrap].qty, inc[scrap].t_warehouse), (7.5, target))
	check("out rows = off-cut + scrap Kg, all from the supplier",
	      (round(sum(flt(r.qty) for r in out), 3), {r.s_warehouse for r in out}), (12.5, {mip.supplier_warehouse}))
	out_cost = sum(flt(r.basic_amount) for r in out)
	in_cost = flt(inc[item].basic_amount) + flt(inc[scrap].basic_amount)
	check("incoming value = outgoing value", abs(out_cost - in_cost) < 1, True)

	se.submit()
	after = t._job_stock_at_supplier(frappe.get_doc("Material Issue Plan", mip_name))
	check("job's stock at the supplier fell by 12.5 Kg", round(sum(before.values()) - sum(after.values()), 3), 12.5)
	mip.reload()
	check("scrap logged on the plan", [(r.item_code, r.qty, r.stock_entry) for r in mip.scrap_return_items],
	      [(scrap, 7.5, se_name)])
	check("Scrap Returned (Kg) on the plan", flt(mip.scrap_returned_kg), 7.5)
	state = t.get_mip_process_loss_state(mip_name)
	check("process loss sees the scrap", state["scrap_returned"], 7.5)

	mip.excess_material_warehouse = None
	check("no Excess Return Warehouse, none chosen -> refused",
	      _throws(lambda: t._excess_return_target(mip), "Excess Return Warehouse"), True)
	check("the popup's choice wins", t._excess_return_target(mip, target, loc), (target, loc))
	if loc:
		check("a location-managed warehouse with no location -> refused",
		      _throws(lambda: t._excess_return_target(mip, target), "Storage Location"), True)
