import frappe
from frappe import _
from frappe.utils import flt, now
from manufyxinvenzaerp.utils.reference_copy import copy_reference_fields_if_blank

FORMULA_GROUPS = {"Structurals", "Plates"}
REFERENCE_FIELDS = ["custom_drawing", "custom_duno_mark_no", "custom_customer_drawing_number", "custom_sales_order"]


def validate_stock_entry(doc, method):
	"""Recalculate qty for formula-group items. Show popup only when qty was manually edited."""
	for row in doc.items:
		_copy_from_material_request_item(row)

	_sync_batch_remarks(doc)

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


def _sync_batch_remarks(doc):
	"""Mirror each item row's assigned batch's own Batch Remarks (client
	change request Phase 6.3) onto its own custom_batch_remarks field.
	Applies to every Stock Entry type (not gated by the Structurals/Plates
	FORMULA_GROUPS check below, which is unrelated) -- one bulk query
	regardless of row count."""
	batch_nos = {r.batch_no for r in doc.items if r.get("batch_no")}
	if not batch_nos:
		return
	remarks_by_batch = dict(frappe.get_all(
		"Batch", filters={"name": ["in", list(batch_nos)]},
		fields=["name", "custom_batch_remarks"], as_list=True,
	))
	for row in doc.items:
		if row.get("batch_no"):
			row.custom_batch_remarks = remarks_by_batch.get(row.batch_no) or ""


def _copy_from_material_request_item(row):
	"""Copy drawing/DUNO/sales order references from the linked MR Item, same
	pattern as Purchase Order's/Purchase Receipt's _copy_from_mr_item -- covers
	the standard "Make Stock Entry" flow from a Material Request (client change
	request Phase 1.3). Project is already a core field on Stock Entry Detail
	so it needs no custom field, but core "Make" flows don't map it forward on
	their own -- copy it here too."""
	copy_reference_fields_if_blank(row, "Material Request Item", "material_request_item", REFERENCE_FIELDS)
	if not row.get("project") and row.get("material_request_item"):
		row.project = frappe.db.get_value("Material Request Item", row.material_request_item, "project")


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
		# Off-cuts coming back from a Return Excess Entry may already be spoken for:
		# another job can claim one through Excess Material Mapping's virtual picker
		# while it is still physically at the supplier. Collected here and reported
		# once at the end, so the user learns the paper reservation just became real.
		from manufyxinvenzaerp.production_management.doctype.material_planning.material_planning import (
			materialize_virtual_excess_claim,
		)

		materialized = []
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
			excess_row = row.get("custom_source_mip_excess_row")
			for batch_no in batch_nos:
				if updates:
					frappe.db.set_value("Batch", batch_no, updates)
				if excess_row:
					mp_name = materialize_virtual_excess_claim(excess_row, batch_no)
					if mp_name:
						materialized.append((batch_no, mp_name))

		if materialized:
			frappe.msgprint(
				_("These returned off-cuts were already reserved and are now backed by a real batch:")
				+ "<br>" + "<br>".join(
					_("Batch {0} → {1}").format(frappe.bold(b), frappe.utils.get_link_to_form("Material Planning", m))
					for b, m in materialized
				),
				title=_("Excess Claims Fulfilled"),
				indicator="green",
			)

	# Release reservations for all consumed batches
	_release_material_planning_reservations(doc)

	# Cut Sheet (client change request Phase 5.2): resize any batch this transfer
	# only partially moved (To Use / W1) down to its Balance (W2) dimensions --
	# same batch, no new one created.
	_resize_cut_sheet_batches(doc)

	# Cut Sheet doctype: the sheet is cut the moment the first piece leaves, so its
	# balance goes onto the batch now (see _apply_cut_sheet_w2).
	_apply_cut_sheet_w2(doc)

	# When materials are sent to supplier (or routed via CNC warehouse), update SCO weight fields.
	# We track via custom_sco_ref (not the standard subcontracting_order) to avoid
	# ERPNext's validate_subcontract_order which throws when supplied_items is empty.
	if doc.stock_entry_type == "Send to Subcontractor" and doc.get("custom_sco_ref"):
		_update_sco_transferred_weight(doc.custom_sco_ref)
		_refresh_linked_mip_weight(sco_ref=doc.custom_sco_ref)

	if doc.stock_entry_type == "Material Transfer" and doc.get("custom_sco_ref"):
		_update_sco_transferred_weight(doc.custom_sco_ref)
		_update_sco_cnc_weight(doc.custom_sco_ref)
		_refresh_linked_mip_weight(sco_ref=doc.custom_sco_ref)

	# SHARED_SCO_JC: WO transfer tracking mirrors SCO tracking above.
	# custom_wo_ref is set on Material Transfer SEs created by our WO transfer buttons.
	if doc.stock_entry_type == "Material Transfer" and doc.get("custom_wo_ref"):
		_update_wo_transferred_weight(doc.custom_wo_ref)
		_update_wo_cnc_weight(doc.custom_wo_ref)
		_refresh_linked_mip_weight(wo_ref=doc.custom_wo_ref)

	# Finished-goods receipt (create_finished_goods_entry's "Make Final Stock Entry"
	# button) -- re-saving the linked MIP here is what actually triggers its own
	# validate()'s _maybe_mark_completed check now that FG stock has been received;
	# the MIP is otherwise never touched by this Stock Entry at all.
	if doc.stock_entry_type == "Manufacture" and doc.get("subcontracting_order"):
		_refresh_linked_mip_weight(sco_ref=doc.subcontracting_order)


