import json
import unittest
from unittest.mock import patch

import frappe

from manufyxinvenzaerp.production_management.doctype.material_planning.material_planning import (
    move_to_exact_match,
)

_WAREHOUSE = "Stores - M"

_UNAVAILABLE = [
    {
        "item_code": "ITEM-HAS-MATCH", "item_name": "Has Match", "qty": 10,
        "length": 100, "width": 50, "thickness": 5,
        "uom": "Kg", "sec_qty": 0, "sec_uom": "", "parent_item_group": "",
        "unit_weight": 0, "bom_no": "", "duno_mark_no": 0, "alternate_item": "",
    },
    {
        "item_code": "ITEM-NO-MATCH", "item_name": "No Match", "qty": 20,
        "length": 200, "width": 100, "thickness": 10,
        "uom": "Kg", "sec_qty": 0, "sec_uom": "", "parent_item_group": "",
        "unit_weight": 0, "bom_no": "", "duno_mark_no": 0, "alternate_item": "",
    },
]


def _mock_sbb(item_code, warehouse, dimensions):
    if item_code == "ITEM-HAS-MATCH":
        return 15.0, [{"batch_no": "BATCH-X", "qty": 15.0, "custom_sec_qty": 0, "custom_sec_uom": ""}]
    return 0.0, []


_DOC = frappe._dict({"for_warehouse": _WAREHOUSE, "unavailable_items": _UNAVAILABLE})


class TestUnavailableActions(unittest.TestCase):

    # UA1 — Item with exact match: appears in matched, not in failed
    def test_ua1_item_with_exact_match(self):
        with patch(
            "manufyxinvenzaerp.production_plan_management.production_plan.get_sbb_available_qty",
            side_effect=_mock_sbb,
        ):
            result = move_to_exact_match(_DOC, json.dumps(["ITEM-HAS-MATCH"]))

        self.assertEqual(len(result["matched"]), 1)
        self.assertEqual(result["matched"][0]["item_code"], "ITEM-HAS-MATCH")
        self.assertEqual(result["matched"][0]["batch_no"], "BATCH-X")
        self.assertEqual(result["failed"], [])

    # UA2 — Item with no exact match: appears in failed, not in matched
    def test_ua2_item_with_no_exact_match(self):
        with patch(
            "manufyxinvenzaerp.production_plan_management.production_plan.get_sbb_available_qty",
            side_effect=_mock_sbb,
        ):
            result = move_to_exact_match(_DOC, json.dumps(["ITEM-NO-MATCH"]))

        self.assertEqual(result["matched"], [])
        self.assertIn("ITEM-NO-MATCH", result["failed"])

    # UA3 — Mixed selection: one matched, one failed
    def test_ua3_mixed_selection(self):
        with patch(
            "manufyxinvenzaerp.production_plan_management.production_plan.get_sbb_available_qty",
            side_effect=_mock_sbb,
        ):
            result = move_to_exact_match(
                _DOC, json.dumps(["ITEM-HAS-MATCH", "ITEM-NO-MATCH"])
            )

        matched_codes = [r["item_code"] for r in result["matched"]]
        self.assertIn("ITEM-HAS-MATCH", matched_codes)
        self.assertIn("ITEM-NO-MATCH", result["failed"])

    # UA4 — Item not in unavailable_items list is silently ignored
    def test_ua4_item_not_in_unavailable_ignored(self):
        with patch(
            "manufyxinvenzaerp.production_plan_management.production_plan.get_sbb_available_qty",
            side_effect=_mock_sbb,
        ):
            result = move_to_exact_match(_DOC, json.dumps(["GHOST-ITEM"]))

        self.assertEqual(result["matched"], [])
        self.assertEqual(result["failed"], [])

    # UA5 — No warehouse set → throws
    def test_ua5_no_warehouse_throws(self):
        doc_no_wh = frappe._dict({"for_warehouse": "", "unavailable_items": _UNAVAILABLE})
        with self.assertRaises(frappe.exceptions.ValidationError):
            move_to_exact_match(doc_no_wh, json.dumps(["ITEM-HAS-MATCH"]))

    # UA6 — Matched row carries correct T2 fields (warehouse, batch_no, required_qty, available_qty)
    def test_ua6_matched_row_fields(self):
        with patch(
            "manufyxinvenzaerp.production_plan_management.production_plan.get_sbb_available_qty",
            side_effect=_mock_sbb,
        ):
            result = move_to_exact_match(_DOC, json.dumps(["ITEM-HAS-MATCH"]))

        row = result["matched"][0]
        self.assertEqual(row["warehouse"], _WAREHOUSE)
        self.assertEqual(row["batch_no"], "BATCH-X")
        self.assertEqual(row["required_qty"], 10)
        self.assertEqual(row["available_qty"], 15.0)
        self.assertEqual(row["length"], 100)
        self.assertEqual(row["width"], 50)
        self.assertEqual(row["thickness"], 5)

    # UA7 — Empty selection returns empty matched and failed
    def test_ua7_empty_selection(self):
        with patch(
            "manufyxinvenzaerp.production_plan_management.production_plan.get_sbb_available_qty",
            side_effect=_mock_sbb,
        ):
            result = move_to_exact_match(_DOC, json.dumps([]))

        self.assertEqual(result["matched"], [])
        self.assertEqual(result["failed"], [])
