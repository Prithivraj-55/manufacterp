// ERP Manual — doctype-wise reference, tree-navigated.
//
// Replaces the two per-doctype "Manual" buttons (Material Planning, Material Issue
// Plan). Content there was walkthrough-style, meant to be read start to finish;
// this page is doctype-wise instead, one category per doctype, each table/topic as
// a sub-tab under it -- meant to be looked something up in, not read straight
// through. The old walkthroughs are migrated in as the fully-populated categories
// below; the client's own nav sketch (Item / Sales Order / Drawing as siblings,
// Material Planning and Production Plan each expanding to their own tables) is
// followed for the categories not yet written up, kept visible as "Coming Soon"
// so the intended shape is there even before the content is.
//
// Layout/tree/scrollspy come from the shared renderer
// (public/js/manual_renderer.js) via manufyx_render_manual_tree(); this file is
// only the content. A leaf uses the same shape as the old flat manuals: {id,
// title, kicker, purpose, fields[], steps[], calcs[], examples[], notes[],
// buttons[]}, everything optional.

frappe.pages["erp-manual"].on_page_load = function (wrapper) {
	let page = frappe.ui.make_app_page({
		parent: wrapper,
		title: "ERP Manual",
		single_column: true,
	});

	// The renderer lives in public/js/manual_renderer.js, pulled in app-wide via
	// app_include_js. If that asset has not been rebuilt/served, the page would
	// otherwise fail with a bare ReferenceError and render blank -- say so plainly
	// instead, because the fix (bench build + a hard refresh) is not guessable from
	// an empty screen.
	if (typeof manufyx_render_manual_tree !== "function") {
		page.main.html(
			'<div style="margin:24px;padding:20px;border:1px solid #C6462F;border-radius:10px;background:#FBEAE6">' +
				"<b>" + __("Manual renderer not loaded") + "</b><br>" +
				__("manufyx_render_manual_tree is undefined — manufyxinvenzaerp.bundle.js did not load. Run <code>bench build --app manufyxinvenzaerp</code> and hard-refresh (Ctrl+Shift+R).") +
				"</div>"
		);
		return;
	}

	manufyx_render_manual_tree(page, {
		heading: __("ERP Manual"),
		intro: __("Doctype by doctype, table by table — pick a category on the left."),
		welcome: {
			title: __("Manufacturing, Start to Finish"),
			body: __(
				"The flow this ERP drives: <b>Material Planning</b> works out where every raw " +
				"material is coming from, <b>Production Plan</b> schedules the job and its " +
				"operations, <b>Job work order</b> is the single execution document for all of " +
				"them, <b>Material Issue Plan</b> is where reserved stock physically leaves the " +
				"warehouse, and each operation runs through <b>Supplier Operation Entry</b> — " +
				"gated by <b>Inspection</b> wherever QC sign-off is required. Those five are fully " +
				"written up on the left. Item, Sales Order and Drawing are placed in the tree " +
				"because the flow starts with them, but are not written up yet."
			),
		},
		categories: ERP_MANUAL_CATEGORIES,
	});
};