def _reduce_batch_sec_qty(batch_no, consumed_qty):
	current = flt(frappe.db.get_value("Batch", batch_no, "custom_sec_qty"))
	frappe.db.set_value("Batch", batch_no, "custom_sec_qty", flt(current - flt(consumed_qty), 3))


# A cut is treated as finished once this much of its To Use (W1) weight has moved.
_CUT_SHEET_TOLERANCE_KG = 0.01


def _resize_cut_sheet_batches(doc):
	"""Resize (in place -- no new batch) every Cut Sheet batch this Stock Entry
	touched. Only Material Issue Plan transfers carry custom_mip_ref, so this is a
	no-op for every other Stock Entry in the system."""
	_reapply_cut_sheet_batch_sizes(doc)


def _restore_cut_sheet_batches(doc):
	"""Cancelling a transfer puts the stock back, so the batch must go back to the
	size it was before that cut -- otherwise the batch keeps advertising the offcut's
	dimensions while holding the full uncut piece again. Runs the same recomputation
	as submit: with this Stock Entry now cancelled its weight drops out of the
	transferred total, so any cut it had completed is simply no longer complete."""
	_reapply_cut_sheet_batch_sizes(doc)


def _apply_cut_sheet_w2(doc, cancelling=False):
	"""Write each Cut Sheet's balance onto its batch on the FIRST transfer taken from
	that sheet, and take it back off if that transfer is cancelled.

	The trigger is the first transfer rather than the last, because that is when the
	sheet is physically cut: from that moment the plate in the rack IS the remnant,
	even though other jobs have not collected their pieces yet. Those pieces are still
	theirs -- the Cut Sheet keeps track of them independently of the batch's size.

	Which sheets this entry touched is read from the Material Planning rows behind it,
	since cancelling clears batch_no off the Stock Entry's own rows."""
	from manufyxinvenzaerp.production_management.doctype.cut_sheet.cut_sheet import (
		apply_w2_to_batch, revert_w2_from_batch,
	)

	mip_name = doc.get("custom_mip_ref")
	if not mip_name:
		return

	item_codes = {row.item_code for row in doc.items if row.item_code}
	if not item_codes:
		return

	mp_names = {r.material_planning for r in frappe.get_all(
		"Material Issue Plan Raw Material", filters={"parent": mip_name},
		fields=["material_planning"]) if r.material_planning}
	if not mp_names:
		return

	cut_sheets = {r.cut_sheet_ref for r in frappe.get_all(
		"Material Planning Material Mapping",
		filters={"parent": ["in", list(mp_names)], "item_code": ["in", list(item_codes)],
		         "cut_sheet_ref": ["!=", ""]},
		fields=["cut_sheet_ref"]) if r.cut_sheet_ref}

	for cs_name in cut_sheets:
		if not frappe.db.exists("Cut Sheet", cs_name):
			continue
		if cancelling:
			# Only undo what THIS entry did; another transfer may have been the one
			# that cut the sheet, and its write-back must stand.
			if frappe.db.get_value("Cut Sheet", cs_name, "w2_applied_stock_entry") == doc.name:
				revert_w2_from_batch(cs_name)
		else:
			apply_w2_to_batch(cs_name, doc.name)


