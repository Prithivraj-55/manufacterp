# app_map — manufyxinvenzaerp

_Generated: 2026-08-11 04:58:22_

## Modules

- accounts_management
- config
- drawing_management
- fixtures
- item_management
- manufyxinvenzaerp
- material_request_management
- patches
- production_management
- production_plan_management
- public
- purchase_order_management
- purchase_receipt_management
- rfq_management
- sq_management
- subcontracting_management
- templates
- tests
- utils

## Python files

_Total: 197_

- accounts_management/__init__.py
- accounts_management/payment_entry.py
- accounts_management/payment_request.py
- accounts_management/report/customer_fund_usage/customer_fund_usage.py
- accounts_management/report/customer_fund_usage/__init__.py
- accounts_management/report/__init__.py
- config/__init__.py
- drawing_management/bom_class_override.py
- drawing_management/doctype/drawing/drawing.py
- drawing_management/doctype/drawing/__init__.py
- drawing_management/doctype/drawing_item/drawing_item.py
- drawing_management/doctype/drawing_item/__init__.py
- drawing_management/doctype/drawing_weight_change_log/drawing_weight_change_log.py
- drawing_management/doctype/drawing_weight_change_log/__init__.py
- drawing_management/doctype/__init__.py
- drawing_management/doctype/job_nature/__init__.py
- drawing_management/doctype/job_nature/job_nature.py
- drawing_management/doctype/nature_of_work/__init__.py
- drawing_management/doctype/nature_of_work/nature_of_work.py
- drawing_management/doctype/production_plan_bom_raw_material/__init__.py
- drawing_management/doctype/production_plan_bom_raw_material/production_plan_bom_raw_material.py
- drawing_management/doctype/rate_schedule/__init__.py
- drawing_management/doctype/rate_schedule_price_log/__init__.py
- drawing_management/doctype/rate_schedule_price_log/rate_schedule_price_log.py
- drawing_management/doctype/rate_schedule/rate_schedule.py
- drawing_management/doctype/sales_order_drawing_raw_material/__init__.py
- drawing_management/doctype/sales_order_drawing_raw_material/sales_order_drawing_raw_material.py
- drawing_management/doctype/sales_order_duno_item/__init__.py
- drawing_management/doctype/sales_order_duno_item/sales_order_duno_item.py
- drawing_management/drawing_utils.py
- drawing_management/__init__.py
- drawing_management/sales_order.py
- drawing_management/so_drawing_import.py
- hooks.py
- __init__.py
- item_management/__init__.py
- item_management/item.py
- manufyxinvenzaerp/doctype/__init__.py
- manufyxinvenzaerp/doctype/manufyxinvenza_settings/__init__.py
- manufyxinvenzaerp/doctype/manufyxinvenza_settings/manufyxinvenza_settings.py
- manufyxinvenzaerp/__init__.py
- material_request_management/__init__.py
- material_request_management/material_request.py
- patches/__init__.py
- patches/v1/backfill_payment_entry_created_flag.py
- patches/v1/fix_bom_item_number_field_type.py
- patches/v1/__init__.py
- patches/v1/remove_sco_transfer_fields.py
- patches/v1/remove_wo_transfer_fields.py
- production_management/doctype/__init__.py
- production_management/doctype/inspection_call_log/__init__.py
- production_management/doctype/inspection_call_log/inspection_call_log.py
- production_management/doctype/inspection_entry/__init__.py
- production_management/doctype/inspection_entry/inspection_entry.py
- production_management/doctype/inspection_entry_item/__init__.py
- production_management/doctype/inspection_entry_item/inspection_entry_item.py
- production_management/doctype/job_card_raw_material/__init__.py
- production_management/doctype/job_card_raw_material/job_card_raw_material.py
- production_management/doctype/material_planning_available_raw_material/__init__.py
- production_management/doctype/material_planning_available_raw_material/material_planning_available_raw_material.py
- production_management/doctype/material_planning_batch_change_log/__init__.py
- production_management/doctype/material_planning_batch_change_log/material_planning_batch_change_log.py
- production_management/doctype/material_planning_bom_item/__init__.py
- production_management/doctype/material_planning_bom_item/material_planning_bom_item.py
- production_management/doctype/material_planning_consolidate_item/__init__.py
- production_management/doctype/material_planning_consolidate_item/material_planning_consolidate_item.py
- production_management/doctype/material_planning/__init__.py
- production_management/doctype/material_planning_material_mapping/__init__.py
- production_management/doctype/material_planning_material_mapping/material_planning_material_mapping.py
- production_management/doctype/material_planning/material_planning.py
- production_management/doctype/material_planning_raw_material/__init__.py
- production_management/doctype/material_planning_raw_material/material_planning_raw_material.py
- production_management/doctype/material_planning/test_material_planning.py
- production_management/doctype/material_planning_unavailable_item/__init__.py
- production_management/doctype/material_planning_unavailable_item/material_planning_unavailable_item.py
- production_management/doctype/process_planning/__init__.py
- production_management/doctype/process_planning/process_planning.py
- production_management/doctype/production_plan_available_raw_material/__init__.py
- production_management/doctype/production_plan_available_raw_material/production_plan_available_raw_material.py
- production_management/doctype/storage_location/__init__.py
- production_management/doctype/storage_location/storage_location.py
- production_management/doctype/store_location/__init__.py
- production_management/doctype/store_location/store_location.py
- production_management/__init__.py
- production_management/inspection.py
- production_management/job_card.py
- production_management/manual_release_check.py
- production_management/page/material_planning_case_studies/__init__.py
- production_management/page/material_planning_manual/__init__.py
- production_management/production_utils.py
- production_management/report/__init__.py
- production_management/report/inspection_status_report/__init__.py
- production_management/report/inspection_status_report/inspection_status_report.py
- production_management/report/inventory_report/__init__.py
- production_management/report/inventory_report/inventory_report.py
- production_management/report/manufyxinvenza_stock_balance/__init__.py
- production_management/report/manufyxinvenza_stock_balance/manufyxinvenza_stock_balance.py
- production_management/report/production_report/__init__.py
- production_management/report/production_report/production_report.py
- production_management/stock_entry.py
- production_plan_management/production_plan.py
- pull_live.py
- purchase_order_management/__init__.py
- purchase_order_management/purchase_order.py
- purchase_receipt_management/__init__.py
- purchase_receipt_management/purchase_receipt.py
- rfq_management/__init__.py
- rfq_management/request_for_quotation.py
- sample_data.py
- setup.py
- sq_management/__init__.py
- sq_management/supplier_quotation.py
- subcontracting_management/doctype/__init__.py
- subcontracting_management/doctype/job_card_consumption_log/__init__.py
- subcontracting_management/doctype/job_card_consumption_log/job_card_consumption_log.py
- subcontracting_management/doctype/material_issue_plan/__init__.py
- subcontracting_management/doctype/material_issue_plan/material_issue_plan.py
- subcontracting_management/doctype/material_issue_plan_raw_material/__init__.py
- subcontracting_management/doctype/material_issue_plan_raw_material/material_issue_plan_raw_material.py
- subcontracting_management/doctype/sco_drawing_item/__init__.py
- subcontracting_management/doctype/sco_drawing_item/sco_drawing_item.py
- subcontracting_management/doctype/sco_excess_material_item/__init__.py
- subcontracting_management/doctype/sco_excess_material_item/sco_excess_material_item.py
- subcontracting_management/doctype/soe_consumption_log/__init__.py
- subcontracting_management/doctype/soe_consumption_log/soe_consumption_log.py
- subcontracting_management/doctype/soe_drawing_detail/__init__.py
- subcontracting_management/doctype/soe_drawing_detail/soe_drawing_detail.py
- subcontracting_management/doctype/soe_inspection_item/__init__.py
- subcontracting_management/doctype/soe_inspection_item/soe_inspection_item.py
- subcontracting_management/doctype/supplier_operation_entry/__init__.py
- subcontracting_management/doctype/supplier_operation_entry/supplier_operation_entry.py
- subcontracting_management/doctype/supplier_operation_item/__init__.py
- subcontracting_management/doctype/supplier_operation_item/supplier_operation_item.py
- subcontracting_management/__init__.py
- subcontracting_management/material_issue_plan_transfer.py
- subcontracting_management/overrides.py
- subcontracting_management/report/excess_material_return_report/excess_material_return_report.py
- subcontracting_management/report/excess_material_return_report/__init__.py
- subcontracting_management/report/__init__.py
- subcontracting_management/subcontracting.py
- templates/__init__.py
- templates/pages/__init__.py
- tests/create_full_test_entry.py
- tests/create_test_data.py
- tests/find_cascade_fixture.py
- tests/find_clean_mp.py
- tests/_find_mip_excess.py
- tests/__init__.py
- tests/revert_wo_jc_cleanup.py
- tests/test_alternate_item.py
- tests/test_classification_logic.py
- tests/test_e2e_material_planning.py
- tests/test_material_planning.py
- tests/test_po_edge_cases.py
- tests/test_purchase_order_creation.py
- tests/test_unavailable_actions.py
- tests/verify_batch_remarks.py
- tests/verify_bom_routing_new_bom.py
- tests/verify_bom_routing_trim.py
- tests/verify_consolidate_alternate_item.py
- tests/verify_consolidate_finalize.py
- tests/verify_consolidate_item2.py
- tests/verify_consolidate_item.py
- tests/verify_consolidate_sec_qty_editable.py
- tests/verify_create_operation_and_inspection_gate.py
- tests/verify_drawing_weight_cascade2.py
- tests/verify_drawing_weight_cascade.py
- tests/verify_excess_material_mapping.py
- tests/verify_excess_material_mapping_row_btn.py
- tests/verify_internal_job_sco.py
- tests/verify_manual_mr_multi_supplier.py
- tests/verify_mip_consolidated_allocation.py
- tests/verify_mip_cut_sheet.py
- tests/verify_mip_excess_auto_suggest.py
- tests/verify_mip_excess_qty_fields.py
- tests/verify_mip_post_purchase_refresh.py
- tests/verify_mip_return_excess_reason.py
- tests/verify_mixed_sco_regression.py
- tests/verify_mp_inspection_gate.py
- tests/verify_mp_multi_mr_guard_message.py
- tests/verify_per_row_unreserve.py
- tests/verify_pp_naming.py
- tests/verify_pr_inspection.py
- tests/verify_process_planning_fields.py
- tests/verify_pr_sequential_allocation.py
- tests/verify_reassign_batch_exact_match2.py
- tests/verify_reassign_batch_exact_match.py
- tests/verify_reassign_batch_inspection_blocked.py
- tests/verify_se_duno_propagation.py
- tests/verify_soe_consumption_weight_kg.py
- tests/verify_status_mirror.py
- tests/verify_unreserve_btn_meta.py
- tests/verify_wo_jc_standard2.py
- tests/verify_wo_jc_standard.py
- utils/dimension_formula.py
- utils/__init__.py
- utils/reference_copy.py

