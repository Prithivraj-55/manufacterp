// Material Planning — User Manual page.
//
// Content is data-driven (the SECTIONS array below) specifically so that
// when Material Planning's own fields/buttons/behaviour change, updating
// this manual is a matter of editing plain-text entries here, not
// rewriting HTML. Keep this in sync whenever Material Planning changes.

frappe.pages["material-planning-manual"].on_page_load = function (wrapper) {
	let page = frappe.ui.make_app_page({
		parent: wrapper,
		title: "Material Planning — User Manual",
		single_column: true,
	});
	// Standard Frappe page header (title + back navigation) stays visible above
	// our custom-styled content -- keeps a reliable way back to the Material
	// Planning form instead of trapping the user in a fully custom shell.

	render_manual(page);
};

// ─── Content model ────────────────────────────────────────────────────────
// Each section: { id, title, kicker, purpose, fields:[{name, note}],
//   buttons:[{name, note}], steps:[string], examples:[{type:"do"|"dont", label, text}],
//   calcs:[{title, item, group, length, width, thickness, sec_qty, unit_weight,
//           formula, result}], notes:[string] }

const MP_MANUAL_SECTIONS = [
	{
		id: "overview",
		kind: "overview",
		title: "How Material Planning Works",
		kicker: "Start here",
		purpose:
			"Material Planning answers one question for every raw material a job needs: " +
			"“where is this going to come from?” It checks your real warehouse stock, " +
			"and sorts every requirement into one of three buckets — already have the exact " +
			"piece, have the item but need to cut/substitute, or don't have it at all and need " +
			"to buy it. Everything downstream (reservations, purchasing, allocation once stock " +
			"arrives) flows from that first sort.",
	},
	{
		id: "raw-materials",
		title: "Raw Materials",
		kicker: "Table 1 of 7",
		purpose:
			"The starting point. This is the full list of raw materials your selected BOMs " +
			"actually need — pulled in with the “Get Raw Materials” button. At this " +
			"stage nothing has been checked against stock yet; it's purely a requirement list, " +
			"item by item, drawing by drawing.",
		fields: [
			{ name: "Item Code / Item Name", note: "What's needed." },
			{ name: "Source BOM / Drawing / DUNO / Mark No / Cust Drawing No", note: "Where this requirement came from — keeps every row traceable back to a specific drawing." },
			{ name: "Item Group", note: "Structurals, Plates, or Nuts and Bolts — this decides which Kg formula applies everywhere downstream." },
			{ name: "Length / Width / Thickness (mm)", note: "The dimensions this requirement needs. Plates use all three; Structurals only really uses Length; Nuts and Bolts uses neither." },
			{ name: "Sec Qty", note: "Number of pieces (Nos) needed." },
			{ name: "Weight (qty)", note: "The required weight in Kg, computed from the dimensions above." },
			{ name: "Available Qty / Shortage Qty", note: "Filled in once stock is checked." },
			{ name: "Unit Weight", note: "The item's weight per metre (or per Nos), from the Item master — the constant every Kg formula multiplies by." },
		],
		calcs: [
			{
				title: "How the requirement's own Weight (Kg) is calculated",
				item: "ISA100", group: "Structurals",
				length: 3000, sec_qty: 5, unit_weight: 14.9,
				formula: "(Length ÷ 1000) × Unit Weight × Sec Qty  =  (3000 ÷ 1000) × 14.9 × 5",
				result: "223.5",
			},
			{
				title: "Same idea for a Plate (uses Width and Thickness too)",
				item: "PLATE10", group: "Plates",
				length: 500, width: 500, thickness: 3, sec_qty: 52,
				formula: "(L ÷ 1000) × (W ÷ 1000) × Thickness × Unit Weight × Sec Qty  =  (500÷1000) × (500÷1000) × 3 × 7.85 × 52",
				result: "306.15",
			},
		],
		buttons: [
			{ name: "Get Raw Materials", note: "Pulls the requirement list in from the BOMs you selected on the Selected BOMs tab." },
			{ name: "Verify Raw Materials", note: "A sanity pass over the pulled-in rows before you commit to checking stock." },
			{ name: "Check Stock Availability", note: "The big one. Runs the whole matching engine and splits every row into Available Raw Materials, Material Mapping, or Unavailable Items — explained in the next sections." },
		],
	},
	{
		id: "exact-match",
		title: "Available Raw Materials (Exact Match)",
		kicker: "Table 2 of 7",
		purpose:
			"Batches that are already the exact size you need, sitting in the warehouse right " +
			"now. No cutting, no substitution, no manual decision — just reserve it and move on. " +
			"This is the best-case outcome of “Check Stock Availability.”",
		fields: [
			{ name: "Item Code / DUNO / Cust Drawing No", note: "Same traceability as Raw Materials." },
			{ name: "Batch No", note: "The specific batch that matched — auto-selected, you don't pick this by hand here." },
			{ name: "Length / Width / Thickness", note: "The batch's own dimensions — identical to what was required, which is exactly why it landed in this table." },
			{ name: "Overall Required Qty", note: "The full quantity this drawing row needs." },
			{ name: "Allocated Qty in Batch (Required Qty)", note: "How much of this specific batch is being claimed for this row — can be less than Overall Required Qty if the batch had to be split across several drawings." },
			{ name: "Available Qty in Batch", note: "How much free stock that batch actually had at match time." },
			{ name: "Reserved / Reserved Qty / Shortfall Qty / Reserved On", note: "Filled in once you reserve this row (see Reserve/Unreserve below)." },
			{ name: "CNC Process", note: "Ticks that this piece needs CNC cutting before it goes to the supplier — full explanation and example below." },
			{ name: "Skip Auto Suggest Batch", note: "Tick this and save to send the row over to Material Mapping instead — useful if you'd rather save this exact-match batch for a different job." },
		],
		steps: [
			"“Check Stock Availability” compares each required row's Length/Width/Thickness against every batch of that item currently free in your warehouse.",
			"A batch only counts as an Exact Match if its own Length, Width, AND Thickness are EQUAL to what's required — not “close enough,” not “bigger and could be cut down.” Exactly equal.",
			"If more than one batch could match, the largest free one is tried first, and if one batch can't cover the whole requirement, the remainder is filled from the next batch — you may see two rows for the same drawing requirement, one per batch used.",
		],
		calcs: [
			{
				title: "Exact match found",
				item: "ISA100", group: "Structurals",
				length: 12000, width: 0, thickness: 0, sec_qty: 5, unit_weight: 14.9,
				formula: "Batch ISA100-L12000-SR001 is 12000mm — exactly what's required (12000 = 12000, 0 = 0, 0 = 0). Kg = (12000÷1000) × 14.9 × 5",
				result: "894.0",
			},
		],
		examples: [
			{
				type: "do",
				label: "Exact match — auto-selected",
				text: "Required: ISA100, Length 12000mm. In stock: Batch ISA100-L12000-SR001, exactly 12000mm. → Same dimensions, so it's an exact match. The batch is auto-selected into this table, ready to reserve.",
			},
			{
				type: "dont",
				label: "Same item, wrong size — NOT auto-selected",
				text: "Required: ISA100, Length 5000mm. In stock: only ISA100-L12000-SR001 (12000mm). → Same item, plenty of stock — but the dimensions don't match exactly, so nothing gets auto-selected here. This requirement goes to Material Mapping instead, where you manually assign that 12000mm bar and the system works out how much of it (by weight) this 5000mm requirement will consume.",
			},
		],
		buttons: [
			{ name: "Reserve (grid button)", note: "Reserves every matched row in one go, with partial-stock awareness — you'll get a summary of what was fully reserved, partially covered, or blocked (e.g. a batch still waiting on inspection)." },
			{ name: "Unreserve (per row)", note: "Releases just that row's claim." },
		],
		notes: [
			"Reserving only ever claims the quantity ON THIS ROW — never the whole batch. Example: Batch ISA100-L12000-SR001 has 12,158.4 Kg free across the warehouse. This row only needs 894 Kg (the calculation above), so reserving it claims exactly 894 Kg. The remaining 11,264.4 Kg stays free — visible and reservable by any other row or any other Material Planning, right up until someone else claims it too.",
			"Reserving is a soft claim, not a physical stock movement — it just marks the quantity as spoken for so no other Material Planning can also claim it. The actual movement out of the warehouse happens later, during Transfer (from the Material Issue Plan).",
			"CNC Process — tick this when the piece needs CNC cutting/machining at your own facility before it's ready to send to the supplier. Instead of moving straight from stores to the supplier/WIP warehouse, a CNC-ticked row's material is sent first to the CNC Warehouse set on the Material Issue Plan (via its “To CNC Warehouse” button); once machining is done, the separate “CNC to Supplier/WIP” button forwards it on. Example: a 10mm plate batch needs laser cutting before subcontracted fabrication — tick CNC Process on its row, and it's routed through the CNC Warehouse first; un-ticked rows on the same plan transfer straight to the supplier as normal.",
		],
	},
	{
		id: "material-mapping",
		title: "Material Mapping (Alternate Stock)",
		kicker: "Table 3 of 7",
		purpose:
			"For everything that has SOME usable stock but isn't an exact-size match — a full-" +
			"length bar or plate that needs cutting down, a substitute (alternate) item, or " +
			"material recovered from another job's excess. This is where you (or an automatic " +
			"process) make the sizing/substitution decision by hand.",
		fields: [
			{ name: "Item Code / Required Qty / Required Sec Qty", note: "What's actually needed — unchanged from the original requirement." },
			{ name: "Length / Width / Thickness / Unit Weight", note: "The REQUIRED dimensions (not the batch's) — shown for reference so you know what you're covering." },
			{ name: "Assign Batch", note: "Pick any batch of this item (or of a substitute item) by hand — no dimension-matching restriction here, unlike Exact Match." },
			{ name: "Status (Mapped / Not Mapped / Virtual (At Supplier) / Claimed (Pending Return))", note: "At a glance, what state this row is in — see the Status legend below." },
			{ name: "Planned Item (from Batch)", note: "The item the assigned batch actually is — will differ from Item Code if you've substituted an alternate item." },
			{ name: "Batch Length / Width / Thickness / Unit Weight", note: "The ASSIGNED BATCH's own dimensions — this is what the Kg formula actually uses, not the required dimensions." },
			{ name: "Sec Qty (NOS) / Calc Qty (Kg)", note: "How many pieces you're taking from the batch, and the Kg that works out to." },
			{ name: "Reserve stock without dimensions", note: "Explained with a worked example below." },
			{ name: "Allocate based on Sec Nos", note: "Explained with a worked example below — only relevant once dimensions are skipped." },
			{ name: "CNC Process", note: "Same meaning as on Available Raw Materials — see that section for the full example." },
			{ name: "Reserved / Reserved Qty / Shortfall Qty / Reserved On", note: "Same reservation bookkeeping as Exact Match — and the same rule: only the quantity ON THIS ROW gets reserved, never the whole batch." },
			{ name: "Batch Total / Reserved / Free Qty", note: "A live snapshot of that batch's stock position across the whole system, not just this row." },
		],
		calcs: [
			{
				title: "Assign Batch — dimensions ON (default), whole-bar consumption",
				item: "ISMB400", group: "Structurals",
				length: 12000, sec_qty: 1, unit_weight: 61.6,
				formula: "Only a full 12000mm bar is available; you assign it and set Sec Qty = 1 whole bar. Calc Qty = (12000÷1000) × 61.6 × 1",
				result: "739.2",
				note: "If the drawing only actually needed the weight of a 3000mm length (184.8 Kg), the rest of this 739.2 Kg is off-cut — tracked later as excess once the job physically cuts it, in Material Issue Plan's Excess Return, not here.",
			},
			{
				title: "“Reserve stock without dimensions” — ON, whole-piece rounding",
				item: "Alternate item (different profile)", group: "Structurals",
				length: 6000, sec_qty: "rounded up, see below", unit_weight: 10,
				formula:
					"Requirement is 500 Kg. This batch's own shape gives Kg-per-piece = (6000÷1000) × 10 = 60 Kg. " +
					"Pieces needed = 500 ÷ 60 = 8.33 → rounded UP to 9 whole pieces (you can't reserve part of a bar). " +
					"Reserved Kg = 9 × 60",
				result: "540.0",
				note: "540 Kg reserved to cover a 500 Kg requirement — the 40 Kg difference is the unavoidable rounding-up to whole pieces, same idea as the Consolidate Item “Difference” column.",
			},
		],
		examples: [
			{
				type: "do",
				label: "“Reserve stock without dimensions” — OFF (default)",
				text: "You assign a batch of the SAME item, just a different piece. The system expects the batch's own Length/Width/Thickness to make sense against what's required, and computes an exact Kg from those dimensions. Precise, dimension-driven — use this whenever the batch's dimensions genuinely describe what you're consuming.",
			},
			{
				type: "do",
				label: "“Reserve stock without dimensions” — ON",
				text: "You're substituting a completely different profile (an Alternate Item), or you simply want to reserve in whole pieces rather than an exact fractional cut. Tick this box and, with “Allocate based on Sec Nos” also on, the system rounds up to the nearest whole number of pieces of the assigned batch needed to cover the requirement — see the worked calculation above. This is exactly what happens automatically when a Purchase Receipt fulfils an Alternate Item — you'll see this box already ticked on rows created that way.",
			},
			{
				type: "dont",
				label: "Don't expect an exact, unrounded Kg with this box ON",
				text: "With “Reserve stock without dimensions” + “Allocate based on Sec Nos” both ON, the reserved Kg is always rounded UP to a whole number of pieces of the assigned batch — it will usually be slightly MORE than the bare requirement, never less. If you need the exact unrounded Kg instead, turn “Allocate based on Sec Nos” off (see below) or use dimension-driven assignment instead.",
			},
		],
		notes: [
			"“Allocate based on Sec Nos” only matters once “Reserve stock without dimensions” is ON. Left ON (its own default): the reserved Kg rounds up to whole pieces of the batch, as shown above. Turned OFF: the exact Required Kg (row.qty) is reserved directly with no rounding — and the later Transfer step will ask you to enter Sec Qty again there, for its own weight calculation.",
			"Status legend — “Mapped”: a real batch is assigned. “Not Mapped”: nothing assigned yet. “Virtual (At Supplier)”: fulfilled from another job's excess material that's staying at the supplier and will never come back to your warehouse — no batch, nothing to transfer. “Claimed (Pending Return)”: fulfilled from another job's excess that HASN'T physically returned to stock yet, but is already promised to this row.",
		],
		buttons: [
			{ name: "Reserve / Unreserve", note: "Same soft-claim mechanism as Available Raw Materials — works whether the row has a real batch or is a Virtual/Pending-Return excess claim." },
			{
				name: "Excess Material Mapping",
				note: "Opens the excess-material picker — see the dedicated section below for the full explanation and worked examples of both cases it covers.",
			},
		],
	},
	{
		id: "excess-material-mapping",
		title: "Excess Material Mapping",
		kicker: "Reusing leftovers from other jobs",
		purpose:
			"Instead of buying fresh raw material, this lets you reuse material that's already " +
			"“spare” from a DIFFERENT job — either genuinely sitting back in your own warehouse " +
			"as an off-cut, or simply promised from another job's Excess Material Items table " +
			"before it's even physically moved anywhere. Opened from the “Excess Material " +
			"Mapping” button on any Material Mapping row.",
		fields: [
			{ name: "Item Code / Item Name", note: "The excess item on offer." },
			{ name: "Source", note: "“Returned Batch” (physically back in your own warehouse) or “Not Yet Returned (Pending)” (still just a row in another job's Excess Material Items table)." },
			{ name: "Batch / MIP", note: "The batch number for a Returned Batch, or the source Material Issue Plan for a Not Yet Returned row." },
			{ name: "L (mm) / W (mm) / T (mm)", note: "Dimensions of the excess piece." },
			{ name: "Sec Qty", note: "How many pieces / what quantity is on offer." },
			{ name: "Free/Qty (Kg)", note: "For a Returned Batch, how much of it is still free to claim. For a Not Yet Returned row, the full quantity on offer." },
			{ name: "Supplier", note: "Shown for Not Yet Returned rows, so you know where the material is physically sitting." },
		],
		calcs: [
			{
				title: "Case 1 — Returned Batch (partial claim allowed)",
				item: "ISA100 off-cut", group: "Structurals",
				length: 300, sec_qty: 1, unit_weight: 14.9,
				formula:
					"Batch ISA100-L300-SR054 has 2 pieces free (8.94 Kg total). You only need 1, so you edit Sec Qty down to 1. " +
					"Kg claimed = (300÷1000) × 14.9 × 1",
				result: "4.47",
				note: "The other piece (4.47 Kg) stays free on that same batch for someone else to claim later — same “only the selected quantity” rule as a normal reservation.",
			},
			{
				title: "Case 2 — Not Yet Returned (all-or-nothing)",
				item: "ZZTEST-VIRTUAL-EXCESS", group: "Structurals",
				length: 1000, sec_qty: 1, unit_weight: 5,
				formula: "This row is claimed WHOLE — Sec Qty is locked, not editable. Kg claimed = the row's full (1000÷1000) × 5 × 1",
				result: "5.0",
				note: "No Stock Entry is created by claiming this — it's a soft promise only. The Material Mapping row's Batch stays blank, and its Status shows “Virtual (At Supplier)” or “Claimed (Pending Return)” depending on how the source row was flagged.",
			},
		],
		examples: [
			{
				type: "do",
				label: "Returned Batch — partially reservable",
				text: "A “Returned Batch” row's Sec Qty field is editable, defaulting to the smaller of the batch's own Sec Qty or its free quantity. You can take less than what's on offer, exactly like a normal batch reservation.",
			},
			{
				type: "dont",
				label: "Don't expect to partially claim a “Not Yet Returned” row",
				text: "Its Sec Qty field is locked read-only to the row's full amount the moment you select it — this kind of excess can only be claimed in full, never split across two jobs.",
			},
		],
		notes: [
			"“Retain at Supplier (Virtual)” material is flagged that way because it will NEVER physically return to your warehouse — it's used/consumed directly at the supplier. “Pending Return” material is just excess that hasn't been walked back to stock yet, but eventually will be — claiming it now doesn't stop that from happening later; it just reserves the outcome in advance.",
		],
	},
	{
		id: "unavailable-items",
		title: "Unavailable Items",
		kicker: "Table 4 of 7 — internal staging",
		purpose:
			"Anything with genuinely no usable stock at all. This table is mostly working " +
			"machinery now, not something you need to act on directly — it's collapsed by " +
			"default to keep the form clean. Every row here is automatically grouped, by item " +
			"code, into the Consolidate Item table below, which is the one you actually work " +
			"from for purchasing.",
		fields: [
			{ name: "Item Code / DUNO / Cust Drawing No", note: "The original per-drawing requirement — kept here for traceability even after it's grouped into Consolidate Item." },
			{ name: "Alternate Item section", note: "An optional per-row substitute, with its own Length/Width/Thickness/Sec Qty/Unit Weight — the older, per-drawing version of the substitution idea now more commonly done once, in bulk, on Consolidate Item instead." },
		],
		notes: [
			"Why it's still here at all: once a Purchase Receipt for these items arrives, the system needs to know exactly which drawing(s) to allocate the received stock back into — that's tracked at THIS row's level, even when the purchase itself was created from the consolidated view above it.",
		],
	},
	{
		id: "consolidate-item",
		title: "Consolidate Item",
		kicker: "Table 5 of 7 — the purchasing table",
		purpose:
			"One row per item code, combining every drawing's need for that item into a single " +
			"purchase-friendly line. If five different drawings all need some ISA100, you get " +
			"ONE row here instead of five — this is the table you actually buy from.",
		fields: [
			{ name: "Required Kg", note: "The total across every drawing/Unavailable Item row that fed into this line." },
			{ name: "Unit Weight", note: "The original item's weight-per-metre (or per Nos), from the Item master — read-only, shown purely for reference so you can see what the Purchase Kg formula is using." },
			{ name: "Length / Width / Thickness / Sec Qty", note: "Enter the size and piece count you intend to buy — Purchase Kg calculates automatically from these." },
			{ name: "Purchase Kg", note: "Auto-calculated, same formula as everywhere else — the Alternate Item's Unit Weight is used instead of the original's, whenever an Alternate Item is set." },
			{ name: "Difference (Purchase Kg − Required Kg)", note: "Almost always a small positive surplus, because you can usually only buy whole pieces/standard lengths, not the exact fractional Kg required. This is normal purchasing rounding, NOT excess material to be returned." },
			{ name: "Alternate Item section", note: "Set once for the whole consolidated line to substitute a different item for every drawing it represents — once set, Length/Width/Thickness/Sec Qty above describe the ALTERNATE item, not the original." },
		],
		calcs: [
			{
				title: "Purchase Kg vs Required Kg",
				item: "ISMB400", group: "Structurals",
				length: 12000, sec_qty: 32, unit_weight: 61.6,
				formula: "You'll buy 32 whole 12m bars. Purchase Kg = (12000÷1000) × 61.6 × 32",
				result: "23,654.40",
				note: "Required Kg across every drawing was 23,039.40 — so Difference = 23,654.40 − 23,039.40 = 614.998 Kg of purchasing surplus, purely from rounding up to whole bars.",
			},
		],
		steps: [
			"Enter Length/Width/Thickness/Sec Qty for how you actually intend to purchase (e.g. one standard 12m bar, however many pieces).",
			"Purchase Kg and Difference calculate automatically.",
			"Click “Create Material Request” to raise the purchase for the selected rows.",
		],
		examples: [
			{
				type: "do",
				label: "Purchasing surplus is normal, not “excess material”",
				text: "Once received, the 614.998 Kg surplus above becomes ordinary free stock of the batch, available to any future job that needs ISMB400. It is NOT sent through the Excess Material Mapping system — that's reserved for material left over after actually CUTTING a job (an off-cut), which needs someone to deliberately flag it. Buying a bit extra up front never triggers that on its own.",
			},
		],
		buttons: [
			{
				name: "Update & Map Exact Matches",
				note:
					"For every row here: if an active Material Request already covers it, the row is left untouched — a purchase is already in motion. Otherwise the row is removed and stock is re-checked against the underlying drawing requirements: an exact match now found goes to Available Raw Materials, a batch item with still no exact match goes to Material Mapping (blank batch, assign by hand), and it only stays unavailable if truly nothing exists.",
			},
			{ name: "Create Material Request", note: "Raises a purchase for the selected rows — orders the Alternate Item instead of the original wherever one is set." },
		],
	},
	{
		id: "after-purchase",
		title: "After Purchase: Automatic Allocation",
		kicker: "Table 6 of 7 — what happens on receipt",
		kind: "info",
		purpose:
			"Once a Purchase Receipt for a Material Request created from this plan is submitted, " +
			"allocation happens AUTOMATICALLY — there is no button to click for this part.",
		steps: [
			"The original item was purchased (no substitution) → the received batch lands in Available Raw Materials, exactly like a real exact match.",
			"An Alternate Item was purchased → the received batch lands in Material Mapping instead, with “Reserve stock without dimensions” already switched on for you, and “Allocate based on Sec Nos” on alongside it — same whole-piece rounding as the worked example above.",
			"If the purchase was consolidated across several drawings' worth of the same item, the received quantity is split sequentially — the first drawing (by row order) is filled completely, then the next, and so on. Any purchasing surplus left after every drawing is fully covered simply becomes free warehouse stock (see the Consolidate Item section above) — it isn't assigned to any one drawing.",
		],
	},
	{
		id: "checking-stock",
		title: "Checking Overall Stock",
		kicker: "Table 7 of 7 — outside Material Planning",
		kind: "info",
		purpose:
			"Everything above shows stock from the point of view of ONE Material Planning " +
			"document. To see overall, warehouse-wide stock — including what's free right now " +
			"across every job, batch, and reservation — use the Manufyxinvenza Stock Balance " +
			"report instead of trying to piece it together from individual plans.",
		steps: [
			"Open it from the Awesomebar (search bar at the top) — type “Manufyxinvenza Stock Balance” and select the report.",
			"It shows item-and-batch-wise on-hand quantity, what's reserved against which Material Planning, and what's genuinely free — the same free-Kg figures the Exact Match and Excess Material Mapping pickers use internally, but for every item and warehouse at once.",
		],
	},
	{
		id: "glossary",
		title: "Quick Reference",
		kind: "glossary",
		kicker: "Keep this handy",
		fields: [
			{ name: "Exact Match", note: "A batch whose own Length/Width/Thickness are EQUAL to what's required — not just “close” or “big enough.”" },
			{ name: "Reserve", note: "A soft claim on stock — marks it as spoken for so nothing else can also claim it. Always just the row's own quantity, never the whole batch. No physical movement happens yet." },
			{ name: "Sec Qty", note: "Secondary quantity — the number of individual pieces (Nos)." },
			{ name: "Alternate Item", note: "A substitute item used in place of what was originally required." },
			{ name: "Consolidated", note: "Multiple drawings' requirements for the same item code, combined into one purchasing line." },
			{ name: "Virtual Excess", note: "Material promised from another job's leftovers that has no physical batch — either it will never return to your warehouse (stays at the supplier) or it just hasn't yet." },
			{ name: "CNC Process", note: "Marks that a piece needs CNC cutting at your own facility before it can go to the supplier — routes it through the Material Issue Plan's CNC Warehouse first." },
			{ name: "DUNO / Mark No", note: "The drawing-level identifier that keeps every row traceable back to exactly which piece, on which drawing, it belongs to." },
		],
	},
];

