# api — manufyxinvenzaerp

_Generated: 2026-08-12 23:32:34_

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
## production_management/doctype/cut_sheet/cut_sheet.py

| Method | Line |
|--------|------|
| `suggest_w1_sec_qty` | 183 |
| `get_available_cut_sheets` | 224 |
| `get_cut_sheet_for_batch` | 248 |
| `allocate_cut_sheet` | 282 |
## production_management/doctype/material_planning/material_planning.py

| Method | Line |
|--------|------|
| `move_to_exact_match` | 1342 |
| `update_exact_match_from_consolidate` | 1505 |
| `finalize_mapping` | 1726 |
| `verify_raw_materials` | 1953 |
| `get_batch_reservation_summary` | 1969 |
| `get_batch_item` | 2005 |
| `get_batch_stock_summary` | 2013 |
| `get_batch_cross_table_usage` | 2251 |
| `validate_planned_stock` | 2383 |
| `reserve_batches` | 2494 |
| `get_available_excess_batches` | 2652 |
| `add_excess_material_mapping` | 2718 |
| `get_available_virtual_excess_items` | 2813 |
| `claim_virtual_excess_mapping` | 2924 |
| `reserve_exact_match_batches` | 3136 |
| `unreserve_exact_match_batches` | 3270 |
| `check_mapping_batch_availability` | 3312 |
| `unreserve_batches` | 3373 |
| `reassign_batch` | 3529 |
| `_test_simulate_se_release` | 3758 |
| `make_production_plan` | 3777 |
| `make_material_request` | 3836 |
| `make_material_request_from_consolidate` | 3990 |
| `update_so_difference_kg` | 4128 |
| `auto_purchase_from_mp` | 4158 |
| `complete_batch_mapping` | 4332 |
| `@frappe.validate_and_sanitize_search_inputs` | 701 |
| `get_bom_info` | 727 |
| `get_so_drawings_for_bom_picker` | 779 |
| `get_raw_materials` | 886 |
| `check_stock_availability` | 989 |
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
| `allocate_pr_stock_to_mp` | 359 |
| `get_pr_mp_allocations` | 844 |
## sq_management/supplier_quotation.py

| Method | Line |
|--------|------|
| `get_sq_item_uom` | 19 |
## subcontracting_management/doctype/material_issue_plan/material_issue_plan.py

| Method | Line |
|--------|------|
| `get_mip_batch_plan_html` | 1148 |
| `download_mip_batch_plan_pdf` | 1154 |
| `check_mip_raw_materials_refreshable` | 203 |
| `refresh_mip_raw_materials_manual` | 217 |
| `refresh_mip_raw_materials` | 237 |
| `create_from_subcontracting_order` | 48 |
| `unlink_excess_claim` | 637 |
| `create_from_work_order` | 67 |
| `populate_from_production_plan` | 86 |
| `refresh_weight_summary` | 954 |
## subcontracting_management/material_issue_plan_transfer.py

| Method | Line |
|--------|------|
| `create_mip_cnc_forward_entry` | 1062 |
| `create_mip_excess_return_entry` | 1135 |
| `get_mip_pending_items` | 220 |
| `update_transfer_sec_qty` | 376 |
| `has_cnc_stock` | 554 |
| `get_mip_readiness_check` | 606 |
| `create_mip_transfer_entry` | 764 |
| `create_mip_partial_transfer` | 812 |
| `get_mip_cnc_pending_items` | 883 |
| `create_mip_cnc_partial_forward` | 940 |
## subcontracting_management/subcontracting.py

| Method | Line |
|--------|------|
| `create_sco_and_mip_from_production_plan` | 189 |
| `backfill_drawing_item_qty` | 2117 |
| `delete_sco_and_mip_for_production_plan` | 214 |
| `get_wo_pending_items` | 2202 |
| `create_partial_wo_transfer` | 2307 |
| `create_cnc_to_wip_entry` | 2363 |
| `create_return_stock_entry_for_wo` | 2462 |
| `get_jc_summary` | 2514 |
| `create_sco_from_production_plan` | 26 |
| `create_work_order_from_pp` | 294 |
| `create_supplier_operation_entries` | 454 |
| `create_send_to_subcontractor_entry` | 474 |
| `get_sco_pending_items` | 570 |
| `create_partial_transfer` | 680 |
| `create_cnc_to_supplier_entry` | 741 |
| `get_soe_summary` | 844 |
| `create_return_stock_entry` | 890 |
| `create_finished_goods_entry` | 948 |

## Total

_116 whitelisted methods_
