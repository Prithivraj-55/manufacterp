import frappe
from frappe import _
from frappe.utils import flt, now

FORMULA_GROUPS = {"Structurals", "Plates"}


def validate_stock_entry(doc, method):
	"""Recalculate qty for formula-group items. Show popup only when qty was manually edited."""
	# For Manufacture, fill Sec Qty (Nos) on consumed rows proportional to the Kg consumed,
	# so the batch piece count is correctly reduced on submit. Done before totals + stock move.
	if doc.stock_entry_type == "Manufacture":
		_populate_manufacture_sec_qty(doc)

	# Always compute header totals regardless of SE type
	doc.custom_total_qty     = flt(sum(flt(r.qty) for r in doc.items), 3)
	doc.custom_total_sec_qty = flt(sum(flt(r.get("custom_sec_qty") or 0) for r in doc.items), 3)

	if doc.stock_entry_type not in {"Repack", "Material Receipt", "Material Issue"}:
		return

	manually_edited = []
	for row in doc.items:
		group = (row.get("custom_parent_item_group") or "").strip()
		if group not in FORMULA_GROUPS:
			continue
		formula_qty = flt(_calc_qty(row, group), 3)
		if not formula_qty:
			continue
		if flt(row.qty, 3) != formula_qty:
			manually_edited.append(row.item_code)
		row.qty = formula_qty

	if manually_edited:
		frappe.msgprint(
			_("Quantities for Structurals/Plates have been recalculated from dimensions."),
			indicator="orange",
		)


def on_submit_stock_entry(doc, method):
	"""Reduce custom_sec_qty on batch for consumed items
	(Material Issue + Repack/Manufacture source rows)."""
	if doc.stock_entry_type == "Material Issue":
		for row in doc.items:
			if row.batch_no and flt(row.get("custom_sec_qty")):
				_reduce_batch_sec_qty(row.batch_no, row.custom_sec_qty)

	elif doc.stock_entry_type in ("Repack", "Manufacture"):
		# Consumed raw-material rows have a source warehouse and are not the
		# produced item; this excludes finished goods and scrap (received rows).
		for row in doc.items:
			if (
				row.s_warehouse
				and not row.is_finished_item
				and row.batch_no
				and flt(row.get("custom_sec_qty"))
			):
				_reduce_batch_sec_qty(row.batch_no, row.custom_sec_qty)

	elif doc.stock_entry_type == "Material Receipt":
		for row in doc.items:
			batch_nos = set()
			if row.batch_no:
				batch_nos.add(row.batch_no)
			# serial_and_batch_bundle is written via db_set during on_submit,
			# so the in-memory row won't have it — read fresh from DB
			bundle = frappe.db.get_value("Stock Entry Detail", row.name, "serial_and_batch_bundle")
			if bundle:
				entries = frappe.get_all(
					"Serial and Batch Entry",
					filters={"parent": bundle},
					fields=["batch_no"],
				)
				batch_nos.update(e.batch_no for e in entries if e.batch_no)
			if not batch_nos:
				continue
			updates = {}
			if row.get("custom_supplier"):
				updates["supplier"] = row.custom_supplier
			group = (row.get("custom_parent_item_group") or "").strip()
			if group in FORMULA_GROUPS:
				if row.get("custom_existing_supplier_invoice_no"):
					updates["custom_existing_supplier_invoice_no"] = row.custom_existing_supplier_invoice_no
				if row.get("custom_existing_invoice_wt"):
					updates["custom_existing_invoice_wt"] = row.custom_existing_invoice_wt
				if row.get("custom_existing_inward_date"):
					updates["custom_existing_inward_date"] = row.custom_existing_inward_date
			for batch_no in batch_nos:
				if updates:
					frappe.db.set_value("Batch", batch_no, updates)

	# Release reservations for all consumed batches
	_release_material_planning_reservations(doc)

	# When materials are sent to supplier (or routed via CNC warehouse), update SCO weight fields.
	# We track via custom_sco_ref (not the standard subcontracting_order) to avoid
	# ERPNext's validate_subcontract_order which throws when supplied_items is empty.
	if doc.stock_entry_type == "Send to Subcontractor" and doc.get("custom_sco_ref"):
		_update_sco_transferred_weight(doc.custom_sco_ref)

	if doc.stock_entry_type == "Material Transfer" and doc.get("custom_sco_ref"):
		_update_sco_transferred_weight(doc.custom_sco_ref)
		_update_sco_cnc_weight(doc.custom_sco_ref)

	# SHARED_SCO_JC: WO transfer tracking mirrors SCO tracking above.
	# custom_wo_ref is set on Material Transfer SEs created by our WO transfer buttons.
	if doc.stock_entry_type == "Material Transfer" and doc.get("custom_wo_ref"):
		_update_wo_transferred_weight(doc.custom_wo_ref)
		_update_wo_cnc_weight(doc.custom_wo_ref)


