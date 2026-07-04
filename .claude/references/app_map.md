# app_map — manufyxinvenzaerp

_Generated: 2026-07-05 02:48:09_

## Modules

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
- www

## Python files

_Total: 110_

- config/__init__.py
- drawing_management/bom_class_override.py
- drawing_management/doctype/drawing/drawing.py
- drawing_management/doctype/drawing/__init__.py
- drawing_management/doctype/drawing_item/drawing_item.py
- drawing_management/doctype/drawing_item/__init__.py
- drawing_management/doctype/__init__.py
- drawing_management/doctype/nature_of_work/__init__.py
- drawing_management/doctype/nature_of_work/nature_of_work.py
- drawing_management/doctype/production_plan_bom_raw_material/__init__.py
- drawing_management/doctype/production_plan_bom_raw_material/production_plan_bom_raw_material.py
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
- patches/v1/fix_bom_item_number_field_type.py
- patches/v1/__init__.py
- patches/v1/remove_sco_transfer_fields.py
- production_management/doctype/__init__.py
- production_management/doctype/job_card_raw_material/__init__.py
- production_management/doctype/job_card_raw_material/job_card_raw_material.py
- production_management/doctype/material_planning_available_raw_material/__init__.py
- production_management/doctype/material_planning_available_raw_material/material_planning_available_raw_material.py
- production_management/doctype/material_planning_bom_item/__init__.py
- production_management/doctype/material_planning_bom_item/material_planning_bom_item.py
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
- production_management/job_card.py
- production_management/production_utils.py
- production_management/report/__init__.py
- production_management/report/manufyxinvenza_stock_balance/__init__.py
- production_management/report/manufyxinvenza_stock_balance/manufyxinvenza_stock_balance.py
- production_management/stock_entry.py
- production_management/test_release.py
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
- subcontracting_management/doctype/supplier_operation_entry/__init__.py
- subcontracting_management/doctype/supplier_operation_entry/supplier_operation_entry.py
- subcontracting_management/doctype/supplier_operation_item/__init__.py
- subcontracting_management/doctype/supplier_operation_item/supplier_operation_item.py
- subcontracting_management/__init__.py
- subcontracting_management/material_issue_plan_transfer.py
- subcontracting_management/overrides.py
- subcontracting_management/subcontracting.py
- templates/__init__.py
- templates/pages/__init__.py
- tests/create_full_test_entry.py
- tests/create_test_data.py
- tests/__init__.py
- tests/test_alternate_item.py
- tests/test_classification_logic.py
- tests/test_e2e_material_planning.py
- tests/test_material_planning.py
- tests/test_po_edge_cases.py
- tests/test_purchase_order_creation.py
- tests/test_unavailable_actions.py

## JavaScript files

_Total: 10_

- drawing_management/doctype/drawing/drawing.js
- production_management/doctype/material_planning/material_planning.js
- production_management/report/manufyxinvenza_stock_balance/manufyxinvenza_stock_balance.js
- public/js/batch.js
- public/js/bom.js
- public/js/item.js
- public/js/production_plan.js
- public/js/purchase_order.js
- public/js/purchase_receipt.js
- subcontracting_management/doctype/material_issue_plan/material_issue_plan.js

## JSON files

_Total: 29_

