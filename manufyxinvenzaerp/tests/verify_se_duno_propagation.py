"""Verify Phase 1.3: Sales Order/DU-Mark No/Project propagate onto Stock Entry
Detail, mirroring the existing PO/PR/MR Item custom-field pattern.

Two checks:
  1. Schema: Stock Entry Detail carries custom_drawing/custom_duno_mark_no/
     custom_customer_drawing_number/custom_sales_order (new) and accepts them
     on insert.
  2. Wiring: a Stock Entry created against a Material Request Item (the
     standard "Make Stock Entry from MR" flow) picks up those custom fields
     plus core `project` from the linked MR Item via
     _copy_from_material_request_item(), the same pattern PO/PR already use.

Run via: bench --site manufact execute manufyxinvenzaerp.tests.verify_se_duno_propagation.run
"""

import frappe
from frappe.utils import today
from manufyxinvenzaerp.tests.create_full_test_entry import get_ctx, ensure_item


def run():
    ctx = get_ctx()
    item = ensure_item(ctx, "ZZTEST-SE-DUNO", "SE DUNO Propagation Test Item", uom="Kg")

    existing_project = frappe.db.get_value("Project", {"project_name": "ZZTEST-SE-DUNO-PROJECT"}, "name")
    if existing_project:
        project_name = existing_project
    else:
        project = frappe.get_doc({"doctype": "Project", "project_name": "ZZTEST-SE-DUNO-PROJECT"})
        project.insert(ignore_permissions=True)
        project_name = project.name

    so_name = frappe.db.get_value("Sales Order", {"docstatus": 1}, "name")

    # 1. Schema check: fields exist on Stock Entry Detail meta.
    meta = frappe.get_meta("Stock Entry Detail")
    for fn in ["custom_drawing", "custom_duno_mark_no", "custom_customer_drawing_number", "custom_sales_order"]:
        assert meta.get_field(fn), f"Stock Entry Detail is missing field {fn}"
    print("Schema check passed — all 4 new fields present on Stock Entry Detail.")

    # 2. Wiring check: build a Material Request with a fully-populated reference row,
    # then a Stock Entry whose row links back to that MR Item via material_request_item.
    mr = frappe.new_doc("Material Request")
    mr.material_request_type = "Material Transfer"
    mr.company = ctx.company
    mr.transaction_date = today()
    mr.schedule_date = today()
    mr.append("items", {
        "item_code": item,
        "qty": 10,
        "uom": "Kg",
        "schedule_date": today(),
        "warehouse": ctx.warehouse,
        "custom_drawing": "",
        "custom_duno_mark_no": "DUNO-SE-TEST",
        "custom_customer_drawing_number": "CDN-SE-TEST",
        "custom_sales_order": so_name or "",
        "project": project_name,
    })
    mr.insert(ignore_permissions=True)
    mr.submit()
    print("Created Material Request:", mr.name)
    mr_item_name = mr.items[0].name

    se = frappe.new_doc("Stock Entry")
    se.stock_entry_type = "Material Transfer"
    se.company = ctx.company
    se.append("items", {
        "item_code": item,
        "qty": 10,
        "uom": "Kg",
        "s_warehouse": ctx.warehouse,
        "t_warehouse": ctx.warehouse,
        "material_request": mr.name,
        "material_request_item": mr_item_name,
        "allow_zero_valuation_rate": 1,
    })
    se.insert(ignore_permissions=True)
    row = se.items[0]

    print("SE row custom_duno_mark_no (expect DUNO-SE-TEST):", row.custom_duno_mark_no)
    print("SE row custom_customer_drawing_number (expect CDN-SE-TEST):", row.custom_customer_drawing_number)
    print("SE row custom_sales_order (expect", so_name, "):", row.custom_sales_order)
    print("SE row project (expect", project_name, "):", row.project)

    assert row.custom_duno_mark_no == "DUNO-SE-TEST", "custom_duno_mark_no did not propagate from MR Item"
    assert row.custom_customer_drawing_number == "CDN-SE-TEST", "custom_customer_drawing_number did not propagate"
    if so_name:
        assert row.custom_sales_order == so_name, "custom_sales_order did not propagate"
    assert row.project == project_name, "project did not propagate from MR Item"

    frappe.db.commit()
    print("\nALL CHECKS DONE — Stock Entry Detail correctly inherits SO/DUNO/Project from Material Request Item.")
    print("Test data left in place (not deleted, per standing policy):", mr.name, se.name)
