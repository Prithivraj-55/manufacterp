"""One-time DB cleanup for Phase 0.4: revert Work Order & Job Card to standard.

Deletes the Custom Field / Property Setter / Client Script records this app added
to Work Order and Job Card, so the live UI actually reverts to vanilla ERPNext.
Source code that created these (setup.py functions, hooks.py wiring) is commented
out, not deleted, and can be restored later if needed -- see the progress tracker.

Deliberately excludes "Job Card-inventory_dimension" and "Job Card-storage_location"
custom fields -- those come from the unrelated Storage Location Inventory Dimension
feature (setup_storage_location), not from the drawing/consumption/inspection
tracking being reverted here.

Run via: bench --site manufact execute manufyxinvenzaerp.tests.revert_wo_jc_cleanup.run
"""

import frappe

CUSTOM_FIELDS_TO_DELETE = [
	"Job Card-custom_section_drawing_details",
	"Job Card-custom_drawing_details",
	"Job Card-custom_consumption_log_section",
	"Job Card-custom_consumption_log",
	"Job Card-custom_available_to_consume_kg",
	"Job Card-custom_total_consumed_kg",
	"Job Card-custom_total_available_nos",
	"Job Card-custom_total_completed_nos",
	"Work Order-custom_all_ops_complete",
	"Work Order-custom_cnc_transferred_weight_kg",
	"Work Order-custom_section_drawings",
	"Work Order-custom_drawing_items",
	"Work Order-custom_section_weights",
	"Work Order-custom_customer_weight_kg",
	"Work Order-custom_total_weight_kg",
	"Work Order-custom_mapped_weight_kg",
	"Work Order-custom_excess_weight_kg",
	"Work Order-custom_excess_banner_html",
	"Work Order-custom_transferred_weight_kg",
	"Work Order-custom_weight_summary_column_break",
	"Work Order-custom_operations_tab",
	"Work Order-custom_operations_html",
	"Job Card-custom_raw_material_consumption_tab",
	"Job Card-custom_raw_material_consumption",
	# NOT deleted: "Job Card-inventory_dimension", "Job Card-storage_location"
	# (unrelated Storage Location Inventory Dimension feature)
	"Job Card-custom_inspection_tab",
	"Job Card-custom_inspection_status",
	"Job Card-custom_inspection_call_date",
	"Job Card-custom_inspection_call_log_section",
	"Job Card-custom_inspection_call_log",
]

PROPERTY_SETTERS_TO_DELETE = [
	"Job Card-for_quantity-in_list_view",
	"Job Card-barcode-hidden",
	"Work Order-production_item-reqd",
	"Work Order-bom_no-reqd",
	"Work Order-qty-reqd",
	"Work Order-source_warehouse-reqd",
	"Work Order-source_warehouse-hidden",
	"Work Order-production_item-hidden",
	"Work Order-item_name-hidden",
	"Work Order-bom_no-hidden",
	"Work Order-sales_order-hidden",
	"Work Order-qty-hidden",
	"Work Order-required_items-hidden",
	"Work Order-required_items_section-hidden",
	"Work Order-allow_alternative_item-hidden",
	"Work Order-use_multi_level_bom-hidden",
	"Work Order-skip_transfer-hidden",
	"Work Order-update_consumed_material_cost_in_project-hidden",
	"Work Order-serial_no_and_batch_for_finished_good_section-hidden",
	"Work Order-has_serial_no-hidden",
	"Work Order-has_batch_no-hidden",
	"Work Order-batch_size-hidden",
	"Work Order-stock_uom-hidden",
	"Work Order-material_request-hidden",
	"Work Order-materials_and_operations_tab-hidden",
	"Work Order-main-field_order",
	"Job Card-bom_no-hidden",
	"Job Card-for_quantity-hidden",
	"Job Card-production_item-hidden",
	"Job Card-employee-hidden",
	"Job Card-timing_detail-hidden",
	"Job Card-scrap_items_section-hidden",
	"Job Card-scrap_items-hidden",
	"Job Card-custom_raw_material_consumption_tab-hidden",
	"Job Card-custom_raw_material_consumption-hidden",
	"Job Card-serial_and_batch_bundle-hidden",
	"Job Card-item_name-hidden",
	"Job Card-transferred_qty-hidden",
	"Job Card-requested_qty-hidden",
	"Job Card-sequence_id-in_list_view",
	"Job Card-sequence_id-in_standard_filter",
	"Job Card-work_order-in_standard_filter",
	"Job Card-main-field_order",
]

CLIENT_SCRIPTS_TO_DELETE = [
	"Job Card-raw-material-consumption-logic",
	"Work Order-wo-drawing-buttons",
	"Work Order-jc-operations-summary",
	"Job Card-drawing-consumption-logic",
]


def run():
	deleted = {"Custom Field": 0, "Property Setter": 0, "Client Script": 0}
	skipped = []

	for name in CUSTOM_FIELDS_TO_DELETE:
		if frappe.db.exists("Custom Field", name):
			frappe.delete_doc("Custom Field", name, ignore_permissions=True, force=True)
			deleted["Custom Field"] += 1
		else:
			skipped.append(("Custom Field", name))

	for name in PROPERTY_SETTERS_TO_DELETE:
		if frappe.db.exists("Property Setter", name):
			frappe.delete_doc("Property Setter", name, ignore_permissions=True, force=True)
			deleted["Property Setter"] += 1
		else:
			skipped.append(("Property Setter", name))

	for name in CLIENT_SCRIPTS_TO_DELETE:
		if frappe.db.exists("Client Script", name):
			frappe.delete_doc("Client Script", name, ignore_permissions=True, force=True)
			deleted["Client Script"] += 1
		else:
			skipped.append(("Client Script", name))

	frappe.db.commit()
	print("Deleted:", deleted)
	print("Not found (already absent):", skipped)

	# Confirm what's left on Work Order / Job Card
	remaining_cf = frappe.get_all(
		"Custom Field", filters={"dt": ["in", ["Work Order", "Job Card"]]}, pluck="name"
	)
	remaining_ps = frappe.get_all(
		"Property Setter", filters={"doc_type": ["in", ["Work Order", "Job Card"]]}, pluck="name"
	)
	print("\nRemaining Custom Fields on Work Order/Job Card:", remaining_cf)
	print("Remaining Property Setters on Work Order/Job Card:", remaining_ps)
