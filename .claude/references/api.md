# api — manufyxinvenzaerp

_Generated: 2026-06-23 00:48:06_

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
| `check_existing_bom` | 125 |
## drawing_management/drawing_utils.py

| Method | Line |
|--------|------|
| `create_production_plan_from_bom` | 203 |
| `parse_drawing_items_csv` | 256 |
| `mark_as_final_revision` | 45 |
| `get_batches_for_drawing_item` | 59 |
| `create_drawings_from_so` | 7 |
| `create_bom_from_drawing` | 91 |
## drawing_management/so_drawing_import.py

| Method | Line |
|--------|------|
| `parse_bom_excel` | 123 |
| `create_drawings_from_import` | 338 |
| `process_drawings` | 489 |
| `verify_raw_materials` | 619 |
| `download_bom_template` | 677 |
| `clear_drawing_import` | 719 |
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
| `reserve_exact_match_batches` | 1094 |
| `unreserve_exact_match_batches` | 1210 |
| `check_mapping_batch_availability` | 1251 |
| `unreserve_batches` | 1311 |
| `_test_simulate_se_release` | 1352 |
| `make_production_plan` | 1371 |
| `@frappe.validate_and_sanitize_search_inputs` | 141 |
| `make_material_request` | 1429 |
| `update_so_difference_kg` | 1576 |
| `get_bom_info` | 167 |
| `get_so_drawings_for_bom_picker` | 219 |
| `get_raw_materials` | 282 |
| `check_stock_availability` | 367 |
| `move_to_exact_match` | 653 |
| `finalize_mapping` | 810 |
| `get_batch_reservation_summary` | 875 |
| `get_batch_item` | 909 |
| `get_batch_stock_summary` | 917 |
| `reserve_batches` | 988 |
## production_management/production_utils.py

| Method | Line |
|--------|------|
| `get_raw_materials_for_job_card` | 120 |
| `get_routing_operations_for_bom` | 95 |
## production_plan_management/production_plan.py

| Method | Line |
|--------|------|
| `get_items_for_material_requests` | 115 |
| `get_mp_planned_weights` | 492 |
| `get_pp_drawings_for_picker` | 544 |
| `get_operations_from_routing` | 691 |
| `get_standard_routing_operations` | 704 |
| `make_material_request` | 717 |
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
| `create_work_order_from_pp` | 122 |
| `create_supplier_operation_entries` | 192 |
| `create_send_to_subcontractor_entry` | 209 |
| `create_sco_from_production_plan` | 24 |
| `get_soe_summary` | 268 |
| `create_return_stock_entry` | 283 |

## Total

_61 whitelisted methods_