def _reduce_batch_sec_qty(batch_no, consumed_qty):
	current = flt(frappe.db.get_value("Batch", batch_no, "custom_sec_qty"))
	frappe.db.set_value("Batch", batch_no, "custom_sec_qty", flt(current - flt(consumed_qty), 3))


def _batch_total_kg_all_wh(batch_no):
	"""Total net stock (Kg) of a batch across all warehouses (submitted SBBs)."""
	return flt(frappe.db.sql(
		"""
		SELECT COALESCE(SUM(sbe.qty), 0)
		FROM `tabSerial and Batch Entry` sbe
		JOIN `tabSerial and Batch Bundle` sbb ON sbb.name = sbe.parent
		WHERE sbe.batch_no = %s AND sbb.docstatus = 1
		""",
		batch_no,
	)[0][0])


def _populate_manufacture_sec_qty(doc):
	"""Set custom_sec_qty (Nos) on Manufacture consumed rows in proportion to the Kg consumed.

	A consumed row removes consumed_kg from a batch that holds custom_sec_qty pieces across
	its total stock — so the pieces consumed = total_sec * consumed_kg / total_kg. Computed at
	validate (before stock moves) so on_submit can decrement the batch and on_cancel reverse it.
	Existing non-zero values are respected (manual entry / re-validate).
	"""
	for row in doc.items:
		if not (row.s_warehouse and not row.is_finished_item and row.batch_no):
			continue
		if flt(row.get("custom_sec_qty")):
			continue
		total_kg = _batch_total_kg_all_wh(row.batch_no)
		if not total_kg:
			continue
		total_sec = flt(frappe.db.get_value("Batch", row.batch_no, "custom_sec_qty"))
		if not total_sec:
			continue
		row.custom_sec_qty = flt(total_sec * (flt(row.qty) / total_kg), 3)


def _collect_consumed_batches(doc):
	"""
	Collect batch_nos consumed by this SE.
	v15 SBB system: batch_no on SE Detail may be NULL (or cleared on cancel).
	Always also look up SBBs linked via voucher_no (any docstatus — on cancel they're docstatus=2).
	"""
	batches = set()
	for row in doc.items:
		if row.batch_no and not row.get("is_finished_item"):
			batches.add(row.batch_no)

	# Always supplement from SBBs linked to this SE — handles v15 SBB-tracked batches
	# and the case where batch_no is cleared on SE Detail after cancel.
	voucher_no = getattr(doc, "name", None)
	sbb_list = frappe.get_all(
		"Serial and Batch Bundle",
		filters={"voucher_no": voucher_no} if voucher_no else {"name": "__nonexistent__"},
		fields=["name"],
	) if voucher_no else []
	if sbb_list:
		sbb_names = [d.name for d in sbb_list]
		sbe_rows = frappe.get_all(
			"Serial and Batch Entry",
			filters={"parent": ["in", sbb_names]},
			fields=["batch_no"],
		)
		for r in sbe_rows:
			if r.batch_no:
				batches.add(r.batch_no)

	return batches


