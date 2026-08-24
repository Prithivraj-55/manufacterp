# api — manufyxinvenzaerp

_Generated: 2026-08-25 00:02:28_

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
| `check_existing_bom` | 189 |
## drawing_management/drawing_utils.py

| Method | Line |
|--------|------|
| `create_production_plan_from_bom` | 168 |
| `parse_drawing_items_csv` | 222 |
| `get_batches_for_drawing_item` | 24 |
| `update_customer_provided_weight` | 343 |
| `create_bom_from_drawing` | 56 |
| `mark_as_final_revision` | 10 |
## drawing_management/so_drawing_import.py

| Method | Line |
|--------|------|
| `get_cancelled_drawing_links` | 1021 |
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
| `check_stock_availability` | 1051 |
| `move_to_exact_match` | 1404 |
| `update_exact_match_from_consolidate` | 1567 |
| `finalize_mapping` | 1791 |
| `verify_raw_materials` | 2018 |
| `get_batch_reservation_summary` | 2034 |
| `get_batch_item` | 2070 |
| `get_batch_stock_summary` | 2078 |
| `get_batch_cross_table_usage` | 2316 |
| `validate_planned_stock` | 2448 |
| `reserve_batches` | 2575 |
| `get_available_excess_batches` | 2747 |
| `add_excess_material_mapping` | 2813 |
| `get_available_virtual_excess_items` | 2908 |
| `claim_virtual_excess_mapping` | 3022 |
| `reserve_exact_match_batches` | 3240 |
| `unreserve_exact_match_batches` | 3387 |
| `check_mapping_batch_availability` | 3438 |
| `unreserve_batches` | 3499 |
| `reassign_batch` | 3664 |
| `make_production_plan` | 3926 |
| `make_material_request` | 3997 |
| `make_material_request_from_consolidate` | 4151 |
| `update_so_difference_kg` | 4289 |
| `auto_suggest_consolidate_dimensions` | 4319 |
| `auto_purchase_from_mp` | 4407 |
| `complete_batch_mapping` | 4596 |
| `@frappe.validate_and_sanitize_search_inputs` | 763 |
| `get_bom_info` | 789 |
| `get_so_drawings_for_bom_picker` | 841 |
| `get_raw_materials` | 948 |
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
| `get_mip_batch_plan_html` | 1139 |
| `download_mip_batch_plan_pdf` | 1145 |
| `check_mip_raw_materials_refreshable` | 175 |
| `refresh_mip_raw_materials_manual` | 189 |
| `refresh_mip_raw_materials` | 209 |
| `save_transfer_draft` | 457 |
| `create_from_subcontracting_order` | 50 |
| `get_transfer_draft` | 506 |
| `` | 69 |
| `populate_from_production_plan` | 72 |
| `unlink_excess_claim` | 822 |
| `refresh_weight_summary` | 963 |
## subcontracting_management/material_issue_plan_transfer.py

| Method | Line |
|--------|------|
| `create_mip_transfer_entry` | 1021 |
| `create_mip_partial_transfer` | 1071 |
| `get_mip_cnc_pending_items` | 1149 |
| `create_mip_cnc_partial_forward` | 1206 |
| `create_mip_cnc_forward_entry` | 1328 |
| `create_mip_excess_return_entry` | 1401 |
| `get_mip_pending_items` | 258 |
| `update_transfer_sec_qty` | 450 |
| `has_cnc_stock` | 769 |
| `get_mip_cnc_button_state` | 789 |
| `get_mip_readiness_check` | 863 |
## subcontracting_management/subcontracting.py

| Method | Line |
|--------|------|
| `` | 1640 |
| `` | 1643 |
| `` | 1646 |
| `` | 1649 |
| `` | 1652 |
| `create_sco_and_mip_from_production_plan` | 189 |
| `delete_sco_and_mip_for_production_plan` | 214 |
| `create_sco_from_production_plan` | 26 |
| `` | 294 |
| `create_supplier_operation_entries` | 297 |
| `get_soe_summary` | 319 |
| `create_finished_goods_entry` | 367 |
## tests/test_whitelist_coverage.py

| Method | Line |
|--------|------|
| `            "so pressing the button that calls them answers 'Method Not Allowed':\n    "` | 111 |
| `    found = set` | 40 |
| ``reserve_batches` was swallowed when a helper was inserted directly above it, and` | 4 |

## Total

_119 whitelisted methods_