def _reapply_cut_sheet_batch_sizes(doc):
	"""Which Cut Sheet batches this Stock Entry affects, taken from the PLAN rather
	than from the entry's own rows: cancelling clears batch_no and unlinks the Serial
	and Batch Bundle on every row, so by the time on_cancel runs the entry no longer
	says which batch it moved. The plan still does, and matching on item code is
	enough -- a Cut Sheet row names exactly one batch."""
	mip_name = doc.get("custom_mip_ref")
	if not mip_name:
		return

	item_codes = {row.item_code for row in doc.items if row.item_code}
	if not item_codes:
		return

	pairs = frappe.get_all(
		"Material Issue Plan Raw Material",
		filters={"parent": mip_name, "cut_sheet": 1, "item_code": ["in", list(item_codes)]},
		fields=["item_code", "batch_no"],
	)
	for item_code, batch_no in {(p.item_code, p.batch_no) for p in pairs if p.batch_no}:
		_apply_cut_sheet_batch_size(mip_name, item_code, batch_no)


def _apply_cut_sheet_batch_size(mip_name, item_code, batch_no):
	"""Set a batch's dimensions from however much of its cut plan has actually been
	cut, derived from the ledger rather than from "a transfer just happened".

	Two things made the previous version wrong. One sheet is routinely cut for
	several marks, so a batch can carry SEVERAL Cut Sheet rows -- they are read here
	in row order and treated as a chain, each cut taking its piece out of what the
	one before it left. And W1 can now be transferred in stages, so a cut that is
	only half issued must not shrink the batch yet.

	Both fall out of one rule: walk the rows in order accumulating their To Use (W1)
	weights, and the batch takes the Balance of the last row whose accumulated weight
	has actually left the warehouse. Nothing moved yet (or moved and was cancelled)
	means the batch goes back to its pre-cut size."""
	rows = frappe.get_all(
		"Material Issue Plan Raw Material",
		filters={"parent": mip_name, "cut_sheet": 1, "item_code": item_code, "batch_no": batch_no},
		fields=["name", "idx", "use_calc_qty", "balance_length", "balance_width", "balance_sec_qty",
		        "precut_length", "precut_width", "precut_sec_qty"],
		order_by="idx asc",
	)
	if not rows:
		return

	first = rows[0]
	if not (flt(first.precut_length) or flt(first.precut_width) or flt(first.precut_sec_qty)):
		# First time this batch is cut: remember the uncut size so a cancel has
		# something to restore to.
		batch = frappe.db.get_value(
			"Batch", batch_no, ["custom_length", "custom_width", "custom_sec_qty"], as_dict=True
		) or {}
		first.precut_length = flt(batch.get("custom_length"))
		first.precut_width = flt(batch.get("custom_width"))
		first.precut_sec_qty = flt(batch.get("custom_sec_qty"))
		frappe.db.set_value(
			"Material Issue Plan Raw Material", first.name,
			{"precut_length": first.precut_length, "precut_width": first.precut_width,
			 "precut_sec_qty": first.precut_sec_qty},
			update_modified=False,
		)

	moved = flt(frappe.db.sql("""
		SELECT COALESCE(SUM(sed.qty), 0)
		FROM `tabStock Entry Detail` sed
		JOIN `tabStock Entry` se ON se.name = sed.parent
		WHERE se.custom_mip_ref = %s AND se.docstatus = 1
		  AND sed.item_code = %s AND sed.batch_no = %s
	""", (mip_name, item_code, batch_no))[0][0])

	completed = None
	cumulative = 0.0
	for r in rows:
		cumulative += flt(r.use_calc_qty)
		if moved + _CUT_SHEET_TOLERANCE_KG < cumulative:
			break
		completed = r

	if completed:
		target = (completed.balance_length, completed.balance_width, completed.balance_sec_qty)
	else:
		target = (first.precut_length, first.precut_width, first.precut_sec_qty)

	frappe.db.set_value("Batch", batch_no, {
		"custom_length": flt(target[0]),
		"custom_width": flt(target[1]),
		"custom_sec_qty": flt(target[2]),
	})


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