// ─── Categories not yet written up — kept visible so the intended shape of the
// manual is there ahead of the content (client's own request: "later we will add
// more details about it"). Each renders as "Coming Soon" until filled in. ────────
// Sales Order — where a job starts. The BOM sheet is uploaded here and turned into
// Drawings and BOMs before Material Planning ever sees it.
const ERP_MANUAL_SALES_ORDER_CHILDREN = [
	{
		id: "so-overview",
		title: "From Sales Order to BOM",
		kicker: "The whole upload flow",
		purpose:
			"Everything downstream — Material Planning, purchasing, transfers, production — is built " +
			"from Drawings and BOMs. Both are created here, from one Excel sheet attached to the " +
			"Sales Order. Get this stage right and the rest follows; get it wrong and every later " +
			"stage inherits the mistake.",
		steps: [
			"Create the Sales Order and enter <b>every finished goods item</b> in the Items table. Not just one line — each FG item the customer has ordered needs its own row.",
			"Prepare the BOM sheet. <b>The same FG item codes must appear in the sheet's FG Item column.</b> A code in the sheet that is not on the order (or spelled differently) has nothing to attach to.",
			"Attach the sheet to <b>BOM Excel File</b> on the Sales Order and save.",
			"<b>Load Items</b> — reads the sheet and stages every drawing and its raw materials onto the order.",
			"<b>Verify Raw Materials</b> — checks what was staged. Fix anything it reports, then run it again.",
			"<b>Create Drawing</b> — creates a Drawing document per drawing in the sheet.",
			"<b>Submit</b> the Sales Order, then <b>Submit Drawing</b>.",
			"<b>Mark as Final Revision</b> — freezes the drawings as the version to build from.",
			"<b>Create and Submit BOM</b> — one BOM per drawing, ready for Material Planning.",
		],
		notes: [
			"<b>Two ways to get the sheet.</b> <b>Download Template</b> (on the Sales Order, before a file is attached) gives you an empty sheet with the correct column headers. " +
			"To see one filled in properly, download the worked sample: " +
			"<a href='/assets/manufyxinvenzaerp/files/Sample_BOM_Sheet.xlsx' download " +
			"style='font-weight:600'>Sample BOM Sheet (filled)</a> — a real 22-drawing sheet with " +
			"100 raw-material rows, showing how the header columns repeat down every row of a drawing.",
			"<b>Column headers must match.</b> The importer finds columns by name, not position, so you may reorder them — but a renamed or missing header is simply not read. Assembly Group, Customer Drawing Number, DUNO/Mark No, FG Item, Total Qty, Total Weight (KG), Nature of Work, Rate Schedule, Item No, Material Code, Grade, Thickness, Width, Length, Reqd Raw Material Qty.",
			"<b>One row per raw material, not per drawing.</b> A drawing needing three materials takes three rows, and its header columns (drawing number, DUNO, FG item, quantities, Nature of Work, Rate Schedule) repeat identically on all three. The importer groups them by Customer Drawing Number.",
		],
		buttons: [
			{ name: "Download Template", note: "An empty sheet with the right headers. Only shown before a file is attached." },
			{ name: "Load Items", note: "Parses the attached sheet onto the order. Disabled once drawings exist, so a reload cannot contradict what was already created." },
			{ name: "Clear Items", note: "Removes staged rows so you can correct the sheet and load again. Rows that already have a Drawing are kept." },
		],
	},
	{
		id: "so-verify",
		title: "Verify Raw Materials",
		kicker: "The gate before drawings",
		purpose:
			"Checks everything staged from the sheet and refuses to pass until it is right. This is " +
			"deliberately strict: a bad row here becomes a bad Drawing, a bad BOM, and a wrong " +
			"requirement in Material Planning, and by then it is far harder to see where it came from.",
		fields: [
			{ name: "Material Code", note: "Must exist in the Item master. A typo here is the most common failure." },
			{ name: "Nature of Work", note: "Must already exist in the Nature of Work master. Checked by name exactly as typed." },
			{ name: "Rate Schedule", note: "Must already exist in the Rate Schedule master — e.g. RS- O/S-001 A. Checked by name; there is no format rule, so your numbering can change freely." },
			{ name: "Dimensions", note: "Plates need Thickness, Width and Length. Structurals need Length. Both need a Unit Weight on the Item master, or no Kg can be calculated." },
		],
		notes: [
			"<b>It blocks, it does not warn.</b> Anything reported has to be corrected in the sheet (or the master record created) before the flow can continue. Correct the sheet, Clear Items, Load Items again, and re-verify.",
			"<b>Why unknown values still reach this screen.</b> The importer stages rows with a direct insert that skips link checking, on purpose — so a wrong Rate Schedule lands in the table and can be reported <i>against the drawing it came from</i>. Rejecting during the upload would abort the whole file over one cell and tell you nothing about where it was.",
			"<b>Blank is allowed</b> for Nature of Work and Rate Schedule. Neither is mandatory on a Drawing, and older imports predate both columns.",
		],
		buttons: [
			{ name: "Verify Raw Materials", note: "Runs the check. Passing sets the order's verified flag; failing lists every problem row with its drawing." },
		],
	},
	{
		id: "so-drawings",
		title: "Create Drawing, Final Revision, BOM",
		kicker: "Turning the sheet into documents",
		purpose:
			"The three build steps. Each processes in batches with a live progress dialog, so a large " +
			"order does not time out and you can watch it work.",
		steps: [
			"<b>Create Drawing</b> — one Drawing document per Customer Drawing Number, carrying its DUNO/Mark No, FG item, customer weight, Nature of Work, Rate Schedule and its full raw-material list. Created as drafts, so they can still be corrected.",
			"<b>Submit Drawing</b> — locks each drawing. The Sales Order itself must be submitted before the next step.",
			"<b>Mark as Final Revision</b> — marks the drawings as the version production will be built from. A BOM can only be created from a submitted, Final Revision drawing.",
			"<b>Create and Submit BOM</b> — one BOM per drawing, from that drawing's raw materials. These are what Material Planning pulls requirements from.",
		],
		notes: [
			"<b>The progress dialog is live.</b> It shows how many are done, how many are pending, elapsed time, an estimate of what is left and the current rate — refreshed every second. The estimate is measured from the run itself, so it is rough at first and tightens as it goes.",
			"<b>BOM creation is the slow step</b>, at roughly a tenth of a second per drawing — a few seconds for a small order, around a minute for 500 drawings. That is ERPNext's own BOM validation and costing, not something the upload is doing badly. Leave the dialog open; it is working.",
			"<b>Drawings are created in batches</b> and can be run again safely: a drawing that already exists is skipped, not duplicated. If a batch fails, fix the cause and re-run — the ones already created stay.",
		],
		buttons: [
			{ name: "Create Drawing", note: "Creates the Drawing documents. Skips any drawing number that already has one." },
			{ name: "Submit Drawing", note: "Submits the created drawings." },
			{ name: "Mark as Final Revision", note: "Requires the Sales Order to be submitted first." },
			{ name: "Create and Submit BOM", note: "Creates and submits one BOM per drawing. The longest step on a large order." },
			{ name: "Submit BOM", note: "Submits BOMs that were created but left in draft." },
		],
	},
];

const ERP_MANUAL_STUB_CATEGORIES = [
	{ id: "item", label: "Item", children: [] },
	{ id: "sales-order", label: "Sales Order", children: ERP_MANUAL_SALES_ORDER_CHILDREN },
	{ id: "drawing", label: "Drawing", children: [] },
];

