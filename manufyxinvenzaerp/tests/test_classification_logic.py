import unittest
from unittest.mock import patch

import frappe

from manufyxinvenzaerp.production_management.doctype.material_planning.material_planning import (
    check_stock_availability,
    finalize_mapping,
)

_RAW = [
    {"item_code": "ITEM-A", "item_name": "Item A", "qty": 10, "length": 100,
     "width": 50, "thickness": 5, "uom": "Kg", "sec_qty": 0, "sec_uom": "",
     "parent_item_group": "", "unit_weight": 0, "bom_no": "", "duno_mark_no": 0},
    {"item_code": "ITEM-B", "item_name": "Item B", "qty": 20, "length": 200,
     "width": 100, "thickness": 10, "uom": "Kg", "sec_qty": 0, "sec_uom": "",
     "parent_item_group": "", "unit_weight": 0, "bom_no": "", "duno_mark_no": 0},
    {"item_code": "ITEM-C", "item_name": "Item C", "qty": 5, "length": 300,
     "width": 150, "thickness": 8, "uom": "Nos", "sec_qty": 0, "sec_uom": "",
     "parent_item_group": "", "unit_weight": 0, "bom_no": "", "duno_mark_no": 0},
]


def _mock_sbb_batches_bulk(item_codes, warehouse, location=None):
    """ITEM-A gets an exact-dimension-matching batch; ITEM-B/ITEM-C get none.

    check_stock_availability calls the bulk fetch (get_sbb_batches_bulk), not
    the older per-item get_sbb_available_qty this used to mock -- see
    get_sbb_batches_bulk's own docstring ("Batched variant of
    get_sbb_available_qty", Report 4 Finding D-02) for why the code moved to
    this shape."""
    return {
        "ITEM-A": [{
            "batch_no": "BATCH-001", "qty": 15.0,
            "custom_length": 100, "custom_thickness": 5, "custom_width": 50,
            "custom_sec_qty": 0, "custom_sec_uom": "",
        }],
    }


def _ensure_batch_items():
    # check_stock_availability looks up has_batch_no from real Item records to
    # route each row; without real Items here that lookup finds nothing, so
    # every row falls into the non-batch branch instead of the batch branch
    # this test (and its get_sbb_available_qty mock) is meant to exercise.
    for row in _RAW:
        item_code = row["item_code"]
        if not frappe.db.exists("Item", item_code):
            frappe.get_doc({
                "doctype": "Item",
                "item_code": item_code,
                "item_name": row["item_name"],
                "stock_uom": row["uom"],
                "has_batch_no": 1,
                "is_stock_item": 1,
                "is_sales_item": 0,
            }).insert(ignore_permissions=True, ignore_if_duplicate=True)
    frappe.db.commit()


class TestClassificationLogic(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        _ensure_batch_items()

    # CL1 — Exact match → T2; everything else → T3; T4 empty after Check Stock
    def test_cl1_no_stock_goes_to_mapping_not_unavailable(self):
        doc = frappe._dict({"for_warehouse": "Stores - M", "raw_materials": _RAW})

        with patch(
            "manufyxinvenzaerp.production_plan_management.production_plan.get_sbb_batches_bulk",
            side_effect=_mock_sbb_batches_bulk,
        ):
            result = check_stock_availability(doc)

        self.assertEqual(
            [r["item_code"] for r in result["available_raw_materials"]],
            ["ITEM-A"],
            "Only exact-match item goes to T2",
        )
        mapping_codes = {r["item_code"] for r in result["material_mapping"]}
        self.assertIn("ITEM-B", mapping_codes, "ITEM-B (partial stock) goes to T3")
        self.assertIn("ITEM-C", mapping_codes, "ITEM-C (no stock) also goes to T3")
        self.assertEqual(result["unavailable_items"], [], "T4 is empty after Check Stock")

    # CL2 — Finalize: batch assigned → stays T3, no batch → moves to T4
    def test_cl2_finalize_mapping_splits_correctly(self):
        mapping_doc = frappe._dict({
            "material_mapping": [
                {"item_code": "ITEM-B", "item_name": "Item B", "qty": 20, "uom": "Kg",
                 "batch": "BATCH-002", "planned_item": "ITEM-B", "sec_qty": 0, "sec_uom": "",
                 "parent_item_group": "", "length": 200, "width": 100, "thickness": 10,
                 "unit_weight": 0, "bom_no": "", "duno_mark_no": 0},
                {"item_code": "ITEM-C", "item_name": "Item C", "qty": 5, "uom": "Nos",
                 "batch": "", "planned_item": "", "sec_qty": 0, "sec_uom": "",
                 "parent_item_group": "", "length": 300, "width": 150, "thickness": 8,
                 "unit_weight": 0, "bom_no": "", "duno_mark_no": 0},
            ]
        })

        final = finalize_mapping(mapping_doc)

        self.assertEqual(
            [r["item_code"] for r in final["material_mapping"]], ["ITEM-B"],
            "ITEM-B has batch → stays in T3",
        )
        self.assertEqual(
            [r["item_code"] for r in final["unavailable_items"]], ["ITEM-C"],
            "ITEM-C has no batch → moves to T4",
        )

    # CL3 — All items mapped → T4 empty
    def test_cl3_all_mapped_leaves_unavailable_empty(self):
        mapping_doc = frappe._dict({
            "material_mapping": [
                {"item_code": "ITEM-B", "batch": "BATCH-002", "planned_item": "ITEM-B",
                 "item_name": "B", "qty": 1, "uom": "Kg", "sec_qty": 0, "sec_uom": "",
                 "parent_item_group": "", "length": 0, "width": 0, "thickness": 0,
                 "unit_weight": 0, "bom_no": "", "duno_mark_no": 0},
                {"item_code": "ITEM-C", "batch": "BATCH-003", "planned_item": "ITEM-C",
                 "item_name": "C", "qty": 1, "uom": "Nos", "sec_qty": 0, "sec_uom": "",
                 "parent_item_group": "", "length": 0, "width": 0, "thickness": 0,
                 "unit_weight": 0, "bom_no": "", "duno_mark_no": 0},
            ]
        })

        final = finalize_mapping(mapping_doc)
        self.assertEqual(len(final["material_mapping"]), 2)
        self.assertEqual(final["unavailable_items"], [])

    # CL4 — No items mapped at all → all go to T4
    def test_cl4_none_mapped_all_go_unavailable(self):
        mapping_doc = frappe._dict({
            "material_mapping": [
                {"item_code": "ITEM-B", "batch": "", "planned_item": "",
                 "item_name": "B", "qty": 1, "uom": "Kg", "sec_qty": 0, "sec_uom": "",
                 "parent_item_group": "", "length": 0, "width": 0, "thickness": 0,
                 "unit_weight": 0, "bom_no": "", "duno_mark_no": 0},
                {"item_code": "ITEM-C", "batch": "", "planned_item": "",
                 "item_name": "C", "qty": 1, "uom": "Nos", "sec_qty": 0, "sec_uom": "",
                 "parent_item_group": "", "length": 0, "width": 0, "thickness": 0,
                 "unit_weight": 0, "bom_no": "", "duno_mark_no": 0},
            ]
        })

        final = finalize_mapping(mapping_doc)
        self.assertEqual(final["material_mapping"], [])
        self.assertEqual(len(final["unavailable_items"]), 2)

    # CL5 — Empty material_mapping → both outputs empty
    def test_cl5_empty_mapping_table(self):
        final = finalize_mapping(frappe._dict({"material_mapping": []}))
        self.assertEqual(final["material_mapping"], [])
        self.assertEqual(final["unavailable_items"], [])