## JavaScript files

_Total: 21_

- accounts_management/report/customer_fund_usage/customer_fund_usage.js
- drawing_management/doctype/drawing/drawing.js
- production_management/doctype/material_planning/material_planning.js
- production_management/page/material_planning_case_studies/material_planning_case_studies.js
- production_management/page/material_planning_manual/material_planning_manual.js
- production_management/report/inspection_status_report/inspection_status_report.js
- production_management/report/inventory_report/inventory_report.js
- production_management/report/manufyxinvenza_stock_balance/manufyxinvenza_stock_balance.js
- production_management/report/production_report/production_report.js
- public/js/batch.js
- public/js/bom.js
- public/js/inspection_entry.js
- public/js/item.js
- public/js/job_card.js
- public/js/payment_request.js
- public/js/production_plan.js
- public/js/purchase_order.js
- public/js/purchase_receipt.js
- public/js/supplier_operation_entry.js
- subcontracting_management/doctype/material_issue_plan/material_issue_plan.js
- subcontracting_management/report/excess_material_return_report/excess_material_return_report.js

## JSON files

_Total: 47_

- accounts_management/report/customer_fund_usage/customer_fund_usage.json
- drawing_management/doctype/drawing/drawing.json
- drawing_management/doctype/drawing_item/drawing_item.json
- drawing_management/doctype/drawing_weight_change_log/drawing_weight_change_log.json
- drawing_management/doctype/job_nature/job_nature.json
- drawing_management/doctype/nature_of_work/nature_of_work.json
- drawing_management/doctype/production_plan_bom_raw_material/production_plan_bom_raw_material.json
- drawing_management/doctype/rate_schedule_price_log/rate_schedule_price_log.json
- drawing_management/doctype/rate_schedule/rate_schedule.json
- drawing_management/doctype/sales_order_drawing_raw_material/sales_order_drawing_raw_material.json
- drawing_management/doctype/sales_order_duno_item/sales_order_duno_item.json
- fixtures/custom_field.json
- fixtures/property_setter.json
- manufyxinvenzaerp/doctype/manufyxinvenza_settings/manufyxinvenza_settings.json
- production_management/doctype/inspection_call_log/inspection_call_log.json
- production_management/doctype/inspection_entry/inspection_entry.json
- production_management/doctype/inspection_entry_item/inspection_entry_item.json
- production_management/doctype/job_card_raw_material/job_card_raw_material.json
- production_management/doctype/material_planning_available_raw_material/material_planning_available_raw_material.json
- production_management/doctype/material_planning_batch_change_log/material_planning_batch_change_log.json
- production_management/doctype/material_planning_bom_item/material_planning_bom_item.json
- production_management/doctype/material_planning_consolidate_item/material_planning_consolidate_item.json
- production_management/doctype/material_planning_material_mapping/material_planning_material_mapping.json
- production_management/doctype/material_planning/material_planning.json
- production_management/doctype/material_planning_raw_material/material_planning_raw_material.json
- production_management/doctype/material_planning_unavailable_item/material_planning_unavailable_item.json
- production_management/doctype/process_planning/process_planning.json
- production_management/doctype/production_plan_available_raw_material/production_plan_available_raw_material.json
- production_management/doctype/storage_location/storage_location.json
- production_management/doctype/store_location/store_location.json
- production_management/page/material_planning_case_studies/material_planning_case_studies.json
- production_management/page/material_planning_manual/material_planning_manual.json
- production_management/report/inspection_status_report/inspection_status_report.json
- production_management/report/inventory_report/inventory_report.json
- production_management/report/manufyxinvenza_stock_balance/manufyxinvenza_stock_balance.json
- production_management/report/production_report/production_report.json
- subcontracting_management/doctype/job_card_consumption_log/job_card_consumption_log.json
- subcontracting_management/doctype/material_issue_plan/material_issue_plan.json
- subcontracting_management/doctype/material_issue_plan_raw_material/material_issue_plan_raw_material.json
- subcontracting_management/doctype/sco_drawing_item/sco_drawing_item.json
- subcontracting_management/doctype/sco_excess_material_item/sco_excess_material_item.json
- subcontracting_management/doctype/soe_consumption_log/soe_consumption_log.json
- subcontracting_management/doctype/soe_drawing_detail/soe_drawing_detail.json
- subcontracting_management/doctype/soe_inspection_item/soe_inspection_item.json
- subcontracting_management/doctype/supplier_operation_entry/supplier_operation_entry.json
- subcontracting_management/doctype/supplier_operation_item/supplier_operation_item.json
- subcontracting_management/report/excess_material_return_report/excess_material_return_report.json

## Doctypes

### drawing
- Path: `drawing_management/doctype/drawing`
- Controller: `drawing_management/doctype/drawing/drawing.py`
- Client script: `drawing_management/doctype/drawing/drawing.js`
- Methods:
  - before_insert:
  - validate:
  - before_submit:
  - on_cancel:
  - _recalculate_all:
  - _check_missing_fields:
  - _calculate_totals:
  - _recalculate_row_qty:
  - _recalculate_row_totals:
  - _check_row_missing_fields:
  - check_existing_bom:

### drawing_item
- Path: `drawing_management/doctype/drawing_item`
- Controller: `drawing_management/doctype/drawing_item/drawing_item.py`
- Client script: none