// ─── Material Planning — migrated verbatim from the old Material Planning manual,
// one child per table/topic exactly as that page's sidebar listed them. ─────────
const ERP_MANUAL_MATERIAL_PLANNING_CHILDREN = [
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
			{ name: "Status (Mapped / Not Mapped / Excess Mapped / Cut Sheet Mapped)", note: "At a glance, what state this row is in — see the Status legend below." },
			{ name: "Planned Item (from Batch)", note: "The item the assigned batch actually is — will differ from Item Code if you've substituted an alternate item." },
			{ name: "Batch Length / Width / Thickness / Unit Weight", note: "The ASSIGNED BATCH's own dimensions — this is what the Kg formula actually uses, not the required dimensions." },
			{ name: "Sec Qty (NOS) / Calc Qty (Kg)", note: "How many pieces you're taking from the batch, and the Kg that works out to." },
			{ name: "Reserve stock without dimensions", note: "Explained with a worked example below — one batch shared across several rows, and how it works on a Cut Sheet row." },
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
				title: "“Reserve stock without dimensions” — ON, exact Kg, fractional pieces",
				item: "Alternate item (different profile)", group: "Structurals",
				length: 6000, sec_qty: "fractional, see below", unit_weight: 10,
				formula:
					"Requirement is 500 Kg. This batch's own shape gives Kg-per-piece = (6000÷1000) × 10 = 60 Kg. " +
					"Sec Nos = 500 ÷ 60 = 8.333 pieces. Reserved Kg = exactly 500",
				result: "500.0 Kg  (8.333 Nos)",
				note: "Nothing is rounded here. Planning reserves precisely the 500 Kg the drawing needs — never a gram more — so the rest of that bar stays free for other rows. Turning 8.333 into whole bars is a physical decision, taken at transfer time in the Material Issue Plan.",
			},
			{
				title: "Same batch shared by SEVERAL rows — each keeps its own exact share",
				item: "2 drawing rows, one shared bar", group: "Structurals",
				length: 1000, sec_qty: "2 rows, see below", unit_weight: 25.38,
				formula:
					"Kg-per-piece for this batch = (1000÷1000) × 25.38 = 25.38 Kg. " +
					"Row 1 needs 33 Kg → 33 ÷ 25.38 = 1.3 Nos. " +
					"Row 2 needs 33 Kg → 1.3 Nos. " +
					"Together: 66 Kg = 2.6 Nos reserved",
				result: "66.0 Kg  (2.6 Nos across 2 rows)",
				note: "Both rows keep their exact 33 Kg / 1.3 Nos. At transfer you can hand over 2.6 pieces-worth as calculated, or raise it to 3 whole pieces — that adds 0.4 × 25.38 = 10.15 Kg, and THAT surplus is what becomes excess to return. Planning stays honest; the rounding decision (and its excess) is recorded where the material physically moves.",
			},
			{
				title: "On a Cut Sheet row — the same tick, sized against ONE piece instead of the batch",
				item: "Plate 5mm (from a Cut Sheet)", group: "Plates",
				length: 500, sec_qty: 4, unit_weight: 7.85,
				formula:
					"W1 is 500 × 250 × 5 = 4.90625 Kg per piece. Requirement is 18 Kg. " +
					"Ticked: 18 ÷ 4.90625. Unticked, typing 4 pieces: 4 × 4.90625",
				result: "Ticked — 18.000 Kg (3.669 Nos)   ·   Unticked, 4 pieces — 19.625 Kg (1.625 Kg excess)",
				note: "Same rule as an ordinary batch, just measured against one Cut Sheet piece instead of the whole plate — see the Cut Sheet section for why that distinction matters.",
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
				text: "One bar or sheet is being shared across several rows, or you're substituting a different profile (an Alternate Item). Tick this box and the row reserves its exact Required Kg, with Sec Nos shown as that weight in pieces of the assigned batch — fractional on purpose (2.5 stays 2.5). This is exactly what happens automatically when a Purchase Receipt fulfils a consolidated or alternate-item line — you'll see this box already ticked on rows created that way.",
			},
			{
				type: "dont",
				label: "Don't expect whole pieces at planning stage",
				text: "A fractional Sec Nos such as 2.5 or 8.333 is correct, not a bug — it is the exact weight the drawings need, expressed in pieces of the batch you assigned. Nothing rounds it up automatically any more. Use “Validate Stock” to see every fractional total at a glance, and settle them at transfer time.",
			},
		],
		notes: [
			"Where rounding now happens: NOWHERE automatically. Material Planning always reserves the exact Required Kg and reports Sec Nos as a plain fraction of the assigned batch. The only place a fraction becomes whole pieces is the Material Issue Plan transfer popup, where you type the number yourself — the system re-checks free stock for the new figure and books the extra weight as excess to return.",
			"Partial transfers are why fractions matter. A Material Planning covering 10 drawings feeds a separate Material Issue Plan per drawing, and each plan only pulls its own drawings' reserved rows. So a batch planned across 5 rows (8 Nos in total) may well present as 4.5 Nos when only 3 of those drawings are being issued — that is expected. Raise it to 5 in the transfer popup if you must hand over whole bars, and the 0.5 piece of surplus is recorded for return.",
			"Case 1 vs Case 2. Case 1 — leave “Reserve stock without dimensions” OFF, pick a batch and type Sec Qty yourself; the system reserves exactly that and never overwrites your number. Case 2 — tick it when one large bar or sheet serves several rows; the system derives the fractional Sec Nos for you from each row's required Kg.",
			"Status legend — “Mapped” (green): an ordinary purchased batch is assigned. “Excess Mapped” (blue): a real batch is assigned and it came back from another job as an off-cut. “Excess Mapped (At Supplier)” (blue): fulfilled from another job's excess that's staying at the supplier and will never reach your warehouse — no batch, nothing to transfer. “Excess Mapped (Pending Return)” (blue): fulfilled from another job's excess that HASN'T physically returned to stock yet, but is already promised to this row; the batch attaches itself automatically the day it does return. “Cut Sheet Mapped” (blue): fulfilled from a Cut Sheet's nesting plan, sized to the piece (W1), not the plate. “Not Mapped” (red): nothing assigned yet. Every blue status counts as mapped — it is material you already have a claim on, so it is included in the Difference in Kg figure and never sent back through purchasing.",
		],
		buttons: [
			{ name: "Reserve / Unreserve", note: "Same soft-claim mechanism as Available Raw Materials — works whether the row has a real batch, a Cut Sheet allocation, or an Excess Mapped claim." },
			{
				name: "Excess Material  (tick on the row)",
				note: "Only appears on a row with NO batch — excess is a promise against a specific off-cut, not stock in your warehouse. Ticking it reveals <b>Select Item</b>, which opens the picker described in the Excess Material Mapping section.",
			},
			{
				name: "Cut Sheet  (tick on the row — read-only)",
				note: "You never tick this yourself: it appears by itself the moment you pick a batch that has a Cut Sheet against it, and names that sheet plus how many pieces are still free. A batch either has a nesting plan or it does not, and a row claiming otherwise would be describing steel that does not exist in that shape. The row then takes on the PIECE's dimensions (W1), not the whole plate's.",
			},
			{
				name: "Validate Stock  (top of the form)",
				note: "A read-only roll-up per item and batch: planned Kg, planned Sec Nos, how many drawings share that batch, the batch's own stock, and any shortfall. Fractional Sec Nos totals show in amber with the whole-piece figure beside them, and shortfalls in red. It changes nothing — it is the quickest way to see which batches still need a whole-piece decision before the job reaches transfer.",
			},
		],
	},
	{
		id: "cut-sheet",
		title: "Cut Sheet",
		kicker: "One nesting plan per plate, shared across jobs",
		purpose:
			"A plate arrives as one batch and gets cut into repeated pieces, leaving a remnant. " +
			"The Cut Sheet is where that plan is written down ONCE, against the batch: this " +
			"piece (W1), this many of them, this remnant (W2). Jobs then take pieces from it " +
			"the same way they reserve batch stock, and the same plate can serve several " +
			"Material Plannings. It is its own document — open it from the Cut Sheet list, not " +
			"from inside a Material Planning.",
		fields: [
			{ name: "Batch", note: "The physical plate being cut. One batch can have only ONE Cut Sheet — two plans for the same steel would each hand out material the other had already promised." },
			{ name: "Sheet (as received)", note: "Length/Width/Thickness/Sec Nos read straight from the batch, never typed, so the two can't disagree." },
			{ name: "W1 — Piece to Cut", note: "Length and Width of the piece. Thickness always comes from the batch: cutting changes Length and Width, never how thick the steel is." },
			{ name: "W1 Sec Nos (available)", note: "How many of that piece this plate yields. YOU enter this — a suggestion is offered from the geometry, but the nesting is your call. It is deliberately not derived from weight; see the worked example." },
			{ name: "Kg per Piece / W1 Total", note: "Calculated. One piece's weight, and all the pieces together." },
			{ name: "W2 — Balance", note: "What is left once the cutting is done. Entered by hand. Written onto the batch when the FIRST transfer from this sheet is submitted." },
			{ name: "Availability", note: "Allocated and Available, in both Sec Nos and Kg — what other jobs have taken and what is still free to claim." },
			{ name: "Allocations", note: "Every Material Planning drawing from this sheet, how many pieces each took, and whether it has physically moved yet." },
		],
		calcs: [
			{
				title: "Why the piece count is yours to enter, not calculated from weight",
				item: "Plate 5mm", group: "Plates",
				length: 1800, sec_qty: 2, unit_weight: 7.85,
				formula:
					"A 1800 × 6300 × 5 plate weighs 445.095 Kg. A 1800 × 3000 piece weighs 211.95 Kg. " +
					"Divide one by the other and you get 2.1",
				result: "but the plate yields 2 pieces, plus a 1800 × 300 remnant",
				note:
					"Steel is cut, not poured. Weight says 2.1 pieces fit; geometry says 2. If the system " +
					"took the weight figure it would over-issue on every single plate, and the shortfall " +
					"would only show up when someone went to the rack. So the count is entered by hand, " +
					"with the geometric answer offered as a starting point.",
			},
			{
				title: "One plate, two jobs, sized two different ways",
				item: "Plate 5mm", group: "Plates",
				length: 500, sec_qty: 4, unit_weight: 7.85,
				formula:
					"W1 is 500 × 250 × 5 = 4.90625 Kg per piece, 10 pieces on the sheet. " +
					"Job A needs 18 Kg and ticks Reserve stock without dimensions: 18 ÷ 4.90625. " +
					"Job B unticks it and types 4 pieces: 4 × 4.90625",
				result: "Job A — 18.000 Kg (3.669 Nos)   ·   Job B — 19.625 Kg (4 Nos, 1.625 Kg excess)",
				note:
					"Both are correct, they just answer different questions. Job A reserves exactly what " +
					"the drawing needs and accepts a fractional share of a piece. Job B takes whole pieces " +
					"because that is what the saw will actually produce, and the 1.625 Kg over the " +
					"requirement is excess. Between them they have taken 7.669 of the 10 pieces, and the " +
					"sheet shows 2.331 still free for anyone else.",
			},
		],
		examples: [
			{
				type: "do",
				label: "Let the batch decide",
				text: "You never tick Cut Sheet on a Material Mapping row. Pick the batch, and if a Cut Sheet exists the tick appears with the sheet's name and its free-piece count, and the row takes on W1's dimensions.",
			},
			{
				type: "dont",
				label: "Don't expect the plate's dimensions on the row",
				text: "A cut row shows the PIECE — 500 × 250, not the 2000 × 1000 plate. If you see the plate's size there, the row has not picked up its Cut Sheet; re-select the batch.",
			},
			{
				type: "dont",
				label: "Don't delete a sheet other jobs are drawing from",
				text: "It refuses, and names the Material Plannings holding pieces. Release those allocations first — otherwise their rows would be left reserving pieces of a plan that no longer exists.",
			},
		],
		notes: [
			"W2 goes onto the batch at the FIRST transfer, not the last. From the moment anyone cuts a piece out, the plate in the rack IS the remnant — whether or not the other jobs have collected their pieces yet. Those pieces are still theirs; the Cut Sheet tracks them independently of the batch's size. Cancel that transfer and the batch goes back to its uncut size.",
			"The batch keeps its original NAME throughout, and that name still spells out the original dimensions. Only the batch's Length/Width/Sec Nos are rewritten. This is known and accepted for now.",
			"Nothing here is physical. There is no stock behind W1: the batch still holds its own Kg, and the real movement is the ordinary Material Issue Plan transfer — it simply carries W1's dimensions instead of the plate's. The Cut Sheet owns the arithmetic and the bookkeeping of who has claimed what.",
			"If W1 × count + W2 does not add up to the plate you get a warning naming the row — never a block, since some loss to the saw is normal. The allowance is Cut Sheet Tolerance (%) in Manufyxinvenza Settings, 2% by default; set it to 0 to be told about any difference at all.",
			"Reducing W1 Sec Nos below what jobs have already taken is refused, naming how many are spoken for. Release an allocation first.",
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
			"Mapping” button on any Material Mapping row, or via “Select Item” once you tick " +
			"Excess Material on a batch-less row.",
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
				title: "Case 2 — Not Yet Returned (claim as many pieces as you need)",
				item: "ZZTEST-VIRTUAL-EXCESS", group: "Structurals",
				length: 1000, sec_qty: 6, unit_weight: 5,
				formula: "A 6-piece off-cut at (1000÷1000) × 5 = 5 Kg each. Take 2 for this job: 2 × 5. " +
					"Another job takes 3, and 1 stays free",
				result: "10.0 Kg claimed · 5.0 Kg still free for anyone else",
				note: "Shared out in pieces, exactly like a Cut Sheet. The picker shows Planned Sec Nos beside Free Sec Nos, and an off-cut disappears from it once nothing is left. No Stock Entry is created by claiming: the Material Mapping row's Batch stays blank and its Status reads “Excess Mapped (At Supplier)” or “Excess Mapped (Pending Return)”. When the off-cut physically returns, the new batch attaches itself to EVERY row holding a piece.",
			},
		],
		examples: [
			{
				type: "do",
				label: "Returned Batch — partially reservable",
				text: "A “Returned Batch” row's Sec Qty field is editable, defaulting to the smaller of the batch's own Sec Qty or its free quantity. You can take less than what's on offer, exactly like a normal batch reservation.",
			},
			{
				type: "do",
				label: "Take only what you need",
				text: "Sec Qty in the picker defaults to everything still free, but it is yours to edit. Whatever you leave stays free for another job — the Availability figures on the Excess Material Items row show Allocated and Available in both Sec Nos and Kg, the same way a Cut Sheet does.",
			},
			{
				type: "do",
				label: "A claim turns real by itself when the off-cut comes back",
				text: "Worked example. Job A ends with a 2000mm ISA100 off-cut (20 Kg) still at the supplier, entered in its Excess Material Items table. Job B claims it — Job B's row shows Status “Excess Mapped (Pending Return)”, Batch blank, but Reserved ticked. Weeks later Job A actually walks the material back: its “Return Excess Entry” button creates the Material Receipt as normal, and the moment that Stock Entry is submitted the new batch (ZZ-L2000-SR014) writes itself into Job B's row, Status flips to “Excess Mapped”, and a green message says so. Nobody re-picks anything, and the material is never free for a third job to grab in between.",
			},
			{
				type: "dont",
				label: "Don't try to change the size of an off-cut someone has claimed",
				text: "Once Job B has claimed it, the off-cut's Length/Width/Sec Qty/Kg are frozen — in the Excess Material Items grid, on the raw-material row's Excess fields, and in the Return Excess Entry dialog alike. All three refuse with the same message naming Job B's Material Planning. This is deliberate: Job B reserved a 2000mm piece, and quietly shrinking it to 1800mm would leave Job B planning around material that no longer exists in that shape.",
			},
			{
				type: "do",
				label: "The measurement was wrong — use Unlink Claim",
				text: "Continuing the example: the off-cut actually measures 1800mm, not 2000mm. Press <b>Unlink Claim</b> on that Excess Material Items row. Job B's reservation is dropped, the off-cut returns to this picker, and the dimensions unlock. Correct them on the raw-material row's Excess Length (the Excess Material Items row recomputes from it — 1.8m × 10 kg/m = 18 Kg), then claim it again. Note the risk the confirmation warns you about: while unlinked, any other job can claim it first.",
			},
		],
		notes: [
			"“Retain at Supplier (Virtual)” material is flagged that way because it will NEVER physically return to your warehouse — it's used/consumed directly at the supplier. “Pending Return” material is just excess that hasn't been walked back to stock yet, but eventually will be — claiming it now doesn't stop that from happening later; it just reserves the outcome in advance.",
			"Where these rows go at transfer time. A claimed off-cut still at the supplier has no batch in your source warehouse, so it can never appear in the transfer popup's list — there is physically nothing to move, and it is already sitting where the transfer would have sent it. Rather than leaving a silent gap, the popup shows a blue panel: “N item(s) are already at <supplier warehouse> — no transfer needed”, listing each one. It is information, not a problem: it never blocks the rest of the transfer.",
			"Edit dimensions on the raw-material row, not in the Excess Material Items grid. For any excess row created from a raw-material row, the Excess Length/Width/Sec Qty fields on that raw-material row are the source of truth — the Excess Material Items row is recalculated from them on every save, so typing directly into the grid gets overwritten. The exception is a rounding-surplus row (Return Reason mentions “Round Up Sec Qty for Transfer”), which has no raw-material row behind it and is edited in the grid directly.",
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
			{ name: "Purchase size check (on save)", note: "Every time you save, each line's Length/Width/Thickness is compared against the biggest piece it has to produce. Anything too short or the wrong thickness is listed in an information popup — see the second worked example below. It never blocks the save." },
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
			{
				title: "Buying SHORTER than the longest piece — the size warning",
				item: "ISMB400", group: "Structurals",
				length: 4000, sec_qty: 50, unit_weight: 61.6,
				formula:
					"You enter Length 4000 and Sec Qty 50. Purchase Kg = (4000÷1000) × 61.6 × 50 = 12,320 Kg, " +
					"which comfortably covers the 11,519.701 Kg required — so on WEIGHT alone this looks fine. " +
					"But the longest single ISMB400 piece the drawings need is 6936.01 mm",
				result: "12,320 Kg bought — but no 6936 mm piece can ever be cut from a 4000 mm bar",
				note:
					"On save you'll get an information popup: “ISMB400 — Length ≥ 6936.01 mm (now 4000)”. " +
					"It does NOT block the save — buying short stock is sometimes deliberate — it simply makes sure " +
					"the clash is never silent. Enough total weight is not the same as usable material.",
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
			"A consolidated purchase, or an Alternate Item, was received → the batch lands in Material Mapping instead of Exact Match, with “Reserve stock without dimensions” already switched on for you. Sec Nos comes through as an exact fraction of the purchased piece size — settle it into whole pieces at transfer time.",
			"If the purchase was consolidated across several drawings' worth of the same item, the received quantity is split sequentially — the first drawing (by row order) is filled completely, then the next, and so on. Any purchasing surplus left after every drawing is fully covered simply becomes free warehouse stock (see the Consolidate Item section above) — it isn't assigned to any one drawing.",
		],
	},
];

