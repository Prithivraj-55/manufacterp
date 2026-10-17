"""Link every existing job worker's warehouse through Warehouse.custom_job_worker.

Job Worker Warehouse used to be found by name -- '<Job Worker> - <Company Abbr>'. It is
now read from the warehouse's Job Worker field (`overrides.resolve_supplier_warehouse`),
so the warehouses made under the old convention are linked once here. This is the only
place the convention is still spelled out, and only to carry the existing data across."""

import json
import os

import frappe
from frappe.modules.utils import sync_customizations_for_doctype


def execute():
	# Patches run before migrate syncs custom/*.json, so put the field in place first.
	folder = frappe.get_app_path("manufyxinvenzaerp", "manufyxinvenzaerp", "custom")
	with open(os.path.join(folder, "warehouse.json")) as f:
		sync_customizations_for_doctype(json.load(f), folder, "warehouse.json")
	suppliers = set(frappe.get_all("Supplier", pluck="name"))
	abbr_by_company = dict(frappe.get_all("Company", fields=["name", "abbr"], as_list=True))
	for wh in frappe.get_all(
		"Warehouse",
		filters={"is_group": 0, "custom_job_worker": ["is", "not set"]},
		fields=["name", "company"],
	):
		suffix = f" - {abbr_by_company.get(wh.company)}"
		if wh.name.endswith(suffix) and wh.name[: -len(suffix)] in suppliers:
			frappe.db.set_value("Warehouse", wh.name, "custom_job_worker", wh.name[: -len(suffix)])
