# Manual one-off debug script (not an automated test) -- run deliberately via
# `bench execute manufyxinvenzaerp.production_management.manual_release_check`
# against a site that actually has MP-2026-00021 / ISMBS-L5000-R001. Renamed
# from test_release.py (it previously matched pytest/unittest's `test_*.py`
# discovery pattern despite living outside tests/ and not being a real test --
# it executes side-effecting code, including a raw frappe.db.commit(), at
# import time), which was crashing `bench run-tests` outright before any real
# test could run, since it references hardcoded document names and a
# stock_entry.py call shape that has since changed. See Phase 1 HP-08 / Phase
# 3 LP-04 in PROJ001 CLAUDE FILES/.
import frappe
from manufyxinvenzaerp.production_management.stock_entry import _release_material_planning_reservations

# Simulate a Manufacture Stock Entry doc consuming batch ISMBS-L5000-R001
class FakeRow:
    def __init__(self, batch_no, finished=False):
        self.batch_no = batch_no
        self.is_finished_item = finished
    def get(self, key, default=None):
        return getattr(self, key, default)

class FakeSE:
    def __init__(self, entry_type, batches):
        self.stock_entry_type = entry_type
        self.items = [FakeRow(b) for b in batches]

# Before state
before = frappe.db.sql(
    "SELECT name, is_reserved FROM `tabMaterial Planning Material Mapping` WHERE parent='MP-2026-00021'",
    as_dict=True
)
print("BEFORE:", {r.name: r.is_reserved for r in before})

# Simulate Manufacture SE consuming ISMBS-L5000-R001
se = FakeSE("Manufacture", ["ISMBS-L5000-R001"])
_release_material_planning_reservations(se)
frappe.db.commit()

after = frappe.db.sql(
    "SELECT name, item_code, batch, is_reserved FROM `tabMaterial Planning Material Mapping` WHERE parent='MP-2026-00021'",
    as_dict=True
)
print("AFTER:", [(r.item_code, r.batch, r.is_reserved) for r in after])