// ─── Production Plan — the old manual's single "production-plan" section split
// three ways, following the client's own reference nav (Drawing table / Operation
// table as siblings). "Drawing / Item Table" is new content, written from the
// po_items fields this session has used directly and repeatedly building test
// Production Plans (item_code, bom_no, planned_qty, stock_uom, custom_drawing,
// custom_duno_mark_no, custom_customer_drawing_number, sales_order,
// custom_material_planning, custom_customer_weight_kg) -- not fabricated, but also
// not yet reviewed against the live form the way the rest of this page has been. ─
const ERP_MANUAL_PRODUCTION_PLAN_CHILDREN = [
	{
		id: "type-setup",
		title: "Type & Setup",
		kicker: "Before the tables — what kind of job this is",
		purpose:
			"Production Plan is where a job actually gets scheduled, once Material Planning has " +
			"sorted out where every raw material is coming from. Type decides the naming series " +
			"and, downstream, which warehouse defaults are pulled onto the Material Issue Plan.",
		fields: [
			{ name: "Type (Internal Job / Supplier Job / Supplier with Material)", note: "Drives the naming series. Doesn't restrict which Work Type each individual operation uses on the Operation table below — those can still be mixed within one plan." },
		],
		buttons: [
			{ name: "Job work order & MIP", note: "Appears once the Production Plan is submitted. Creates the Job work order AND its Material Issue Plan together in one click. Safe to click again later — it just opens what already exists instead of duplicating." },
			{ name: "Delete Job work order and MIP", note: "Sits next to the Vendor/Contractor field. Deletes both together, with a confirmation prompt — refuses outright if any real stock movement or production has already happened against either one, so nothing gets silently lost." },
		],
		notes: [
			"If any operation in the Operation table has Work Type Subcontractor, Vendor/Contractor must be set before “Job work order & MIP” will create anything.",
		],
	},
	{
		id: "drawing-table",
		title: "Drawing / Item Table",
		kicker: "Which drawings this plan produces",
		purpose:
			"One row per drawing/item this Production Plan is scheduling. Each row carries its " +
			"own Sales Order, DUNO/Mark No and Customer Drawing Number, and points back at the " +
			"Material Planning that reserved its raw material — that link is how Material Issue " +
			"Plan later knows exactly which reserved rows belong to this job.",
		fields: [
			{ name: "Item Code / BOM No", note: "What is being produced, and the Bill of Materials it is produced against." },
			{ name: "Planned Qty / Stock UOM", note: "How many of this item this plan produces." },
			{ name: "Sales Order / DUNO Mark No / Customer Drawing Number", note: "Traceability back to the customer order and the specific drawing/mark." },
			{ name: "Material Planning", note: "The Material Planning document that reserved raw material for this row. Material Issue Plan reads this link to pull in only the rows belonging to this plan's own drawings." },
			{ name: "Customer Weight (Kg)", note: "The customer-provided weight for this item, carried through from the Sales Order/Drawing." },
		],
	},
	{
		id: "operation-table",
		title: "Operation Table (Process Planning)",
		kicker: "The sequence of operations, and who performs each one",
		purpose:
			"The ordered list of operations this job goes through — e.g. Material Issue, Fit-up, " +
			"Welding, Final, Blasting, Painting. One Supplier Operation Entry gets created per " +
			"row, in this exact order, once the Job work order is created.",
		fields: [
			{ name: "Operation Name", note: "The step itself." },
			{ name: "Work Type (Internal Jobcard / Subcontractor)", note: "Who performs THIS operation. Can vary row by row in the same plan — e.g. Welding done in-house, Blasting sent to a supplier — but every Subcontractor row must come before every Internal Jobcard row, no interleaving." },
			{ name: "Inspection Mandatory", note: "Tick on any operation that needs a formal QC sign-off before its completed quantity counts. Covered in full in the Inspection category." },
		],
		buttons: [
			{ name: "Set Work Type", note: "Bulk-sets Work Type across selected rows instead of editing each one by hand." },
		],
	},
];

