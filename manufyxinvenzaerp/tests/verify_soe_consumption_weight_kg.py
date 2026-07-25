"""Verify Phase 4.4: SOE Consumption Log's Weight (Kg) auto-calc setup --
confirms the linked drawing has usable total_weight/no_of_qty_to_manufacture
data, and reports the expected weight-per-Nos so the browser click-through can
be checked against a known value.

Run via: bench --site manufact execute manufyxinvenzaerp.tests.verify_soe_consumption_weight_kg.run
"""

import frappe
from frappe.utils import flt


def run():
    soe = frappe.get_doc("Supplier Operation Entry", "SCO-SOE-0056")
    print("SOE:", soe.name, "| drawing_details:", len(soe.drawing_details or []))
    for r in soe.drawing_details or []:
        print(" drawing:", r.drawing, "| duno:", r.duno_mark_no)
        d = frappe.db.get_value("Drawing", r.drawing, ["total_weight", "no_of_qty_to_manufacture"], as_dict=True)
        print(" Drawing total_weight:", d.total_weight, "| no_of_qty_to_manufacture:", d.no_of_qty_to_manufacture)
        if flt(d.no_of_qty_to_manufacture):
            weight_per_nos = flt(d.total_weight) / flt(d.no_of_qty_to_manufacture)
            print(" weight per Nos:", weight_per_nos)
            print(" expected weight_kg for qty_nos=2:", flt(weight_per_nos * 2, 3))
        else:
            print(" WARNING: no_of_qty_to_manufacture is 0/blank -- weight_kg calc will yield 0")