### drawing_weight_change_log
- Path: `drawing_management/doctype/drawing_weight_change_log`
- Controller: `drawing_management/doctype/drawing_weight_change_log/drawing_weight_change_log.py`
- Client script: none

### job_nature
- Path: `drawing_management/doctype/job_nature`
- Controller: `drawing_management/doctype/job_nature/job_nature.py`
- Client script: none

### nature_of_work
- Path: `drawing_management/doctype/nature_of_work`
- Controller: `drawing_management/doctype/nature_of_work/nature_of_work.py`
- Client script: none

### production_plan_bom_raw_material
- Path: `drawing_management/doctype/production_plan_bom_raw_material`
- Controller: `drawing_management/doctype/production_plan_bom_raw_material/production_plan_bom_raw_material.py`
- Client script: none

### rate_schedule_price_log
- Path: `drawing_management/doctype/rate_schedule_price_log`
- Controller: `drawing_management/doctype/rate_schedule_price_log/rate_schedule_price_log.py`
- Client script: none

### rate_schedule
- Path: `drawing_management/doctype/rate_schedule`
- Controller: `drawing_management/doctype/rate_schedule/rate_schedule.py`
- Client script: none
- Methods:
  - before_insert:
  - validate:
  - _track_rate_change:

### sales_order_drawing_raw_material
- Path: `drawing_management/doctype/sales_order_drawing_raw_material`
- Controller: `drawing_management/doctype/sales_order_drawing_raw_material/sales_order_drawing_raw_material.py`
- Client script: none

### sales_order_duno_item
- Path: `drawing_management/doctype/sales_order_duno_item`
- Controller: `drawing_management/doctype/sales_order_duno_item/sales_order_duno_item.py`
- Client script: none

### manufyxinvenza_settings
- Path: `manufyxinvenzaerp/doctype/manufyxinvenza_settings`
- Controller: `manufyxinvenzaerp/doctype/manufyxinvenza_settings/manufyxinvenza_settings.py`
- Client script: none

### inspection_call_log
- Path: `production_management/doctype/inspection_call_log`
- Controller: `production_management/doctype/inspection_call_log/inspection_call_log.py`
- Client script: none

### inspection_entry
- Path: `production_management/doctype/inspection_entry`
- Controller: `production_management/doctype/inspection_entry/inspection_entry.py`
- Client script: none
- Methods:
  - validate:
  - _autofill_total_qty_to_check:
  - _set_inspection_complete_date:
  - before_submit:
  - _validate_scalar_result:
  - _validate_soe_items:
  - _validate_pr_items:

### inspection_entry_item
- Path: `production_management/doctype/inspection_entry_item`
- Controller: `production_management/doctype/inspection_entry_item/inspection_entry_item.py`
- Client script: none

### job_card_raw_material
- Path: `production_management/doctype/job_card_raw_material`
- Controller: `production_management/doctype/job_card_raw_material/job_card_raw_material.py`
- Client script: none

### material_planning_available_raw_material
- Path: `production_management/doctype/material_planning_available_raw_material`
- Controller: `production_management/doctype/material_planning_available_raw_material/material_planning_available_raw_material.py`
- Client script: none

### material_planning_batch_change_log
- Path: `production_management/doctype/material_planning_batch_change_log`
- Controller: `production_management/doctype/material_planning_batch_change_log/material_planning_batch_change_log.py`
- Client script: none

### material_planning_bom_item
- Path: `production_management/doctype/material_planning_bom_item`
- Controller: `production_management/doctype/material_planning_bom_item/material_planning_bom_item.py`
- Client script: none

### material_planning_consolidate_item
- Path: `production_management/doctype/material_planning_consolidate_item`
- Controller: `production_management/doctype/material_planning_consolidate_item/material_planning_consolidate_item.py`
- Client script: none
- Methods:
  - recalculate:

### material_planning_material_mapping
- Path: `production_management/doctype/material_planning_material_mapping`
- Controller: `production_management/doctype/material_planning_material_mapping/material_planning_material_mapping.py`
- Client script: none

### material_planning
- Path: `production_management/doctype/material_planning`
- Controller: `production_management/doctype/material_planning/material_planning.py`
- Client script: `production_management/doctype/material_planning/material_planning.js`
- Methods:
  - validate:
  - _warn_undersized_purchase_dimensions:
  - _sync_batch_remarks:
  - _consolidate_unavailable_items:
  - _recalculate_consolidate_items:
  - _auto_update_planning_status:
  - _validate_no_cross_table_batch_duplicate:
  - _update_weight_summary:
  - _apply_rwd_fractional_nos:
  - _move_skipped_arm_to_mapping:
  - _validate_batch_calc_qty:
  - _validate_alternate_item_qty:
  - search_bom:
  - get_bom_info:
  - get_so_drawings_for_bom_picker:
  - _nos_from_weight:
  - _reconcile_sec_qty_with_sales_order:
  - get_raw_materials:
  - check_stock_availability:
  - _alloc_sec_qty:
  - _get_non_batch_stock:
  - _get_non_batch_stock_bulk:
  - move_to_exact_match:
  - update_exact_match_from_consolidate:
  - finalize_mapping:
  - _verify_nos_vs_qty:
  - verify_raw_materials:
  - get_batch_reservation_summary:
  - get_batch_item:
  - get_batch_stock_summary:
  - _get_batch_inspection_block_reason:
  - _get_batch_total_stock:
  - _get_batch_reserved_by_others:
  - _get_batch_reserved_by_others_bulk:
  - _get_non_batch_reserved_by_others:
  - _get_non_batch_reserved_by_others_bulk:
  - get_batch_cross_table_usage:
  - _update_bom_item_weights:
  - _calc_kg_per_nos:
  - _calc_usable_nos_split:
  - _row_get:
  - validate_planned_stock:
  - _add:
  - _sec_nos_for_weight:
  - reserve_batches:
  - _get_batch_reserved_by_self:
  - get_available_excess_batches:
  - add_excess_material_mapping:
  - get_available_virtual_excess_items:
  - _release_virtual_excess_source:
  - claim_virtual_excess_mapping:
  - reserve_exact_match_batches:
  - unreserve_exact_match_batches:
  - check_mapping_batch_availability:
  - unreserve_batches:
  - _get_batch_dims:
  - _calc_batch_qty:
  - _precheck_batch_reassignment:
  - _mark_excess_item_mapped:
  - _batch_change_remarks:
  - reassign_batch:
  - _apply_batch_to_mapping_row:
  - _test_simulate_se_release:
  - __init__:
  - get:
  - __init__:
  - make_production_plan:
  - make_material_request:
  - make_material_request_from_consolidate:
  - _update_so_difference_kg_for_pair:
  - update_so_difference_kg:
  - unlink_material_request_on_cancel:
  - auto_purchase_from_mp:
  - _collect_batch_mapping_issues:
  - complete_batch_mapping:

### material_planning_raw_material
- Path: `production_management/doctype/material_planning_raw_material`
- Controller: `production_management/doctype/material_planning_raw_material/material_planning_raw_material.py`
- Client script: none

### material_planning_unavailable_item
- Path: `production_management/doctype/material_planning_unavailable_item`
- Controller: `production_management/doctype/material_planning_unavailable_item/material_planning_unavailable_item.py`
- Client script: none

### process_planning
- Path: `production_management/doctype/process_planning`
- Controller: `production_management/doctype/process_planning/process_planning.py`
- Client script: none

### production_plan_available_raw_material
- Path: `production_management/doctype/production_plan_available_raw_material`
- Controller: `production_management/doctype/production_plan_available_raw_material/production_plan_available_raw_material.py`
- Client script: none

### storage_location
- Path: `production_management/doctype/storage_location`
- Controller: `production_management/doctype/storage_location/storage_location.py`
- Client script: none

### store_location
- Path: `production_management/doctype/store_location`
- Controller: `production_management/doctype/store_location/store_location.py`
- Client script: none

### job_card_consumption_log
- Path: `subcontracting_management/doctype/job_card_consumption_log`
- Controller: `subcontracting_management/doctype/job_card_consumption_log/job_card_consumption_log.py`
- Client script: none