const ERP_MANUAL_JOB_WORK_ORDER_CHILDREN = [
	{
		id: "overview",
		title: "Job work order",
		kicker: "One document drives every operation",
		purpose:
			"Created from a submitted Production Plan, the Job work order is the single execution " +
			"document for EVERY operation in the plan, whether it's done in-house or by a supplier — " +
			"there is no separate Work Order/Job Card involved.",
		fields: [
			{ name: "Drawing Items", note: "Every drawing/DUNO this job covers, each with its own Customer Provided Weight, Planned RM Weight, Mapped Weight, Excess Weight, and Transferred Weight — rolled up from Material Planning." },
			{ name: "All Operations Complete", note: "Ticks itself once every operation in the chain has been submitted." },
		],
		steps: [
			"Submitting the Job work order and clicking “Job work order & MIP” back on Production Plan creates one Supplier Operation Entry per Operation table row, in sequence order.",
			"Each operation only becomes submittable once every earlier one already is — operation 3 can't be completed before operation 2 is.",
			"The Operations tab shows a live summary table — Seq, Operation, Status, Overall Qty, Available to Consume, Total Consumed, Difference, Entry, Drawings. Click any operation's name (shown in blue, underlined) to jump straight into that Supplier Operation Entry.",
		],
		buttons: [
			{ name: "Material Issue Plan (under Create)", note: "Creates the Material Issue Plan if it doesn't already exist, or opens the existing one." },
			{ name: "Supplier Operation Entries (under Create)", note: "Creates any still-missing Supplier Operation Entry in the chain — normally already done automatically by “Job work order & MIP”." },
		],
		notes: [
			"“Job work order” is a display name only — underneath, it's still the same Subcontracting Order doctype; it just reads as “Job work order” everywhere in the UI.",
			"The old separate “Work Order / Subcontract PO” create option under Production Plan is disabled — use “Job work order & MIP” there instead.",
		],
	},
];