- drawing_management/doctype/drawing/drawing.json
- drawing_management/doctype/drawing_item/drawing_item.json
- drawing_management/doctype/nature_of_work/nature_of_work.json
- drawing_management/doctype/production_plan_bom_raw_material/production_plan_bom_raw_material.json
- drawing_management/doctype/sales_order_drawing_raw_material/sales_order_drawing_raw_material.json
- drawing_management/doctype/sales_order_duno_item/sales_order_duno_item.json
- fixtures/custom_field.json
- fixtures/property_setter.json
- manufyxinvenzaerp/doctype/manufyxinvenza_settings/manufyxinvenza_settings.json
- production_management/doctype/job_card_raw_material/job_card_raw_material.json
- production_management/doctype/material_planning_available_raw_material/material_planning_available_raw_material.json
- production_management/doctype/material_planning_bom_item/material_planning_bom_item.json
- production_management/doctype/material_planning_material_mapping/material_planning_material_mapping.json
- production_management/doctype/material_planning/material_planning.json
- production_management/doctype/material_planning_raw_material/material_planning_raw_material.json
- production_management/doctype/material_planning_unavailable_item/material_planning_unavailable_item.json
- production_management/doctype/process_planning/process_planning.json
- production_management/doctype/production_plan_available_raw_material/production_plan_available_raw_material.json
- production_management/doctype/storage_location/storage_location.json
- production_management/doctype/store_location/store_location.json
- production_management/report/manufyxinvenza_stock_balance/manufyxinvenza_stock_balance.json
- subcontracting_management/doctype/material_issue_plan/material_issue_plan.json
- subcontracting_management/doctype/material_issue_plan_raw_material/material_issue_plan_raw_material.json
- subcontracting_management/doctype/sco_drawing_item/sco_drawing_item.json
- subcontracting_management/doctype/sco_excess_material_item/sco_excess_material_item.json
- subcontracting_management/doctype/soe_consumption_log/soe_consumption_log.json
- subcontracting_management/doctype/soe_drawing_detail/soe_drawing_detail.json
- subcontracting_management/doctype/supplier_operation_entry/supplier_operation_entry.json
- subcontracting_management/doctype/supplier_operation_item/supplier_operation_item.json

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

### nature_of_work
- Path: `drawing_management/doctype/nature_of_work`
- Controller: `drawing_management/doctype/nature_of_work/nature_of_work.py`
- Client script: none

### production_plan_bom_raw_material
- Path: `drawing_management/doctype/production_plan_bom_raw_material`
- Controller: `drawing_management/doctype/production_plan_bom_raw_material/production_plan_bom_raw_material.py`
- Client script: none

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

### job_card_raw_material
- Path: `production_management/doctype/job_card_raw_material`
- Controller: `production_management/doctype/job_card_raw_material/job_card_raw_material.py`
- Client script: none

### material_planning_available_raw_material
- Path: `production_management/doctype/material_planning_available_raw_material`
- Controller: `production_management/doctype/material_planning_available_raw_material/material_planning_available_raw_material.py`
- Client script: none

### material_planning_bom_item
- Path: `production_management/doctype/material_planning_bom_item`
- Controller: `production_management/doctype/material_planning_bom_item/material_planning_bom_item.py`
- Client script: none

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
  - _apply_rwd_group_allocations:
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
  - move_to_exact_match:
  - finalize_mapping:
  - _verify_nos_vs_qty:
  - verify_raw_materials:
  - get_batch_reservation_summary:
  - get_batch_item:
  - get_batch_stock_summary:
  - _get_batch_total_stock:
  - _get_batch_reserved_by_others:
  - _get_non_batch_reserved_by_others:
  - _update_bom_item_weights:
  - _calc_kg_per_nos:
  - _calc_usable_nos_split:
  - _row_get:
  - _calc_group_rwd_allocations:
  - reserve_batches:
  - reserve_exact_match_batches:
  - unreserve_exact_match_batches:
  - check_mapping_batch_availability:
  - unreserve_batches:
  - reassign_batch:
  - _apply_batch_to_mapping_row:
  - _test_simulate_se_release:
  - __init__:
  - get:
  - __init__:
  - make_production_plan:
  - make_material_request:
  - update_so_difference_kg:
  - unlink_material_request_on_cancel:
  - auto_purchase_from_mp:

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

### material_issue_plan
- Path: `subcontracting_management/doctype/material_issue_plan`
- Controller: `subcontracting_management/doctype/material_issue_plan/material_issue_plan.py`
- Client script: `subcontracting_management/doctype/material_issue_plan/material_issue_plan.js`
- Methods:
  - after_insert:
  - create_from_subcontracting_order:
  - populate_from_production_plan:
  - refresh_mip_raw_materials:
  - refresh_weight_summary:
  - get_target_context:
  - _resolve_warehouses:

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

### supplier_operation_entry
- Path: `subcontracting_management/doctype/supplier_operation_entry`
- Controller: `subcontracting_management/doctype/supplier_operation_entry/supplier_operation_entry.py`
- Client script: none