function render_manual(page) {
	inject_styles();

	let nav_html = MP_MANUAL_SECTIONS.map(
		// No real "#..." href on purpose -- Frappe's router intercepts anchor
		// clicks with hash hrefs and tries to resolve them as a page route
		// (showing a "Page #mpm-... not found" dialog), even with
		// preventDefault() in our own handler below. Navigation is done purely
		// via the click handler + scrollIntoView instead.
		(s) => `<a href="javascript:void(0)" class="mpm-nav-link" data-id="${s.id}">${frappe.utils.escape_html(s.title)}</a>`
	).join("");

	let sections_html = MP_MANUAL_SECTIONS.map(render_section).join("");

	page.main.html(`
		<div class="mpm-root">
			<header class="mpm-hero">
				<div class="mpm-hero-kicker">${__("Material Planning")}</div>
				<h1>${__("The Complete Guide")}</h1>
				<p>${__("A step-by-step walkthrough of every table, field, and button — with worked examples — written so a first-time user can follow it start to finish.")}</p>
			</header>
			<div class="mpm-body">
				<nav class="mpm-nav">${nav_html}</nav>
				<main class="mpm-content">${sections_html}</main>
			</div>
		</div>
	`);

	setup_scrollspy(page);
}

function render_section(s) {
	if (s.kind === "overview") {
		return `
		<section id="mpm-${s.id}" class="mpm-card mpm-overview">
			<div class="mpm-kicker">${frappe.utils.escape_html(s.kicker)}</div>
			<h2>${frappe.utils.escape_html(s.title)}</h2>
			<p class="mpm-purpose">${s.purpose}</p>
			${render_flow_diagram()}
		</section>`;
	}

	let parts = [];
	parts.push(`<div class="mpm-kicker">${frappe.utils.escape_html(s.kicker || "")}</div>`);
	parts.push(`<h2>${frappe.utils.escape_html(s.title)}</h2>`);
	if (s.purpose) parts.push(`<p class="mpm-purpose">${s.purpose}</p>`);

	if (s.fields && s.fields.length) {
		parts.push(`
			<h3>${s.kind === "glossary" ? __("Terms") : __("Fields")}</h3>
			<table class="mpm-field-table">
				<tbody>
					${s.fields.map((f) => `
						<tr>
							<td class="mpm-field-name">${frappe.utils.escape_html(f.name)}</td>
							<td class="mpm-field-note">${f.note}</td>
						</tr>
					`).join("")}
				</tbody>
			</table>
		`);
	}

	if (s.steps && s.steps.length) {
		parts.push(`
			<h3>${__("How It Works")}</h3>
			<ol class="mpm-steps">
				${s.steps.map((step) => `<li>${step}</li>`).join("")}
			</ol>
		`);
	}

	if (s.calcs && s.calcs.length) {
		parts.push(`
			<h3>${__("Worked Example")}</h3>
			<div class="mpm-calcs">
				${s.calcs.map(render_calc).join("")}
			</div>
		`);
	}

	if (s.examples && s.examples.length) {
		parts.push(`
			<h3>${__("Examples")}</h3>
			<div class="mpm-examples">
				${s.examples.map((ex) => `
					<div class="mpm-example mpm-example-${ex.type}">
						<div class="mpm-example-icon">${ex.type === "do" ? "✓" : "✕"}</div>
						<div class="mpm-example-body">
							<div class="mpm-example-label">${frappe.utils.escape_html(ex.label)}</div>
							<div class="mpm-example-text">${ex.text}</div>
						</div>
					</div>
				`).join("")}
			</div>
		`);
	}

	if (s.buttons && s.buttons.length) {
		parts.push(`
			<h3>${__("Buttons")}</h3>
			<div class="mpm-buttons">
				${s.buttons.map((b) => `
					<div class="mpm-button-row">
						<span class="mpm-button-pill">${frappe.utils.escape_html(b.name)}</span>
						<span class="mpm-button-note">${b.note}</span>
					</div>
				`).join("")}
			</div>
		`);
	}

	if (s.notes && s.notes.length) {
		parts.push(`
			<div class="mpm-notes">
				${s.notes.map((n) => `<div class="mpm-note">${n}</div>`).join("")}
			</div>
		`);
	}

	return `<section id="mpm-${s.id}" class="mpm-card">${parts.join("\n")}</section>`;
}

