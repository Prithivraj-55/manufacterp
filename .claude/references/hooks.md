# hooks — manufyxinvenzaerp

_Generated: 2026-08-10 00:31:56_

## doc_events

```python
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
}
```

## override_doctype_class

```python
override_doctype_class = {
    "BOM": "manufyxinvenzaerp.drawing_management.bom_class_override.BOM",
    "Subcontracting Order": "manufyxinvenzaerp.subcontracting_management.overrides.CustomSubcontractingOrder",
    "Stock Entry": "manufyxinvenzaerp.subcontracting_management.overrides.CustomStockEntry",
}
```

## override_doctype_dashboards

```python
override_doctype_dashboards = {
	"Sales Order": "manufyxinvenzaerp.drawing_management.drawing_utils.get_so_dashboard_data",
	"Subcontracting Order": "manufyxinvenzaerp.subcontracting_management.subcontracting.get_sco_dashboard_data",
}
```

## doctype_js (client scripts injected into standard doctypes)

```python
app_include_js = "/assets/manufyxinvenzaerp/js/item.js"
doctype_js = {
doctype_js = {
    "Production Plan": "public/js/production_plan.js",
    "BOM": "public/js/bom.js",
    "Purchase Order": "public/js/purchase_order.js",
    "Purchase Receipt": "public/js/purchase_receipt.js",
    "Batch": "public/js/batch.js",
    # "Job Card": "public/js/job_card.js",
    # DISABLED (client change request Phase 0.4): Job Card reverted to standard.
    "Supplier Operation Entry": "public/js/supplier_operation_entry.js",
    "Inspection Entry": "public/js/inspection_entry.js",
}
```

## fixtures

```python
fixtures = ["Custom Field", "Property Setter"]
```

## App lifecycle

```python
after_install = "manufyxinvenzaerp.setup.after_install"
after_migrate = "manufyxinvenzaerp.setup.after_migrate"
```

## scheduler_events

_None registered (all commented out)._