def _linked_material_plannings(doc):
	"""Material Planning docs whose reservations belong to this consumption.

	Traced via Work Order → Production Plan → po_items.custom_material_planning, plus any
	direct custom_production_plan on the Stock Entry. Used to scope reservation release so a
	shared batch reserved by *other* MPs is never wrongly un-reserved.
	Empty set => caller falls back to legacy batch-wide (all-MP) behaviour.
	"""
	pp_names = set()
	wo = doc.get("work_order")
	if wo:
		pp = frappe.db.get_value("Work Order", wo, "production_plan")
		if pp:
			pp_names.add(pp)
	if doc.get("custom_production_plan"):
		pp_names.add(doc.get("custom_production_plan"))

	mps = set()
	for pp in pp_names:
		for mp in frappe.get_all(
			"Production Plan Item", filters={"parent": pp}, pluck="custom_material_planning"
		):
			if mp:
				mps.add(mp)
	return mps


def _release_material_planning_reservations(doc):
	"""
	After a consumption Stock Entry is submitted, clear is_reserved on the Material Planning
	rows (both Material Mapping and Available Raw Material) whose batch was consumed — so the
	reserved qty no longer subtracts from free stock once the material is gone.

	Scoped to the Material Plannings linked to this consumption (via Work Order/Production Plan)
	so a batch shared with other MPs keeps those other reservations intact. When no link can be
	resolved, falls back to the legacy batch-wide behaviour on the Material Mapping table.
	"""
	consumed_types = {"Manufacture", "Material Transfer", "Material Issue", "Repack"}
	if doc.stock_entry_type not in consumed_types:
		return

	consumed_batches = _collect_consumed_batches(doc)
	if not consumed_batches:
		return

	linked_mps = _linked_material_plannings(doc)
	cleared = {"is_reserved": 0, "reserved_qty": 0, "shortfall_qty": 0, "reserved_on": None}

	if linked_mps:
		# Scoped release: only this consumption's own MP reservations, on both tables.
		for child_dt, batch_field in (
			("Material Planning Material Mapping", "batch"),
			("Material Planning Available Raw Material", "batch_no"),
		):
			rows = frappe.get_all(
				child_dt,
				filters={
					batch_field: ["in", list(consumed_batches)],
					"parent": ["in", list(linked_mps)],
					"is_reserved": 1,
				},
				pluck="name",
			)
			for name in rows:
				frappe.db.set_value(child_dt, name, cleared, update_modified=False)
		return

	# Fallback (no Production Plan link): legacy batch-wide release on Material Mapping.
	reserved_rows = frappe.get_all(
		"Material Planning Material Mapping",
		filters={"batch": ["in", list(consumed_batches)], "is_reserved": 1},
		pluck="name",
	)
	for name in reserved_rows:
		frappe.db.set_value("Material Planning Material Mapping", name, cleared, update_modified=False)


def on_cancel_stock_entry(doc, method):
	"""When a Stock Entry is cancelled, batch stock returns — restore Material Planning
	reservations and the consumed Sec Qty (Nos) on the batch."""
	_restore_material_planning_reservations(doc)
	_restore_batch_sec_qty(doc)

	# Recalculate transferred weight on SCO if a relevant SE is cancelled
	if doc.stock_entry_type == "Send to Subcontractor" and doc.get("custom_sco_ref"):
		_update_sco_transferred_weight(doc.custom_sco_ref)

	if doc.stock_entry_type == "Material Transfer" and doc.get("custom_sco_ref"):
		_update_sco_transferred_weight(doc.custom_sco_ref)
		_update_sco_cnc_weight(doc.custom_sco_ref)

	# SHARED_SCO_JC: WO cancel mirrors SCO cancel above.
	if doc.stock_entry_type == "Material Transfer" and doc.get("custom_wo_ref"):
		_update_wo_transferred_weight(doc.custom_wo_ref)
		_update_wo_cnc_weight(doc.custom_wo_ref)