function render_calc(c) {
	let dim_rows = [];
	if (c.length !== undefined) dim_rows.push(["Length", c.length + " mm"]);
	if (c.width !== undefined) dim_rows.push(["Width", c.width + " mm"]);
	if (c.thickness !== undefined) dim_rows.push(["Thickness", c.thickness + " mm"]);
	dim_rows.push(["Sec Qty", c.sec_qty]);
	dim_rows.push(["Unit Weight", c.unit_weight]);

	return `
	<div class="mpm-calc">
		<div class="mpm-calc-title">${frappe.utils.escape_html(c.title)}</div>
		<div class="mpm-calc-item">${frappe.utils.escape_html(c.item)} <span>· ${frappe.utils.escape_html(c.group)}</span></div>
		<table class="mpm-calc-dims">
			${dim_rows.map(([k, v]) => `<tr><td>${k}</td><td>${v}</td></tr>`).join("")}
		</table>
		<div class="mpm-calc-formula">${c.formula}</div>
		<div class="mpm-calc-result">= ${c.result} Kg</div>
		${c.note ? `<div class="mpm-calc-note">${c.note}</div>` : ""}
	</div>`;
}

function render_flow_diagram() {
	return `
	<div class="mpm-flow">
		<div class="mpm-flow-box mpm-flow-start">${__("Raw Materials")}</div>
		<div class="mpm-flow-arrow">↓ ${__("Check Stock Availability")}</div>
		<div class="mpm-flow-split">
			<div class="mpm-flow-box mpm-flow-good">${__("Available Raw Materials")}<span>${__("exact size, ready to reserve")}</span></div>
			<div class="mpm-flow-box mpm-flow-mid">${__("Material Mapping")}<span>${__("needs cutting, substitution, or excess reuse")}</span></div>
			<div class="mpm-flow-box mpm-flow-bad">${__("Unavailable Items")}<span>${__("nothing in stock")}</span></div>
		</div>
		<div class="mpm-flow-arrow">↓ ${__("grouped by item code")}</div>
		<div class="mpm-flow-box mpm-flow-mid">${__("Consolidate Item")}<span>${__("one line per item, ready to purchase")}</span></div>
		<div class="mpm-flow-arrow">↓ ${__("Create Material Request → Purchase Order → Purchase Receipt")}</div>
		<div class="mpm-flow-box mpm-flow-good">${__("Allocated back automatically")}<span>${__("into Available Raw Materials or Material Mapping")}</span></div>
	</div>`;
}

