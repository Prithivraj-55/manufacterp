# api — manufyxinvenzaerp

_Generated: 2026-05-28 18:06:28_

All `@frappe.whitelist()` methods. Call from JS:
`frappe.call({ method: 'manufyxinvenzaerp.<dotted.path>', args: {...} })`

## drawing_management/bom_class_override.py

| Method | Line |
|--------|------|
| `get_bom_items` | 1255 |
| `get_children` | 1288 |
| `get_bom_diff` | 1467 |
| `@frappe.validate_and_sanitize_search_inputs` | 1522 |
| `make_variant_bom` | 1574 |
| `get_routing` | 353 |
| `get_bom_material_detail` | 424 |
| `update_cost` | 509 |
## drawing_management/doctype/drawing/drawing.py

| Method | Line |
|--------|------|
| `check_existing_bom` | 104 |
## drawing_management/drawing_utils.py

| Method | Line |
|--------|------|
| `create_production_plan_from_bom` | 235 |
| `parse_drawing_items_csv` | 288 |
| `mark_as_final_revision` | 45 |
| `get_batches_for_drawing_item` | 59 |
| `create_drawings_from_so` | 7 |
| `create_bom_from_drawing` | 91 |
## item_management/item.py

| Method | Line |
|--------|------|
| `has_item_transactions` | 125 |
## material_request_management/material_request.py

| Method | Line |
|--------|------|
| `get_mr_item_uom` | 16 |
## production_management/doctype/material_planning/material_planning.py

| Method | Line |
|--------|------|
| `unreserve_exact_match_batches` | 1014 |
| `check_mapping_batch_availability` | 1055 |
| `unreserve_batches` | 1110 |
| `_test_simulate_se_release` | 1151 |
| `make_production_plan` | 1170 |
| `make_material_request` | 1227 |
| `get_raw_materials` | 132 |
| `check_stock_availability` | 248 |
| `move_to_exact_match` | 480 |
| `@frappe.validate_and_sanitize_search_inputs` | 58 |
| `finalize_mapping` | 619 |
| `get_batch_reservation_summary` | 683 |
| `get_batch_item` | 717 |
| `get_batch_stock_summary` | 725 |
| `reserve_batches` | 796 |
| `get_bom_info` | 84 |
| `reserve_exact_match_batches` | 898 |
## production_management/production_utils.py

| Method | Line |
|--------|------|
| `get_raw_materials_for_job_card` | 120 |
| `get_routing_operations_for_bom` | 95 |
## production_plan_management/production_plan.py

| Method | Line |
|--------|------|
| `get_items_for_material_requests` | 115 |
| `make_material_request` | 492 |
## purchase_order_management/purchase_order.py

| Method | Line |
|--------|------|
| `get_po_item_uom` | 16 |
## purchase_receipt_management/purchase_receipt.py

| Method | Line |
|--------|------|
| `get_pr_item_uom` | 18 |
| `get_mp_for_pr` | 252 |
| `allocate_pr_stock_to_mp` | 271 |
## sq_management/supplier_quotation.py

| Method | Line |
|--------|------|
| `get_sq_item_uom` | 27 |
## subcontracting_management/subcontracting.py

| Method | Line |
|--------|------|
| `create_supplier_operation_entries` | 173 |
| `create_sco_from_production_plan` | 26 |
| `create_send_to_subcontractor_entry` | 293 |
| `create_wip_transfer_stock_entry` | 343 |
| `create_return_stock_entry` | 401 |
| `create_work_order_from_pp` | 98 |

## Total

_49 whitelisted methods_