const ERP_MANUAL_SOE_CHILDREN = [
	{
		id: "overview",
		title: "Supplier Operation Entry (Operations)",
		kicker: "One per operation, tracking Nos completed",
		purpose:
			"One Supplier Operation Entry exists per Operation table row. The first operation " +
			"tracks Kg consumed from what was transferred; every operation after that tracks Nos " +
			"(pieces) handed forward from the one before it.",
		fields: [
			{ name: "Consumption Log", note: "Log how many Nos (pieces) of each drawing were completed, with a Date. Weight (Kg) is auto-calculated from the drawing's own per-piece weight." },
			{ name: "Drawing Details", note: "Per-drawing Qty to Manufacture, Available to Consume (Nos), Completed Qty (Nos), Customer Weight (Kg) and Planned Weight (Kg)." },
			{ name: "Available to Consume (Nos)", note: "The first operation gets this from what's actually been transferred; every later one gets it from the PREVIOUS operation's own Completed Qty, once that operation is saved (while still draft) or submitted." },
		],
		steps: [
			"Logging Nos against a drawing in Consumption Log auto-advances Status from Open to In Progress, and — when Inspection Mandatory is off — immediately updates that drawing's Completed Qty.",
			"Status must be set to Completed before a Supplier Operation Entry can be submitted, and every earlier operation in the sequence must already be submitted too.",
		],
		buttons: [
			{ name: "Add All Drawing (Testing group)", note: "Fills Consumption Log with one row per drawing at its full available quantity in one click, instead of adding rows one by one. For quick testing/data entry, not a normal production step." },
		],
		notes: [
			"If Inspection Mandatory is ticked for this operation, Consumption Log no longer completes anything directly — see Inspection for what happens instead.",
		],
	},
];