### supplier_operation_item
- Path: `subcontracting_management/doctype/supplier_operation_item`
- Controller: `subcontracting_management/doctype/supplier_operation_item/supplier_operation_item.py`
- Client script: none

## Module-level controllers

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
  - 7:create_drawings_from_so:
  - 45:mark_as_final_revision:
  - 59:get_batches_for_drawing_item:
  - 91:create_bom_from_drawing:
  - 148:validate_bom_from_drawing:
  - 203:create_production_plan_from_bom:
  - 256:parse_drawing_items_csv:
  - 370:get_so_dashboard_data:

### drawing_management/sales_order.py
Functions:
  - 5:recalculate_raw_material_qty:

### drawing_management/so_drawing_import.py
Functions:
  - 10:_calc_qty:
  - 23:_get_file_path:
  - 32:_parse_excel:
  - 123:parse_bom_excel:
  - 318:_bulk_insert:
  - 338:create_drawings_from_import:
  - 489:process_drawings:
  - 619:verify_raw_materials:
  - 677:download_bom_template:
  - 719:clear_drawing_import:

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
  - 16:get_mr_item_uom:
  - 32:validate_material_request:
  - 38:before_submit_material_request:
  - 43:_recalculate_qty:
  - 62:_check_missing_fields:

### production_management/job_card.py
Functions:
  - 8:validate_job_card:
  - 59:_get_wip_stock:
  - 67:before_submit_manufacture_stock_entry:

### production_management/production_utils.py
Functions:
  - 29:create_operations_workstations_routing:
  - 37:_create_operations:
  - 47:_create_workstations:
  - 62:_create_routing:
  - 95:get_routing_operations_for_bom:
  - 120:get_raw_materials_for_job_card:
  - 171:_get_transferred_qty_for_item:
  - 182:_get_previous_operation_consumed:
  - 221:_get_prev_soe_consumed_for_jc:
  - 265:validate_final_operation_consumption:

### production_management/stock_entry.py
Functions:
  - 8:validate_stock_entry:
  - 41:on_submit_stock_entry:
  - 113:_reduce_batch_sec_qty:
  - 118:_batch_total_kg_all_wh:
  - 131:_populate_manufacture_sec_qty:
  - 153:_collect_consumed_batches:
  - 186:_linked_material_plannings:
  - 217:_release_material_planning_reservations:
  - 267:on_cancel_stock_entry:
  - 287:_restore_batch_sec_qty:
  - 305:_restore_material_planning_reservations:
  - 358:_update_sco_transferred_weight:
  - 426:_update_sco_cnc_weight:
  - 474:_update_wo_transferred_weight:
  - 518:_update_wo_cnc_weight:
  - 563:_calc_qty:

### production_management/test_release.py

### production_plan_management/production_plan.py
Functions:
  - 21:get_sbb_available_qty:
  - 115:get_items_for_material_requests:
  - 308:get_exploded_items:
  - 315:get_bom_items_direct:
  - 381:get_uom_conversion_factor:
  - 387:get_warehouse_list:
  - 403:get_material_request_items:
  - 492:get_mp_planned_weights:
  - 507:_calc_mp_drawing_weight:
  - 524:_calc_mp_weight:
  - 544:get_pp_drawings_for_picker:
  - 558:_picker_rows_from_mp:
  - 605:_picker_rows_from_so:
  - 660:_mark_already_in_pp:
  - 691:get_operations_from_routing:
  - 704:get_standard_routing_operations:
  - 717:make_material_request:
  - 788:after_save_production_plan:
  - 793:validate_process_planning_contiguity:
  - 818:unlink_production_plan_on_trash:
  - 831:_recalculate_sec_qty:

### pull_live.py
Functions:
  - 15:get_session:
  - 23:fetch_list:
  - 43:fetch_doc:
  - 49:upsert:
  - 75:sync_singles:
  - 91:sync_doctype:
  - 113:run:

### purchase_order_management/purchase_order.py
Functions:
  - 17:get_po_item_uom:
  - 33:validate_purchase_order:
  - 44:_copy_from_mr_item:
  - 57:before_submit_purchase_order:
  - 62:_recalculate_qty:
  - 81:_check_missing_fields:

### purchase_receipt_management/purchase_receipt.py
Functions:
  - 19:get_pr_item_uom:
  - 35:validate_purchase_receipt:
  - 46:before_submit_purchase_receipt:
  - 51:before_insert_batch:
  - 59:_setup_batch_from_purchase_receipt:
  - 131:_setup_batch_from_stock_entry:
  - 197:_get_receipt_suffix:
  - 205:_get_se_suffix:
  - 213:_copy_from_po_item:
  - 227:_recalculate_qty:
  - 246:_check_missing_fields:
  - 268:get_mp_for_pr:
  - 287:allocate_pr_stock_to_mp:
  - 418:on_submit_purchase_receipt:

### rfq_management/request_for_quotation.py
Functions:
  - 15:validate_rfq:
  - 20:_copy_from_mr_item:

### sample_data.py
Functions:
  - 4:run:

### setup.py
Functions:
  - 1231:after_install:
  - 1276:after_migrate:
  - 1322:setup_storage_location:
  - 1344:create_item_client_script:
  - 1360:create_item_custom_fields:
  - 1436:create_purchase_order_custom_fields:
  - 1542:hide_purchase_order_weight_fields:
  - 1556:create_purchase_order_client_script:
  - 1572:create_purchase_receipt_custom_fields:
  - 1681:create_batch_custom_fields:
  - 1746:create_purchase_receipt_client_script:
  - 1762:create_material_request_custom_fields:
  - 1882:create_material_request_client_script:
  - 1898:create_rfq_custom_fields:
  - 1974:create_rfq_client_script:
  - 1990:create_sq_custom_fields:
  - 2069:create_sq_client_script:
  - 2085:create_bom_custom_fields:
  - 2192:create_so_custom_fields:
  - 2269:create_so_client_script:
  - 2285:create_bom_client_script:
  - 2305:create_production_plan_custom_fields:
  - 2529:create_production_plan_client_script:
  - 2551:create_job_card_custom_fields:
  - 2816:create_job_card_client_script:
  - 2834:create_stock_entry_custom_fields:
  - 2974:create_stock_entry_client_script:
  - 2996:remove_sco_purchase_order_mandatory:
  - 3007:create_sco_custom_fields:
  - 3424:create_sco_client_script:
  - 3440:create_sco_ops_client_script:
  - 3456:create_soe_client_script:
  - 3472:create_manufacturing_settings_custom_fields:
  - 3499:create_work_order_custom_fields:
  - 3674:layout_work_order_fields:
  - 3772:create_job_card_drawing_fields:
  - 3840:layout_job_card_fields:
  - 4325:create_wo_client_script:
  - 4342:create_wo_ops_client_script:
  - 4359:create_jc_drawing_client_script:
  - 4380:create_material_planning_auto_purchase_fields:

### sq_management/supplier_quotation.py
Functions:
  - 27:get_sq_item_uom:
  - 43:validate_supplier_quotation:
  - 50:before_submit_supplier_quotation:
  - 55:_copy_from_rfq_item_if_blank:
  - 83:_has_custom_data:
  - 88:_recalculate_qty:
  - 107:_check_missing_fields:

### subcontracting_management/material_issue_plan_transfer.py
Functions:
  - 25:_linked_mp_names:
  - 37:_tag_stock_entry:
  - 45:get_mip_pending_items:
  - 144:create_mip_transfer_entry:
  - 183:create_mip_partial_transfer:
  - 238:create_mip_cnc_forward_entry:
  - 328:create_mip_excess_return_entry:

### subcontracting_management/overrides.py
Functions:
  - 11:_is_pp_flow_sco:

### subcontracting_management/subcontracting.py
Functions:
  - 12:get_sco_dashboard_data:
  - 26:create_sco_from_production_plan:
  - 151:create_work_order_from_pp:
  - 286:create_supplier_operation_entries:
  - 303:create_send_to_subcontractor_entry:
  - 399:get_sco_pending_items:
  - 509:create_partial_transfer:
  - 570:create_cnc_to_supplier_entry:
  - 673:get_soe_summary:
  - 719:create_return_stock_entry:
  - 777:create_finished_goods_entry:
  - 864:validate_supplier_operation_entry:
  - 977:before_submit_supplier_operation_entry:
  - 1011:_propagate_available_to_next:
  - 1033:_propagate_drawing_nos_to_next:
  - 1073:_update_sco_drawing_item_completion:
  - 1097:on_update_supplier_operation_entry:
  - 1104:_push_sco_completion_to_wo:
  - 1144:on_submit_supplier_operation_entry:
  - 1172:before_delete_supplier_operation_entry:
  - 1194:on_cancel_subcontracting_order:
  - 1215:_build_soe_drawing_rows:
  - 1253:_create_soes_for_sco:
  - 1316:_get_mp_total_weight:
  - 1344:_get_mp_actual_transferred_weight:
  - 1390:_refresh_wo_drawing_transferred_weights:
  - 1445:_get_sco_transfer_warehouses:
  - 1457:_refresh_sco_drawing_transferred_weights:
  - 1505:_get_mp_drawing_weight:
  - 1522:_get_mp_mapped_weight_by_duno:
  - 1577:_get_mp_excess_by_duno:
  - 1596:_get_mp_reserved_batches:
  - 1690:_get_pp_planned_qty:
  - 1705:backfill_drawing_item_qty:
  - 1725:_get_supplier_wh_consumption_items:
  - 1769:get_wo_pending_items:
  - 1874:create_partial_wo_transfer:
  - 1930:create_cnc_to_wip_entry:
  - 2029:create_return_stock_entry_for_wo:
  - 2081:get_jc_summary:
  - 2126:on_submit_work_order:
  - 2134:on_cancel_work_order:
  - 2143:validate_job_card_drawing_entry:
  - 2257:before_submit_job_card_drawing_entry:
  - 2294:_propagate_drawing_nos_to_next_jc:
  - 2334:_update_wo_drawing_item_completion:
  - 2359:on_update_job_card_drawing_entry:
  - 2367:on_submit_job_card_drawing_entry:
  - 2393:_build_jc_drawing_rows:
  - 2426:_populate_jcs_for_wo:

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

### tests/test_alternate_item.py
Functions:
  - 15:_get_unavailable_rows:
  - 23:_clear_mr_links:

### tests/test_classification_logic.py
Functions:
  - 24:_mock_sbb:

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

## Whitelisted API methods