### material_issue_plan
- Path: `subcontracting_management/doctype/material_issue_plan`
- Controller: `subcontracting_management/doctype/material_issue_plan/material_issue_plan.py`
- Client script: `subcontracting_management/doctype/material_issue_plan/material_issue_plan.js`
- Methods:
  - after_insert:
  - validate:
  - on_trash:
  - create_from_subcontracting_order:
  - create_from_work_order:
  - populate_from_production_plan:
  - _mip_refresh_blocked_message:
  - check_mip_raw_materials_refreshable:
  - refresh_mip_raw_materials_manual:
  - refresh_mip_raw_materials:
  - _carry_forward_editable_fields:
  - _lookup_drawing_planned_weight:
  - _sync_excess_return_from_raw_materials:
  - _sync_cut_sheet_calc:
  - _sync_batch_remarks:
  - _maybe_mark_completed:
  - recheck_mip_completion:
  - _auto_suggest_excess_from_cut_sheet:
  - refresh_weight_summary:
  - get_target_context:
  - _resolve_warehouses:
  - get_mip_batch_plan_html:
  - download_mip_batch_plan_pdf:
  - _render_mip_batch_plan_html:

### material_issue_plan_raw_material
- Path: `subcontracting_management/doctype/material_issue_plan_raw_material`
- Controller: `subcontracting_management/doctype/material_issue_plan_raw_material/material_issue_plan_raw_material.py`
- Client script: none

### sco_drawing_item
- Path: `subcontracting_management/doctype/sco_drawing_item`
- Controller: `subcontracting_management/doctype/sco_drawing_item/sco_drawing_item.py`
- Client script: none

### sco_excess_material_item
- Path: `subcontracting_management/doctype/sco_excess_material_item`
- Controller: `subcontracting_management/doctype/sco_excess_material_item/sco_excess_material_item.py`
- Client script: none

### soe_consumption_log
- Path: `subcontracting_management/doctype/soe_consumption_log`
- Controller: `subcontracting_management/doctype/soe_consumption_log/soe_consumption_log.py`
- Client script: none

### soe_drawing_detail
- Path: `subcontracting_management/doctype/soe_drawing_detail`
- Controller: `subcontracting_management/doctype/soe_drawing_detail/soe_drawing_detail.py`
- Client script: none

### soe_inspection_item
- Path: `subcontracting_management/doctype/soe_inspection_item`
- Controller: `subcontracting_management/doctype/soe_inspection_item/soe_inspection_item.py`
- Client script: none

### supplier_operation_entry
- Path: `subcontracting_management/doctype/supplier_operation_entry`
- Controller: `subcontracting_management/doctype/supplier_operation_entry/supplier_operation_entry.py`
- Client script: none

### supplier_operation_item
- Path: `subcontracting_management/doctype/supplier_operation_item`
- Controller: `subcontracting_management/doctype/supplier_operation_item/supplier_operation_item.py`
- Client script: none

## Module-level controllers

### accounts_management/payment_entry.py
Functions:
  - 4:on_submit_payment_entry:
  - 8:on_cancel_payment_entry:
  - 12:_sync_payment_entry_created_flag:

### accounts_management/payment_request.py
Functions:
  - 5:validate_payment_request:
  - 29:payment_entry_query:
  - 56:get_fund_usage:

### drawing_management/bom_class_override.py
Functions:
  - 1060:get_bom_item_rate:
  - 1095:get_valuation_rate:
  - 1151:get_list_context:
  - 1156:get_bom_items_as_dict:
  - 1255:get_bom_items:
  - 1262:validate_bom_no:
  - 1288:get_children:
  - 1329:add_additional_cost:
  - 1346:add_non_stock_items_cost:
  - 1379:add_operations_cost:
  - 1467:get_bom_diff:
  - 1523:item_query:
  - 1574:make_variant_bom:
  - 1612:get_op_cost_from_sub_assemblies:
  - 1630:get_scrap_items_from_sub_assemblies:

### drawing_management/drawing_utils.py
Functions:
  - 8:create_drawings_from_so:
  - 46:mark_as_final_revision:
  - 60:get_batches_for_drawing_item:
  - 92:create_bom_from_drawing:
  - 149:validate_bom_from_drawing:
  - 204:create_production_plan_from_bom:
  - 258:parse_drawing_items_csv:
  - 370:get_so_dashboard_data:
  - 379:update_customer_provided_weight:
  - 431:_cascade_customer_weight:

### drawing_management/sales_order.py
Functions:
  - 6:recalculate_raw_material_qty:

### drawing_management/so_drawing_import.py
Functions:
  - 11:_calc_qty:
  - 19:_get_file_path:
  - 28:_parse_excel:
  - 119:parse_bom_excel:
  - 314:_bulk_insert:
  - 334:create_drawings_from_import:
  - 485:process_drawings:
  - 615:verify_raw_materials:
  - 673:download_bom_template:
  - 715:clear_drawing_import:

### hooks.py

### item_management/item.py
Functions:
  - 15:validate_item:
  - 24:validate_parent_item_group:
  - 29:set_calculation_type:
  - 36:validate_uom_configuration:
  - 77:validate_batch_configuration:
  - 92:validate_batch_prefix:
  - 104:_has_transactions:
  - 112:validate_locked_fields:
  - 125:has_item_transactions:

### material_request_management/material_request.py
Functions:
  - 11:get_mr_item_uom:
  - 27:validate_material_request:
  - 33:before_submit_material_request:
  - 38:_recalculate_qty:
  - 53:_check_missing_fields:

### production_management/inspection.py
Functions:
  - 40:_inspection_applicable:
  - 55:validate_job_card_inspection:
  - 59:validate_soe_inspection:
  - 63:validate_purchase_receipt_inspection:
  - 67:_validate_inspection_call_log:
  - 75:before_submit_job_card_inspection_gate:
  - 79:before_submit_soe_inspection_gate:
  - 83:_before_submit_inspection_gate:
  - 106:add_inspection_call:
  - 153:update_inspection_call_date:
  - 173:create_inspection_entry:
  - 257:on_submit_inspection_entry:
  - 326:_apply_soe_inspection_results:
  - 380:_resolve_pr_item_batch_nos:
  - 404:_get_source_doc:
  - 419:_resolve_traceability:

### production_management/job_card.py
Functions:
  - 8:validate_job_card:
  - 62:_get_wip_stock:
  - 70:before_submit_manufacture_stock_entry:

### production_management/manual_release_check.py

### production_management/production_utils.py
Functions:
  - 23:create_operations_workstations_routing:
  - 31:_create_operations:
  - 41:_create_workstations:
  - 56:_create_routing:
  - 89:get_routing_operations_for_bom:
  - 114:get_raw_materials_for_job_card:
  - 165:_get_transferred_qty_for_item:
  - 176:_get_previous_operation_consumed:
  - 221:_get_prev_soe_consumed_for_jc:
  - 265:validate_final_operation_consumption:

### production_management/stock_entry.py
Functions:
  - 10:validate_stock_entry:
  - 48:_sync_batch_remarks:
  - 66:_copy_from_material_request_item:
  - 78:on_submit_stock_entry:
  - 165:_reduce_batch_sec_qty:
  - 170:_resize_cut_sheet_batches:
  - 204:_batch_total_kg_all_wh:
  - 217:_populate_manufacture_sec_qty:
  - 239:_collect_consumed_batches:
  - 272:_linked_material_plannings:
  - 303:_release_material_planning_reservations:
  - 367:_refresh_linked_mip_weight:
  - 398:on_cancel_stock_entry:
  - 421:_restore_batch_sec_qty:
  - 439:_restore_material_planning_reservations:
  - 492:_update_sco_transferred_weight:
  - 603:_update_sco_cnc_weight:
  - 651:_update_wo_transferred_weight:
  - 694:_update_wo_cnc_weight:
  - 741:_calc_qty:

### production_plan_management/production_plan.py
Functions:
  - 22:get_sbb_available_qty:
  - 149:get_sbb_batches_bulk:
  - 266:match_batches_by_dimension:
  - 284:get_items_for_material_requests:
  - 477:get_exploded_items:
  - 484:get_bom_items_direct:
  - 550:get_uom_conversion_factor:
  - 556:get_warehouse_list:
  - 572:get_material_request_items:
  - 661:get_mp_planned_weights:
  - 676:_calc_mp_drawing_weight:
  - 693:_calc_mp_weight:
  - 713:get_pp_drawings_for_picker:
  - 727:_picker_rows_from_mp:
  - 774:_picker_rows_from_so:
  - 829:_mark_already_in_pp:
  - 860:get_operations_from_routing:
  - 873:get_standard_routing_operations:
  - 886:make_material_request:
  - 964:autoname_production_plan:
  - 974:after_save_production_plan:
  - 979:validate_process_planning_contiguity:
  - 1016:unlink_production_plan_on_trash:
  - 1029:_recalculate_sec_qty:

### pull_live.py
Functions:
  - 29:get_session:
  - 37:fetch_list:
  - 57:fetch_doc:
  - 63:upsert:
  - 89:sync_singles:
  - 105:sync_doctype:
  - 127:run:

### purchase_order_management/purchase_order.py
Functions:
  - 10:get_po_item_uom:
  - 26:validate_purchase_order:
  - 37:_copy_from_mr_item:
  - 42:before_submit_purchase_order:
  - 47:_recalculate_qty:
  - 62:_check_missing_fields:

### purchase_receipt_management/purchase_receipt.py
Functions:
  - 16:get_pr_item_uom:
  - 32:validate_purchase_receipt:
  - 43:before_submit_purchase_receipt:
  - 48:before_insert_batch:
  - 56:_setup_batch_from_purchase_receipt:
  - 128:_setup_batch_from_stock_entry:
  - 199:_get_receipt_suffix:
  - 207:_get_se_suffix:
  - 215:_copy_from_po_item:
  - 221:_recalculate_qty:
  - 236:_check_missing_fields:
  - 242:_resolve_pr_batch_no:
  - 257:get_mp_for_pr:
  - 277:_pr_dimensions_match:
  - 295:_build_mapping_row:
  - 359:allocate_pr_stock_to_mp:
  - 703:_archive_consolidate_items:
  - 767:on_submit_purchase_receipt:
  - 832:_get_batch_from_bundle:
  - 844:get_pr_mp_allocations:

### rfq_management/request_for_quotation.py
Functions:
  - 16:validate_rfq:
  - 21:_copy_from_mr_item:

### sample_data.py
Functions:
  - 4:run:

### setup.py
Functions:
  - 1231:create_default_warehouse_types:
  - 1245:after_install:
  - 1300:after_migrate:
  - 1359:setup_storage_location:
  - 1381:create_item_client_script:
  - 1397:create_item_custom_fields:
  - 1482:create_purchase_order_custom_fields:
  - 1588:hide_purchase_order_weight_fields:
  - 1602:create_purchase_order_client_script:
  - 1618:create_purchase_receipt_custom_fields:
  - 1797:create_batch_custom_fields:
  - 1882:create_purchase_receipt_client_script:
  - 1898:create_material_request_custom_fields:
  - 2023:create_material_request_client_script:
  - 2039:create_rfq_custom_fields:
  - 2115:create_rfq_client_script:
  - 2131:create_sq_custom_fields:
  - 2210:create_sq_client_script:
  - 2226:create_bom_custom_fields:
  - 2333:create_so_custom_fields:
  - 2410:create_so_client_script:
  - 2426:create_bom_client_script:
  - 2446:create_production_plan_custom_fields:
  - 2762:create_production_plan_client_script:
  - 2785:create_job_card_custom_fields:
  - 3053:create_job_card_client_script:
  - 3071:create_stock_entry_custom_fields:
  - 3263:create_stock_entry_client_script:
  - 3285:create_subcontracting_order_translation:
  - 3310:remove_sco_purchase_order_mandatory:
  - 3321:hide_sco_job_worker_warehouse:
  - 3350:make_sco_job_worker_conditional:
  - 3385:create_sco_custom_fields:
  - 3847:create_sco_client_script:
  - 3863:create_sco_ops_client_script:
  - 3879:create_soe_client_script:
  - 3895:create_manufacturing_settings_custom_fields:
  - 3923:create_work_order_custom_fields:
  - 4036:layout_work_order_fields:
  - 4132:create_job_card_drawing_fields:
  - 4205:create_job_card_inspection_fields:
  - 4261:layout_job_card_fields:
  - 4547:create_wo_client_script:
  - 4565:create_wo_ops_client_script:
  - 4583:create_jc_drawing_client_script:
  - 4604:create_material_planning_auto_purchase_fields:
  - 4651:create_payment_request_custom_fields:

### sq_management/supplier_quotation.py
Functions:
  - 19:get_sq_item_uom:
  - 35:validate_supplier_quotation:
  - 42:before_submit_supplier_quotation:
  - 47:_copy_from_rfq_item_if_blank:
  - 65:_has_custom_data:
  - 70:_recalculate_qty:
  - 85:_check_missing_fields:

### subcontracting_management/material_issue_plan_transfer.py
Functions:
  - 28:_ensure_mip_editable:
  - 38:_cnc_rows_missing_warehouse:
  - 45:_ensure_cnc_routing:
  - 83:_validate_selected_against_stock:
  - 148:_linked_mp_names:
  - 152:_linked_mp_names_and_duno_scope:
  - 187:_tag_stock_entry:
  - 195:get_mip_pending_items:
  - 342:update_transfer_sec_qty:
  - 388:_batch_free_qty:
  - 397:_log_round_up_excess:
  - 476:has_cnc_stock:
  - 495:_get_mip_transfer_stock_entry_names:
  - 512:_get_already_transferred_batches:
  - 528:get_mip_readiness_check:
  - 663:create_mip_transfer_entry:
  - 711:create_mip_partial_transfer:
  - 782:get_mip_cnc_pending_items:
  - 839:create_mip_cnc_partial_forward:
  - 910:_cnc_sent_and_forwarded:
  - 961:create_mip_cnc_forward_entry:
  - 1023:create_mip_excess_return_entry:

### subcontracting_management/overrides.py
Functions:
  - 11:_is_pp_flow_sco:
  - 18:resolve_supplier_warehouse:

### subcontracting_management/subcontracting.py
Functions:
  - 12:get_sco_dashboard_data:
  - 26:create_sco_from_production_plan:
  - 189:create_sco_and_mip_from_production_plan:
  - 214:delete_sco_and_mip_for_production_plan:
  - 294:create_work_order_from_pp:
  - 454:create_supplier_operation_entries:
  - 474:create_send_to_subcontractor_entry:
  - 570:get_sco_pending_items:
  - 680:create_partial_transfer:
  - 741:create_cnc_to_supplier_entry:
  - 844:get_soe_summary:
  - 890:create_return_stock_entry:
  - 948:create_finished_goods_entry:
  - 1065:validate_supplier_operation_entry:
  - 1195:_sync_soe_inspection_items:
  - 1230:before_submit_supplier_operation_entry:
  - 1264:_propagate_available_to_next:
  - 1286:_propagate_drawing_nos_to_next:
  - 1326:_update_sco_drawing_item_completion:
  - 1350:on_update_supplier_operation_entry:
  - 1357:_push_sco_completion_to_wo:
  - 1397:on_submit_supplier_operation_entry:
  - 1425:before_delete_supplier_operation_entry:
  - 1447:on_cancel_subcontracting_order:
  - 1468:_build_soe_drawing_rows:
  - 1515:_create_soes_for_sco:
  - 1591:_get_mp_total_weight:
  - 1619:_get_mp_actual_transferred_weight:
  - 1665:_refresh_wo_drawing_transferred_weights:
  - 1711:_get_sco_transfer_warehouses:
  - 1723:_get_sco_supplier_warehouse:
  - 1740:_get_wo_transfer_warehouses:
  - 1754:_refresh_sco_drawing_transferred_weights:
  - 1795:_get_mp_drawing_weight:
  - 1812:_get_mp_drawing_weights_by_duno:
  - 1838:_get_mp_mapped_weight_by_duno:
  - 1905:_get_mp_excess_by_duno:
  - 1924:_get_mp_reserved_batches:
  - 2034:_get_pp_planned_qty:
  - 2049:backfill_drawing_item_qty:
  - 2069:_get_supplier_wh_consumption_items:
  - 2117:get_wo_pending_items:
  - 2222:create_partial_wo_transfer:
  - 2278:create_cnc_to_wip_entry:
  - 2377:create_return_stock_entry_for_wo:
  - 2429:get_jc_summary:
  - 2474:on_submit_work_order:
  - 2482:on_cancel_work_order:
  - 2491:validate_job_card_drawing_entry:
  - 2605:before_submit_job_card_drawing_entry:
  - 2642:_propagate_drawing_nos_to_next_jc:
  - 2682:_update_wo_drawing_item_completion:
  - 2707:on_update_job_card_drawing_entry:
  - 2715:on_submit_job_card_drawing_entry:
  - 2741:_build_jc_drawing_rows:
  - 2774:_populate_jcs_for_wo:

### tests/create_full_test_entry.py
Functions:
  - 32:get_ctx:
  - 61:ensure_item:
  - 80:ensure_fg_item:
  - 100:ensure_batch:
  - 119:make_receipt:
  - 142:make_bom:
  - 181:make_material_planning:
  - 200:run:

### tests/create_test_data.py
Functions:
  - 19:get_context:
  - 52:make_item:
  - 73:make_fg_item:
  - 93:make_batch:
  - 112:make_stock_entry:
  - 135:make_bom:
  - 171:run:

### tests/find_cascade_fixture.py
Functions:
  - 4:run:

### tests/find_clean_mp.py
Functions:
  - 3:run:

### tests/_find_mip_excess.py
Functions:
  - 4:run:

### tests/revert_wo_jc_cleanup.py
Functions:
  - 106:run:

### tests/test_alternate_item.py
Functions:
  - 15:_get_unavailable_rows:
  - 23:_clear_mr_links:

### tests/test_classification_logic.py
Functions:
  - 24:_mock_sbb_batches_bulk:
  - 41:_ensure_batch_items:

### tests/test_e2e_material_planning.py
Functions:
  - 28:_get_context:
  - 46:_make_mp:
  - 61:test_flow_1_get_raw_materials:
  - 80:test_flow_2_check_stock_availability:
  - 136:test_flow_3_get_batch_item:
  - 152:test_flow_4_make_production_plan:
  - 168:test_ec1_submit_without_bom:
  - 184:test_ec2_get_raw_materials_no_company:
  - 201:test_ec3_check_stock_no_warehouse:
  - 217:test_ec4_get_batch_item_invalid:
  - 227:test_ec5_empty_bom_items:
  - 242:test_ec6_make_pp_on_draft:
  - 259:run:

### tests/test_material_planning.py
Functions:
  - 25:_make_item:
  - 45:_make_batch:
  - 62:_raw_material_row:
  - 88:test_uc1_exact_match_goes_to_available:
  - 125:test_uc2_partial_stock_goes_to_mapping:
  - 161:test_uc3_no_stock_goes_to_unavailable:
  - 196:test_uc4_get_batch_item:
  - 211:test_uc5_mixed_items_all_three_buckets:
  - 263:run:

### tests/test_po_edge_cases.py
Functions:
  - 15:_find_or_create_mr:
  - 43:_cancel_all_mrs:

### tests/test_purchase_order_creation.py
Functions:
  - 23:get_ctx:
  - 33:_make_test_mp:
  - 64:test_v1_po_created_with_correct_supplier:
  - 78:test_v2_po_items_match_unavailable_rows:
  - 98:test_v3_po_linked_back_on_rows:
  - 113:test_v4_partial_selection_only_links_selected:
  - 130:test_v5_error_when_no_items_selected:
  - 142:test_v6_error_when_no_unavailable_items:
  - 161:test_v7_po_is_draft:
  - 172:test_v8_multiple_pos_for_same_mp:
  - 191:run:

### tests/test_unavailable_actions.py
Functions:
  - 29:_mock_sbb:
  - 38:_ensure_batch_items:

### tests/verify_batch_remarks.py
Functions:
  - 34:run:

### tests/verify_bom_routing_new_bom.py
Functions:
  - 14:run:

### tests/verify_bom_routing_trim.py
Functions:
  - 15:run:

### tests/verify_consolidate_alternate_item.py
Functions:
  - 41:run:

### tests/verify_consolidate_finalize.py
Functions:
  - 22:run:

### tests/verify_consolidate_item2.py
Functions:
  - 4:run:

### tests/verify_consolidate_item.py
Functions:
  - 10:run:

### tests/verify_consolidate_sec_qty_editable.py
Functions:
  - 16:run:

### tests/verify_create_operation_and_inspection_gate.py
Functions:
  - 20:run:

### tests/verify_drawing_weight_cascade2.py
Functions:
  - 4:run:

### tests/verify_drawing_weight_cascade.py
Functions:
  - 16:run:

### tests/verify_excess_material_mapping.py
Functions:
  - 21:run:

### tests/verify_excess_material_mapping_row_btn.py
Functions:
  - 48:run:

### tests/verify_internal_job_sco.py
Functions:
  - 13:run:

### tests/verify_manual_mr_multi_supplier.py
Functions:
  - 25:run:

### tests/verify_mip_consolidated_allocation.py
Functions:
  - 33:run:

### tests/verify_mip_cut_sheet.py
Functions:
  - 26:run:

### tests/verify_mip_excess_auto_suggest.py
Functions:
  - 25:run:

### tests/verify_mip_excess_qty_fields.py
Functions:
  - 19:run:

### tests/verify_mip_post_purchase_refresh.py
Functions:
  - 27:run:

### tests/verify_mip_return_excess_reason.py
Functions:
  - 42:run:

### tests/verify_mixed_sco_regression.py
Functions:
  - 14:run:

### tests/verify_mp_inspection_gate.py
Functions:
  - 39:_make_inspected_item_and_pr:
  - 70:run:

### tests/verify_mp_multi_mr_guard_message.py
Functions:
  - 20:run:

### tests/verify_per_row_unreserve.py
Functions:
  - 15:run:

### tests/verify_pp_naming.py
Functions:
  - 6:run:

### tests/verify_pr_inspection.py
Functions:
  - 19:run:

### tests/verify_process_planning_fields.py
Functions:
  - 11:run:

### tests/verify_pr_sequential_allocation.py
Functions:
  - 24:run:

### tests/verify_reassign_batch_exact_match2.py
Functions:
  - 16:run:

### tests/verify_reassign_batch_exact_match.py
Functions:
  - 13:run:

### tests/verify_reassign_batch_inspection_blocked.py
Functions:
  - 22:run:

### tests/verify_se_duno_propagation.py
Functions:
  - 21:run:

### tests/verify_soe_consumption_weight_kg.py
Functions:
  - 13:run:

### tests/verify_status_mirror.py
Functions:
  - 10:run:

### tests/verify_unreserve_btn_meta.py
Functions:
  - 3:run:

### tests/verify_wo_jc_standard2.py
Functions:
  - 4:run:

### tests/verify_wo_jc_standard.py
Functions:
  - 4:run:

### utils/dimension_formula.py
Functions:
  - 36:calculate_qty:
  - 58:calculate_sec_qty_from_qty:
  - 69:check_missing_fields:

### utils/reference_copy.py
Functions:
  - 18:fetch_fields:
  - 27:copy_reference_fields_if_blank:

## Whitelisted API methods