# Stock Entry types that move reserved material out of the warehouse it was reserved
# in, and therefore release (on submit) or restore (on cancel) the Material Planning
# reservations behind it. One constant so the two stay in step -- a type released on
# submit but not restored on cancel would strand the reservation.
#
# 'Send to Subcontractor' was missing from this list, which mattered more than the rest
# put together: it is THE primary transfer in this app's flow, moving reserved material
# from Stores to the supplier. The main path released nothing, so batches stayed
# reserved after their stock had physically gone and their free qty was under-reported
# to every later plan.
RESERVATION_RELEASING_SE_TYPES = {
	"Manufacture", "Material Transfer", "Material Issue", "Repack", "Send to Subcontractor",
}


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
	if doc.get("custom_mip_ref"):
		pp = frappe.db.get_value("Material Issue Plan", doc.get("custom_mip_ref"), "production_plan")
		if pp:
			pp_names.add(pp)
	# Also via the Subcontracting Order, on either field. The finished-goods entry
	# (create_finished_goods_entry) sets only the core `subcontracting_order` -- no
	# custom_mip_ref, no custom_sco_ref -- so without this it resolves to nothing and
	# the caller drops to the legacy fallback, which releases Material Mapping rows and
	# silently leaves every exact-match reservation held forever.
	for fieldname in ("custom_sco_ref", "subcontracting_order"):
		sco = doc.get(fieldname)
		if not sco:
			continue
		pp = frappe.db.get_value("Subcontracting Order", sco, "custom_production_plan")
		if pp:
			pp_names.add(pp)

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
	if doc.stock_entry_type not in RESERVATION_RELEASING_SE_TYPES:
		return

	consumed_batches = _collect_consumed_batches(doc)
	if not consumed_batches:
		return

	linked_mps = _linked_material_plannings(doc)
	cleared = {"is_reserved": 0, "reserved_qty": 0, "shortfall_qty": 0, "reserved_on": None}

	if linked_mps:
		# When a primary (non-CNC) SE is submitted, preserve CNC row reservations so
		# the CNC transfer can still run without needing to re-reserve. Only clear CNC
		# reservations if this SE itself is a CNC-destined transfer.
		cnc_warehouse = None
		if doc.get("custom_mip_ref"):
			cnc_warehouse = frappe.db.get_value(
				"Material Issue Plan", doc.get("custom_mip_ref"), "cnc_warehouse"
			)
		se_is_cnc_transfer = bool(
			cnc_warehouse and any(getattr(item, "t_warehouse", None) == cnc_warehouse for item in doc.items)
		)

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
				fields=["name", "cnc_process"],
			)
			for r in rows:
				if r.cnc_process and not se_is_cnc_transfer:
					continue  # preserve CNC reservations when submitting a non-CNC SE
				frappe.db.set_value(child_dt, r.name, cleared, update_modified=False)
		return

	# Fallback (no Production Plan link): batch-wide release across BOTH tables.
	# It used to cover Material Mapping only, so an exact-match reservation whose entry
	# could not be traced to a plan stayed held forever, and the batch's free qty was
	# under-reported to every later plan even though its stock had gone.
	for child_dt, batch_field in (
		("Material Planning Material Mapping", "batch"),
		("Material Planning Available Raw Material", "batch_no"),
	):
		for name in frappe.get_all(
			child_dt,
			filters={batch_field: ["in", list(consumed_batches)], "is_reserved": 1},
			pluck="name",
		):
			frappe.db.set_value(child_dt, name, cleared, update_modified=False)


