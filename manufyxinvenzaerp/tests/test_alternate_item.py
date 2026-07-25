import json
import unittest

import frappe
from frappe.utils import today

from manufyxinvenzaerp.production_management.doctype.material_planning.material_planning import (
    make_material_request,
    unlink_material_request_on_cancel,
)

MP_NAME = "MP-2026-00005"


def _get_unavailable_rows():
    return frappe.get_all(
        "Material Planning Unavailable Item",
        filters={"parent": MP_NAME},
        fields=["name", "item_code", "alternate_item"],
    )


def _clear_mr_links():
    # Cancel any active MRs linked to this MP so the duplicate guard doesn't block tests
    active_mrs = frappe.get_all(
        "Material Request",
        filters={"custom_material_planning": MP_NAME, "status": ["not in", ["Cancelled", "Stopped"]]},
        fields=["name"],
    )
    for mr in active_mrs:
        frappe.db.set_value("Material Request", mr.name, "status", "Cancelled")

    # Clear alternate_item on all unavailable rows
    for row in _get_unavailable_rows():
        frappe.db.set_value("Material Planning Unavailable Item", row.name, "alternate_item", None)

    frappe.db.set_value("Material Planning", MP_NAME, "planning_status", "Draft")
    frappe.db.commit()


class TestAlternateItem(unittest.TestCase):

    def setUp(self):
        _clear_mr_links()

    def tearDown(self):
        frappe.db.rollback()
        _clear_mr_links()

    def _set_alternate(self, item_code, alternate):
        row = frappe.db.get_value(
            "Material Planning Unavailable Item",
            {"parent": MP_NAME, "item_code": item_code},
            "name",
        )
        if row:
            frappe.db.set_value("Material Planning Unavailable Item", row, "alternate_item", alternate)
            frappe.db.commit()

    # AI1 — No alternate: original item goes into MR
    def test_ai1_no_alternate_uses_original_item(self):
        rows = _get_unavailable_rows()
        if not rows:
            self.skipTest("No unavailable items on MP-2026-00005")

        target = rows[0].item_code
        mr_name = make_material_request(MP_NAME, json.dumps([target]))
        mr = frappe.get_doc("Material Request", mr_name)

        codes = [i.item_code for i in mr.items]
        self.assertIn(target, codes, "Original item should be in MR when no alternate set")

    # AI2 — Alternate set: alternate item goes into MR, not original
    def test_ai2_alternate_item_used_in_mr(self):
        rows = _get_unavailable_rows()
        if not rows:
            self.skipTest("No unavailable items on MP-2026-00005")

        # Find an item we can use as alternate (any different item in DB)
        target_row = rows[0]
        alt_item = frappe.db.get_value(
            "Item", {"name": ["!=", target_row.item_code], "disabled": 0}, "name"
        )
        if not alt_item:
            self.skipTest("No alternate item available in DB")

        self._set_alternate(target_row.item_code, alt_item)

        mr_name = make_material_request(MP_NAME, json.dumps([target_row.item_code]))
        mr = frappe.get_doc("Material Request", mr_name)

        codes = [i.item_code for i in mr.items]
        self.assertIn(alt_item, codes, "Alternate item should be in MR")
        self.assertNotIn(target_row.item_code, codes, "Original item should NOT be in MR when alternate set")

    # AI3 — Alternate set: description mentions original item code for traceability
    def test_ai3_description_mentions_original_item(self):
        rows = _get_unavailable_rows()
        if not rows:
            self.skipTest("No unavailable items on MP-2026-00005")

        target_row = rows[0]
        alt_item = frappe.db.get_value(
            "Item", {"name": ["!=", target_row.item_code], "disabled": 0}, "name"
        )
        if not alt_item:
            self.skipTest("No alternate item available in DB")

        self._set_alternate(target_row.item_code, alt_item)

        mr_name = make_material_request(MP_NAME, json.dumps([target_row.item_code]))
        mr = frappe.get_doc("Material Request", mr_name)

        alt_row = next(i for i in mr.items if i.item_code == alt_item)
        self.assertIn(target_row.item_code, alt_row.description,
                      "Description should reference original item code")

    # AI4 — Mixed: some with alternate, some without
    def test_ai4_mixed_alternate_and_original(self):
        rows = _get_unavailable_rows()
        if len(rows) < 2:
            self.skipTest("Need at least 2 unavailable items for this test")

        row_with_alt = rows[0]
        row_without_alt = rows[1]

        alt_item = frappe.db.get_value(
            "Item",
            {"name": ["not in", [row_with_alt.item_code, row_without_alt.item_code]], "disabled": 0},
            "name",
        )
        if not alt_item:
            self.skipTest("No alternate item available")

        self._set_alternate(row_with_alt.item_code, alt_item)

        mr_name = make_material_request(
            MP_NAME,
            json.dumps([row_with_alt.item_code, row_without_alt.item_code])
        )
        mr = frappe.get_doc("Material Request", mr_name)
        codes = [i.item_code for i in mr.items]

        self.assertIn(alt_item, codes, "Row with alternate: alternate should be in MR")
        self.assertNotIn(row_with_alt.item_code, codes, "Row with alternate: original should NOT be in MR")
        self.assertIn(row_without_alt.item_code, codes, "Row without alternate: original should be in MR")

    # AI5 — UOM is taken from alternate item, not original
    def test_ai5_uom_from_alternate_item(self):
        rows = _get_unavailable_rows()
        if not rows:
            self.skipTest("No unavailable items")

        target_row = rows[0]
        alt_item = frappe.db.get_value(
            "Item", {"name": ["!=", target_row.item_code], "disabled": 0}, "name"
        )
        if not alt_item:
            self.skipTest("No alternate item available")

        self._set_alternate(target_row.item_code, alt_item)

        mr_name = make_material_request(MP_NAME, json.dumps([target_row.item_code]))
        mr = frappe.get_doc("Material Request", mr_name)

        alt_row = next(i for i in mr.items if i.item_code == alt_item)
        expected_uom = frappe.db.get_value("Item", alt_item, "stock_uom") or "Nos"
        self.assertEqual(alt_row.uom, expected_uom, "UOM should come from alternate item's stock_uom")

    # AI6 — Duplicate MR blocked even when alternate item is set
    def test_ai6_duplicate_blocked_with_alternate(self):
        rows = _get_unavailable_rows()
        if not rows:
            self.skipTest("No unavailable items")

        target = rows[0].item_code
        alt_item = frappe.db.get_value(
            "Item", {"name": ["!=", target], "disabled": 0}, "name"
        )
        if alt_item:
            self._set_alternate(target, alt_item)

        # First MR succeeds
        make_material_request(MP_NAME, json.dumps([target]))

        # Second MR should be blocked
        with self.assertRaises(frappe.exceptions.ValidationError):
            make_material_request(MP_NAME, json.dumps([target]))

    # AI7 — MP name is stored on the MR (custom_material_planning field)
    def test_ai7_mr_references_mp(self):
        rows = _get_unavailable_rows()
        if not rows:
            self.skipTest("No unavailable items")

        target_row = rows[0]
        alt_item = frappe.db.get_value(
            "Item", {"name": ["!=", target_row.item_code], "disabled": 0}, "name"
        )
        if alt_item:
            self._set_alternate(target_row.item_code, alt_item)

        mr_name = make_material_request(MP_NAME, json.dumps([target_row.item_code]))

        linked_mp = frappe.db.get_value("Material Request", mr_name, "custom_material_planning")
        self.assertEqual(linked_mp, MP_NAME,
                         "MR's custom_material_planning should reference the Material Planning")
