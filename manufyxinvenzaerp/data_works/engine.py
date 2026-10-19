"""Data Works: reset a site's data for go-live, from the Data Works page.

Three steps, each safe to run twice:
  transactions    delete every transaction and test master; keep the item master and other masters
  warehouses      rename the default warehouse, create the new ones, rebuild Storage Locations
  rate_schedules  replace Job Natures and Rate Schedules with data/rate_schedules.json

What is built comes from data/setup.json and data/rate_schedules.json -- warehouse names are
data, never code. Only a System Manager can open the page, and every button asks for the site name.
This is a one-time tool: remove the page once the live reset is done.
"""

import json
import os
import traceback
from contextlib import contextmanager

import frappe
from frappe.model.delete_doc import delete_dynamic_links
from frappe.utils import now_datetime

STEPS = ("transactions", "warehouses", "rate_schedules")
LABELS = {
	"transactions": "Delete transactions and test data",
	"warehouses": "Create warehouses and storage locations",
	"rate_schedules": "Create rate schedules",
}


# ---------------------------------------------------------------- data and guards

def _data(name):
	with open(os.path.join(os.path.dirname(__file__), "data", name)) as f:
		return json.load(f)


def _guard():
	frappe.only_for("System Manager")


def _status_path():
	return frappe.get_site_path("private", "data_works_status.json")


def _log_path():
	return frappe.get_site_path("private", "data_works.log")


def _log(msg):
	line = f"{now_datetime():%H:%M:%S}  {msg}"
	with open(_log_path(), "a") as f:
		f.write(line + "\n")
	print(line)


def _set_status(state, step=None):
	with open(_status_path(), "w") as f:
		json.dump({"state": state, "step": step, "at": str(now_datetime())}, f)


def _get_status():
	try:
		with open(_status_path()) as f:
			return json.load(f)
	except (OSError, ValueError):
		return {"state": "idle", "step": None}


def _company():
	"""The company of Stock Settings -> Default Warehouse, else the only company."""
	wh = frappe.db.get_single_value("Stock Settings", "default_warehouse")
	company = frappe.db.get_value("Warehouse", wh, "company") if wh else None
	return company or frappe.get_all("Company", pluck="name", limit=1)[0]


def _wh_name(warehouse_name, company):
	return f"{warehouse_name} - {frappe.db.get_value('Company', company, 'abbr')}"


# ---------------------------------------------------------------- whitelisted API

@frappe.whitelist()
def get_state():
	frappe.only_for("System Manager")
	return {
		"site": frappe.local.site,
		"status": _get_status(),
		"steps": [{"step": s, "label": LABELS[s]} for s in STEPS],
	}


@frappe.whitelist()
def preview(step):
	"""What a step would do, as {"title", "lines"} for the confirmation dialog."""
	_guard()
	if step == "all":
		lines = ["A database backup is taken first, then the three steps below run in order."]
		for s in STEPS:
			lines.append(f"-- {LABELS[s]} --")
			lines += _preview_step(s)
		return {"title": "Run everything", "lines": lines}
	return {"title": LABELS[step], "lines": _preview_step(step)}


@frappe.whitelist()
def run(step, confirm_site):
	_guard()
	if confirm_site != frappe.local.site:
		frappe.throw("The site name you typed does not match this site.")
	if step not in STEPS and step not in ("all", "backup"):
		frappe.throw("Unknown step.")
	if _get_status()["state"] == "running":
		frappe.throw("A Data Works step is already running. Watch the log below.")
	_set_status("running", step)
	with open(_log_path(), "w") as f:
		f.write("")
	frappe.enqueue(
		"manufyxinvenzaerp.data_works.engine.run_job",
		queue="long", timeout=7200, step=step, user=frappe.session.user,
	)
	return "queued"


@frappe.whitelist()
def get_log(offset=0):
	frappe.only_for("System Manager")
	try:
		with open(_log_path()) as f:
			lines = f.read().splitlines()
	except OSError:
		lines = []
	offset = int(offset)
	return {"lines": lines[offset:], "next": len(lines), "status": _get_status()}


# ---------------------------------------------------------------- job

def run_job(step, user=None):
	"""Background job (also callable from bench execute). Stops at the first failure."""
	frappe.set_user(user or "Administrator")
	try:
		if step in ("all", "backup"):
			_backup()
		for s in (STEPS if step == "all" else [step] if step in STEPS else []):
			_log(f"=== {LABELS[s]} ===")
			globals()[f"_do_{s}"]()
			frappe.db.commit()
		_log("DONE")
		_set_status("done", step)
	except Exception:
		frappe.db.rollback()
		_log("FAILED\n" + traceback.format_exc())
		_set_status("failed", step)