def _refresh_linked_mip_weight(sco_ref=None, wo_ref=None):
	"""After SE submit/cancel, refresh the transferred_weight_kg on the linked MIP."""
	from manufyxinvenzaerp.subcontracting_management.doctype.material_issue_plan.material_issue_plan import (
		refresh_weight_summary,
	)
	try:
		if sco_ref:
			mip_name = frappe.db.get_value("Material Issue Plan", {"subcontracting_order": sco_ref})
		elif wo_ref:
			mip_name = frappe.db.get_value("Material Issue Plan", {"work_order": wo_ref})
		else:
			return
		if mip_name:
			refresh_weight_summary(mip_name)
	except Exception:
		frappe.log_error(frappe.get_traceback(), "MIP weight refresh failed")
		# Report 3 Finding H-02 / Phase 1 HP-04: surface this to the submitting
		# user instead of only recording it in the Error Log -- the Material
		# Issue Plan's displayed transferred weight can otherwise go silently
		# stale after this Stock Entry submit/cancel with no on-screen signal.
		frappe.msgprint(
			_(
				"Could not refresh the linked Material Issue Plan's transferred weight after "
				"this Stock Entry. Its displayed weight summary may be stale until it is "
				"manually refreshed."
			),
			indicator="orange",
			title=_("Material Issue Plan Refresh Failed"),
		)


def on_cancel_stock_entry(doc, method):
	"""When a Stock Entry is cancelled, batch stock returns — restore Material Planning
	reservations and the consumed Sec Qty (Nos) on the batch."""
	_restore_material_planning_reservations(doc)
	_restore_batch_sec_qty(doc)

	# Cut Sheet: the stock is back, so the batch must stop advertising the offcut's
	# dimensions. Runs after _restore_batch_sec_qty, which would otherwise overwrite
	# the Sec Qty this puts back.
	_restore_cut_sheet_batches(doc)
	_apply_cut_sheet_w2(doc, cancelling=True)

	# Recalculate transferred weight on SCO if a relevant SE is cancelled
	if doc.stock_entry_type == "Send to Subcontractor" and doc.get("custom_sco_ref"):
		_update_sco_transferred_weight(doc.custom_sco_ref)
		_refresh_linked_mip_weight(sco_ref=doc.custom_sco_ref)

	if doc.stock_entry_type == "Material Transfer" and doc.get("custom_sco_ref"):
		_update_sco_transferred_weight(doc.custom_sco_ref)
		_update_sco_cnc_weight(doc.custom_sco_ref)
		_refresh_linked_mip_weight(sco_ref=doc.custom_sco_ref)

	# SHARED_SCO_JC: WO cancel mirrors SCO cancel above.
	if doc.stock_entry_type == "Material Transfer" and doc.get("custom_wo_ref"):
		_update_wo_transferred_weight(doc.custom_wo_ref)
		_update_wo_cnc_weight(doc.custom_wo_ref)
		_refresh_linked_mip_weight(wo_ref=doc.custom_wo_ref)


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
	if doc.stock_entry_type not in RESERVATION_RELEASING_SE_TYPES:
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

	# Fallback (no Production Plan link): batch-wide restore across BOTH tables, mirroring
	# the release fallback exactly -- releasing on submit without restoring on cancel
	# would strand the reservation.
	for child_dt, batch_field, qty_field in (
		("Material Planning Material Mapping", "batch", "qty"),
		("Material Planning Available Raw Material", "batch_no", "required_qty"),
	):
		for r in frappe.get_all(
			child_dt,
			filters={batch_field: ["in", list(consumed_batches)], "is_reserved": 0},
			fields=["name", qty_field],
		):
			_reserve(child_dt, r.name, r.get(qty_field))