- `item_management/item.py:125` — `has_item_transactions`
- `purchase_order_management/purchase_order.py:17` — `get_po_item_uom`
- `sq_management/supplier_quotation.py:27` — `get_sq_item_uom`
- `drawing_management/drawing_utils.py:7` — `create_drawings_from_so`
- `drawing_management/drawing_utils.py:45` — `mark_as_final_revision`
- `drawing_management/drawing_utils.py:59` — `get_batches_for_drawing_item`
- `drawing_management/drawing_utils.py:91` — `create_bom_from_drawing`
- `drawing_management/drawing_utils.py:203` — `create_production_plan_from_bom`
- `drawing_management/drawing_utils.py:256` — `parse_drawing_items_csv`
- `drawing_management/bom_class_override.py:353` — `get_routing`
- `drawing_management/bom_class_override.py:424` — `get_bom_material_detail`
- `drawing_management/bom_class_override.py:509` — `update_cost`
- `drawing_management/bom_class_override.py:1255` — `get_bom_items`
- `drawing_management/bom_class_override.py:1288` — `get_children`
- `drawing_management/bom_class_override.py:1467` — `get_bom_diff`
- `drawing_management/bom_class_override.py:1522` — `@frappe.validate_and_sanitize_search_inputs`
- `drawing_management/bom_class_override.py:1574` — `make_variant_bom`
- `drawing_management/so_drawing_import.py:123` — `parse_bom_excel`
- `drawing_management/so_drawing_import.py:338` — `create_drawings_from_import`
- `drawing_management/so_drawing_import.py:489` — `process_drawings`
- `drawing_management/so_drawing_import.py:619` — `verify_raw_materials`
- `drawing_management/so_drawing_import.py:677` — `download_bom_template`
- `drawing_management/so_drawing_import.py:719` — `clear_drawing_import`
- `drawing_management/doctype/drawing/drawing.py:125` — `check_existing_bom`
- `production_plan_management/production_plan.py:115` — `get_items_for_material_requests`
- `production_plan_management/production_plan.py:492` — `get_mp_planned_weights`
- `production_plan_management/production_plan.py:544` — `get_pp_drawings_for_picker`
- `production_plan_management/production_plan.py:691` — `get_operations_from_routing`
- `production_plan_management/production_plan.py:704` — `get_standard_routing_operations`
- `production_plan_management/production_plan.py:717` — `make_material_request`
- `material_request_management/material_request.py:16` — `get_mr_item_uom`
- `subcontracting_management/material_issue_plan_transfer.py:45` — `get_mip_pending_items`
- `subcontracting_management/material_issue_plan_transfer.py:144` — `create_mip_transfer_entry`
- `subcontracting_management/material_issue_plan_transfer.py:183` — `create_mip_partial_transfer`
- `subcontracting_management/material_issue_plan_transfer.py:238` — `create_mip_cnc_forward_entry`
- `subcontracting_management/material_issue_plan_transfer.py:328` — `create_mip_excess_return_entry`
- `subcontracting_management/subcontracting.py:26` — `create_sco_from_production_plan`
- `subcontracting_management/subcontracting.py:151` — `create_work_order_from_pp`
- `subcontracting_management/subcontracting.py:286` — `create_supplier_operation_entries`
- `subcontracting_management/subcontracting.py:303` — `create_send_to_subcontractor_entry`
- `subcontracting_management/subcontracting.py:399` — `get_sco_pending_items`
- `subcontracting_management/subcontracting.py:509` — `create_partial_transfer`
- `subcontracting_management/subcontracting.py:570` — `create_cnc_to_supplier_entry`
- `subcontracting_management/subcontracting.py:673` — `get_soe_summary`
- `subcontracting_management/subcontracting.py:719` — `create_return_stock_entry`
- `subcontracting_management/subcontracting.py:777` — `create_finished_goods_entry`
- `subcontracting_management/subcontracting.py:1705` — `backfill_drawing_item_qty`
- `subcontracting_management/subcontracting.py:1769` — `get_wo_pending_items`
- `subcontracting_management/subcontracting.py:1874` — `create_partial_wo_transfer`
- `subcontracting_management/subcontracting.py:1930` — `create_cnc_to_wip_entry`
- `subcontracting_management/subcontracting.py:2029` — `create_return_stock_entry_for_wo`
- `subcontracting_management/subcontracting.py:2081` — `get_jc_summary`
- `subcontracting_management/doctype/material_issue_plan/material_issue_plan.py:17` — `create_from_subcontracting_order`
- `subcontracting_management/doctype/material_issue_plan/material_issue_plan.py:36` — `populate_from_production_plan`
- `subcontracting_management/doctype/material_issue_plan/material_issue_plan.py:96` — `refresh_mip_raw_materials`
- `subcontracting_management/doctype/material_issue_plan/material_issue_plan.py:185` — `refresh_weight_summary`
- `production_management/production_utils.py:95` — `get_routing_operations_for_bom`
- `production_management/production_utils.py:120` — `get_raw_materials_for_job_card`
- `production_management/doctype/material_planning/material_planning.py:270` — `@frappe.validate_and_sanitize_search_inputs`
- `production_management/doctype/material_planning/material_planning.py:296` — `get_bom_info`
- `production_management/doctype/material_planning/material_planning.py:348` — `get_so_drawings_for_bom_picker`
- `production_management/doctype/material_planning/material_planning.py:455` — `get_raw_materials`
- `production_management/doctype/material_planning/material_planning.py:543` — `check_stock_availability`
- `production_management/doctype/material_planning/material_planning.py:836` — `move_to_exact_match`
- `production_management/doctype/material_planning/material_planning.py:999` — `finalize_mapping`
- `production_management/doctype/material_planning/material_planning.py:1192` — `verify_raw_materials`
- `production_management/doctype/material_planning/material_planning.py:1208` — `get_batch_reservation_summary`
- `production_management/doctype/material_planning/material_planning.py:1242` — `get_batch_item`
- `production_management/doctype/material_planning/material_planning.py:1250` — `get_batch_stock_summary`
- `production_management/doctype/material_planning/material_planning.py:1454` — `reserve_batches`
- `production_management/doctype/material_planning/material_planning.py:1577` — `reserve_exact_match_batches`
- `production_management/doctype/material_planning/material_planning.py:1694` — `unreserve_exact_match_batches`
- `production_management/doctype/material_planning/material_planning.py:1735` — `check_mapping_batch_availability`
- `production_management/doctype/material_planning/material_planning.py:1801` — `unreserve_batches`
- `production_management/doctype/material_planning/material_planning.py:1842` — `reassign_batch`
- `production_management/doctype/material_planning/material_planning.py:1989` — `_test_simulate_se_release`
- `production_management/doctype/material_planning/material_planning.py:2008` — `make_production_plan`
- `production_management/doctype/material_planning/material_planning.py:2066` — `make_material_request`
- `production_management/doctype/material_planning/material_planning.py:2217` — `update_so_difference_kg`
- `production_management/doctype/material_planning/material_planning.py:2272` — `auto_purchase_from_mp`
- `purchase_receipt_management/purchase_receipt.py:19` — `get_pr_item_uom`
- `purchase_receipt_management/purchase_receipt.py:268` — `get_mp_for_pr`
- `purchase_receipt_management/purchase_receipt.py:287` — `allocate_pr_stock_to_mp`

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
		"validate": "manufyxinvenzaerp.purchase_receipt_management.purchase_receipt.validate_purchase_receipt",
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
	"Work Order": {
		"on_submit": "manufyxinvenzaerp.subcontracting_management.subcontracting.on_submit_work_order",
		"on_cancel": "manufyxinvenzaerp.subcontracting_management.subcontracting.on_cancel_work_order",
	},
	"Job Card": {
		"validate": [
			"manufyxinvenzaerp.production_management.job_card.validate_job_card",
			"manufyxinvenzaerp.subcontracting_management.subcontracting.validate_job_card_drawing_entry",
		],
		"before_submit": "manufyxinvenzaerp.subcontracting_management.subcontracting.before_submit_job_card_drawing_entry",
		"on_update": "manufyxinvenzaerp.subcontracting_management.subcontracting.on_update_job_card_drawing_entry",
		"on_submit": "manufyxinvenzaerp.subcontracting_management.subcontracting.on_submit_job_card_drawing_entry",
	},
	"Stock Entry": {
		"validate": "manufyxinvenzaerp.production_management.stock_entry.validate_stock_entry",
		"before_submit": "manufyxinvenzaerp.production_management.job_card.before_submit_manufacture_stock_entry",
		"on_submit": "manufyxinvenzaerp.production_management.stock_entry.on_submit_stock_entry",
		"on_cancel": "manufyxinvenzaerp.production_management.stock_entry.on_cancel_stock_entry",
	},
	"Supplier Operation Entry": {
		"validate": "manufyxinvenzaerp.subcontracting_management.subcontracting.validate_supplier_operation_entry",
		"before_submit": "manufyxinvenzaerp.subcontracting_management.subcontracting.before_submit_supplier_operation_entry",
		"on_update": "manufyxinvenzaerp.subcontracting_management.subcontracting.on_update_supplier_operation_entry",
		"on_submit": "manufyxinvenzaerp.subcontracting_management.subcontracting.on_submit_supplier_operation_entry",
		"before_delete": "manufyxinvenzaerp.subcontracting_management.subcontracting.before_delete_supplier_operation_entry",
	},
	"Subcontracting Order": {
		"on_cancel": "manufyxinvenzaerp.subcontracting_management.subcontracting.on_cancel_subcontracting_order",
	},
	"Production Plan": {
		"validate": [
			"manufyxinvenzaerp.production_plan_management.production_plan.after_save_production_plan",
			"manufyxinvenzaerp.production_plan_management.production_plan.validate_process_planning_contiguity",
		],
		"on_trash": "manufyxinvenzaerp.production_plan_management.production_plan.unlink_production_plan_on_trash",
		"on_cancel": "manufyxinvenzaerp.production_plan_management.production_plan.unlink_production_plan_on_trash",
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