def _backup():
	from frappe.utils.backups import new_backup

	odb = new_backup(ignore_files=True, force=True)
	_log(f"Backup taken: {odb.backup_path_db}")


# ---------------------------------------------------------------- step 1: transactions

def _table(doctype):
	return frappe.db.exists("DocType", doctype) and frappe.db.table_exists(doctype)


def _test_names():
	"""(doctype, name) of every master whose name starts with a test prefix."""
	prefixes = _data("setup.json")["test_name_prefixes"]
	found = []
	for doctype, field in (("Item", "name"), ("Supplier", "name"), ("Customer", "name"), ("Project", "project_name")):
		if not _table(doctype):
			continue
		for p in prefixes:
			found += [(doctype, n) for n in frappe.get_all(doctype, filters={field: ["like", f"{p}%"]}, pluck="name")]
	return sorted(set(found))


def _preview_step(step):
	cfg = _data("setup.json")
	if step == "transactions":
		lines = []
		for dt in cfg["ledger_doctypes"] + cfg["transaction_doctypes"]:
			if _table(dt) and (n := frappe.db.count(dt)):
				lines.append(f"{dt}: {n} to delete")
		lines += [f"Test {dt}: {n}" for dt, n in _test_names()]
		return lines or ["Nothing to delete."]
	if step == "warehouses":
		company = _company()
		default = frappe.db.get_single_value("Stock Settings", "default_warehouse")
		lines = [f"Rename the default warehouse {default} to {_wh_name(cfg['rename_default_warehouse_to'], company)}"]
		lines += [f"Create warehouse {_wh_name(w, company)} if missing" for w in cfg["create_warehouses"]]
		lines += [f"Delete warehouse {_wh_name(w, company)} if present" for w in cfg["remove_warehouses"]]
		lines.append(f"Delete all {frappe.db.count('Storage Location')} existing Storage Locations")
		for loc in cfg["storage_locations"]:
			lines.append(f"Create {loc['prefix']}{loc['from']} to {loc['prefix']}{loc['to']} in {loc['warehouse']}")
		return lines
	rs = _data("rate_schedules.json")
	return [
		f"Delete {frappe.db.count('Rate Schedule')} Rate Schedules and {frappe.db.count('Job Nature')} Job Natures",
		f"Create {len(rs['job_natures'])} Job Natures and {len(rs['rate_schedules'])} Rate Schedules",
	]


def _series_file():
	return frappe.get_site_path("private", "data_works_series.json")


def _note_series(names):
	"""Remember the naming-series key of every document about to go. A step that fails half way and
	is run again has lost those documents, so the keys are kept on disk until the reset is done."""
	keys = set()
	try:
		with open(_series_file()) as f:
			keys = set(json.load(f))
	except (OSError, ValueError):
		pass
	keys |= {n.rstrip("0123456789") for n in names if n}
	with open(_series_file(), "w") as f:
		json.dump(sorted(keys), f)


def _reset_series():
	"""Naming series restart at 1 once every document of that series is gone."""
	try:
		with open(_series_file()) as f:
			keys = json.load(f)
	except (OSError, ValueError):
		return
	for key in keys:
		if key:
			frappe.db.sql("update `tabSeries` set current = 0 where name = %s", key)
	os.remove(_series_file())


@contextmanager
def _inline_cleanup():
	"""delete_doc queues one background job per document to tidy its comments, versions and
	shares. Hundreds of them overload the queue, so queue nothing here and run the same tidy-up
	inline after each delete."""
	real = frappe.enqueue
	frappe.enqueue = lambda *a, **k: None
	try:
		yield
	finally:
		frappe.enqueue = real


def _delete(dt, name, force=False):
	frappe.delete_doc(
		dt, name, force=force, ignore_permissions=True, ignore_on_trash=force, delete_permanently=force
	)
	delete_dynamic_links(dt, name)


