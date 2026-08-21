# api — manufyxinvenzaerp

_Generated: 2026-08-21 12:56:31_

All `@frappe.whitelist()` methods. Call from JS:
`frappe.call({ method: 'manufyxinvenzaerp.<dotted.path>', args: {...} })`

## accounts_management/payment_request.py

| Method | Line |
|--------|------|
| `@frappe.validate_and_sanitize_search_inputs` | 28 |
| `get_fund_usage` | 56 |
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
| `parse_bom_excel` | 127 |
| `create_drawings_from_import` | 371 |
| `process_drawings` | 552 |
| `verify_raw_materials` | 820 |
| `download_bom_template` | 931 |
| `clear_drawing_import` | 986 |
## item_management/item.py

| Method | Line |
|--------|------|
| `has_item_transactions` | 125 |
## material_request_management/material_request.py

| Method | Line |
|--------|------|
| `get_mr_item_uom` | 11 |
## permissions_bulk.py

| Method | Line |
|--------|------|
| `apply_permissions` | 144 |
| `get_targets` | 67 |
| `get_role_state` | 92 |
## production_management/doctype/cut_sheet/cut_sheet.py

| Method | Line |
|--------|------|
| `suggest_w1_sec_qty` | 260 |
| `get_available_cut_sheets` | 301 |
| `get_cut_sheet_for_batch` | 325 |
| `allocate_cut_sheet` | 359 |
## production_management/doctype/material_planning/material_planning.py

| Method | Line |
|--------|------|
| `move_to_exact_match` | 1352 |
| `update_exact_match_from_consolidate` | 1515 |
| `finalize_mapping` | 1736 |
| `verify_raw_materials` | 1963 |
| `get_batch_reservation_summary` | 1979 |
| `get_batch_item` | 2015 |
| `get_batch_stock_summary` | 2023 |
| `get_batch_cross_table_usage` | 2261 |
| `validate_planned_stock` | 2393 |
| `_require_write` | 2504 |
| `get_available_excess_batches` | 2692 |
| `add_excess_material_mapping` | 2758 |
| `get_available_virtual_excess_items` | 2853 |
| `claim_virtual_excess_mapping` | 2964 |
| `reserve_exact_match_batches` | 3176 |
| `unreserve_exact_match_batches` | 3323 |
| `check_mapping_batch_availability` | 3374 |
| `unreserve_batches` | 3435 |
| `reassign_batch` | 3600 |
| `_test_simulate_se_release` | 3860 |
| `make_production_plan` | 3879 |
| `make_material_request` | 3950 |
| `make_material_request_from_consolidate` | 4104 |
| `update_so_difference_kg` | 4242 |
| `auto_suggest_consolidate_dimensions` | 4272 |
| `auto_purchase_from_mp` | 4360 |
| `complete_batch_mapping` | 4549 |
| `@frappe.validate_and_sanitize_search_inputs` | 711 |
| `get_bom_info` | 737 |
| `get_so_drawings_for_bom_picker` | 789 |
| `get_raw_materials` | 896 |
| `check_stock_availability` | 999 |
## production_management/inspection.py

| Method | Line |
|--------|------|
| `update_inspection_call_date` | 143 |
| `create_inspection_entry` | 163 |
| `add_inspection_call` | 96 |
## production_management/production_utils.py

| Method | Line |
|--------|------|
| `` | 114 |
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
| `get_mp_for_pr` | 275 |
| `allocate_pr_stock_to_mp` | 377 |
| `get_pr_mp_allocations` | 882 |
## sq_management/supplier_quotation.py

| Method | Line |
|--------|------|
| `get_sq_item_uom` | 19 |
## subcontracting_management/doctype/material_issue_plan/material_issue_plan.py

| Method | Line |
|--------|------|
| `refresh_weight_summary` | 1224 |
| `get_mip_batch_plan_html` | 1400 |
| `download_mip_batch_plan_pdf` | 1406 |
| `check_mip_raw_materials_refreshable` | 192 |
| `refresh_mip_raw_materials_manual` | 206 |
| `refresh_mip_raw_materials` | 226 |
| `save_transfer_draft` | 483 |
| `create_from_subcontracting_order` | 53 |
| `get_transfer_draft` | 532 |
| `` | 72 |
| `populate_from_production_plan` | 75 |
| `unlink_excess_claim` | 863 |
## subcontracting_management/material_issue_plan_transfer.py

| Method | Line |
|--------|------|
| `create_mip_partial_transfer` | 1044 |
| `get_mip_cnc_pending_items` | 1122 |
| `create_mip_cnc_partial_forward` | 1179 |
| `create_mip_cnc_forward_entry` | 1301 |
| `create_mip_excess_return_entry` | 1374 |
| `get_mip_pending_items` | 222 |
| `update_transfer_sec_qty` | 421 |
| `has_cnc_stock` | 742 |
| `get_mip_cnc_button_state` | 762 |
| `get_mip_readiness_check` | 836 |
| `create_mip_transfer_entry` | 994 |
## subcontracting_management/subcontracting.py

| Method | Line |
|--------|------|
| `create_sco_and_mip_from_production_plan` | 189 |
| `backfill_drawing_item_qty` | 1984 |
| `` | 2069 |
| `` | 2072 |
| `` | 2075 |
| `` | 2078 |
| `` | 2081 |
| `delete_sco_and_mip_for_production_plan` | 214 |
| `create_sco_from_production_plan` | 26 |
| `` | 294 |
| `create_supplier_operation_entries` | 297 |
| `create_send_to_subcontractor_entry` | 317 |
| `get_sco_pending_items` | 413 |
| `create_partial_transfer` | 523 |
| `create_cnc_to_supplier_entry` | 584 |
| `get_soe_summary` | 687 |
| `create_return_stock_entry` | 733 |
| `create_finished_goods_entry` | 791 |

## Total

_123 whitelisted methods_