- `item_management/item.py:125` — `has_item_transactions`
- `accounts_management/payment_request.py:28` — `@frappe.validate_and_sanitize_search_inputs`
- `accounts_management/payment_request.py:56` — `get_fund_usage`
- `purchase_order_management/purchase_order.py:10` — `get_po_item_uom`
- `sq_management/supplier_quotation.py:19` — `get_sq_item_uom`
- `drawing_management/drawing_utils.py:8` — `create_drawings_from_so`
- `drawing_management/drawing_utils.py:46` — `mark_as_final_revision`
- `drawing_management/drawing_utils.py:60` — `get_batches_for_drawing_item`
- `drawing_management/drawing_utils.py:92` — `create_bom_from_drawing`
- `drawing_management/drawing_utils.py:204` — `create_production_plan_from_bom`
- `drawing_management/drawing_utils.py:258` — `parse_drawing_items_csv`
- `drawing_management/drawing_utils.py:379` — `update_customer_provided_weight`
- `drawing_management/bom_class_override.py:353` — `get_routing`
- `drawing_management/bom_class_override.py:424` — `get_bom_material_detail`
- `drawing_management/bom_class_override.py:509` — `update_cost`
- `drawing_management/bom_class_override.py:1255` — `get_bom_items`
- `drawing_management/bom_class_override.py:1288` — `get_children`
- `drawing_management/bom_class_override.py:1467` — `get_bom_diff`
- `drawing_management/bom_class_override.py:1522` — `@frappe.validate_and_sanitize_search_inputs`
- `drawing_management/bom_class_override.py:1574` — `make_variant_bom`
- `drawing_management/so_drawing_import.py:119` — `parse_bom_excel`
- `drawing_management/so_drawing_import.py:334` — `create_drawings_from_import`
- `drawing_management/so_drawing_import.py:485` — `process_drawings`
- `drawing_management/so_drawing_import.py:615` — `verify_raw_materials`
- `drawing_management/so_drawing_import.py:673` — `download_bom_template`
- `drawing_management/so_drawing_import.py:715` — `clear_drawing_import`
- `drawing_management/doctype/drawing/drawing.py:109` — `check_existing_bom`
- `production_plan_management/production_plan.py:284` — `get_items_for_material_requests`
- `production_plan_management/production_plan.py:661` — `get_mp_planned_weights`
- `production_plan_management/production_plan.py:713` — `get_pp_drawings_for_picker`
- `production_plan_management/production_plan.py:860` — `get_operations_from_routing`
- `production_plan_management/production_plan.py:873` — `get_standard_routing_operations`
- `production_plan_management/production_plan.py:886` — `make_material_request`
- `material_request_management/material_request.py:11` — `get_mr_item_uom`
- `subcontracting_management/material_issue_plan_transfer.py:195` — `get_mip_pending_items`
- `subcontracting_management/material_issue_plan_transfer.py:342` — `update_transfer_sec_qty`
- `subcontracting_management/material_issue_plan_transfer.py:476` — `has_cnc_stock`
- `subcontracting_management/material_issue_plan_transfer.py:528` — `get_mip_readiness_check`
- `subcontracting_management/material_issue_plan_transfer.py:663` — `create_mip_transfer_entry`
- `subcontracting_management/material_issue_plan_transfer.py:711` — `create_mip_partial_transfer`
- `subcontracting_management/material_issue_plan_transfer.py:782` — `get_mip_cnc_pending_items`
- `subcontracting_management/material_issue_plan_transfer.py:839` — `create_mip_cnc_partial_forward`
- `subcontracting_management/material_issue_plan_transfer.py:961` — `create_mip_cnc_forward_entry`
- `subcontracting_management/material_issue_plan_transfer.py:1023` — `create_mip_excess_return_entry`
- `subcontracting_management/subcontracting.py:26` — `create_sco_from_production_plan`
- `subcontracting_management/subcontracting.py:189` — `create_sco_and_mip_from_production_plan`
- `subcontracting_management/subcontracting.py:214` — `delete_sco_and_mip_for_production_plan`
- `subcontracting_management/subcontracting.py:294` — `create_work_order_from_pp`
- `subcontracting_management/subcontracting.py:454` — `create_supplier_operation_entries`
- `subcontracting_management/subcontracting.py:474` — `create_send_to_subcontractor_entry`
- `subcontracting_management/subcontracting.py:570` — `get_sco_pending_items`
- `subcontracting_management/subcontracting.py:680` — `create_partial_transfer`
- `subcontracting_management/subcontracting.py:741` — `create_cnc_to_supplier_entry`
- `subcontracting_management/subcontracting.py:844` — `get_soe_summary`
- `subcontracting_management/subcontracting.py:890` — `create_return_stock_entry`
- `subcontracting_management/subcontracting.py:948` — `create_finished_goods_entry`
- `subcontracting_management/subcontracting.py:2049` — `backfill_drawing_item_qty`
- `subcontracting_management/subcontracting.py:2117` — `get_wo_pending_items`
- `subcontracting_management/subcontracting.py:2222` — `create_partial_wo_transfer`
- `subcontracting_management/subcontracting.py:2278` — `create_cnc_to_wip_entry`
- `subcontracting_management/subcontracting.py:2377` — `create_return_stock_entry_for_wo`
- `subcontracting_management/subcontracting.py:2429` — `get_jc_summary`
- `subcontracting_management/doctype/material_issue_plan/material_issue_plan.py:43` — `create_from_subcontracting_order`
- `subcontracting_management/doctype/material_issue_plan/material_issue_plan.py:62` — `create_from_work_order`
- `subcontracting_management/doctype/material_issue_plan/material_issue_plan.py:81` — `populate_from_production_plan`
- `subcontracting_management/doctype/material_issue_plan/material_issue_plan.py:192` — `check_mip_raw_materials_refreshable`
- `subcontracting_management/doctype/material_issue_plan/material_issue_plan.py:206` — `refresh_mip_raw_materials_manual`
- `subcontracting_management/doctype/material_issue_plan/material_issue_plan.py:226` — `refresh_mip_raw_materials`
- `subcontracting_management/doctype/material_issue_plan/material_issue_plan.py:618` — `refresh_weight_summary`
- `subcontracting_management/doctype/material_issue_plan/material_issue_plan.py:807` — `get_mip_batch_plan_html`
- `subcontracting_management/doctype/material_issue_plan/material_issue_plan.py:813` — `download_mip_batch_plan_pdf`
- `production_management/inspection.py:106` — `add_inspection_call`
- `production_management/inspection.py:153` — `update_inspection_call_date`
- `production_management/inspection.py:173` — `create_inspection_entry`
- `production_management/production_utils.py:89` — `get_routing_operations_for_bom`
- `production_management/production_utils.py:114` — `get_raw_materials_for_job_card`
- `production_management/doctype/material_planning/material_planning.py:456` — `@frappe.validate_and_sanitize_search_inputs`
- `production_management/doctype/material_planning/material_planning.py:482` — `get_bom_info`
- `production_management/doctype/material_planning/material_planning.py:534` — `get_so_drawings_for_bom_picker`
- `production_management/doctype/material_planning/material_planning.py:641` — `get_raw_materials`
- `production_management/doctype/material_planning/material_planning.py:744` — `check_stock_availability`
- `production_management/doctype/material_planning/material_planning.py:1097` — `move_to_exact_match`
- `production_management/doctype/material_planning/material_planning.py:1260` — `update_exact_match_from_consolidate`
- `production_management/doctype/material_planning/material_planning.py:1481` — `finalize_mapping`
- `production_management/doctype/material_planning/material_planning.py:1708` — `verify_raw_materials`
- `production_management/doctype/material_planning/material_planning.py:1724` — `get_batch_reservation_summary`
- `production_management/doctype/material_planning/material_planning.py:1760` — `get_batch_item`
- `production_management/doctype/material_planning/material_planning.py:1768` — `get_batch_stock_summary`
- `production_management/doctype/material_planning/material_planning.py:2006` — `get_batch_cross_table_usage`
- `production_management/doctype/material_planning/material_planning.py:2138` — `validate_planned_stock`
- `production_management/doctype/material_planning/material_planning.py:2233` — `reserve_batches`
- `production_management/doctype/material_planning/material_planning.py:2390` — `get_available_excess_batches`
- `production_management/doctype/material_planning/material_planning.py:2456` — `add_excess_material_mapping`
- `production_management/doctype/material_planning/material_planning.py:2551` — `get_available_virtual_excess_items`
- `production_management/doctype/material_planning/material_planning.py:2651` — `claim_virtual_excess_mapping`
- `production_management/doctype/material_planning/material_planning.py:2780` — `reserve_exact_match_batches`
- `production_management/doctype/material_planning/material_planning.py:2913` — `unreserve_exact_match_batches`
- `production_management/doctype/material_planning/material_planning.py:2954` — `check_mapping_batch_availability`
- `production_management/doctype/material_planning/material_planning.py:3015` — `unreserve_batches`
- `production_management/doctype/material_planning/material_planning.py:3167` — `reassign_batch`
- `production_management/doctype/material_planning/material_planning.py:3396` — `_test_simulate_se_release`
- `production_management/doctype/material_planning/material_planning.py:3415` — `make_production_plan`
- `production_management/doctype/material_planning/material_planning.py:3474` — `make_material_request`
- `production_management/doctype/material_planning/material_planning.py:3628` — `make_material_request_from_consolidate`
- `production_management/doctype/material_planning/material_planning.py:3766` — `update_so_difference_kg`
- `production_management/doctype/material_planning/material_planning.py:3796` — `auto_purchase_from_mp`
- `production_management/doctype/material_planning/material_planning.py:3970` — `complete_batch_mapping`
- `purchase_receipt_management/purchase_receipt.py:16` — `get_pr_item_uom`
- `purchase_receipt_management/purchase_receipt.py:257` — `get_mp_for_pr`
- `purchase_receipt_management/purchase_receipt.py:359` — `allocate_pr_stock_to_mp`
- `purchase_receipt_management/purchase_receipt.py:844` — `get_pr_mp_allocations`