const ERP_MANUAL_INSPECTION_CHILDREN = [
	{
		id: "overview",
		title: "Inspection (Mandatory Operations)",
		kicker: "QC sign-off before quantity counts as done",
		purpose:
			"When an operation's Inspection Mandatory box is ticked, logging Nos in Consumption " +
			"Log no longer completes them on its own — they sit as pending review until an " +
			"Inspection Entry accepts them. This is the one gate that guarantees nothing moves to " +
			"the next operation, or into a Final Stock Entry, without QC sign-off.",
		fields: [
			{ name: "Inspection Items (on the Supplier Operation Entry)", note: "One row per drawing, auto-showing what's been logged in Consumption Log but not yet accepted. Recalculates itself on every save — nothing to maintain by hand, and it never shows more than the drawing's real Qty to Manufacture, however many times something is re-logged." },
			{ name: "Inspection Entry — Status / Feedback / Overall Remarks / Rework Remarks", note: "Status is Open/Working/Completed; Feedback is Ok/Not Ok." },
			{ name: "Inspection Items (on the Inspection Entry)", note: "One row per drawing, copied in from the source Supplier Operation Entry: Completed Qty (frozen at creation), Accepted Qty (you enter), Rejected Qty (auto = Completed − Accepted)." },
		],
		steps: [
			"Click “Create Inspection” on the Supplier Operation Entry's Inspection tab — it logs the call and creates the Inspection Entry in one step, carrying over whatever is currently pending.",
			"Enter Accepted Qty per drawing row — Rejected Qty fills in automatically.",
			"Set Feedback before marking Status Completed — trying to complete without it first shows “Enter Feedback to complete it” and reverts Status.",
			"Set Status to Completed and save — you're asked to confirm (“cannot be edited once submitted”); confirming saves AND submits in one action, there is no separate manual Submit step.",
			"On submit, each row's Accepted Qty is added onto that drawing's Completed Qty on the Supplier Operation Entry — this is what lets the next operation proceed. Rejected Qty isn't written anywhere; it simply reappears in the Supplier Operation Entry's own Inspection Items table the moment it's logged again in Consumption Log, ready for another round.",
		],
		calcs: [
			{
				title: "A full rework round-trip",
				item: "Drawing 1", group: "Qty to Manufacture: 2 pieces",
				sec_qty: "see steps", unit_weight: "n/a",
				formula:
					"Round 1: 2 Nos logged in Consumption Log → 2 pending in Inspection Items → Inspection Entry 1: Accepted 1, Rejected 1 → " +
					"Completed Qty becomes 1, and 1 stays pending (capped at the real 2-piece total no matter how many times it's re-logged). " +
					"Round 2: the rejected piece is reworked and logged again → 1 pending again → Inspection Entry 2: Accepted 1",
				result: "2 / 2 (fully complete)",
				note: "Completed Qty finishes at exactly 2 — the drawing's real total — never more, regardless of how many rounds or re-logged Nos it took to get there.",
			},
		],
		examples: [
			{
				type: "do",
				label: "Rejected Nos are never lost",
				text: "Re-logging the same drawing in Consumption Log after a rejection brings it straight back into the Inspection Items table for another round — with no validation blocking the resubmission, even though the cumulative log total now exceeds the drawing's nominal quantity.",
			},
			{
				type: "dont",
				label: "Don't expect Consumption Log alone to complete anything once Inspection Mandatory is on",
				text: "Completion only ever happens through a submitted Inspection Entry's Accepted Qty — logging Nos just queues them for review.",
			},
		],
		notes: [
			"Rework Remarks is mandatory whenever total Rejected Qty across the Inspection Entry's rows is greater than 1.",
			"Total Checked / Cleared / Rework Qty still appear (read-only) at the top of the Inspection Entry for reporting — they're auto-totalled from the Inspection Items rows, not entered directly.",
		],
	},
];

