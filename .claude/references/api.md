# api — manufyxinvenzaerp

_Generated: 2026-08-03 19:57:50_

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
| `check_existing_bom` | 109 |
## drawing_management/drawing_utils.py

| Method | Line |
|--------|------|
| `create_production_plan_from_bom` | 204 |
| `parse_drawing_items_csv` | 258 |
| `update_customer_provided_weight` | 379 |
| `mark_as_final_revision` | 46 |
| `get_batches_for_drawing_item` | 60 |
| `create_drawings_from_so` | 8 |
| `create_bom_from_drawing` | 92 |
## drawing_management/so_drawing_import.py

| Method | Line |
|--------|------|
| `parse_bom_excel` | 119 |
| `create_drawings_from_import` | 334 |
| `process_drawings` | 485 |
| `verify_raw_materials` | 615 |
| `download_bom_template` | 673 |
| `clear_drawing_import` | 715 |
## item_management/item.py

| Method | Line |
|--------|------|
| `has_item_transactions` | 125 |
## material_request_management/material_request.py

| Method | Line |
|--------|------|
| `get_mr_item_uom` | 11 |
## production_management/doctype/material_planning/material_planning.py

| Method | Line |
|--------|------|
| `move_to_exact_match` | 1047 |
| `finalize_mapping` | 1210 |
| `verify_raw_materials` | 1409 |
| `get_batch_reservation_summary` | 1425 |
| `get_batch_item` | 1461 |
| `get_batch_stock_summary` | 1469 |
| `get_batch_cross_table_usage` | 1707 |
| `reserve_batches` | 1894 |
| `get_available_excess_batches` | 2062 |
| `add_excess_material_mapping` | 2128 |
| `reserve_exact_match_batches` | 2222 |
| `unreserve_exact_match_batches` | 2355 |
| `check_mapping_batch_availability` | 2396 |
| `unreserve_batches` | 2462 |
| `reassign_batch` | 2577 |
| `_test_simulate_se_release` | 2807 |
| `make_production_plan` | 2826 |
| `make_material_request` | 2885 |
| `make_material_request_from_consolidate` | 3039 |
| `update_so_difference_kg` | 3177 |
| `auto_purchase_from_mp` | 3207 |
| `complete_batch_mapping` | 3381 |
| `@frappe.validate_and_sanitize_search_inputs` | 406 |
| `get_bom_info` | 432 |
| `get_so_drawings_for_bom_picker` | 484 |
| `get_raw_materials` | 591 |
| `check_stock_availability` | 694 |
## production_management/inspection.py

| Method | Line |
|--------|------|
| `add_inspection_call` | 104 |
| `update_inspection_call_date` | 133 |
| `create_inspection_entry` | 153 |
## production_management/production_utils.py

| Method | Line |
|--------|------|
| `get_raw_materials_for_job_card` | 114 |
| `get_routing_operations_for_bom` | 89 |
## production_plan_management/production_plan.py

| Method | Line |
|--------|------|
| `get_items_for_material_requests` | 284 |
| `get_mp_planned_weights` | 661 |
| `get_pp_drawings_for_picker` | 713 |
| `get_operations_from_routing` | 860 |
| `get_standard_routing_operations` | 873 |
| `make_material_request` | 886 |
## purchase_order_management/purchase_order.py

| Method | Line |
|--------|------|
| `get_po_item_uom` | 10 |
## purchase_receipt_management/purchase_receipt.py

| Method | Line |
|--------|------|
| `get_pr_item_uom` | 16 |
| `get_mp_for_pr` | 252 |
| `allocate_pr_stock_to_mp` | 273 |
| `get_pr_mp_allocations` | 632 |
## sq_management/supplier_quotation.py

| Method | Line |
|--------|------|
| `get_sq_item_uom` | 19 |
## subcontracting_management/doctype/material_issue_plan/material_issue_plan.py

| Method | Line |
|--------|------|
| `refresh_mip_raw_materials` | 160 |
| `create_from_subcontracting_order` | 41 |
| `refresh_weight_summary` | 437 |
| `create_from_work_order` | 60 |
| `populate_from_production_plan` | 79 |
## subcontracting_management/material_issue_plan_transfer.py

| Method | Line |
|--------|------|
| `has_cnc_stock` | 171 |
| `get_mip_readiness_check` | 213 |
| `create_mip_transfer_entry` | 310 |
| `create_mip_partial_transfer` | 355 |
| `create_mip_cnc_forward_entry` | 421 |
| `get_mip_pending_items` | 48 |
| `create_mip_excess_return_entry` | 526 |
## subcontracting_management/subcontracting.py

| Method | Line |
|--------|------|
| `backfill_drawing_item_qty` | 1815 |
| `create_work_order_from_pp` | 183 |
| `get_wo_pending_items` | 1879 |
| `create_partial_wo_transfer` | 1984 |
| `create_cnc_to_wip_entry` | 2040 |
| `create_return_stock_entry_for_wo` | 2139 |
| `get_jc_summary` | 2191 |
| `create_sco_from_production_plan` | 26 |
| `create_supplier_operation_entries` | 343 |
| `create_send_to_subcontractor_entry` | 363 |
| `get_sco_pending_items` | 459 |
| `create_partial_transfer` | 569 |
| `create_cnc_to_supplier_entry` | 630 |
| `get_soe_summary` | 733 |
| `create_return_stock_entry` | 779 |
| `create_finished_goods_entry` | 837 |

## Total

_96 whitelisted methods_