def _update_sco_transferred_weight(sco_name):
	"""Recompute SCO.custom_transferred_weight_kg:
	  - qty from submitted 'Send to Subcontractor' SEs to the supplier/WIP warehouse, PLUS
	  - qty from submitted 'Material Transfer' SEs that go CNC warehouse → supplier/WIP warehouse.
	Also refreshes Op-1 SOE's available_to_consume_kg if it is still in draft.

	supplier_warehouse resolution mirrors get_target_context/_resolve_warehouses in
	material_issue_plan.py: the Material Issue Plan's own field takes priority (it is
	what the transfer itself was actually resolved against), falling back to the SCO's
	core field for a Supplier Job/Supplier with Material flow. An Internal Job SCO has
	no Job Worker, so its supplier_warehouse never auto-sets (see
	CustomSubcontractingOrder._auto_set_supplier_warehouse) -- if BOTH are still blank
	(e.g. the user hasn't set MIP's Supplier / WIP Warehouse either), fall back further
	to matching on qty transferred out of the known source warehouse instead of into an
	unknown destination -- 'Send to Subcontractor'/'Material Transfer' Stock Entries
	tagged with this SCO's own custom_sco_ref are never used for anything else, so this
	is unambiguous even without a recorded destination warehouse."""
	mip = frappe.db.get_value(
		"Material Issue Plan", {"subcontracting_order": sco_name},
		["supplier_warehouse", "source_warehouse", "cnc_warehouse"], as_dict=True,
	)
	sco_supplier_warehouse = frappe.db.get_value("Subcontracting Order", sco_name, "supplier_warehouse")
	supplier_warehouse = (mip.supplier_warehouse if mip else "") or sco_supplier_warehouse
	cnc_warehouse = mip.cnc_warehouse if mip else None

	if supplier_warehouse:
		# Direct source → supplier/WIP transfers, matched on the known destination.
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
	else:
		# No destination warehouse recorded anywhere (Internal Job, WIP warehouse never
		# set) -- fall back to unfiltered qty for this SCO's own Send to Subcontractor
		# entries, safe since that entry type + ref combination is exclusive to this
		# transfer.
		r1 = frappe.db.sql(
			"""
			SELECT COALESCE(SUM(sed.qty), 0)
			FROM `tabStock Entry Detail` sed
			JOIN `tabStock Entry` se ON se.name = sed.parent
			WHERE se.custom_sco_ref = %s
			  AND se.stock_entry_type = 'Send to Subcontractor'
			  AND se.docstatus = 1
			""",
			(sco_name,),
		)
	direct_qty = flt(r1[0][0]) if r1 and r1[0][0] else 0

	# CNC warehouse → supplier/WIP warehouse transfers
	cnc_to_supplier_qty = 0.0
	if cnc_warehouse and supplier_warehouse:
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
	elif cnc_warehouse:
		r2 = frappe.db.sql(
			"""
			SELECT COALESCE(SUM(sed.qty), 0)
			FROM `tabStock Entry Detail` sed
			JOIN `tabStock Entry` se ON se.name = sed.parent
			WHERE se.custom_sco_ref = %s
			  AND se.stock_entry_type = 'Material Transfer'
			  AND se.docstatus = 1
			  AND sed.s_warehouse = %s
			""",
			(sco_name, cnc_warehouse),
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

	from manufyxinvenzaerp.subcontracting_management.subcontracting import (
		_refresh_sco_drawing_transferred_weights,
	)
	_refresh_sco_drawing_transferred_weights(frappe.get_doc("Subcontracting Order", sco_name))


def _update_sco_cnc_weight(sco_name):
	"""Recompute SCO.custom_cnc_transferred_weight_kg:
	  net qty currently in the CNC warehouse = sent to CNC minus already forwarded to supplier.
	"""
	from manufyxinvenzaerp.subcontracting_management.subcontracting import _get_sco_transfer_warehouses

	supplier_warehouse = frappe.db.get_value("Subcontracting Order", sco_name, "supplier_warehouse")
	_, cnc_warehouse = _get_sco_transfer_warehouses(sco_name)
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

	from manufyxinvenzaerp.subcontracting_management.subcontracting import (
		_refresh_wo_drawing_transferred_weights,
	)
	_refresh_wo_drawing_transferred_weights(frappe.get_doc("Work Order", wo_name))


def _update_wo_cnc_weight(wo_name):
	"""Recompute WO.custom_cnc_transferred_weight_kg:
	net qty currently in CNC warehouse = sent to CNC minus already forwarded to WIP.
	# SHARED_SCO_JC: mirrors _update_sco_cnc_weight
	"""
	from manufyxinvenzaerp.subcontracting_management.subcontracting import _get_wo_transfer_warehouses

	_, cnc_warehouse = _get_wo_transfer_warehouses(wo_name)
	wip_warehouse = frappe.db.get_value("Work Order", wo_name, "wip_warehouse")
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
