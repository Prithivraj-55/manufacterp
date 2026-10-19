"""Warehouses for the tests, read from the site's own settings -- never by name.

Warehouse names are site data. On 2026-10-18 Stores was renamed RM Yard and every test
that spelled 'Stores - MIPL' broke at once. Each helper reads one setting and, when it is
blank, fails naming that setting, so a site that is not configured reads as exactly that
rather than as a failing check.
"""

import frappe


def _setting(doctype, fieldname):
	value = frappe.db.get_single_value(doctype, fieldname)
	if not value:
		frappe.throw(f"Set {doctype} → {fieldname} on this site first: the tests take their warehouse from it.")
	return value


def stock_warehouse():
	"""Where raw material is received and planned from: Stock Settings → Default Warehouse."""
	return _setting("Stock Settings", "default_warehouse")


def _company_default(fieldname, company=None):
	company = company or company_of(stock_warehouse())
	value = frappe.db.get_value("Company", company, fieldname)
	if not value:
		frappe.throw(f"Set Company {company} → {fieldname} on this site first: the tests take their warehouse from it.")
	return value


def wip_warehouse(company=None):
	"""Company → Default Work In Progress Warehouse (the stock warehouse's company by default)."""
	return _company_default("default_wip_warehouse", company)


def fg_warehouse(company=None):
	"""Company → Default Finished Goods Warehouse (the stock warehouse's company by default)."""
	return _company_default("default_fg_warehouse", company)


def job_worker_warehouse(company=None):
	"""A warehouse linked to a Job Worker (Warehouse → Job Worker)."""
	filters = {"custom_job_worker": ["is", "set"], "is_group": 0, "disabled": 0}
	if company:
		filters["company"] = company
	name = frappe.db.get_value("Warehouse", filters, "name")
	if not name:
		frappe.throw("No Warehouse on this site has its Job Worker set; the tests need one.")
	return name


def company_of(warehouse):
	return frappe.db.get_value("Warehouse", warehouse, "company")
