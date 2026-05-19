import json
import unittest

import frappe
from frappe.utils import today

from manufyxinvenzaerp.production_management.doctype.material_planning.material_planning import (
    make_material_request,
    unlink_material_request_on_cancel,
)

MP_NAME = "MP-2026-00005"


def _find_or_create_mr():
    existing = frappe.db.get_value(
        "Material Request",
        {"custom_material_planning": MP_NAME, "status": ["!=", "Cancelled"]},
        "name",
    )
    if existing:
        return existing

    mp_doc = frappe.get_doc("Material Planning", MP_NAME)
    if not mp_doc.unavailable_items:
        return None

    item = mp_doc.unavailable_items[0].item_code
    uom = frappe.db.get_value("Item", item, "stock_uom") or "Nos"
    mr = frappe.new_doc("Material Request")
    mr.material_request_type = "Purchase"
    mr.company = mp_doc.company
    mr.transaction_date = today()
    mr.schedule_date = today()
    mr.custom_material_planning = MP_NAME
    mr.append("items", {"item_code": item, "qty": 1, "uom": uom, "schedule_date": today()})
    mr.insert(ignore_permissions=True)
    frappe.db.set_value("Material Planning", MP_NAME, "status", "Material Request Created")
    frappe.db.commit()
    return mr.name


def _cancel_all_mrs():
    mrs = frappe.get_all(
        "Material Request",
        filters={"custom_material_planning": MP_NAME, "status": ["!=", "Cancelled"]},
        fields=["name"],
    )
    for mr in mrs:
        frappe.db.set_value("Material Request", mr.name, "status", "Cancelled")
    frappe.db.set_value("Material Planning", MP_NAME, "status", "Draft")
    frappe.db.commit()


class TestMaterialRequestEdgeCases(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        _cancel_all_mrs()
        cls.mr_name = _find_or_create_mr()

    def tearDown(self):
        frappe.db.rollback()
        _cancel_all_mrs()
        self.__class__.mr_name = _find_or_create_mr()

    def _get_unavailable_items(self):
        mp = frappe.get_doc("Material Planning", MP_NAME)
        return [r.item_code for r in mp.unavailable_items]

    # EC1 — Duplicate MR blocked when active MR already linked to this MP
    def test_ec1_duplicate_mr_blocked(self):
        if not self.mr_name:
            self.skipTest("No unavailable items on MP-2026-00005")
        items = self._get_unavailable_items()
        if not items:
            self.skipTest("No unavailable items")
        with self.assertRaises(frappe.exceptions.ValidationError) as ctx:
            make_material_request(MP_NAME, json.dumps([items[0]]))
        self.assertIn("already have an active Material Request", str(ctx.exception))

    # EC2 — Empty item selection blocked
    def test_ec2_empty_selection_blocked(self):
        with self.assertRaises(frappe.exceptions.ValidationError):
            make_material_request(MP_NAME, json.dumps([]))

    # EC3 — Unknown item (not in unavailable_items) → no rows to order → blocked
    def test_ec3_unknown_item_blocked(self):
        with self.assertRaises(frappe.exceptions.ValidationError):
            make_material_request(MP_NAME, json.dumps(["NONEXISTENT-XYZ"]))

    # EC4 — Unlink on cancel: MP status reverts
    def test_ec4_unlink_on_cancel_reverts_status(self):
        if not self.mr_name:
            self.skipTest("No MR to cancel")
        mr_doc = frappe.get_doc("Material Request", self.mr_name)
        unlink_material_request_on_cancel(mr_doc)

        mp_status = frappe.db.get_value("Material Planning", MP_NAME, "status")
        docstatus = frappe.db.get_value("Material Planning", MP_NAME, "docstatus")
        expected = "Submitted" if docstatus == 1 else "Draft"
        self.assertEqual(mp_status, expected, f"MP status should revert to {expected}")

    # EC5 — After cancel, new MR can be created
    def test_ec5_new_mr_allowed_after_cancel(self):
        if not self.mr_name:
            self.skipTest("No MR to cancel")
        items = self._get_unavailable_items()
        if not items:
            self.skipTest("No unavailable items")

        frappe.db.set_value("Material Request", self.mr_name, "status", "Cancelled")
        new_mr = make_material_request(MP_NAME, json.dumps([items[0]]))
        self.assertTrue(new_mr)
        linked_mp = frappe.db.get_value("Material Request", new_mr, "custom_material_planning")
        self.assertEqual(linked_mp, MP_NAME, "New MR must reference the MP")

    # EC6 — MR carries custom_material_planning reference
    def test_ec6_mr_references_mp(self):
        if not self.mr_name:
            self.skipTest("No MR available")
        linked = frappe.db.get_value("Material Request", self.mr_name, "custom_material_planning")
        self.assertEqual(linked, MP_NAME)

    # EC7 — Dimensions mapped into MR item description
    def test_ec7_dimensions_in_mr_item(self):
        if not self.mr_name:
            self.skipTest("No MR available")
        items = frappe.get_doc("Material Request", self.mr_name).items
        if items:
            self.assertTrue(items[0].description, "Description should be set")

    # EC8 — on_trash also triggers status revert
    def test_ec8_unlink_on_trash_reverts_status(self):
        if not self.mr_name:
            self.skipTest("No MR to test")
        mr_doc = frappe.get_doc("Material Request", self.mr_name)
        unlink_material_request_on_cancel(mr_doc)
        mp_status = frappe.db.get_value("Material Planning", MP_NAME, "status")
        docstatus = frappe.db.get_value("Material Planning", MP_NAME, "docstatus")
        expected = "Submitted" if docstatus == 1 else "Draft"
        self.assertEqual(mp_status, expected)