// ─── Material Issue Plan — migrated verbatim from the old Material Issue Plan
// manual, one child per topic exactly as that page's sidebar listed them. ───────
const ERP_MANUAL_MATERIAL_ISSUE_PLAN_CHILDREN = [
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
];

const ERP_MANUAL_REPORTS_CHILDREN = [
	{
		id: "overview",
		title: "Checking Overall Stock & Reports",
		kicker: "Outside any one Material Planning",
		kind: "info",
		purpose:
			"Everything in Material Planning shows stock from the point of view of ONE document. " +
			"To see overall, warehouse-wide stock — or to check specifically what needs chasing — " +
			"use the reports below instead of piecing it together from individual plans.",
		steps: [
			"<b>Manufyxinvenza Stock Balance</b> — open from the Awesomebar. Item-and-batch-wise on-hand quantity, what's reserved against which Material Planning, and what's genuinely free — the same free-Kg figures the Exact Match and Excess Material Mapping pickers use internally, but for every item and warehouse at once.",
			"<b>Excess Material Return Report</b> — the chase-list for off-cuts. Defaults to “Pending Return” (still out there AND actually coming back — drops anything already returned or flagged Retain at Supplier) over the last three months, and names every Material Planning holding a piece of each off-cut.",
			"<b>Cut Sheet Report</b> — which plates are cut, who is drawing from them, and what is left. “W2 Not Written” filters to sheets that have been cut but never had their balance written back to the batch — the state where the plate in the rack and the system disagree.",
		],
	},
];

const ERP_MANUAL_GLOSSARY_CHILDREN = [
	{
		id: "overview",
		title: "Glossary",
		kind: "glossary",
		kicker: "Terms used across this manual",
		fields: [
			{ name: "Exact Match", note: "A batch whose own Length/Width/Thickness are EQUAL to what's required — not just “close” or “big enough.”" },
			{ name: "Reserve", note: "A soft claim on stock — marks it as spoken for so nothing else can also claim it. Always just the row's own quantity, never the whole batch. No physical movement happens yet." },
			{ name: "Sec Qty / Sec Nos", note: "The same idea under two names used interchangeably across the app — a count of physical pieces (bars, plates, cut pieces). Fractional at planning time, whole when material actually moves." },
			{ name: "Alternate Item", note: "A substitute item used in place of what was originally required." },
			{ name: "Consolidated", note: "Multiple drawings' requirements for the same item code, combined into one purchasing line." },
			{ name: "Virtual / Pending Return", note: "An off-cut claimed by a job while still at the supplier. No batch, no stock entry — a promise, until it physically returns. “Retain at Supplier” means it never will; “Pending Return” means it hasn't yet." },
			{ name: "CNC Process", note: "Marks that a piece needs CNC cutting at your own facility before it can go to the supplier — routes it through the Material Issue Plan's CNC Warehouse first." },
			{ name: "W1 / W2", note: "On a Cut Sheet: W1 is the piece being cut, W2 the remnant left on the plate afterwards." },
			{ name: "DUNO / Mark No", note: "The drawing-level identifier that keeps every row traceable back to exactly which piece, on which drawing, it belongs to." },
			{ name: "Job work order", note: "Display name only — the same Subcontracting Order doctype underneath, created from a Production Plan, driving every operation whether performed in-house or by a supplier." },
			{ name: "Consumption Log", note: "Where completed Nos (pieces) are logged, per drawing, on a Supplier Operation Entry — the source of truth for what's been done at that operation." },
			{ name: "Inspection Mandatory", note: "A per-operation flag (set on Production Plan's Operation table) that requires an Inspection Entry to accept quantity before it counts as Completed." },
			{ name: "Reqd Qty vs Issued Qty", note: "On a Material Issue Plan row: what must be transferred, versus what has gone so far. Equal when the row is fully issued." },
			{ name: "Excess Qty vs Transfer Excess Kg", note: "The first is the mapped batch measured against the drawing's planned weight, set when the row is fetched. The second is surplus created by rounding Sec Nos up at transfer time." },
			{ name: "Finished Goods Warehouse", note: "The Material Issue Plan field that receives both the finished good (Make Final Stock Entry) and any off-cut/unconsumed material (Return Excess Entry)." },
		],
	},
];

const ERP_MANUAL_CATEGORIES = [
	...ERP_MANUAL_STUB_CATEGORIES,
	{ id: "material-planning", label: "Material Planning", children: ERP_MANUAL_MATERIAL_PLANNING_CHILDREN },
	{ id: "production-plan", label: "Production Plan", children: ERP_MANUAL_PRODUCTION_PLAN_CHILDREN },
	{ id: "job-work-order", label: "Job Work Order", children: ERP_MANUAL_JOB_WORK_ORDER_CHILDREN },
	{ id: "material-issue-plan", label: "Material Issue Plan", children: ERP_MANUAL_MATERIAL_ISSUE_PLAN_CHILDREN },
	{ id: "supplier-operation-entry", label: "Supplier Operation Entry", children: ERP_MANUAL_SOE_CHILDREN },
	{ id: "inspection", label: "Inspection", children: ERP_MANUAL_INSPECTION_CHILDREN },
	{ id: "reports", label: "Reports & Stock Checking", children: ERP_MANUAL_REPORTS_CHILDREN },
	{ id: "glossary", label: "Glossary", children: ERP_MANUAL_GLOSSARY_CHILDREN },
];