def _restore_batch_sec_qty(doc):
	"""Reverse the custom_sec_qty reduction done on submit, mirroring on_submit_stock_entry."""
	if doc.stock_entry_type == "Material Issue":
		for row in doc.items:
			if row.batch_no and flt(row.get("custom_sec_qty")):
				_reduce_batch_sec_qty(row.batch_no, -flt(row.custom_sec_qty))

	elif doc.stock_entry_type in ("Repack", "Manufacture"):
		for row in doc.items:
			if (
				row.s_warehouse
				and not row.is_finished_item
				and row.batch_no
				and flt(row.get("custom_sec_qty"))
			):
				_reduce_batch_sec_qty(row.batch_no, -flt(row.custom_sec_qty))


def _restore_material_planning_reservations(doc):
	"""
	Re-apply is_reserved=1 on the Material Planning rows whose batch was consumed by this SE
	(they were cleared on submit), mirroring _release_material_planning_reservations: scoped to
	the linked Material Plannings on both tables, or legacy batch-wide on Material Mapping when
	no Production Plan link exists. Only currently-unreserved rows with the batch are restored.
	"""
	consumed_types = {"Manufacture", "Material Transfer", "Material Issue", "Repack"}
	if doc.stock_entry_type not in consumed_types:
		return

	consumed_batches = _collect_consumed_batches(doc)
	if not consumed_batches:
		return

	linked_mps = _linked_material_plannings(doc)

	def _reserve(child_dt, name, qty):
		frappe.db.set_value(
			child_dt, name,
			{"is_reserved": 1, "reserved_qty": flt(qty), "shortfall_qty": 0, "reserved_on": now()},
			update_modified=False,
		)

	if linked_mps:
		# Scoped restore on both tables (qty source differs per child table).
		for child_dt, batch_field, qty_field in (
			("Material Planning Material Mapping", "batch", "qty"),
			("Material Planning Available Raw Material", "batch_no", "required_qty"),
		):
			rows = frappe.get_all(
				child_dt,
				filters={
					batch_field: ["in", list(consumed_batches)],
					"parent": ["in", list(linked_mps)],
					"is_reserved": 0,
				},
				fields=["name", qty_field],
			)
			for r in rows:
				_reserve(child_dt, r.name, r.get(qty_field))
		return

	# Fallback (no Production Plan link): legacy batch-wide restore on Material Mapping.
	mapping_rows = frappe.get_all(
		"Material Planning Material Mapping",
		filters={"batch": ["in", list(consumed_batches)], "is_reserved": 0},
		fields=["name", "qty"],
	)
	for r in mapping_rows:
		_reserve("Material Planning Material Mapping", r.name, r.qty)