def _do_transactions():
	cfg = _data("setup.json")
	with _inline_cleanup():
		for dt in cfg["ledger_doctypes"]:
			if _table(dt):
				_note_series(frappe.get_all(dt, pluck="name"))
				frappe.db.delete(dt)
				_log(f"{dt}: cleared")
		frappe.db.commit()
		for dt in cfg["transaction_doctypes"]:
			if not _table(dt):
				continue
			docs = frappe.get_all(dt, pluck="name")
			_note_series(docs)
			for n in docs:
				# Frappe will not delete a submitted document; the ledgers are already gone, so
				# marking it cancelled first is all that stands in the way.
				frappe.db.set_value(dt, n, "docstatus", 2, update_modified=False)
				_delete(dt, n, force=True)
			if docs:
				_log(f"{dt}: {len(docs)} deleted")
			# every document of this doctype is gone, so its old 'Deleted' comments and versions are too
			frappe.db.delete("Comment", {"reference_doctype": dt})
			frappe.db.delete("Version", {"ref_doctype": dt})
			frappe.db.commit()

		tests = _test_names()
		_note_series([n for d, n in tests if d == "Project"])
		items = [n for dt, n in tests if dt == "Item"]
		for ip in frappe.get_all("Item Price", filters={"item_code": ["in", items]}, pluck="name"):
			_delete("Item Price", ip)
		for dt in ("Project", "Item", "Supplier", "Customer"):
			for d, n in tests:
				if d == dt:
					_delete(dt, n)
					_log(f"Test {dt} deleted: {n}")
	_reset_series()


# ---------------------------------------------------------------- step 2: warehouses

def _do_warehouses():
	cfg = _data("setup.json")
	company = _company()
	wtype = cfg["warehouse_type"]

	if frappe.db.exists("Warehouse Type", wtype):
		frappe.db.set_value("Warehouse Type", wtype, "custom_storage_location_applicable", 1)
	else:
		frappe.get_doc(
			{"doctype": "Warehouse Type", "name": wtype, "custom_storage_location_applicable": 1}
		).insert(ignore_permissions=True)
		_log(f"Warehouse Type created: {wtype}")

	target = _wh_name(cfg["rename_default_warehouse_to"], company)
	default = frappe.db.get_single_value("Stock Settings", "default_warehouse")
	if frappe.db.exists("Warehouse", target):
		_log(f"{target} already exists")
	elif default:
		frappe.rename_doc("Warehouse", default, target, force=True)
		frappe.db.set_value("Warehouse", target, "warehouse_name", cfg["rename_default_warehouse_to"])
		_log(f"{default} renamed to {target}")
	else:
		frappe.throw("Stock Settings has no Default Warehouse to rename.")
	frappe.db.set_value("Warehouse", target, "warehouse_type", wtype)
	parent = frappe.db.get_value("Warehouse", target, "parent_warehouse")

	for w in cfg["create_warehouses"]:
		name = _wh_name(w, company)
		if not frappe.db.exists("Warehouse", name):
			frappe.get_doc(
				{"doctype": "Warehouse", "warehouse_name": w, "company": company,
				 "parent_warehouse": parent, "warehouse_type": wtype}
			).insert(ignore_permissions=True)
			_log(f"Warehouse created: {name}")
		else:
			frappe.db.set_value("Warehouse", name, "warehouse_type", wtype)

	for w in cfg["remove_warehouses"]:
		name = _wh_name(w, company)
		if frappe.db.exists("Warehouse", name):
			frappe.delete_doc("Warehouse", name, ignore_permissions=True)
			_log(f"Warehouse deleted: {name}")

	for field, w in cfg["company_defaults"].items():
		name = _wh_name(w, company)
		if frappe.db.exists("Warehouse", name):
			frappe.db.set_value("Company", company, field, name)

	for loc in frappe.get_all("Storage Location", pluck="name"):
		frappe.delete_doc("Storage Location", loc, force=True, ignore_permissions=True)
	made = 0
	for loc in cfg["storage_locations"]:
		wh = _wh_name(loc["warehouse"], company)
		for i in range(loc["from"], loc["to"] + 1):
			doc = frappe.get_doc({"doctype": "Storage Location", "warehouse": wh})
			doc.__newname = f"{loc['prefix']}{i}"
			doc.insert(ignore_permissions=True)
			made += 1
	_log(f"Storage Locations created: {made}")


# ---------------------------------------------------------------- step 3: rate schedules

def _do_rate_schedules():
	data = _data("rate_schedules.json")
	for dt in ("Rate Schedule", "Job Nature"):
		for n in frappe.get_all(dt, pluck="name"):
			frappe.delete_doc(dt, n, ignore_permissions=True)
	for jn in data["job_natures"]:
		frappe.get_doc({"doctype": "Job Nature", **jn}).insert(ignore_permissions=True)
	for rs in data["rate_schedules"]:
		frappe.get_doc({"doctype": "Rate Schedule", **rs}).insert(ignore_permissions=True)
	_log(f"Job Natures: {len(data['job_natures'])}, Rate Schedules: {len(data['rate_schedules'])}")
