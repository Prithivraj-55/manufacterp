# doctypes — manufyxinvenzaerp

_Generated: 2026-07-04 00:33:54_

## drawing

| Key | Value |
|-----|-------|
| Module | drawing_management |
| Path | `drawing_management/doctype/drawing` |
| Controller | `drawing_management/doctype/drawing/drawing.py` |
| Client script | `drawing_management/doctype/drawing/drawing.js` |

### Methods

| Method | Whitelisted |
|--------|-------------|
| ` before_insert` | no |
| ` validate` | no |
| ` before_submit` | no |
| ` on_cancel` | no |
| ` _recalculate_all` | no |
| ` _check_missing_fields` | no |
| ` _calculate_totals` | no |
| ` _recalculate_row_qty` | no |
| ` _recalculate_row_totals` | no |
| ` _check_row_missing_fields` | no |
| ` check_existing_bom` | no |

---

## drawing_item

| Key | Value |
|-----|-------|
| Module | drawing_management |
| Path | `drawing_management/doctype/drawing_item` |
| Controller | `drawing_management/doctype/drawing_item/drawing_item.py` |
| Client script | none |

---

## nature_of_work

| Key | Value |
|-----|-------|
| Module | drawing_management |
| Path | `drawing_management/doctype/nature_of_work` |
| Controller | `drawing_management/doctype/nature_of_work/nature_of_work.py` |
| Client script | none |

---

## production_plan_bom_raw_material

| Key | Value |
|-----|-------|
| Module | drawing_management |
| Path | `drawing_management/doctype/production_plan_bom_raw_material` |
| Controller | `drawing_management/doctype/production_plan_bom_raw_material/production_plan_bom_raw_material.py` |
| Client script | none |

---

## sales_order_drawing_raw_material

| Key | Value |
|-----|-------|
| Module | drawing_management |
| Path | `drawing_management/doctype/sales_order_drawing_raw_material` |
| Controller | `drawing_management/doctype/sales_order_drawing_raw_material/sales_order_drawing_raw_material.py` |
| Client script | none |

---

## sales_order_duno_item

| Key | Value |
|-----|-------|
| Module | drawing_management |
| Path | `drawing_management/doctype/sales_order_duno_item` |
| Controller | `drawing_management/doctype/sales_order_duno_item/sales_order_duno_item.py` |
| Client script | none |

---

## manufyxinvenza_settings

| Key | Value |
|-----|-------|
| Module | manufyxinvenzaerp |
| Path | `manufyxinvenzaerp/doctype/manufyxinvenza_settings` |
| Controller | `manufyxinvenzaerp/doctype/manufyxinvenza_settings/manufyxinvenza_settings.py` |
| Client script | none |

---

## job_card_raw_material

| Key | Value |
|-----|-------|
| Module | production_management |
| Path | `production_management/doctype/job_card_raw_material` |
| Controller | `production_management/doctype/job_card_raw_material/job_card_raw_material.py` |
| Client script | none |

---

## material_planning_available_raw_material

| Key | Value |
|-----|-------|
| Module | production_management |
| Path | `production_management/doctype/material_planning_available_raw_material` |
| Controller | `production_management/doctype/material_planning_available_raw_material/material_planning_available_raw_material.py` |
| Client script | none |

---

## material_planning_bom_item

| Key | Value |
|-----|-------|
| Module | production_management |
| Path | `production_management/doctype/material_planning_bom_item` |
| Controller | `production_management/doctype/material_planning_bom_item/material_planning_bom_item.py` |
| Client script | none |

---

## material_planning_material_mapping

| Key | Value |
|-----|-------|
| Module | production_management |
| Path | `production_management/doctype/material_planning_material_mapping` |
| Controller | `production_management/doctype/material_planning_material_mapping/material_planning_material_mapping.py` |
| Client script | none |

---

## material_planning

| Key | Value |
|-----|-------|
| Module | production_management |
| Path | `production_management/doctype/material_planning` |
| Controller | `production_management/doctype/material_planning/material_planning.py` |
| Client script | `production_management/doctype/material_planning/material_planning.js` |

### Methods

