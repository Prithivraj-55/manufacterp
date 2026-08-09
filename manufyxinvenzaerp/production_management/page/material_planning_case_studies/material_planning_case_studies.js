// Material Planning — Overall Manual (Case Studies) page.
//
// Different purpose from the feature-by-feature "Manual" page
// (material_planning_manual.js): this page walks through REAL documents,
// case by case, with actual quantities/batches/purchase history, so a user
// can see exactly how the calculations and allocations played out on a real
// job. Everything is wrapped in an IIFE and namespaced with an "mpc-" prefix
// (Material Planning Case studies) so it never collides with the other
// manual page's globals when both have been loaded in the same session.
//
// Add a new case by appending to CASE_STUDIES below. A case still being
// built (Production Plan / Material Issue Plan not run yet) should set
// status: "in-progress" and leave the not-yet-available fields undefined --
// render_case() shows a "Coming soon" placeholder for whatever is missing.

(function () {

const CASE1_RAW_MATERIALS = [
	{item_number:"1p69", item_code:"PLATE10", item_name:"PLATE10", parent_item_group:"Plates", duno_mark_no:"1B1", length:424.68, width:180.0, thickness:10.0, sec_qty:4.0, qty:24.003, uom:"Kg", sec_uom:"Nos", unit_weight:7.85},
	{item_number:"1a11", item_code:"ISA100", item_name:"ISA100", parent_item_group:"Structurals", duno_mark_no:"1B1", length:340.0, width:0.0, thickness:0.0, sec_qty:16.0, qty:81.056, uom:"Kg", sec_uom:"Nos", unit_weight:14.9},
	{item_number:"1w27", item_code:"ISMB400", item_name:"ISMB400", parent_item_group:"Structurals", duno_mark_no:"1B1", length:6936.0, width:0.0, thickness:0.0, sec_qty:4.0, qty:1709.03, uom:"Kg", sec_uom:"Nos", unit_weight:61.6},
	{item_number:"1a11", item_code:"ISA100", item_name:"ISA100", parent_item_group:"Structurals", duno_mark_no:"1B2", length:340.0, width:0.0, thickness:0.0, sec_qty:16.0, qty:81.056, uom:"Kg", sec_uom:"Nos", unit_weight:14.9},
	{item_number:"1w27", item_code:"ISMB400", item_name:"ISMB400", parent_item_group:"Structurals", duno_mark_no:"1B2", length:6936.0, width:0.0, thickness:0.0, sec_qty:4.0, qty:1709.03, uom:"Kg", sec_uom:"Nos", unit_weight:61.6},
	{item_number:"1p69", item_code:"PLATE10", item_name:"PLATE10", parent_item_group:"Plates", duno_mark_no:"1B2", length:424.68, width:180.0, thickness:10.0, sec_qty:4.0, qty:24.003, uom:"Kg", sec_uom:"Nos", unit_weight:7.85},
	{item_number:"1w27", item_code:"ISMB400", item_name:"ISMB400", parent_item_group:"Structurals", duno_mark_no:"1B3", length:6936.01, width:0.0, thickness:0.0, sec_qty:16.0, qty:6836.131, uom:"Kg", sec_uom:"Nos", unit_weight:61.6},
	{item_number:"1a11", item_code:"ISA100", item_name:"ISA100", parent_item_group:"Structurals", duno_mark_no:"1B3", length:340.0, width:0.0, thickness:0.0, sec_qty:64.0, qty:324.224, uom:"Kg", sec_uom:"Nos", unit_weight:14.9},
	{item_number:"1w28", item_code:"ISMB400", item_name:"ISMB400", parent_item_group:"Structurals", duno_mark_no:"1B4", length:5136.0, width:0.0, thickness:0.0, sec_qty:4.0, qty:1265.51, uom:"Kg", sec_uom:"Nos", unit_weight:61.6},
	{item_number:"1a11", item_code:"ISA100", item_name:"ISA100", parent_item_group:"Structurals", duno_mark_no:"1B4", length:340.0, width:0.0, thickness:0.0, sec_qty:8.0, qty:40.528, uom:"Kg", sec_uom:"Nos", unit_weight:14.9},
	{item_number:"1a2", item_code:"ISA100", item_name:"ISA100", parent_item_group:"Structurals", duno_mark_no:"1B4", length:340.0, width:0.0, thickness:0.0, sec_qty:8.0, qty:40.528, uom:"Kg", sec_uom:"Nos", unit_weight:14.9},
	{item_number:"1w2", item_code:"ISMB450", item_name:"ISMB450", parent_item_group:"Structurals", duno_mark_no:"1B5", length:7331.55, width:0.0, thickness:0.0, sec_qty:1.0, qty:530.804, uom:"Kg", sec_uom:"Nos", unit_weight:72.4},
	{item_number:"1a5", item_code:"ISA100", item_name:"ISA100", parent_item_group:"Structurals", duno_mark_no:"1B5", length:390.0, width:0.0, thickness:0.0, sec_qty:2.0, qty:11.622, uom:"Kg", sec_uom:"Nos", unit_weight:14.9},
	{item_number:"1p49", item_code:"PLATE10", item_name:"PLATE10", parent_item_group:"Plates", duno_mark_no:"1B5", length:158.28, width:155.0, thickness:10.0, sec_qty:1.0, qty:1.926, uom:"Kg", sec_uom:"Nos", unit_weight:7.85},
	{item_number:"1a3", item_code:"ISA100", item_name:"ISA100", parent_item_group:"Structurals", duno_mark_no:"1B5", length:320.0, width:0.0, thickness:0.0, sec_qty:2.0, qty:9.536, uom:"Kg", sec_uom:"Nos", unit_weight:14.9},
	{item_number:"1p50", item_code:"PLATE10", item_name:"PLATE10", parent_item_group:"Plates", duno_mark_no:"1B5", length:181.0, width:141.0, thickness:10.0, sec_qty:1.0, qty:2.003, uom:"Kg", sec_uom:"Nos", unit_weight:7.85},
	{item_number:"1a5", item_code:"ISA100", item_name:"ISA100", parent_item_group:"Structurals", duno_mark_no:"1B6", length:390.0, width:0.0, thickness:0.0, sec_qty:2.0, qty:11.622, uom:"Kg", sec_uom:"Nos", unit_weight:14.9},
	{item_number:"1w2", item_code:"ISMB450", item_name:"ISMB450", parent_item_group:"Structurals", duno_mark_no:"1B6", length:7331.55, width:0.0, thickness:0.0, sec_qty:1.0, qty:530.804, uom:"Kg", sec_uom:"Nos", unit_weight:72.4},
	{item_number:"1p49", item_code:"PLATE10", item_name:"PLATE10", parent_item_group:"Plates", duno_mark_no:"1B6", length:158.28, width:155.0, thickness:10.0, sec_qty:1.0, qty:1.926, uom:"Kg", sec_uom:"Nos", unit_weight:7.85},
	{item_number:"1a3", item_code:"ISA100", item_name:"ISA100", parent_item_group:"Structurals", duno_mark_no:"1B6", length:320.0, width:0.0, thickness:0.0, sec_qty:2.0, qty:9.536, uom:"Kg", sec_uom:"Nos", unit_weight:14.9},
	{item_number:"1p50", item_code:"PLATE10", item_name:"PLATE10", parent_item_group:"Plates", duno_mark_no:"1B6", length:181.0, width:141.0, thickness:10.0, sec_qty:1.0, qty:2.003, uom:"Kg", sec_uom:"Nos", unit_weight:7.85},
	{item_number:"1a3", item_code:"ISA100", item_name:"ISA100", parent_item_group:"Structurals", duno_mark_no:"1B7", length:320.0, width:0.0, thickness:0.0, sec_qty:2.0, qty:9.536, uom:"Kg", sec_uom:"Nos", unit_weight:14.9},
	{item_number:"1a5", item_code:"ISA100", item_name:"ISA100", parent_item_group:"Structurals", duno_mark_no:"1B7", length:390.0, width:0.0, thickness:0.0, sec_qty:2.0, qty:11.622, uom:"Kg", sec_uom:"Nos", unit_weight:14.9},
	{item_number:"1p52", item_code:"PLATE10", item_name:"PLATE10", parent_item_group:"Plates", duno_mark_no:"1B7", length:186.85, width:180.0, thickness:10.0, sec_qty:1.0, qty:2.64, uom:"Kg", sec_uom:"Nos", unit_weight:7.85},
	{item_number:"1p51", item_code:"PLATE10", item_name:"PLATE10", parent_item_group:"Plates", duno_mark_no:"1B7", length:181.0, width:141.0, thickness:10.0, sec_qty:1.0, qty:2.003, uom:"Kg", sec_uom:"Nos", unit_weight:7.85},
	{item_number:"1w2", item_code:"ISMB450", item_name:"ISMB450", parent_item_group:"Structurals", duno_mark_no:"1B7", length:7331.55, width:0.0, thickness:0.0, sec_qty:1.0, qty:530.804, uom:"Kg", sec_uom:"Nos", unit_weight:72.4},
	{item_number:"1a3", item_code:"ISA100", item_name:"ISA100", parent_item_group:"Structurals", duno_mark_no:"1B8", length:320.0, width:0.0, thickness:0.0, sec_qty:2.0, qty:9.536, uom:"Kg", sec_uom:"Nos", unit_weight:14.9},
	{item_number:"1a5", item_code:"ISA100", item_name:"ISA100", parent_item_group:"Structurals", duno_mark_no:"1B8", length:390.0, width:0.0, thickness:0.0, sec_qty:2.0, qty:11.622, uom:"Kg", sec_uom:"Nos", unit_weight:14.9},
	{item_number:"1p51", item_code:"PLATE10", item_name:"PLATE10", parent_item_group:"Plates", duno_mark_no:"1B8", length:181.0, width:141.0, thickness:10.0, sec_qty:1.0, qty:2.003, uom:"Kg", sec_uom:"Nos", unit_weight:7.85},
	{item_number:"1p52", item_code:"PLATE10", item_name:"PLATE10", parent_item_group:"Plates", duno_mark_no:"1B8", length:186.85, width:180.0, thickness:10.0, sec_qty:1.0, qty:2.64, uom:"Kg", sec_uom:"Nos", unit_weight:7.85},
	{item_number:"1w2", item_code:"ISMB450", item_name:"ISMB450", parent_item_group:"Structurals", duno_mark_no:"1B8", length:7331.55, width:0.0, thickness:0.0, sec_qty:1.0, qty:530.804, uom:"Kg", sec_uom:"Nos", unit_weight:72.4},
	{item_number:"1w12", item_code:"ISMB250", item_name:"ISMB250", parent_item_group:"Structurals", duno_mark_no:"1B9", length:7479.1, width:0.0, thickness:0.0, sec_qty:1.0, qty:278.97, uom:"Kg", sec_uom:"Nos", unit_weight:37.3},
	{item_number:"1p94", item_code:"PLATE10", item_name:"PLATE10", parent_item_group:"Plates", duno_mark_no:"1B9", length:192.31, width:180.0, thickness:10.0, sec_qty:2.0, qty:5.435, uom:"Kg", sec_uom:"Nos", unit_weight:7.85},
	{item_number:"1a4", item_code:"ISA100", item_name:"ISA100", parent_item_group:"Structurals", duno_mark_no:"1B9", length:190.0, width:0.0, thickness:0.0, sec_qty:4.0, qty:11.324, uom:"Kg", sec_uom:"Nos", unit_weight:14.9},
	{item_number:"1p53", item_code:"PLATE10", item_name:"PLATE10", parent_item_group:"Plates", duno_mark_no:"1B9", length:225.86, width:192.0, thickness:10.0, sec_qty:1.0, qty:3.404, uom:"Kg", sec_uom:"Nos", unit_weight:7.85},
	{item_number:"1p63", item_code:"PLATE10", item_name:"PLATE10", parent_item_group:"Plates", duno_mark_no:"1B9", length:225.86, width:192.0, thickness:10.0, sec_qty:1.0, qty:3.404, uom:"Kg", sec_uom:"Nos", unit_weight:7.85},
	{item_number:"1p86", item_code:"PLATE10", item_name:"PLATE10", parent_item_group:"Plates", duno_mark_no:"1B9", length:200.0, width:192.0, thickness:10.0, sec_qty:2.0, qty:6.029, uom:"Kg", sec_uom:"Nos", unit_weight:7.85},
	{item_number:"1w13", item_code:"ISMB250", item_name:"ISMB250", parent_item_group:"Structurals", duno_mark_no:"1B10", length:979.1, width:0.0, thickness:0.0, sec_qty:4.0, qty:146.082, uom:"Kg", sec_uom:"Nos", unit_weight:37.3},
	{item_number:"1p48", item_code:"PLATE10", item_name:"PLATE10", parent_item_group:"Plates", duno_mark_no:"1B10", length:220.71, width:210.0, thickness:10.0, sec_qty:8.0, qty:29.107, uom:"Kg", sec_uom:"Nos", unit_weight:7.85},
	{item_number:"1a4", item_code:"ISA100", item_name:"ISA100", parent_item_group:"Structurals", duno_mark_no:"1B10", length:190.0, width:0.0, thickness:0.0, sec_qty:16.0, qty:45.296, uom:"Kg", sec_uom:"Nos", unit_weight:14.9},
	{item_number:"1a4", item_code:"ISA100", item_name:"ISA100", parent_item_group:"Structurals", duno_mark_no:"1B11", length:190.0, width:0.0, thickness:0.0, sec_qty:4.0, qty:11.324, uom:"Kg", sec_uom:"Nos", unit_weight:14.9},
	{item_number:"1w12", item_code:"ISMB250", item_name:"ISMB250", parent_item_group:"Structurals", duno_mark_no:"1B11", length:7479.1, width:0.0, thickness:0.0, sec_qty:1.0, qty:278.97, uom:"Kg", sec_uom:"Nos", unit_weight:37.3},
	{item_number:"1p64", item_code:"PLATE10", item_name:"PLATE10", parent_item_group:"Plates", duno_mark_no:"1B11", length:200.0, width:192.0, thickness:10.0, sec_qty:1.0, qty:3.014, uom:"Kg", sec_uom:"Nos", unit_weight:7.85},
	{item_number:"1p86", item_code:"PLATE10", item_name:"PLATE10", parent_item_group:"Plates", duno_mark_no:"1B11", length:200.0, width:192.0, thickness:10.0, sec_qty:2.0, qty:6.029, uom:"Kg", sec_uom:"Nos", unit_weight:7.85},
	{item_number:"1p54", item_code:"PLATE10", item_name:"PLATE10", parent_item_group:"Plates", duno_mark_no:"1B11", length:228.07, width:192.0, thickness:10.0, sec_qty:1.0, qty:3.437, uom:"Kg", sec_uom:"Nos", unit_weight:7.85},
	{item_number:"1p94", item_code:"PLATE10", item_name:"PLATE10", parent_item_group:"Plates", duno_mark_no:"1B11", length:192.31, width:180.0, thickness:10.0, sec_qty:2.0, qty:5.435, uom:"Kg", sec_uom:"Nos", unit_weight:7.85},
	{item_number:"1p58", item_code:"PLATE10", item_name:"PLATE10", parent_item_group:"Plates", duno_mark_no:"1B12", length:204.12, width:145.0, thickness:10.0, sec_qty:2.0, qty:4.647, uom:"Kg", sec_uom:"Nos", unit_weight:7.85},
	{item_number:"1a4", item_code:"ISA100", item_name:"ISA100", parent_item_group:"Structurals", duno_mark_no:"1B12", length:190.0, width:0.0, thickness:0.0, sec_qty:4.0, qty:11.324, uom:"Kg", sec_uom:"Nos", unit_weight:14.9},
	{item_number:"1w17", item_code:"ISMB250", item_name:"ISMB250", parent_item_group:"Structurals", duno_mark_no:"1B12", length:3186.0, width:0.0, thickness:0.0, sec_qty:1.0, qty:118.838, uom:"Kg", sec_uom:"Nos", unit_weight:37.3},
	{item_number:"1p87", item_code:"PLATE10", item_name:"PLATE10", parent_item_group:"Plates", duno_mark_no:"1B12", length:173.11, width:148.0, thickness:10.0, sec_qty:2.0, qty:4.022, uom:"Kg", sec_uom:"Nos", unit_weight:7.85},
	{item_number:"1p88", item_code:"PLATE10", item_name:"PLATE10", parent_item_group:"Plates", duno_mark_no:"1B12", length:170.64, width:149.0, thickness:10.0, sec_qty:2.0, qty:3.992, uom:"Kg", sec_uom:"Nos", unit_weight:7.85},
	{item_number:"1p59", item_code:"PLATE10", item_name:"PLATE10", parent_item_group:"Plates", duno_mark_no:"1B13", length:210.81, width:157.0, thickness:10.0, sec_qty:1.0, qty:2.598, uom:"Kg", sec_uom:"Nos", unit_weight:7.85},
	{item_number:"1a4", item_code:"ISA100", item_name:"ISA100", parent_item_group:"Structurals", duno_mark_no:"1B13", length:190.0, width:0.0, thickness:0.0, sec_qty:4.0, qty:11.324, uom:"Kg", sec_uom:"Nos", unit_weight:14.9},
	{item_number:"1w11", item_code:"ISMB250", item_name:"ISMB250", parent_item_group:"Structurals", duno_mark_no:"1B13", length:879.1, width:0.0, thickness:0.0, sec_qty:1.0, qty:32.79, uom:"Kg", sec_uom:"Nos", unit_weight:37.3},
	{item_number:"1a4", item_code:"ISA100", item_name:"ISA100", parent_item_group:"Structurals", duno_mark_no:"1B14", length:190.0, width:0.0, thickness:0.0, sec_qty:4.0, qty:11.324, uom:"Kg", sec_uom:"Nos", unit_weight:14.9},
	{item_number:"1p61", item_code:"PLATE10", item_name:"PLATE10", parent_item_group:"Plates", duno_mark_no:"1B14", length:200.81, width:152.0, thickness:10.0, sec_qty:1.0, qty:2.396, uom:"Kg", sec_uom:"Nos", unit_weight:7.85},
	{item_number:"1w11", item_code:"ISMB250", item_name:"ISMB250", parent_item_group:"Structurals", duno_mark_no:"1B14", length:879.1, width:0.0, thickness:0.0, sec_qty:1.0, qty:32.79, uom:"Kg", sec_uom:"Nos", unit_weight:37.3},
	{item_number:"1a4", item_code:"ISA100", item_name:"ISA100", parent_item_group:"Structurals", duno_mark_no:"1B15", length:190.0, width:0.0, thickness:0.0, sec_qty:2.0, qty:5.662, uom:"Kg", sec_uom:"Nos", unit_weight:14.9},
	{item_number:"1a12", item_code:"ISA100", item_name:"ISA100", parent_item_group:"Structurals", duno_mark_no:"1B15", length:190.0, width:0.0, thickness:0.0, sec_qty:2.0, qty:5.662, uom:"Kg", sec_uom:"Nos", unit_weight:14.9},
	{item_number:"1p145", item_code:"PLATE10", item_name:"PLATE10", parent_item_group:"Plates", duno_mark_no:"1B15", length:210.81, width:201.0, thickness:10.0, sec_qty:1.0, qty:3.326, uom:"Kg", sec_uom:"Nos", unit_weight:7.85},
	{item_number:"1w11", item_code:"ISMB250", item_name:"ISMB250", parent_item_group:"Structurals", duno_mark_no:"1B15", length:879.1, width:0.0, thickness:0.0, sec_qty:1.0, qty:32.79, uom:"Kg", sec_uom:"Nos", unit_weight:37.3},
];

const CASE1_CONSOLIDATE_ITEMS = [
	{ item_code: "PLATE10", group: "Plates", unit_weight: 7.85, required_kg: 302.85, length: 500, width: 500, thickness: 3, sec_qty: 52, purchase_kg: 306.15, difference_kg: 3.30 },
	{ item_code: "ISA100", group: "Structurals", unit_weight: 14.9, required_kg: 1530.528, length: 3000, width: 0, thickness: 0, sec_qty: 37, purchase_kg: 1653.90, difference_kg: 123.372 },
	{ item_code: "ISMB400", group: "Structurals", unit_weight: 61.6, required_kg: 23039.402, length: 12000, width: 0, thickness: 0, sec_qty: 32, purchase_kg: 23654.40, difference_kg: 614.998 },
	{ item_code: "ISMB450", group: "Structurals", unit_weight: 72.4, required_kg: 4246.432, length: 6000, width: 0, thickness: 0, sec_qty: 10, purchase_kg: 4344.00, difference_kg: 97.568 },
	{ item_code: "ISMB250", group: "Structurals", unit_weight: 37.3, required_kg: 1842.46, length: 3000, width: 0, thickness: 0, sec_qty: 17, purchase_kg: 1902.30, difference_kg: 59.84 },
];

const CASE1_ALLOCATION_EXAMPLES = [
	{
		item_code: "PLATE10", duno: "1B1", required_qty: 24.003,
		batch: "PLT10-T3-L500-W500-R006", available_qty: 24.003, reserved_qty: 24.003, shortfall_qty: 0,
		note: "This drawing's exact requirement (24.003 Kg) was fully covered from the single batch this receipt created — no shortfall.",
	},
	{
		item_code: "ISA100", duno: "1B1", required_qty: 81.056,
		batch: "ISA100-L3000-R006", available_qty: 81.056, reserved_qty: 81.056, shortfall_qty: 0,
		note: "Every ISA100 requirement across all 15 drawings pulled from this same batch, each getting exactly its own required Kg.",
	},
	{
		item_code: "ISMB400", duno: "1B1", required_qty: 1709.03,
		batch: "ISMB400-L12000-R006", available_qty: 1709.03, reserved_qty: 1709.03, shortfall_qty: 0,
		note: "The largest single line in this MP (23,654.40 Kg purchased) — still allocated per-drawing, one Available Raw Materials row per DUNO.",
	},
];

const CASE_STUDIES = [
	{
		id: "case-1",
		status: "in-progress",
		nav_label: "Case 1 — MP-2026-00010",
		title: "Case 1 — MP-2026-00010",
		kicker: "Direct purchase, no alternate items",
		docs: {
			"Material Planning": "MP-2026-00010",
			"Material Request": "MAT-MR-2026-00004 (submitted, Received)",
			"Purchase Order": "PUR-ORD-2026-00010 (INTERNATIONAL STEEL PRO)",
			"Purchase Receipt": "PR-26-00006 (Completed)",
			"Production Plan": "PP-SUP-2026-00001-1 (Type: Supplier Job)",
			"Job work order": "SC-ORD-2026-00001 (INTERNATIONAL STEEL PRO)",
			"Material Issue Plan": "MIP-2026-00001",
		},
		overview:
			"This is the simplest, baseline case: every raw material started with ZERO exact-match " +
			"stock (all previous reservations had been removed before this run), so all 61 raw " +
			"material rows fell straight through to Unavailable Items and were consolidated into " +
			"5 purchase lines. Every one of those 5 lines was purchased as the ORIGINAL item — no " +
			"alternate/substitute item was used anywhere in this case, and every drawing's " +
			"requirement was met in full with no shortfall. One Material Request, one Purchase " +
			"Order, one Purchase Receipt covered everything, and allocation back into Available Raw " +
			"Materials happened automatically the moment the receipt was submitted.",
		raw_materials: CASE1_RAW_MATERIALS,
		weight_examples: [
			{
				group: "Plates", item: "PLATE10", duno: "1B1",
				length: 424.68, width: 180, thickness: 10, sec_qty: 4, unit_weight: 7.85,
				formula: "(L÷1000) × (W÷1000) × Thickness × Unit Weight × Sec Qty  =  (424.68÷1000) × (180÷1000) × 10 × 7.85 × 4",
				result: "24.003",
			},
			{
				group: "Structurals", item: "ISA100", duno: "1B1",
				length: 340, sec_qty: 16, unit_weight: 14.9,
				formula: "(Length÷1000) × Unit Weight × Sec Qty  =  (340÷1000) × 14.9 × 16",
				result: "81.056",
			},
		],
		consolidate_items: CASE1_CONSOLIDATE_ITEMS,
		allocation_examples: CASE1_ALLOCATION_EXAMPLES,
		production_plan: `
			<table class="mpc-doc-table">
				<tbody>
					<tr><td class="mpc-doc-key">Production Plan</td><td>PP-SUP-2026-00001-1</td></tr>
					<tr><td class="mpc-doc-key">Type</td><td>Supplier Job</td></tr>
					<tr><td class="mpc-doc-key">Vendor/Contractor</td><td>INTERNATIONAL STEEL PRO</td></tr>
					<tr><td class="mpc-doc-key">Drawings covered</td><td>1B1, 1B2, 1B3, 1B4, 1B5 — Planned Qty 2, 2, 4, 2, 1 Nos</td></tr>
					<tr><td class="mpc-doc-key">Job work order</td><td>SC-ORD-2026-00001</td></tr>
					<tr><td class="mpc-doc-key">Material Issue Plan</td><td>MIP-2026-00001</td></tr>
				</tbody>
			</table>
			<p class="mpc-note-inline">
				Process Planning laid out six operations, in this order, all performed by the same
				supplier (Work Type Subcontractor throughout): <b>Material Issue</b>, <b>Fit-up
				(Inspection Mandatory)</b>, <b>Welding</b>, <b>Final (Inspection Mandatory)</b>,
				<b>Blasting</b>, <b>Painting</b>. Clicking "Job work order &amp; MIP" created
				SC-ORD-2026-00001 and MIP-2026-00001 together in one step, then "Supplier Operation
				Entries" created one Supplier Operation Entry per row above, in sequence.
			</p>
		`,
		material_issue_plan: `
			<table class="mpc-doc-table">
				<tbody>
					<tr><td class="mpc-doc-key">Material Issue Plan</td><td>MIP-2026-00001</td></tr>
					<tr><td class="mpc-doc-key">Source Warehouse</td><td>Stores - MIPL</td></tr>
					<tr><td class="mpc-doc-key">Supplier Warehouse</td><td>INTERNATIONAL STEEL PRO - MIPL</td></tr>
					<tr><td class="mpc-doc-key">Finished Goods Warehouse</td><td>Stores - MIPL</td></tr>
					<tr><td class="mpc-doc-key">Raw Materials rows</td><td>13 — one per reserved batch × drawing combination</td></tr>
				</tbody>
			</table>
			<p class="mpc-note-inline">
				Every row traces back to a batch that was BOTH purchased and reserved back in
				Material Planning 1 — e.g. PLATE10 batch PLT10-T3-L500-W500-R006 supplies drawings
				1B1, 1B2 and 1B5 from the same reservation; ISA100 batch ISA100-L3000-R006 supplies
				all five drawings. "Select Materials to Transfer" moved this stock out to the
				supplier warehouse — Job work order 1's own Transferred Weight (12,638.923 Kg)
				reflects that movement. Once all six operations finished, "Make Final Stock Entry"
				became available here to consume the supplier-warehouse stock and receive the
				finished good into the Finished Goods Warehouse.
			</p>
		`,
		operations: `
			<div class="mpc-table-scroll">
			<table class="mpc-data-table">
				<thead>
					<tr><th>Seq</th><th>Operation</th><th>Inspection Mandatory</th><th>Result</th></tr>
				</thead>
				<tbody>
					<tr><td>1</td><td>Material Issue</td><td>No</td><td>11 Nos completed directly from Consumption Log — this operation is Kg-based, tracking Available to Consume (Kg) from Job work order 1's Transferred Weight</td></tr>
					<tr><td>2</td><td>Fit-up</td><td><b>Yes</b></td><td>Inspected across 2 rounds (Inspection Entry INSP-0001, INSP-0002) — Total Checked 11, Cleared 11, Rework 0 both times (Feedback Ok) — every Nos passed cleanly, no rejections</td></tr>
					<tr><td>3</td><td>Welding</td><td>No</td><td>11 Nos completed directly from Consumption Log</td></tr>
					<tr><td>4</td><td>Final</td><td><b>Yes</b></td><td>Inspected across 2 rounds with a real rework loop — see the worked example below</td></tr>
					<tr><td>5</td><td>Blasting</td><td>No</td><td>11 Nos completed directly from Consumption Log</td></tr>
					<tr><td>6</td><td>Painting</td><td>No</td><td>11 Nos completed directly — the last operation, so this is what set Job work order 1's "All Operations Complete" flag</td></tr>
				</tbody>
			</table>
			</div>
			<h3>${__("Worked Example — Inspection Rework Loop (Operation 4, Final)")}</h3>
			<p class="mpc-note-inline">
				Two of the five drawings on this operation needed a second inspection round after
				part of their quantity was rejected in round 1. Both finished at exactly their real
				total — never more — because the pending quantity shown to Inspection always caps
				at the drawing's own Qty to Manufacture, however many times it's re-logged.
			</p>
			<div class="mpc-calcs">
				<div class="mpc-calc">
					<div class="mpc-calc-title">BEAM-1B1 -SHT-1 OF 291 <span>· Qty to Manufacture: 2 Nos</span></div>
					<table class="mpc-calc-dims">
						<tr><td>Round 1 — Inspection Entry</td><td>INSP-0003</td></tr>
						<tr><td>Logged in Consumption Log</td><td>2 Nos</td></tr>
						<tr><td>Accepted / Rejected</td><td>1 / 1</td></tr>
						<tr><td>Completed Qty after Round 1</td><td>1 Nos</td></tr>
					</table>
					<div class="mpc-calc-formula">The rejected piece was re-logged in Consumption Log, taking the raw total to 3 — but Inspection Items caps pending at Qty to Manufacture (2) minus Completed (1) = 1 Nos, never 2, however many were technically logged.</div>
					<table class="mpc-calc-dims">
						<tr><td>Round 2 — Inspection Entry</td><td>INSP-0004</td></tr>
						<tr><td>Pending shown</td><td>1 Nos</td></tr>
						<tr><td>Accepted / Rejected</td><td>1 / 0</td></tr>
					</table>
					<div class="mpc-calc-result">Completed Qty = 2 / 2 — fully done</div>
				</div>
				<div class="mpc-calc">
					<div class="mpc-calc-title">BEAM-1B3 -SHT-3 OF 291 <span>· Qty to Manufacture: 4 Nos</span></div>
					<table class="mpc-calc-dims">
						<tr><td>Round 1 — Inspection Entry</td><td>INSP-0003</td></tr>
						<tr><td>Logged in Consumption Log at the time</td><td>2 Nos</td></tr>
						<tr><td>Accepted / Rejected</td><td>1 / 1</td></tr>
						<tr><td>Completed Qty after Round 1</td><td>1 Nos</td></tr>
					</table>
					<div class="mpc-calc-formula">A further 2 Nos were logged afterwards, taking the raw total to 4 — matching the drawing's real quantity — so Round 2's pending = 4 − 1 = 3 Nos.</div>
					<table class="mpc-calc-dims">
						<tr><td>Round 2 — Inspection Entry</td><td>INSP-0004</td></tr>
						<tr><td>Pending shown</td><td>3 Nos</td></tr>
						<tr><td>Accepted / Rejected</td><td>3 / 0</td></tr>
					</table>
					<div class="mpc-calc-result">Completed Qty = 4 / 4 — fully done</div>
				</div>
			</div>
			<p class="mpc-note-inline">
				Rework Remarks were required on Round 1 (total Rejected was 2, above the
				"greater than 1" threshold) — entered as "work". Round 2's total Rejected was 0,
				so no remarks were required there.
			</p>
		`,
	},
	{
		id: "case-2",
		status: "pending",
		nav_label: "Case 2 — Coming Soon",
		title: "Case 2 — Alternate Items + Internal/External Split",
		kicker: "Not started yet",
		overview:
			"Will cover alternate item mapping for a subset of items (including an alternate item " +
			"actually being purchased), a mix of Internal Jobcard and Supplier (subcontracted) " +
			"operations in the same Production Plan, and any other feature not exercised by Case 1 " +
			"(Excess Material Mapping, CNC routing, partial/short receipts, etc.).",
	},
];

frappe.pages["material-planning-case-studies"].on_page_load = function (wrapper) {
	let page = frappe.ui.make_app_page({
		parent: wrapper,
		title: "Material Planning — Overall Manual",
		single_column: true,
	});
	render_page(page);
};

function render_page(page) {
	inject_styles();

	let nav_html = CASE_STUDIES.map(
		(c) => `<a href="javascript:void(0)" class="mpc-nav-link" data-id="${c.id}">${frappe.utils.escape_html(c.nav_label)}</a>`
	).join("");

	let cases_html = CASE_STUDIES.map(render_case).join("");

	page.main.html(`
		<div class="mpc-root">
			<header class="mpc-hero">
				<div class="mpc-hero-kicker">${__("Material Planning")}</div>
				<h1>${__("Overall Manual — Real Case Walkthroughs")}</h1>
				<p>${__("Unlike the feature-by-feature Manual, this page follows real Material Planning documents start to finish — actual items, dimensions, batches and purchase history — so you can see exactly how the calculations played out on a real job.")}</p>
			</header>
			<div class="mpc-body">
				<nav class="mpc-nav">${nav_html}</nav>
				<main class="mpc-content">${cases_html}</main>
			</div>
		</div>
	`);

	setup_scrollspy(page);
	setup_download_buttons(page);
}

function render_case(c) {
	if (c.status === "pending") {
		return `
		<section id="mpc-${c.id}" class="mpc-card mpc-pending">
			<div class="mpc-kicker">${frappe.utils.escape_html(c.kicker)}</div>
			<h2>${frappe.utils.escape_html(c.title)}</h2>
			<p class="mpc-purpose">${c.overview}</p>
			<div class="mpc-pending-badge">${__("Coming soon")}</div>
		</section>`;
	}

	let parts = [];

	// --- Overview ---
	parts.push(`
		<div class="mpc-kicker">${frappe.utils.escape_html(c.kicker)}</div>
		<h2>${frappe.utils.escape_html(c.title)}</h2>
		<p class="mpc-purpose">${c.overview}</p>
		<table class="mpc-doc-table">
			<tbody>
				${Object.entries(c.docs).map(([k, v]) => `
					<tr><td class="mpc-doc-key">${frappe.utils.escape_html(k)}</td><td>${frappe.utils.escape_html(v)}</td></tr>
				`).join("")}
			</tbody>
		</table>
	`);

	// --- Raw materials / sales order item list + download ---
	if (c.raw_materials && c.raw_materials.length) {
		parts.push(`
			<h3>${__("Raw Material Requirement List")} <span class="mpc-h3-sub">(${c.raw_materials.length} ${__("rows, from the Sales Order's drawings")})</span></h3>
			<p class="mpc-note-inline">${__("The full requirement list is long, so it isn't reproduced row by row here — download it instead and open it alongside this page.")}</p>
			<button class="btn btn-sm btn-default mpc-download-btn" data-case="${c.id}">
				${frappe.utils.icon("download", "xs")} ${__("Download Raw Material List (CSV)")}
			</button>
		`);
	}

	// --- Weight calculation, one Plates + one Structurals example only ---
	if (c.weight_examples && c.weight_examples.length) {
		parts.push(`
			<h3>${__("How the Weights Were Calculated")}</h3>
			<p class="mpc-note-inline">${__("Only one Plates item and one Structurals item are shown here as worked examples — the same formula applies identically to every other row in the list above.")}</p>
			<div class="mpc-calcs">
				${c.weight_examples.map(render_calc).join("")}
			</div>
		`);
	}

	// --- Consolidate Item: overall required, what was entered, what was purchased ---
	if (c.consolidate_items && c.consolidate_items.length) {
		parts.push(`
			<h3>${__("Consolidate Item — Required vs. Entered vs. Purchased")}</h3>
			<p class="mpc-note-inline">${__("One row per item code. “Required Kg” is the total pulled in automatically from every drawing; Length/Width/Thickness/Sec Qty were then entered by hand to describe what was actually being bought; “Purchase Kg” and “Difference” calculated automatically from that.")}</p>
			<div class="mpc-table-scroll">
			<table class="mpc-data-table">
				<thead>
					<tr>
						<th>${__("Item")}</th><th>${__("Group")}</th><th>${__("Unit Weight")}</th><th>${__("Required Kg")}</th>
						<th>${__("Purchase Dims (L×W×T, Sec Qty)")}</th><th>${__("Purchase Kg")}</th><th>${__("Difference Kg")}</th>
					</tr>
				</thead>
				<tbody>
					${c.consolidate_items.map((r) => `
						<tr>
							<td class="mpc-strong">${frappe.utils.escape_html(r.item_code)}</td>
							<td>${frappe.utils.escape_html(r.group)}</td>
							<td>${format_num(r.unit_weight)}</td>
							<td>${format_num(r.required_kg)}</td>
							<td>${r.length} × ${r.width} × ${r.thickness} mm, ${r.sec_qty} Nos</td>
							<td>${format_num(r.purchase_kg)}</td>
							<td class="mpc-diff">${format_num(r.difference_kg)}</td>
						</tr>
					`).join("")}
				</tbody>
			</table>
			</div>
		`);
	}

	// --- Allocation results for a few items ---
	if (c.allocation_examples && c.allocation_examples.length) {
		parts.push(`
			<h3>${__("Allocation After Purchase Receipt — a Few Examples")}</h3>
			<p class="mpc-note-inline">${__("On PR submit, allocation ran automatically for all 43 Available Raw Materials rows this receipt produced. A few are shown here as examples — the same pattern repeated for every drawing/item combination.")}</p>
			<div class="mpc-calcs">
				${c.allocation_examples.map(render_allocation).join("")}
			</div>
		`);
	}

	// --- Production Plan / Material Issue Plan / Operations & Inspection ---
	parts.push(`
		<h3>${__("Production Plan")}</h3>
		${render_pending_or(c.production_plan, __("Not run yet for this case — will be added here once Production Plan entries are made for MP-2026-00010."))}
		<h3>${__("Material Issue Plan")}</h3>
		${render_pending_or(c.material_issue_plan, __("Not run yet for this case — will be added here once Material Issue Plan entries are made for MP-2026-00010."))}
		<h3>${__("Operations & Inspection")}</h3>
		${render_pending_or(c.operations, __("Not run yet for this case — will be added here once the Job work order's operations are run."))}
	`);

	return `<section id="mpc-${c.id}" class="mpc-card">${parts.join("\n")}</section>`;
}

function render_pending_or(content, placeholder_text) {
	if (content) return content;
	return `<div class="mpc-note-pending">${placeholder_text}</div>`;
}

function render_calc(c) {
	let dim_rows = [];
	if (c.length !== undefined) dim_rows.push(["Length", c.length + " mm"]);
	if (c.width !== undefined) dim_rows.push(["Width", c.width + " mm"]);
	if (c.thickness !== undefined) dim_rows.push(["Thickness", c.thickness + " mm"]);
	dim_rows.push(["Sec Qty", c.sec_qty]);
	dim_rows.push(["Unit Weight", c.unit_weight]);

	return `
	<div class="mpc-calc">
		<div class="mpc-calc-title">${frappe.utils.escape_html(c.item)} <span>· ${frappe.utils.escape_html(c.group)} · DUNO ${frappe.utils.escape_html(c.duno)}</span></div>
		<table class="mpc-calc-dims">
			${dim_rows.map(([k, v]) => `<tr><td>${k}</td><td>${v}</td></tr>`).join("")}
		</table>
		<div class="mpc-calc-formula">${c.formula}</div>
		<div class="mpc-calc-result">= ${c.result} Kg</div>
	</div>`;
}

function render_allocation(a) {
	return `
	<div class="mpc-calc">
		<div class="mpc-calc-title">${frappe.utils.escape_html(a.item_code)} <span>· DUNO ${frappe.utils.escape_html(a.duno)}</span></div>
		<table class="mpc-calc-dims">
			<tr><td>${__("Required Qty")}</td><td>${format_num(a.required_qty)} Kg</td></tr>
			<tr><td>${__("Batch Assigned")}</td><td>${frappe.utils.escape_html(a.batch)}</td></tr>
			<tr><td>${__("Available in Batch")}</td><td>${format_num(a.available_qty)} Kg</td></tr>
			<tr><td>${__("Reserved Qty")}</td><td>${format_num(a.reserved_qty)} Kg</td></tr>
			<tr><td>${__("Shortfall Qty")}</td><td>${format_num(a.shortfall_qty)} Kg</td></tr>
		</table>
		<div class="mpc-calc-note">${a.note}</div>
	</div>`;
}

function format_num(n) {
	if (n === undefined || n === null) return "";
	return Number(n).toLocaleString(undefined, { maximumFractionDigits: 3 });
}

function setup_download_buttons(page) {
	page.main.find(".mpc-download-btn").on("click", function () {
		let case_id = $(this).data("case");
		let c = CASE_STUDIES.find((x) => x.id === case_id);
		if (!c || !c.raw_materials) return;

		let header = ["item_number","item_code","item_name","parent_item_group","duno_mark_no","length","width","thickness","sec_qty","qty","uom","sec_uom","unit_weight"];
		let rows = c.raw_materials.map((r) => header.map((h) => r[h]).join(","));
		let csv = header.join(",") + "\n" + rows.join("\n");

		let blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
		let url = URL.createObjectURL(blob);
		let a = document.createElement("a");
		a.href = url;
		a.download = (c.docs && c.docs["Material Planning"] ? c.docs["Material Planning"] : case_id) + "_raw_materials.csv";
		document.body.appendChild(a);
		a.click();
		document.body.removeChild(a);
		URL.revokeObjectURL(url);
	});
}

function setup_scrollspy(page) {
	let $links = page.main.find(".mpc-nav-link");

	$links.on("click", function (e) {
		e.preventDefault();
		let id = $(this).data("id");
		let $target = page.main.find("#mpc-" + id);
		if ($target.length) {
			$target[0].scrollIntoView({ behavior: "smooth", block: "start" });
		}
	});

	let sections = CASE_STUDIES.map((c) => page.main.find("#mpc-" + c.id)[0]).filter(Boolean);
	if (!sections.length || !window.IntersectionObserver) return;

	let observer = new IntersectionObserver(
		(entries) => {
			entries.forEach((entry) => {
				if (entry.isIntersecting) {
					let id = entry.target.id.replace("mpc-", "");
					$links.removeClass("active");
					page.main.find(`.mpc-nav-link[data-id="${id}"]`).addClass("active");
				}
			});
		},
		{ root: null, rootMargin: "-15% 0px -70% 0px", threshold: 0 }
	);
	sections.forEach((el) => observer.observe(el));
}

function inject_styles() {
	if (document.getElementById("mpc-styles")) return;
	let style = document.createElement("style");
	style.id = "mpc-styles";
	style.innerHTML = `
		.mpc-root {
			--mpc-bg: #FBEDE8;
			--mpc-card-bg: #FFFFFF;
			--mpc-heading: #3B1730;
			--mpc-accent: #E8613C;
			--mpc-accent-soft: #FCE3D8;
			--mpc-text: #4A4550;
			--mpc-text-muted: #948C97;
			--mpc-good: #1F9254;
			--mpc-good-bg: #E7F6EE;
			--mpc-border: #F0DDD5;
			background: var(--mpc-bg);
			min-height: 100%;
			margin: -15px -25px;
			padding: 0 0 60px 0;
			font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
			color: var(--mpc-text);
		}
		.mpc-hero { text-align: center; padding: 56px 20px 40px; max-width: 760px; margin: 0 auto; }
		.mpc-hero-kicker { text-transform: uppercase; letter-spacing: 2px; font-size: 12px; font-weight: 700; color: var(--mpc-accent); margin-bottom: 10px; }
		.mpc-hero h1 { font-family: Georgia, "Times New Roman", serif; font-weight: 700; font-size: 36px; color: var(--mpc-heading); margin: 0 0 14px; }
		.mpc-hero p { font-size: 15px; color: var(--mpc-text-muted); line-height: 1.6; margin: 0; }
		.mpc-body { display: flex; max-width: 1100px; margin: 0 auto; padding: 0 20px; gap: 32px; align-items: flex-start; }
		.mpc-nav {
			position: sticky; top: 20px; flex: 0 0 220px; display: flex; flex-direction: column; gap: 2px;
			background: var(--mpc-card-bg); border: 1px solid var(--mpc-border); border-radius: 12px; padding: 10px;
			max-height: calc(100vh - 40px); overflow-y: auto;
		}
		.mpc-nav-link {
			display: block; padding: 9px 12px; border-radius: 8px; font-size: 13px; font-weight: 500;
			color: var(--mpc-text); text-decoration: none; border-left: 3px solid transparent; transition: background .15s, color .15s;
		}
		.mpc-nav-link:hover { background: var(--mpc-accent-soft); color: var(--mpc-heading); text-decoration: none; }
		.mpc-nav-link.active { background: var(--mpc-accent-soft); color: var(--mpc-accent); border-left-color: var(--mpc-accent); font-weight: 700; }
		.mpc-content { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 24px; }
		.mpc-card { background: var(--mpc-card-bg); border: 1px solid var(--mpc-border); border-radius: 16px; padding: 32px 36px; box-shadow: 0 2px 10px rgba(59, 23, 48, 0.04); scroll-margin-top: 20px; }
		.mpc-kicker { text-transform: uppercase; letter-spacing: 1.5px; font-size: 11px; font-weight: 700; color: var(--mpc-accent); margin-bottom: 6px; }
		.mpc-card h2 { font-family: Georgia, "Times New Roman", serif; font-weight: 700; font-size: 26px; color: var(--mpc-heading); margin: 0 0 14px; }
		.mpc-card h3 { font-size: 14px; font-weight: 700; color: var(--mpc-heading); text-transform: uppercase; letter-spacing: .5px; margin: 26px 0 10px; }
		.mpc-h3-sub { text-transform: none; font-weight: 400; color: var(--mpc-text-muted); letter-spacing: 0; }
		.mpc-purpose { font-size: 15px; line-height: 1.7; color: var(--mpc-text); margin: 0; }
		.mpc-note-inline { font-size: 13px; line-height: 1.6; color: var(--mpc-text-muted); margin: 0 0 12px; }
		.mpc-note-pending { font-size: 13.5px; color: var(--mpc-text-muted); font-style: italic; background: var(--mpc-accent-soft); border-radius: 10px; padding: 12px 16px; }
		.mpc-doc-table { width: 100%; border-collapse: collapse; margin-top: 16px; }
		.mpc-doc-table tr { border-top: 1px solid var(--mpc-border); }
		.mpc-doc-table tr:first-child { border-top: none; }
		.mpc-doc-table td { padding: 8px 0; font-size: 13px; }
		.mpc-doc-key { width: 200px; font-weight: 700; color: var(--mpc-heading); }
		.mpc-download-btn { display: inline-flex; align-items: center; gap: 6px; }
		.mpc-table-scroll { overflow-x: auto; }
		.mpc-data-table { width: 100%; border-collapse: collapse; font-size: 13px; min-width: 640px; }
		.mpc-data-table th { text-align: left; padding: 8px 10px; background: var(--mpc-accent-soft); color: var(--mpc-heading); font-weight: 700; font-size: 11.5px; text-transform: uppercase; letter-spacing: .4px; }
		.mpc-data-table td { padding: 8px 10px; border-top: 1px solid var(--mpc-border); }
		.mpc-strong { font-weight: 700; color: var(--mpc-heading); }
		.mpc-diff { color: var(--mpc-accent); font-weight: 600; }
		.mpc-calcs { display: flex; flex-direction: column; gap: 16px; }
		.mpc-calc { background: #fffaf7; border: 1.5px dashed var(--mpc-accent); border-radius: 12px; padding: 18px 20px; }
		.mpc-calc-title { font-weight: 700; font-size: 13.5px; color: var(--mpc-heading); margin-bottom: 10px; }
		.mpc-calc-title span { font-weight: 400; color: var(--mpc-text-muted); }
		.mpc-calc-dims { border-collapse: collapse; margin-bottom: 12px; }
		.mpc-calc-dims td { font-size: 12.5px; padding: 3px 14px 3px 0; color: var(--mpc-text); }
		.mpc-calc-dims td:first-child { color: var(--mpc-text-muted); }
		.mpc-calc-formula { font-family: "SFMono-Regular", Consolas, Menlo, monospace; font-size: 12.5px; line-height: 1.6; color: var(--mpc-text); background: var(--mpc-accent-soft); border-radius: 8px; padding: 10px 12px; margin-bottom: 10px; }
		.mpc-calc-result { font-size: 18px; font-weight: 700; color: var(--mpc-good); }
		.mpc-calc-note { margin-top: 10px; font-size: 12.5px; line-height: 1.6; color: var(--mpc-text-muted); font-style: italic; }
		.mpc-pending { text-align: center; padding: 48px 36px; }
		.mpc-pending-badge { display: inline-block; margin-top: 16px; background: var(--mpc-heading); color: #fff; font-size: 12px; font-weight: 700; padding: 6px 16px; border-radius: 20px; }
		@media (max-width: 900px) {
			.mpc-body { flex-direction: column; }
			.mpc-nav { position: static; flex: none; width: 100%; flex-direction: row; overflow-x: auto; max-height: none; }
		}
	`;
	document.head.appendChild(style);
}

})();
