"""Give every open Material Issue Plan an Excess Return Warehouse.

Returned off-cut used to be received into the plan's Finished Goods Warehouse. It now
goes to the Excess Return Warehouse (client, Oct 2026), so plans made before that field
existed get their Source (RM) warehouse -- the store the material left from -- the same
default a new plan gets. Changeable on the plan or in the return popup."""

import frappe


def execute():
	if not frappe.db.has_column("Material Issue Plan", "excess_material_warehouse"):
		return
	frappe.db.sql(
		"""UPDATE `tabMaterial Issue Plan`
		   SET excess_material_warehouse = source_warehouse
		   WHERE docstatus < 2 AND IFNULL(excess_material_warehouse, '') = ''
		     AND IFNULL(source_warehouse, '') != ''"""
	)
