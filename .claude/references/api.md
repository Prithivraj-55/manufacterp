# api — manufyxinvenzaerp

_Generated: 2026-06-19 14:49:00_

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
| `reserve_exact_match_batches` | 1041 |
| `unreserve_exact_match_batches` | 1157 |
| `check_mapping_batch_availability` | 1198 |
| `unreserve_batches` | 1258 |
| `_test_simulate_se_release` | 1299 |
| `make_production_plan` | 1318 |
| `make_material_request` | 1376 |
| `@frappe.validate_and_sanitize_search_inputs` | 141 |
| `update_so_difference_kg` | 1510 |
| `get_bom_info` | 167 |
| `get_so_drawings_for_bom_picker` | 219 |
| `get_raw_materials` | 282 |
| `check_stock_availability` | 367 |
| `move_to_exact_match` | 609 |
| `finalize_mapping` | 757 |
| `get_batch_reservation_summary` | 822 |
| `get_batch_item` | 856 |
| `get_batch_stock_summary` | 864 |
| `reserve_batches` | 935 |
## production_management/production_utils.py

| Method | Line |
|--------|------|
| `get_raw_materials_for_job_card` | 120 |
| `get_routing_operations_for_bom` | 95 |
## production_plan_management/production_plan.py

| Method | Line |
|--------|------|
| `get_items_for_material_requests` | 115 |
| `get_pp_drawings_for_picker` | 492 |
| `get_operations_from_routing` | 617 |
| `get_standard_routing_operations` | 630 |
| `make_material_request` | 643 |
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
| `create_work_order_from_pp` | 119 |
| `create_supplier_operation_entries` | 189 |
| `create_sco_from_production_plan` | 24 |
| `create_send_to_subcontractor_entry` | 257 |
| `create_wip_transfer_stock_entry` | 309 |
| `create_return_stock_entry` | 331 |

## Total

_60 whitelisted methods_
