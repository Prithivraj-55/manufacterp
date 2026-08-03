import frappe
from frappe.model.document import Document
from frappe.utils import flt


class MaterialPlanningConsolidateItem(Document):
	pass


def recalculate(row):
	"""Purchase Kg from Length/Width/Thickness/Sec Qty, and the Required-vs-Purchase
	difference. Reuses the same Structurals/Plates/Nuts-and-Bolts formula as
	Material Planning's own _calc_batch_qty (material_planning.py) rather than
	reimplementing it.

	When an Alternate Item is set on the row, Length/Width/Thickness/Sec Qty are
	reinterpreted as describing THAT item instead of the original (no separate
	alternate_length/width/thickness/sec_qty fields) — only the group (for which
	dimensions apply) and unit weight need to come from the alternate item."""
	from manufyxinvenzaerp.production_management.doctype.material_planning.material_planning import (
		_calc_batch_qty,
	)

	if row.alternate_item:
		group, unit_weight = row.alternate_parent_item_group, row.alternate_unit_weight
	else:
		group, unit_weight = row.parent_item_group, row.unit_weight

	row.purchase_kg = _calc_batch_qty(
		group, row.length, row.width, row.thickness, row.sec_qty, unit_weight
	)
	row.difference_kg = flt(flt(row.required_kg) - flt(row.purchase_kg), 3)