function setup_scrollspy(page) {
	let $links = page.main.find(".mpm-nav-link");

	$links.on("click", function (e) {
		e.preventDefault();
		let id = $(this).data("id");
		let $target = page.main.find("#mpm-" + id);
		if ($target.length) {
			$target[0].scrollIntoView({ behavior: "smooth", block: "start" });
		}
	});

	let sections = MP_MANUAL_SECTIONS.map((s) => page.main.find("#mpm-" + s.id)[0]).filter(Boolean);
	if (!sections.length || !window.IntersectionObserver) return;

	let observer = new IntersectionObserver(
		(entries) => {
			entries.forEach((entry) => {
				if (entry.isIntersecting) {
					let id = entry.target.id.replace("mpm-", "");
					$links.removeClass("active");
					page.main.find(`.mpm-nav-link[data-id="${id}"]`).addClass("active");
				}
			});
		},
		{ root: null, rootMargin: "-15% 0px -70% 0px", threshold: 0 }
	);
	sections.forEach((el) => observer.observe(el));
}

function inject_styles() {
	if (document.getElementById("mpm-styles")) return;
	let style = document.createElement("style");
	style.id = "mpm-styles";
	style.innerHTML = `
		.mpm-root {
			--mpm-bg: #FBEDE8;
			--mpm-card-bg: #FFFFFF;
			--mpm-heading: #3B1730;
			--mpm-accent: #E8613C;
			--mpm-accent-soft: #FCE3D8;
			--mpm-text: #4A4550;
			--mpm-text-muted: #948C97;
			--mpm-good: #1F9254;
			--mpm-good-bg: #E7F6EE;
			--mpm-bad: #C6462F;
			--mpm-bad-bg: #FBEAE6;
			--mpm-border: #F0DDD5;
			background: var(--mpm-bg);
			min-height: 100%;
			margin: -15px -25px;
			padding: 0 0 60px 0;
			font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
			color: var(--mpm-text);
		}
		.mpm-hero {
			text-align: center;
			padding: 56px 20px 40px;
			max-width: 720px;
			margin: 0 auto;
		}
		.mpm-hero-kicker {
			text-transform: uppercase;
			letter-spacing: 2px;
			font-size: 12px;
			font-weight: 700;
			color: var(--mpm-accent);
			margin-bottom: 10px;
		}
		.mpm-hero h1 {
			font-family: Georgia, "Times New Roman", serif;
			font-weight: 700;
			font-size: 40px;
			color: var(--mpm-heading);
			margin: 0 0 14px;
		}
		.mpm-hero p {
			font-size: 15px;
			color: var(--mpm-text-muted);
			line-height: 1.6;
			margin: 0;
		}
		.mpm-body {
			display: flex;
			max-width: 1100px;
			margin: 0 auto;
			padding: 0 20px;
			gap: 32px;
			align-items: flex-start;
		}
		.mpm-nav {
			position: sticky;
			top: 20px;
			flex: 0 0 220px;
			display: flex;
			flex-direction: column;
			gap: 2px;
			background: var(--mpm-card-bg);
			border: 1px solid var(--mpm-border);
			border-radius: 12px;
			padding: 10px;
			max-height: calc(100vh - 40px);
			overflow-y: auto;
		}
		.mpm-nav-link {
			display: block;
			padding: 9px 12px;
			border-radius: 8px;
			font-size: 13px;
			font-weight: 500;
			color: var(--mpm-text);
			text-decoration: none;
			border-left: 3px solid transparent;
			transition: background .15s, color .15s;
		}
		.mpm-nav-link:hover {
			background: var(--mpm-accent-soft);
			color: var(--mpm-heading);
			text-decoration: none;
		}
		.mpm-nav-link.active {
			background: var(--mpm-accent-soft);
			color: var(--mpm-accent);
			border-left-color: var(--mpm-accent);
			font-weight: 700;
		}
		.mpm-content {
			flex: 1;
			min-width: 0;
			display: flex;
			flex-direction: column;
			gap: 24px;
		}
		.mpm-card {
			background: var(--mpm-card-bg);
			border: 1px solid var(--mpm-border);
			border-radius: 16px;
			padding: 32px 36px;
			box-shadow: 0 2px 10px rgba(59, 23, 48, 0.04);
			scroll-margin-top: 20px;
		}
		.mpm-kicker {
			text-transform: uppercase;
			letter-spacing: 1.5px;
			font-size: 11px;
			font-weight: 700;
			color: var(--mpm-accent);
			margin-bottom: 6px;
		}
		.mpm-card h2 {
			font-family: Georgia, "Times New Roman", serif;
			font-weight: 700;
			font-size: 26px;
			color: var(--mpm-heading);
			margin: 0 0 14px;
		}
		.mpm-card h3 {
			font-size: 14px;
			font-weight: 700;
			color: var(--mpm-heading);
			text-transform: uppercase;
			letter-spacing: .5px;
			margin: 26px 0 12px;
		}
		.mpm-purpose {
			font-size: 15px;
			line-height: 1.7;
			color: var(--mpm-text);
			margin: 0;
		}
		.mpm-field-table {
			width: 100%;
			border-collapse: collapse;
		}
		.mpm-field-table tr {
			border-top: 1px solid var(--mpm-border);
		}
		.mpm-field-table tr:first-child { border-top: none; }
		.mpm-field-table td {
			padding: 10px 0;
			vertical-align: top;
			font-size: 13.5px;
			line-height: 1.6;
		}
		.mpm-field-name {
			width: 240px;
			font-weight: 700;
			color: var(--mpm-heading);
			padding-right: 20px !important;
		}
		.mpm-field-note { color: var(--mpm-text); }
		.mpm-steps {
			margin: 0;
			padding-left: 22px;
			font-size: 14px;
			line-height: 1.8;
			color: var(--mpm-text);
		}
		.mpm-steps li { margin-bottom: 6px; }
		.mpm-calcs {
			display: flex;
			flex-direction: column;
			gap: 16px;
		}
		.mpm-calc {
			background: #fffaf7;
			border: 1.5px dashed var(--mpm-accent);
			border-radius: 12px;
			padding: 18px 20px;
		}
		.mpm-calc-title {
			font-weight: 700;
			font-size: 13.5px;
			color: var(--mpm-heading);
			margin-bottom: 8px;
		}
		.mpm-calc-item {
			font-size: 13px;
			font-weight: 600;
			color: var(--mpm-accent);
			margin-bottom: 10px;
		}
		.mpm-calc-item span { font-weight: 400; color: var(--mpm-text-muted); }
		.mpm-calc-dims {
			border-collapse: collapse;
			margin-bottom: 12px;
		}
		.mpm-calc-dims td {
			font-size: 12.5px;
			padding: 3px 14px 3px 0;
			color: var(--mpm-text);
		}
		.mpm-calc-dims td:first-child { color: var(--mpm-text-muted); }
		.mpm-calc-formula {
			font-family: "SFMono-Regular", Consolas, Menlo, monospace;
			font-size: 12.5px;
			line-height: 1.6;
			color: var(--mpm-text);
			background: var(--mpm-accent-soft);
			border-radius: 8px;
			padding: 10px 12px;
			margin-bottom: 10px;
		}
		.mpm-calc-result {
			font-size: 18px;
			font-weight: 700;
			color: var(--mpm-good);
		}
		.mpm-calc-note {
			margin-top: 10px;
			font-size: 12.5px;
			line-height: 1.6;
			color: var(--mpm-text-muted);
			font-style: italic;
		}
		.mpm-examples {
			display: flex;
			flex-direction: column;
			gap: 14px;
		}
		.mpm-example {
			display: flex;
			gap: 14px;
			padding: 16px 18px;
			border-radius: 12px;
			align-items: flex-start;
		}
		.mpm-example-do { background: var(--mpm-good-bg); }
		.mpm-example-dont { background: var(--mpm-bad-bg); }
		.mpm-example-icon {
			flex: 0 0 26px;
			width: 26px;
			height: 26px;
			border-radius: 50%;
			display: flex;
			align-items: center;
			justify-content: center;
			font-weight: 700;
			font-size: 14px;
			color: #fff;
			margin-top: 1px;
		}
		.mpm-example-do .mpm-example-icon { background: var(--mpm-good); }
		.mpm-example-dont .mpm-example-icon { background: var(--mpm-bad); }
		.mpm-example-label {
			font-weight: 700;
			font-size: 13.5px;
			margin-bottom: 4px;
		}
		.mpm-example-do .mpm-example-label { color: var(--mpm-good); }
		.mpm-example-dont .mpm-example-label { color: var(--mpm-bad); }
		.mpm-example-text {
			font-size: 13.5px;
			line-height: 1.65;
			color: var(--mpm-text);
		}
		.mpm-buttons {
			display: flex;
			flex-direction: column;
			gap: 10px;
		}
		.mpm-button-row {
			display: flex;
			align-items: flex-start;
			gap: 14px;
			font-size: 13.5px;
			line-height: 1.6;
		}
		.mpm-button-pill {
			flex: 0 0 auto;
			white-space: nowrap;
			background: var(--mpm-heading);
			color: #fff;
			font-size: 12px;
			font-weight: 600;
			padding: 5px 12px;
			border-radius: 20px;
		}
		.mpm-button-note { color: var(--mpm-text); padding-top: 3px; }
		.mpm-notes { margin-top: 22px; display: flex; flex-direction: column; gap: 10px; }
		.mpm-note {
			font-size: 13px;
			line-height: 1.6;
			color: var(--mpm-heading);
			background: var(--mpm-accent-soft);
			border-radius: 10px;
			padding: 12px 16px;
		}
		.mpm-flow {
			margin-top: 28px;
			display: flex;
			flex-direction: column;
			align-items: center;
			gap: 6px;
		}
		.mpm-flow-box {
			background: #fff;
			border: 1.5px solid var(--mpm-border);
			border-radius: 12px;
			padding: 12px 18px;
			text-align: center;
			font-weight: 700;
			font-size: 13.5px;
			color: var(--mpm-heading);
			min-width: 220px;
		}
		.mpm-flow-box span {
			display: block;
			font-weight: 400;
			font-size: 11.5px;
			color: var(--mpm-text-muted);
			margin-top: 3px;
		}
		.mpm-flow-start { background: var(--mpm-heading); color: #fff; }
		.mpm-flow-good { border-color: var(--mpm-good); background: var(--mpm-good-bg); }
		.mpm-flow-mid { border-color: var(--mpm-accent); background: var(--mpm-accent-soft); }
		.mpm-flow-bad { border-color: var(--mpm-bad); background: var(--mpm-bad-bg); }
		.mpm-flow-arrow {
			font-size: 12px;
			color: var(--mpm-text-muted);
			font-weight: 600;
			margin: 2px 0;
		}
		.mpm-flow-split {
			display: flex;
			gap: 14px;
			flex-wrap: wrap;
			justify-content: center;
		}
		@media (max-width: 900px) {
			.mpm-body { flex-direction: column; }
			.mpm-nav { position: static; flex: none; width: 100%; flex-direction: row; overflow-x: auto; max-height: none; }
		}
	`;
	document.head.appendChild(style);
}
