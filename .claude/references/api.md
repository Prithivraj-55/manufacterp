# api — manufyxinvenzaerp

_Generated: 2026-07-05 02:48:09_

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
| `verify_raw_materials` | 1192 |
| `get_batch_reservation_summary` | 1208 |
| `get_batch_item` | 1242 |
| `get_batch_stock_summary` | 1250 |
| `reserve_batches` | 1454 |
| `reserve_exact_match_batches` | 1577 |
| `unreserve_exact_match_batches` | 1694 |
| `check_mapping_batch_availability` | 1735 |
| `unreserve_batches` | 1801 |
| `reassign_batch` | 1842 |
| `_test_simulate_se_release` | 1989 |
| `make_production_plan` | 2008 |
| `make_material_request` | 2066 |
| `update_so_difference_kg` | 2217 |
| `auto_purchase_from_mp` | 2272 |
| `@frappe.validate_and_sanitize_search_inputs` | 270 |
| `get_bom_info` | 296 |
| `get_so_drawings_for_bom_picker` | 348 |
| `get_raw_materials` | 455 |
| `check_stock_availability` | 543 |
| `move_to_exact_match` | 836 |
| `finalize_mapping` | 999 |
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
| `get_po_item_uom` | 17 |
## purchase_receipt_management/purchase_receipt.py

| Method | Line |
|--------|------|
| `get_pr_item_uom` | 19 |
| `get_mp_for_pr` | 268 |
| `allocate_pr_stock_to_mp` | 287 |
## sq_management/supplier_quotation.py

| Method | Line |
|--------|------|
| `get_sq_item_uom` | 27 |
## subcontracting_management/doctype/material_issue_plan/material_issue_plan.py

| Method | Line |
|--------|------|
| `create_from_subcontracting_order` | 17 |
| `refresh_weight_summary` | 185 |
| `populate_from_production_plan` | 36 |
| `refresh_mip_raw_materials` | 96 |
## subcontracting_management/material_issue_plan_transfer.py

| Method | Line |
|--------|------|
| `create_mip_transfer_entry` | 144 |
| `create_mip_partial_transfer` | 183 |
| `create_mip_cnc_forward_entry` | 238 |
| `create_mip_excess_return_entry` | 328 |
| `get_mip_pending_items` | 45 |
## subcontracting_management/subcontracting.py

| Method | Line |
|--------|------|
| `create_work_order_from_pp` | 151 |
| `backfill_drawing_item_qty` | 1705 |
| `get_wo_pending_items` | 1769 |
| `create_partial_wo_transfer` | 1874 |
| `create_cnc_to_wip_entry` | 1930 |
| `create_return_stock_entry_for_wo` | 2029 |
| `get_jc_summary` | 2081 |
| `create_sco_from_production_plan` | 26 |
| `create_supplier_operation_entries` | 286 |
| `create_send_to_subcontractor_entry` | 303 |
| `get_sco_pending_items` | 399 |
| `create_partial_transfer` | 509 |
| `create_cnc_to_supplier_entry` | 570 |
| `get_soe_summary` | 673 |
| `create_return_stock_entry` | 719 |
| `create_finished_goods_entry` | 777 |

## Total

_83 whitelisted methods_
