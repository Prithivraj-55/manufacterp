// Material Issue Plan — user manual.
//
// Layout, scrollspy and styling come from the shared renderer
// (public/js/manual_renderer.js); this file is only the content. Section shape is
// {id, title, kicker, purpose, fields[], steps[], calcs[], examples[], notes[],
// buttons[]}, everything optional.
//
// Keep this in step with material_issue_plan.js / material_issue_plan_transfer.py:
// it documents the transfer popup, Cut Sheet rows, Excess Return and the CNC legs,
// all of which change more often than most of the app.

frappe.pages["material-issue-plan-manual"].on_page_load = function (wrapper) {
	let page = frappe.ui.make_app_page({
		parent: wrapper,
		title: "Manufyxinvenza Manual — Material Issue Plan",
		single_column: true,
	});

	manufyx_render_manual(page, {
		kicker: __("Material Issue Plan"),
		heading: __("Getting Material Out of the Door"),
		intro: __("Material Planning only ever <b>promises</b> steel to a job. This is where it physically leaves your warehouse — how the list is built, how a fractional Sec Nos becomes whole bars, what happens to the surplus, and how material routed through CNC gets there and back out again. Worked through with real figures at every step."),
		sections: MIP_MANUAL_SECTIONS,
	});
};

const MIP_MANUAL_SECTIONS = [
	{
		id: "overview",
		kind: "overview",
		flow: false,
		kicker: "Start here",
		title: "What a Material Issue Plan Is For",
		purpose:
			"One Material Issue Plan per Production Plan. It pulls in every raw-material row " +
			"reserved for that job's drawings, and is the only place stock actually moves: out " +
			"to the supplier (or your WIP warehouse), optionally via CNC, and back again as " +
			"excess. Nothing here invents quantities — it inherits what Material Planning " +
			"reserved and asks you to decide the one thing a planner cannot know in advance: " +
			"how many whole physical pieces are going out today.",
	},
	{
		id: "raw-materials",
		title: "Raw Materials",
		kicker: "The list, and where it comes from",
		purpose:
			"Every reserved row for this job's drawings, pulled from the linked Material " +
			"Planning(s). It is rebuilt rather than edited: press <b>Refresh Raw Materials</b> " +
			"and the rows are re-read from Material Planning, which is how a late purchase or a " +
			"batch mapped after this plan was created still finds its way in.",
		fields: [
			{ name: "Reqd Qty", note: "What this row must transfer — the weight of the batch mapped to it in Material Planning. Not the customer's weight and not the drawing's; the actual mapped material." },
			{ name: "Issued Qty", note: "Cumulative Kg transferred so far across every Stock Entry from this plan. A row can be issued in stages." },
			{ name: "Excess Qty", note: "Reqd Qty minus the drawing's own planned raw-material weight — surplus the mapped batch carries beyond what the drawing needs. Set when the row is fetched." },
			{ name: "Transfer Excess Kg", note: "Surplus created by YOU rounding Sec Nos up at transfer time. Separate from Excess Qty, and accumulates across partial transfers." },
			{ name: "Sec Qty / Sec UOM", note: "The row's share in pieces. Frequently fractional — see the worked example below, that is expected and not an error." },
			{ name: "CNC Process", note: "Inherited from Material Planning. Ticked means this material must go to the CNC warehouse first; it is not a preference." },
			{ name: "Batch / Batch Remarks", note: "The reserved batch and any remarks recorded against it at inspection." },
		],
		examples: [
			{
				type: "dont",
				label: "Don't type into these rows expecting it to stick",
				text: "Everything except the Excess Return and Cut Sheet fields is rebuilt from Material Planning on the next refresh. To change what a row draws from, change it there.",
			},
			{
				type: "do",
				label: "Refresh after a late purchase",
				text: "Stock bought after this plan was created is allocated back into Material Planning by the Purchase Receipt, which refreshes this plan automatically. If you have the form open, reload it.",
			},
		],
		notes: [
			"Only this plan's own drawings appear. One Material Planning can cover ten drawings and feed ten separate Material Issue Plans; each pulls only the rows belonging to the drawings in its own Production Plan.",
			"Rows fulfilled from a Cut Sheet arrive already sized to the PIECE, not the plate — a 2000 × 1000 sheet cut into 500 × 250 pieces shows 500 × 250 here. That is what physically goes out.",
		],
	},
	{
		id: "warehouses",
		title: "Warehouses",
		kicker: "Where material goes",
		purpose: "Four warehouses decide every movement this plan can make. Three are needed before anything can be transferred.",
		fields: [
			{ name: "Source Warehouse", note: "Where the reserved stock is now — normally Stores. Defaults from the Production Plan's Raw Material Warehouse." },
			{ name: "Supplier / WIP Warehouse", note: "The destination. For a supplier job this is the Job Worker's own warehouse, resolved automatically once a Job Worker is set on the Subcontracting Order. For an internal job there is no supplier, so this is entered by hand and is the ONLY place the WIP warehouse is recorded." },
			{ name: "CNC Warehouse", note: "Required if any row is flagged CNC Process. Material goes here first and is forwarded on afterwards." },
			{ name: "Finished Goods Warehouse", note: "Receives both the finished item (Make Final Stock Entry) and returned off-cuts (Return Excess Entry). Neither button works until it is set." },
		],
		notes: [
			"A blank Supplier/WIP Warehouse blocks every transfer and quietly breaks the weight tracking back on the Subcontracting Order — if a transfer button does nothing useful, check here first.",
		],
	},
	{
		id: "transfer",
		title: "Select Materials to Transfer",
		kicker: "The popup that moves stock",
		purpose:
			"One popup for every leg — source to supplier, source to CNC, and CNC onward — so " +
			"there is a single place to learn. It lists what is still pending, lets you take " +
			"part of it, and is the only point in the whole system where a fractional Sec Nos " +
			"becomes whole physical pieces.",
		fields: [
			{ name: "Planned", note: "What this row was always going to transfer." },
			{ name: "Transferred", note: "What has already gone, across earlier partial transfers. Re-open the popup after a partial transfer and this is how you see where you stand." },
			{ name: "In Stock", note: "What the batch physically holds in the source warehouse right now. Zero usually means the Purchase Receipt has not been made yet — the row is planned and reserved, but the steel is not in the building." },
			{ name: "Sec Nos", note: "Editable. The hint below it reads e.g. “7.92 (Plan) · or 8 whole” so you can see the planned fraction and the nearest whole-piece figure together." },
			{ name: "Transfer Qty (Kg)", note: "Read-only, derived from Sec Nos. It is not editable on purpose: a hand-typed weight that disagreed with the piece count would ship a Stock Entry whose Sec Qty and weight contradict each other, and consumption downstream is driven by Sec Qty." },
		],
		steps: [
			"Open <b>Transfer → Select Materials to Transfer</b>. A readiness check runs first and tells you about anything that would silently reduce what moves — stock mapped but not reserved, CNC rows with no CNC warehouse, or material already sitting at the supplier.",
			"Tick the rows to send. Rows short of stock are left unticked for you.",
			"Adjust <b>Sec Nos</b> where you must hand over whole pieces. The system re-checks free stock for the higher figure and refuses it outright if the batch cannot cover it.",
			"Submit. The Stock Entry is created, Transferred goes up, and any surplus from rounding is booked as excess to return.",
			"Come back later for the rest. Partial transfers are expected, and the popup shows exactly how much has gone and how much is left.",
		],
		calcs: [
			{
				title: "Why Sec Nos reads 4.5 and what to do about it",
				item: "ISMB450", group: "Structurals",
				length: 900, sec_qty: "4.5 planned", unit_weight: 72.4,
				formula:
					"One purchased bar is 900 mm, so one piece is (900÷1000) × 72.4 = 65.16 Kg. " +
					"This batch is shared by 5 drawings — 8 Nos in total across the Material Planning — " +
					"but this plan covers only 3 of them, so it pulls 4.5 Nos. " +
					"Leave it: 4.5 × 65.16. Or type 5: 5 × 65.16",
				result: "293.22 Kg (4.5 Nos)   →   or 325.80 Kg (5 Nos), 32.58 Kg excess",
				note:
					"The fraction is not an error — it is this plan's share of a bar the other jobs also " +
					"draw from. Material Planning always reserves the exact weight a drawing needs and " +
					"never rounds, because at planning time nobody knows which jobs will be issued " +
					"together. Type 5 only if you genuinely cannot hand over half a bar; the extra " +
					"32.58 Kg is recorded as excess to come back.",
			},
			{
				title: "Where that 32.58 Kg lands on the item table",
				item: "ISMB450", group: "Structurals",
				length: 900, sec_qty: "3 rows sharing the batch", unit_weight: 72.4,
				formula:
					"Those 4.5 Nos were 3 drawings at 2 Nos, 1.5 Nos and 1 Nos. The surplus belongs to " +
					"all three, split by their Sec Nos: 2÷4.5 × 32.58, 1.5÷4.5 × 32.58, 1÷4.5 × 32.58",
				result: "14.48 + 10.86 + 7.24 = 32.58 Kg",
				note:
					"Each figure lands in that row's Transfer Excess Kg, so the surplus is visible against " +
					"the drawings that caused it rather than as one lump. The parts always add back to the " +
					"whole. Round up again on a later transfer and the column accumulates.",
			},
		],
		examples: [
			{
				type: "do",
				label: "Transfer in stages",
				text: "Send what you have, come back for the rest. The popup nets off what has already gone, so you can never double-issue a row by revisiting it.",
			},
			{
				type: "dont",
				label: "Don't expect a row with no stock to move",
				text: "If In Stock reads 0 the batch is not in the source warehouse yet. The row stays pending, and a red panel explains why rather than leaving you to work it out.",
			},
			{
				type: "dont",
				label: "Don't go looking for material already at the supplier",
				text: "A row fulfilled from an off-cut that never left the supplier is deliberately absent from the list — there is nothing in your warehouse to move. A blue panel names those rows so the gap is explained rather than silent.",
			},
		],
		notes: [
			"Nothing is offered unless it is BOTH purchased and reserved. Reserving is a separate deliberate step back on Material Planning; if stock is mapped but not reserved, the readiness check names the Material Planning so the fix is one click away.",
			"Nothing rounds by itself, anywhere in the system. This popup is the only place a fraction becomes whole pieces, and only because you typed it.",
		],
	},
	{
		id: "cnc",
		title: "CNC Routing",
		kicker: "Two legs, two Stock Entries",
		purpose:
			"Material flagged <b>CNC Process</b> in Material Planning must reach the CNC " +
			"warehouse before it reaches the supplier. That is a routing instruction, not a " +
			"preference, so it is enforced rather than assumed.",
		steps: [
			"<b>Transfer → To CNC Warehouse</b> sends the flagged rows to CNC.",
			"Machining happens. Only material that has physically arrived can be forwarded.",
			"<b>Transfer → CNC to Supplier/WIP</b> appears once there is something at CNC, and moves it onward as a SEPARATE Stock Entry. Partial forwarding is supported — release it as machining finishes.",
		],
		examples: [
			{
				type: "dont",
				label: "Don't leave CNC Warehouse blank on a plan with CNC rows",
				text: "The transfer is BLOCKED outright, not warned about. With no CNC warehouse the flag would be quietly ignored and the material would go straight to the supplier, skipping the machining step — and by the time anyone noticed, the stock would have moved.",
			},
			{
				type: "do",
				label: "Two ways to clear that block",
				text: "Either set the CNC Warehouse here, or untick CNC Process on those rows back in Material Planning if the step is genuinely not required. The block message offers both.",
			},
		],
	},
	{
		id: "excess-return",
		title: "Excess Material Items",
		kicker: "Getting the leftovers back",
		purpose:
			"Everything left over after the job — the surplus from rounding Sec Nos up, and " +
			"whatever the shop floor measures once the material is actually cut. Each row is " +
			"either returned to your warehouse as a real batch, or claimed directly by another " +
			"job while it is still at the supplier.",
		fields: [
			{ name: "Length / Width / Sec Nos", note: "The off-cut's real dimensions. Rounding-surplus rows arrive with placeholder dimensions (one standard piece) — overwrite them with what you actually measure." },
			{ name: "Return Type", note: "“Return to Own Warehouse” is the normal case. “Retain at Supplier (Virtual)” means it will never physically come back — it is consumed there — and such rows are skipped by the return entry." },
			{ name: "Return Reason", note: "Mandatory before a return entry can be created. It is what makes the returned stock explainable months later." },
			{ name: "Availability", note: "Allocated and Available, in Sec Nos and Kg — how much of this off-cut other jobs have claimed and how much is still free." },
			{ name: "Unlink Claim", note: "Releases a Material Planning's claim so the dimensions can be corrected. The off-cut then goes back into the picker for anyone to claim." },
		],
		calcs: [
			{
				title: "One off-cut, shared between jobs",
				item: "Plate 5mm", group: "Plates",
				length: 1000, sec_qty: 6, unit_weight: 7.85,
				formula:
					"A 1000 × 500 × 5 off-cut, 6 pieces at (1000÷1000) × (500÷1000) × 5 × 7.85 = 19.625 Kg each. " +
					"Job B claims 2, Job C claims 3",
				result: "5 pieces claimed (98.125 Kg) · 1 piece (19.625 Kg) still free",
				note:
					"Claiming does not create a Stock Entry — it is a promise against a specific off-cut. " +
					"The claiming rows show Batch blank with Status “Excess Mapped (Pending Return)”. When " +
					"the off-cut is physically returned, the new batch attaches itself to every row holding " +
					"a piece, and no one has to re-pick anything.",
			},
		],
		examples: [
			{
				type: "dont",
				label: "Don't change the size of an off-cut someone has claimed",
				text: "It is refused, naming the Material Planning that holds it — from this grid, from the raw-material row's Excess fields, and from the Return Excess dialog alike. Another job planned around that exact piece; shrinking it would only surface at their transfer, far too late to fix cheaply.",
			},
			{
				type: "do",
				label: "The measurement was wrong — Unlink Claim",
				text: "Release it, correct the dimensions on the raw-material row's Excess Length/Width, then let it be claimed again. Note the risk the confirmation warns about: while unlinked, another job can take it first.",
			},
			{
				type: "do",
				label: "Edit the raw-material row, not this grid",
				text: "For an off-cut created from a raw-material row, that row's Excess Length/Width/Sec Qty are the source of truth — this grid is recalculated from them on every save. The exception is a rounding-surplus row, which has no raw-material row behind it and is edited here directly.",
			},
		],
		notes: [
			"Return Excess Entry creates one Material Receipt for every unreturned row, into the Finished Goods Warehouse, and the batches it creates are traceable back to the off-cut they came from.",
		],
	},
	{
		id: "finish",
		title: "Finishing the Job",
		kicker: "Final stock entry and completion",
		purpose:
			"Once every operation on the Job work order is complete, the finished goods are " +
			"received and the plan closes itself.",
		steps: [
			"<b>Make Final Stock Entry</b> appears when all operations are done. It creates a draft Manufacture Stock Entry consuming the supplier-warehouse raw material and producing the finished item into the Finished Goods Warehouse — review it and submit from there.",
			"The plan moves to <b>Completed</b> by itself once finished goods have been received AND every Excess Material Items row is resolved: returned, claimed by another job, or flagged Retain at Supplier.",
			"Completed is one-way. The document locks; nothing later moves it back.",
		],
		notes: [
			"If the plan will not complete, it is nearly always an unresolved excess row — check that table before anything else.",
		],
	},
	{
		id: "buttons",
		title: "Every Button",
		kicker: "Quick reference",
		purpose: "What each action does, in one place.",
		fields: [
			{ name: "Refresh Raw Materials", note: "Rebuilds the list from Material Planning. Warns first, because Cut Sheet and Excess Return values you entered on rows are re-applied by matching — but anything else typed on a row is lost." },
			{ name: "Validate Stock", note: "Read-only preview of exactly what this plan will hand over: Kg and Sec Nos per item and batch, fractional totals in amber, shortfalls in red. Changes nothing — use it before transferring." },
			{ name: "Select Materials to Transfer", note: "The main transfer popup. Source → Supplier/WIP." },
			{ name: "To CNC Warehouse", note: "First leg for CNC-flagged rows. Only appears when a CNC Warehouse is set." },
			{ name: "CNC to Supplier/WIP", note: "Second leg. Only appears once material has physically arrived at CNC." },
			{ name: "Return Excess Entry", note: "Review quantities and enter a mandatory reason per row, then the return Stock Entry is created into the Finished Goods Warehouse." },
			{ name: "Make Final Stock Entry", note: "Draft Manufacture entry for the finished goods. Appears once all operations are complete." },
			{ name: "PDF", note: "A shareable batch plan — DUNO/Mark No, Customer Drawing No, planned Kg, batch details and Sec Qty — for the production or supplier team." },
		],
	},
	{
		id: "glossary",
		kind: "glossary",
		title: "Glossary",
		kicker: "Terms used here",
		fields: [
			{ name: "Sec Nos", note: "A count of physical pieces — bars, plates, cut pieces. Fractional at planning time, whole when material actually moves." },
			{ name: "W1 / W2", note: "On a Cut Sheet: W1 is the piece being cut, W2 the remnant left on the plate afterwards." },
			{ name: "Reqd Qty vs Issued Qty", note: "What the row must transfer, versus what has gone so far. Equal when the row is fully issued." },
			{ name: "Excess Qty vs Transfer Excess Kg", note: "The first is the mapped batch measured against the drawing's planned weight, set when the row is fetched. The second is surplus you created by rounding Sec Nos up at transfer time." },
			{ name: "Virtual / Pending Return", note: "An off-cut claimed by a job while still at the supplier. No batch, no stock entry — a promise, until it physically returns." },
		],
	},
];