def _update_sco_transferred_weight(sco_name):
	"""Recompute SCO.custom_transferred_weight_kg:
	  - qty from submitted 'Send to Subcontractor' SEs to the supplier warehouse, PLUS
	  - qty from submitted 'Material Transfer' SEs that go CNC warehouse → supplier warehouse.
	Also refreshes Op-1 SOE's available_to_consume_kg if it is still in draft.
	"""
	supplier_warehouse, cnc_warehouse = frappe.db.get_value(
		"Subcontracting Order", sco_name, ["supplier_warehouse", "custom_cnc_warehouse"]
	)
	if not supplier_warehouse:
		return

	# Direct source → supplier transfers
	r1 = frappe.db.sql(
		"""
		SELECT COALESCE(SUM(sed.qty), 0)
		FROM `tabStock Entry Detail` sed
		JOIN `tabStock Entry` se ON se.name = sed.parent
		WHERE se.custom_sco_ref = %s
		  AND se.stock_entry_type = 'Send to Subcontractor'
		  AND se.docstatus = 1
		  AND sed.t_warehouse = %s
		""",
		(sco_name, supplier_warehouse),
	)
	direct_qty = flt(r1[0][0]) if r1 and r1[0][0] else 0

	# CNC warehouse → supplier warehouse transfers
	cnc_to_supplier_qty = 0.0
	if cnc_warehouse:
		r2 = frappe.db.sql(
			"""
			SELECT COALESCE(SUM(sed.qty), 0)
			FROM `tabStock Entry Detail` sed
			JOIN `tabStock Entry` se ON se.name = sed.parent
			WHERE se.custom_sco_ref = %s
			  AND se.stock_entry_type = 'Material Transfer'
			  AND se.docstatus = 1
			  AND sed.s_warehouse = %s
			  AND sed.t_warehouse = %s
			""",
			(sco_name, cnc_warehouse, supplier_warehouse),
		)
		cnc_to_supplier_qty = flt(r2[0][0]) if r2 and r2[0][0] else 0

	transferred = flt(direct_qty + cnc_to_supplier_qty, 3)
	frappe.db.set_value(
		"Subcontracting Order", sco_name, "custom_transferred_weight_kg", transferred
	)

	# Keep Op-1 SOE in sync while still in draft
	soe_op1 = frappe.db.get_value(
		"Supplier Operation Entry",
		{"subcontracting_order": sco_name, "sequence_id": 1, "docstatus": 0},
		"name",
	)
	if soe_op1:
		frappe.db.set_value(
			"Supplier Operation Entry", soe_op1, "available_to_consume_kg", transferred
		)


def _update_sco_cnc_weight(sco_name):
	"""Recompute SCO.custom_cnc_transferred_weight_kg:
	  net qty currently in the CNC warehouse = sent to CNC minus already forwarded to supplier.
	"""
	cnc_warehouse, supplier_warehouse = frappe.db.get_value(
		"Subcontracting Order", sco_name, ["custom_cnc_warehouse", "supplier_warehouse"]
	)
	if not cnc_warehouse:
		return

	r1 = frappe.db.sql(
		"""
		SELECT COALESCE(SUM(sed.qty), 0)
		FROM `tabStock Entry Detail` sed
		JOIN `tabStock Entry` se ON se.name = sed.parent
		WHERE se.custom_sco_ref = %s
		  AND se.stock_entry_type = 'Material Transfer'
		  AND se.docstatus = 1
		  AND sed.t_warehouse = %s
		""",
		(sco_name, cnc_warehouse),
	)
	sent_to_cnc = flt(r1[0][0]) if r1 and r1[0][0] else 0

	sent_to_supplier = 0.0
	if supplier_warehouse:
		r2 = frappe.db.sql(
			"""
			SELECT COALESCE(SUM(sed.qty), 0)
			FROM `tabStock Entry Detail` sed
			JOIN `tabStock Entry` se ON se.name = sed.parent
			WHERE se.custom_sco_ref = %s
			  AND se.stock_entry_type = 'Material Transfer'
			  AND se.docstatus = 1
			  AND sed.s_warehouse = %s
			  AND sed.t_warehouse = %s
			""",
			(sco_name, cnc_warehouse, supplier_warehouse),
		)
		sent_to_supplier = flt(r2[0][0]) if r2 and r2[0][0] else 0

	cnc_qty = max(0.0, flt(sent_to_cnc - sent_to_supplier, 3))
	frappe.db.set_value(
		"Subcontracting Order", sco_name, "custom_cnc_transferred_weight_kg", cnc_qty
	)


