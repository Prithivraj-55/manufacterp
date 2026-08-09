# api — manufyxinvenzaerp

_Generated: 2026-08-10 00:31:56_

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
| `update_exact_match_from_consolidate` | 1210 |
| `finalize_mapping` | 1431 |
| `verify_raw_materials` | 1658 |
| `get_batch_reservation_summary` | 1674 |
| `get_batch_item` | 1710 |
| `get_batch_stock_summary` | 1718 |
| `get_batch_cross_table_usage` | 1956 |
| `reserve_batches` | 2143 |
| `get_available_excess_batches` | 2311 |
| `add_excess_material_mapping` | 2377 |
| `get_available_virtual_excess_items` | 2472 |
| `claim_virtual_excess_mapping` | 2572 |
| `reserve_exact_match_batches` | 2701 |
| `unreserve_exact_match_batches` | 2834 |
| `check_mapping_batch_availability` | 2875 |
| `unreserve_batches` | 2941 |
| `reassign_batch` | 3093 |
| `_test_simulate_se_release` | 3327 |
| `make_production_plan` | 3346 |
| `make_material_request` | 3405 |
| `make_material_request_from_consolidate` | 3559 |
| `update_so_difference_kg` | 3697 |
| `auto_purchase_from_mp` | 3727 |
| `complete_batch_mapping` | 3901 |
| `@frappe.validate_and_sanitize_search_inputs` | 406 |
| `get_bom_info` | 432 |
| `get_so_drawings_for_bom_picker` | 484 |
| `get_raw_materials` | 591 |
| `check_stock_availability` | 694 |
## production_management/inspection.py

| Method | Line |
|--------|------|
| `add_inspection_call` | 106 |
| `update_inspection_call_date` | 153 |
| `create_inspection_entry` | 173 |
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
| `get_mp_for_pr` | 257 |
| `allocate_pr_stock_to_mp` | 278 |
| `get_pr_mp_allocations` | 653 |
## sq_management/supplier_quotation.py

| Method | Line |
|--------|------|
| `get_sq_item_uom` | 19 |
## subcontracting_management/doctype/material_issue_plan/material_issue_plan.py

| Method | Line |
|--------|------|
| `check_mip_raw_materials_refreshable` | 184 |
| `refresh_mip_raw_materials_manual` | 198 |
| `refresh_mip_raw_materials` | 218 |
| `create_from_subcontracting_order` | 42 |
| `refresh_weight_summary` | 610 |
| `create_from_work_order` | 61 |
| `get_mip_batch_plan_html` | 792 |
| `download_mip_batch_plan_pdf` | 798 |
| `populate_from_production_plan` | 80 |
## subcontracting_management/material_issue_plan_transfer.py

| Method | Line |
|--------|------|
| `has_cnc_stock` | 330 |
| `get_mip_readiness_check` | 382 |
| `create_mip_transfer_entry` | 479 |
| `create_mip_partial_transfer` | 526 |
| `create_mip_cnc_forward_entry` | 594 |
| `create_mip_excess_return_entry` | 700 |
| `get_mip_pending_items` | 86 |
## subcontracting_management/subcontracting.py

| Method | Line |
|--------|------|
| `create_sco_and_mip_from_production_plan` | 183 |
| `backfill_drawing_item_qty` | 2043 |
| `delete_sco_and_mip_for_production_plan` | 208 |
| `get_wo_pending_items` | 2111 |
| `create_partial_wo_transfer` | 2216 |
| `create_cnc_to_wip_entry` | 2272 |
| `create_return_stock_entry_for_wo` | 2371 |
| `get_jc_summary` | 2423 |
| `create_sco_from_production_plan` | 26 |
| `create_work_order_from_pp` | 288 |
| `create_supplier_operation_entries` | 448 |
| `create_send_to_subcontractor_entry` | 468 |
| `get_sco_pending_items` | 564 |
| `create_partial_transfer` | 674 |
| `create_cnc_to_supplier_entry` | 735 |
| `get_soe_summary` | 838 |
| `create_return_stock_entry` | 884 |
| `create_finished_goods_entry` | 942 |

## Total

_105 whitelisted methods_