## hooks.py — doc_events

doc_events = {
	"Item": {
		"validate": "manufyxinvenzaerp.item_management.item.validate_item",
	},
	"Sales Order": {
		"validate": "manufyxinvenzaerp.drawing_management.sales_order.recalculate_raw_material_qty",
	},
	"Purchase Order": {
		"validate": "manufyxinvenzaerp.purchase_order_management.purchase_order.validate_purchase_order",
		"before_submit": "manufyxinvenzaerp.purchase_order_management.purchase_order.before_submit_purchase_order",
	},
	"Purchase Receipt": {
		"validate": [
			"manufyxinvenzaerp.purchase_receipt_management.purchase_receipt.validate_purchase_receipt",
			"manufyxinvenzaerp.production_management.inspection.validate_purchase_receipt_inspection",
		],
		"before_submit": "manufyxinvenzaerp.purchase_receipt_management.purchase_receipt.before_submit_purchase_receipt",
		"on_submit": "manufyxinvenzaerp.purchase_receipt_management.purchase_receipt.on_submit_purchase_receipt",
	},
	"Batch": {
		"before_insert": "manufyxinvenzaerp.purchase_receipt_management.purchase_receipt.before_insert_batch",
	},
	"BOM": {
		"validate": "manufyxinvenzaerp.drawing_management.drawing_utils.validate_bom_from_drawing",
	},
	"Material Request": {
		"validate": "manufyxinvenzaerp.material_request_management.material_request.validate_material_request",
		"before_submit": "manufyxinvenzaerp.material_request_management.material_request.before_submit_material_request",
		"on_cancel": "manufyxinvenzaerp.production_management.doctype.material_planning.material_planning.unlink_material_request_on_cancel",
		"on_trash": "manufyxinvenzaerp.production_management.doctype.material_planning.material_planning.unlink_material_request_on_cancel",
	},
	"Request for Quotation": {
		"validate": "manufyxinvenzaerp.rfq_management.request_for_quotation.validate_rfq",
	},
	"Supplier Quotation": {
		"validate": "manufyxinvenzaerp.sq_management.supplier_quotation.validate_supplier_quotation",
		"before_submit": "manufyxinvenzaerp.sq_management.supplier_quotation.before_submit_supplier_quotation",
	},
	# --- DISABLED (client change request Phase 0.4): Work Order & Job Card reverted to
	# standard ERPNext. Kept commented for reference / possible future re-enable.
	# "Work Order": {
	# 	"on_submit": "manufyxinvenzaerp.subcontracting_management.subcontracting.on_submit_work_order",
	# 	"on_cancel": "manufyxinvenzaerp.subcontracting_management.subcontracting.on_cancel_work_order",
	# },
	# "Job Card": {
	# 	"validate": [
	# 		"manufyxinvenzaerp.production_management.job_card.validate_job_card",
	# 		"manufyxinvenzaerp.subcontracting_management.subcontracting.validate_job_card_drawing_entry",
	# 		"manufyxinvenzaerp.production_management.inspection.validate_job_card_inspection",
	# 	],
	# 	"before_submit": [
	# 		"manufyxinvenzaerp.subcontracting_management.subcontracting.before_submit_job_card_drawing_entry",
	# 		"manufyxinvenzaerp.production_management.inspection.before_submit_job_card_inspection_gate",
	# 	],
	# 	"on_update": "manufyxinvenzaerp.subcontracting_management.subcontracting.on_update_job_card_drawing_entry",
	# 	"on_submit": "manufyxinvenzaerp.subcontracting_management.subcontracting.on_submit_job_card_drawing_entry",
	# },
	"Stock Entry": {
		"validate": "manufyxinvenzaerp.production_management.stock_entry.validate_stock_entry",
		# "before_submit": "manufyxinvenzaerp.production_management.job_card.before_submit_manufacture_stock_entry",
		# DISABLED (Phase 0.4): only relevant to Work Order/Job Card's custom consumption flow.
		"on_submit": "manufyxinvenzaerp.production_management.stock_entry.on_submit_stock_entry",
		"on_cancel": "manufyxinvenzaerp.production_management.stock_entry.on_cancel_stock_entry",
	},
	"Supplier Operation Entry": {
		"validate": [
			"manufyxinvenzaerp.subcontracting_management.subcontracting.validate_supplier_operation_entry",
			"manufyxinvenzaerp.production_management.inspection.validate_soe_inspection",
		],
		"before_submit": [
			"manufyxinvenzaerp.subcontracting_management.subcontracting.before_submit_supplier_operation_entry",
			"manufyxinvenzaerp.production_management.inspection.before_submit_soe_inspection_gate",
		],
		"on_update": "manufyxinvenzaerp.subcontracting_management.subcontracting.on_update_supplier_operation_entry",
		"on_submit": "manufyxinvenzaerp.subcontracting_management.subcontracting.on_submit_supplier_operation_entry",
		"before_delete": "manufyxinvenzaerp.subcontracting_management.subcontracting.before_delete_supplier_operation_entry",
	},
	"Subcontracting Order": {
		"on_cancel": "manufyxinvenzaerp.subcontracting_management.subcontracting.on_cancel_subcontracting_order",
	},
	"Production Plan": {
		"autoname": "manufyxinvenzaerp.production_plan_management.production_plan.autoname_production_plan",
		"validate": [
			"manufyxinvenzaerp.production_plan_management.production_plan.after_save_production_plan",
			"manufyxinvenzaerp.production_plan_management.production_plan.validate_process_planning_contiguity",
		],
		"on_trash": "manufyxinvenzaerp.production_plan_management.production_plan.unlink_production_plan_on_trash",
		"on_cancel": "manufyxinvenzaerp.production_plan_management.production_plan.unlink_production_plan_on_trash",
	},
	"Inspection Entry": {
		"on_submit": "manufyxinvenzaerp.production_management.inspection.on_submit_inspection_entry",
	},
	"Payment Request": {
		"validate": "manufyxinvenzaerp.accounts_management.payment_request.validate_payment_request",
	},
	"Payment Entry": {
		"on_submit": "manufyxinvenzaerp.accounts_management.payment_entry.on_submit_payment_entry",
		"on_cancel": "manufyxinvenzaerp.accounts_management.payment_entry.on_cancel_payment_entry",
	},
}

## hooks.py — overrides

override_doctype_class = {
    "BOM": "manufyxinvenzaerp.drawing_management.bom_class_override.BOM",
    "Subcontracting Order": "manufyxinvenzaerp.subcontracting_management.overrides.CustomSubcontractingOrder",
    "Stock Entry": "manufyxinvenzaerp.subcontracting_management.overrides.CustomStockEntry",
}


override_doctype_dashboards = {
	"Sales Order": "manufyxinvenzaerp.drawing_management.drawing_utils.get_so_dashboard_data",
	"Subcontracting Order": "manufyxinvenzaerp.subcontracting_management.subcontracting.get_sco_dashboard_data",
}


## hooks.py — fixtures & lifecycle

fixtures = ["Custom Field", "Property Setter"]
after_install = "manufyxinvenzaerp.setup.after_install"
after_migrate = "manufyxinvenzaerp.setup.after_migrate"

