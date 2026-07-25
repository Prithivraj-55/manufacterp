import frappe
from frappe.model.document import Document
from frappe.utils import flt


class MaterialPlanningConsolidateItem(Document):
	pass


def recalculate(row):
	"""Purchase Kg from Length/Width/Thickness/Sec Qty, and the Required-vs-Purchase
	difference. Reuses the same Structurals/Plates/Nuts-and-Bolts formula as
	Material Planning's own _calc_batch_qty (material_planning.py) rather than
	reimplementing it."""
	from manufyxinvenzaerp.production_management.doctype.material_planning.material_planning import (
		_calc_batch_qty,
	)

	row.purchase_kg = _calc_batch_qty(
		row.parent_item_group, row.length, row.width, row.thickness, row.sec_qty, row.unit_weight
	)
	row.difference_kg = flt(flt(row.required_kg) - flt(row.purchase_kg), 3)