def _update_wo_transferred_weight(wo_name):
	"""Recompute WO.custom_transferred_weight_kg and sync Op-1 JC available_to_consume_kg.
	Counts: source → WIP transfers PLUS CNC → WIP transfers (both via custom_wo_ref SEs).
	# SHARED_SCO_JC: mirrors _update_sco_transferred_weight
	"""
	wip_warehouse = frappe.db.get_value("Work Order", wo_name, "wip_warehouse")
	cnc_warehouse = frappe.db.get_value("Work Order", wo_name, "custom_cnc_warehouse")
	if not wip_warehouse:
		return

	# Source → WIP (any Material Transfer with custom_wo_ref going TO wip_warehouse,
	# excluding CNC→WIP which is counted separately to avoid double-counting)
	r1 = frappe.db.sql(
		"""
		SELECT COALESCE(SUM(sed.qty), 0)
		FROM `tabStock Entry Detail` sed
		JOIN `tabStock Entry` se ON se.name = sed.parent
		WHERE se.custom_wo_ref = %s
		  AND se.stock_entry_type = 'Material Transfer'
		  AND se.docstatus = 1
		  AND sed.t_warehouse = %s
		""",
		(wo_name, wip_warehouse),
	)
	direct_qty = flt(r1[0][0]) if r1 and r1[0][0] else 0

	transferred = flt(direct_qty, 3)
	frappe.db.set_value("Work Order", wo_name, "custom_transferred_weight_kg", transferred)

	# Sync Op-1 JC custom_available_to_consume_kg while still in draft
	jc_op1 = frappe.db.get_value(
		"Job Card",
		{"work_order": wo_name, "sequence_id": 1, "docstatus": 0},
		"name",
	)
	if jc_op1:
		frappe.db.set_value("Job Card", jc_op1, "custom_available_to_consume_kg", transferred)


def _update_wo_cnc_weight(wo_name):
	"""Recompute WO.custom_cnc_transferred_weight_kg:
	net qty currently in CNC warehouse = sent to CNC minus already forwarded to WIP.
	# SHARED_SCO_JC: mirrors _update_sco_cnc_weight
	"""
	cnc_warehouse = frappe.db.get_value("Work Order", wo_name, "custom_cnc_warehouse")
	wip_warehouse  = frappe.db.get_value("Work Order", wo_name, "wip_warehouse")
	if not cnc_warehouse:
		return

	r1 = frappe.db.sql(
		"""
		SELECT COALESCE(SUM(sed.qty), 0)
		FROM `tabStock Entry Detail` sed
		JOIN `tabStock Entry` se ON se.name = sed.parent
		WHERE se.custom_wo_ref = %s
		  AND se.stock_entry_type = 'Material Transfer'
		  AND se.docstatus = 1
		  AND sed.t_warehouse = %s
		""",
		(wo_name, cnc_warehouse),
	)
	sent_to_cnc = flt(r1[0][0]) if r1 and r1[0][0] else 0

	sent_to_wip = 0.0
	if wip_warehouse:
		r2 = frappe.db.sql(
			"""
			SELECT COALESCE(SUM(sed.qty), 0)
			FROM `tabStock Entry Detail` sed
			JOIN `tabStock Entry` se ON se.name = sed.parent
			WHERE se.custom_wo_ref = %s
			  AND se.stock_entry_type = 'Material Transfer'
			  AND se.docstatus = 1
			  AND sed.s_warehouse = %s
			  AND sed.t_warehouse = %s
			""",
			(wo_name, cnc_warehouse, wip_warehouse),
		)
		sent_to_wip = flt(r2[0][0]) if r2 and r2[0][0] else 0

	cnc_qty = max(0.0, flt(sent_to_cnc - sent_to_wip, 3))
	frappe.db.set_value("Work Order", wo_name, "custom_cnc_transferred_weight_kg", cnc_qty)


def _calc_qty(row, group):
	l = flt(row.get("custom_length"))
	w = flt(row.get("custom_width"))
	t = flt(row.get("custom_thickness"))
	uw = flt(row.get("custom_unit_weight"))
	sq = flt(row.get("custom_sec_qty"))

	if group == "Structurals" and l and uw and sq:
		return (l / 1000) * uw * sq
	if group == "Plates" and l and w and t and uw and sq:
		return (l / 1000) * (w / 1000) * t * uw * sq
	return 0.0