| Method | Whitelisted |
|--------|-------------|
| ` validate` | no |
| ` _move_skipped_arm_to_mapping` | no |
| ` _validate_batch_calc_qty` | no |
| ` search_bom` | no |
| ` get_bom_info` | no |
| ` get_so_drawings_for_bom_picker` | no |
| ` get_raw_materials` | no |
| ` check_stock_availability` | no |
| ` _alloc_sec_qty` | no |
| ` _get_non_batch_stock` | no |
| ` move_to_exact_match` | no |
| ` finalize_mapping` | no |
| ` get_batch_reservation_summary` | no |
| ` get_batch_item` | no |
| ` get_batch_stock_summary` | no |
| ` _get_batch_total_stock` | no |
| ` _get_batch_reserved_by_others` | no |
| ` _get_non_batch_reserved_by_others` | no |
| ` _update_bom_item_weights` | no |
| ` reserve_batches` | no |
| ` reserve_exact_match_batches` | no |
| ` unreserve_exact_match_batches` | no |
| ` check_mapping_batch_availability` | no |
| ` unreserve_batches` | no |
| ` _test_simulate_se_release` | no |
| ` __init__` | no |
| ` get` | no |
| ` __init__` | no |
| ` make_production_plan` | no |
| ` make_material_request` | no |
| ` update_so_difference_kg` | no |
| ` unlink_material_request_on_cancel` | no |
| ` auto_purchase_from_mp` | no |

---

## material_planning_raw_material

| Key | Value |
|-----|-------|
| Module | production_management |
| Path | `production_management/doctype/material_planning_raw_material` |
| Controller | `production_management/doctype/material_planning_raw_material/material_planning_raw_material.py` |
| Client script | none |

---

## material_planning_unavailable_item

| Key | Value |
|-----|-------|
| Module | production_management |
| Path | `production_management/doctype/material_planning_unavailable_item` |
| Controller | `production_management/doctype/material_planning_unavailable_item/material_planning_unavailable_item.py` |
| Client script | none |

---

## process_planning

| Key | Value |
|-----|-------|
| Module | production_management |
| Path | `production_management/doctype/process_planning` |
| Controller | `production_management/doctype/process_planning/process_planning.py` |
| Client script | none |

---

## production_plan_available_raw_material

| Key | Value |
|-----|-------|
| Module | production_management |
| Path | `production_management/doctype/production_plan_available_raw_material` |
| Controller | `production_management/doctype/production_plan_available_raw_material/production_plan_available_raw_material.py` |
| Client script | none |

---

## storage_location

| Key | Value |
|-----|-------|
| Module | production_management |
| Path | `production_management/doctype/storage_location` |
| Controller | `production_management/doctype/storage_location/storage_location.py` |
| Client script | none |

---

## store_location

| Key | Value |
|-----|-------|
| Module | production_management |
| Path | `production_management/doctype/store_location` |
| Controller | `production_management/doctype/store_location/store_location.py` |
| Client script | none |

---

## sco_drawing_item

| Key | Value |
|-----|-------|
| Module | subcontracting_management |
| Path | `subcontracting_management/doctype/sco_drawing_item` |
| Controller | `subcontracting_management/doctype/sco_drawing_item/sco_drawing_item.py` |
| Client script | none |

---

## sco_excess_material_item

| Key | Value |
|-----|-------|
| Module | subcontracting_management |
| Path | `subcontracting_management/doctype/sco_excess_material_item` |
| Controller | `subcontracting_management/doctype/sco_excess_material_item/sco_excess_material_item.py` |
| Client script | none |

---

## soe_consumption_log

| Key | Value |
|-----|-------|
| Module | subcontracting_management |
| Path | `subcontracting_management/doctype/soe_consumption_log` |
| Controller | `subcontracting_management/doctype/soe_consumption_log/soe_consumption_log.py` |
| Client script | none |

---

## soe_drawing_detail

| Key | Value |
|-----|-------|
| Module | subcontracting_management |
| Path | `subcontracting_management/doctype/soe_drawing_detail` |
| Controller | `subcontracting_management/doctype/soe_drawing_detail/soe_drawing_detail.py` |
| Client script | none |

---

## supplier_operation_entry

| Key | Value |
|-----|-------|
| Module | subcontracting_management |
| Path | `subcontracting_management/doctype/supplier_operation_entry` |
| Controller | `subcontracting_management/doctype/supplier_operation_entry/supplier_operation_entry.py` |
| Client script | none |
| doc_events | see hooks.md |

---

## supplier_operation_item

| Key | Value |
|-----|-------|
| Module | subcontracting_management |
| Path | `subcontracting_management/doctype/supplier_operation_item` |
| Controller | `subcontracting_management/doctype/supplier_operation_item/supplier_operation_item.py` |
| Client script | none |

---

