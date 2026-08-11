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
			{ name: "Reserve stock without dimensions", note: "Explained with a worked example below — one batch shared across several rows." },
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
			"Status legend — “Mapped” (green): an ordinary purchased batch is assigned. “Excess Mapped” (blue): a real batch is assigned and it came back from another job as an off-cut. “Excess Mapped (At Supplier)” (blue): fulfilled from another job's excess that's staying at the supplier and will never reach your warehouse — no batch, nothing to transfer. “Excess Mapped (Pending Return)” (blue): fulfilled from another job's excess that HASN'T physically returned to stock yet, but is already promised to this row; the batch attaches itself automatically the day it does return. “Not Mapped” (red): nothing assigned yet. Every blue status counts as mapped — it is material you already have a claim on, so it is included in the Difference in Kg figure and never sent back through purchasing.",
		],
		buttons: [
			{ name: "Reserve / Unreserve", note: "Same soft-claim mechanism as Available Raw Materials — works whether the row has a real batch or is a Virtual/Pending-Return excess claim." },
			{
				name: "Excess Material Mapping",
				note: "Opens the excess-material picker — see the dedicated section below for the full explanation and worked examples of both cases it covers.",
			},
			{
				name: "Excess Material  (tick on the row)",
				note: "Only appears on a row with NO batch — excess is a promise against a specific off-cut, not stock in your warehouse. Ticking it reveals <b>Select Item</b>, which opens the same picker described in the section below.",
			},
			{
				name: "Cut Sheet  (tick on the row — read-only)",
				note: "You never tick this yourself: it appears by itself the moment you pick a batch that has a Cut Sheet against it, and names that sheet plus how many pieces are still free. A batch either has a nesting plan or it does not, and a row claiming otherwise would be describing steel that does not exist in that shape. The row then takes on the PIECE's dimensions (W1), not the whole plate's.",
			},
			{
				name: "Reserve stock without dimensions  (on a Cut Sheet row)",
				note: "Chooses how the take is sized, and both ways are valid. <b>Ticked</b> — the row reserves exactly its Required Qty, and Sec Nos becomes that weight as a fraction of one W1 piece (read-only; 18 Kg of a 4.90625 Kg piece is 3.669). <b>Unticked</b> — you type whole pieces, and the weight follows (4 pieces = 19.625 Kg); anything above the Required Qty is excess. A suggested count is filled in for you but never overwrites a figure you typed.",
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
				text: "Worked example. Job A ends with a 2000mm ISA100 off-cut (20 Kg) still at the supplier, entered in its Excess Material Items table. Job B claims it — Job B's row shows Status “Claimed (Pending Return)”, Batch blank, but Reserved ticked. Weeks later Job A actually walks the material back: its “Return Excess Entry” button creates the Material Receipt as normal, and the moment that Stock Entry is submitted the new batch (ZZ-L2000-SR014) writes itself into Job B's row, Status flips to “Mapped”, and a green message says so. Nobody re-picks anything, and the material is never free for a third job to grab in between.",
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
	{
		id: "production-plan",
		title: "Production Plan",
		kicker: "After Material Planning — starting the job",
		purpose:
			"Once Material Planning has sorted out where every raw material is coming from, " +
			"Production Plan is where you actually schedule the job — pick the Type, lay out the " +
			"operations it goes through and who performs each one, and from here create the Job " +
			"work order and Material Issue Plan that drive everything downstream. Example used " +
			"below: Production Plan 1, created against Material Planning 1.",
		fields: [
			{ name: "Type (Internal Job / Supplier Job / Supplier with Material)", note: "Drives the naming series. Doesn't restrict which Work Type each individual operation uses below — those can still be mixed within one plan." },
			{ name: "Process Planning — Operation Name", note: "The ordered list of operations this job goes through, e.g. Material Issue, Fit-up, Welding, Final, Blasting, Painting. One Supplier Operation Entry gets created per row, in this exact order." },
			{ name: "Process Planning — Work Type (Internal Jobcard / Subcontractor)", note: "Who performs THIS operation. Can vary row by row in the same plan — e.g. Welding done in-house, Blasting sent to a supplier — but every Subcontractor row must come before every Internal Jobcard row, no interleaving." },
			{ name: "Process Planning — Inspection Mandatory", note: "Tick on any operation that needs a formal QC sign-off before its completed quantity counts. Covered in full in the Inspection section below." },
		],
		buttons: [
			{ name: "Set Work Type", note: "Bulk-sets Work Type across selected Process Planning rows instead of editing each one by hand." },
			{ name: "Job work order & MIP", note: "Appears once the Production Plan is submitted. Creates the Job work order (see below) AND its Material Issue Plan together in one click. Safe to click again later — it just opens what already exists instead of duplicating." },
			{ name: "Delete Job work order and MIP", note: "Sits next to the Vendor/Contractor field. Deletes both together, with a confirmation prompt — refuses outright if any real stock movement or production has already happened against either one, so nothing gets silently lost." },
		],
		notes: [
			"“Job work order” is a display name only — underneath, it's still the same Subcontracting Order doctype; it just reads as “Job work order” everywhere in the UI.",
			"If any operation in the Process Planning table has Work Type Subcontractor, Vendor/Contractor must be set before “Job work order & MIP” will create anything.",
		],
	},
	{
		id: "job-work-order",
		title: "Job work order",
		kicker: "One document drives every operation",
		purpose:
			"Created from Production Plan 1, Job work order 1 is the single execution document " +
			"for EVERY operation in the plan, whether it's done in-house or by a supplier — there " +
			"is no separate Work Order/Job Card involved.",
		fields: [
			{ name: "Drawing Items", note: "Every drawing/DUNO this job covers, each with its own Customer Provided Weight, Planned RM Weight, Mapped Weight, Excess Weight, and Transferred Weight — rolled up from Material Planning 1." },
			{ name: "All Operations Complete", note: "Ticks itself once every operation in the chain has been submitted." },
		],
		steps: [
			"Submitting Job work order 1 and clicking “Job work order & MIP” back on Production Plan 1 creates one Supplier Operation Entry per Process Planning row, in sequence order — Supplier Operation Entry 1, Supplier Operation Entry 2, and so on.",
			"Each operation only becomes submittable once every earlier one already is — Supplier Operation Entry 3 can't be completed before Supplier Operation Entry 2 is.",
			"The Operations tab shows a live summary table — Seq, Operation, Status, Overall Qty, Available to Consume, Total Consumed, Difference, Entry, Drawings. Click any operation's name (shown in blue, underlined) to jump straight into that Supplier Operation Entry.",
		],
		buttons: [
			{ name: "Material Issue Plan (under Create)", note: "Creates the Material Issue Plan if it doesn't already exist, or opens the existing one." },
			{ name: "Supplier Operation Entries (under Create)", note: "Creates any still-missing Supplier Operation Entry in the chain — normally already done automatically by “Job work order & MIP”." },
		],
		notes: [
			"The old separate “Work Order / Subcontract PO” create option under Production Plan is disabled — use “Job work order & MIP” there instead.",
		],
	},
	{
		id: "material-issue-plan",
		title: "Material Issue Plan",
		kicker: "Getting reserved stock to the supplier/WIP warehouse",
		purpose:
			"Created alongside Job work order 1, Material Issue Plan 1 is where reserved batches " +
			"actually leave your warehouse — the physical stock movement that Material Planning's " +
			"“Reserve” only ever soft-claimed.",
		fields: [
			{ name: "Raw Materials", note: "Every reserved batch pulled in for this job's drawings, with Reqd Qty (the mapped batch's weight), Issued Qty (cumulative transferred so far across every Stock Entry), Excess Qty (the mapped batch measured against the drawing's own planned weight), Transfer Excess Kg (surplus created by rounding Sec Nos up at transfer time), and per-row Excess Return fields. (Cut plans are no longer entered per row — they live on the Cut Sheet against the batch.)" },
			{ name: "Finished Goods Warehouse", note: "Receives BOTH the finished good (via Make Final Stock Entry) and any unconsumed/off-cut material (via Return Excess Entry). Must be set before either button will work." },
		],
		buttons: [
			{ name: "Select Materials to Transfer / To CNC Warehouse", note: "Move reserved batches out to the supplier — or, for CNC-flagged rows, to the CNC Warehouse first. Only batches that are BOTH purchased AND reserved are ever offered, filtered by Item Code only, since one consolidated batch can legitimately serve several drawings at once. Sec Nos is EDITABLE in this popup — see the worked example below." },
			{ name: "Validate Stock", note: "A read-only preview of exactly what this plan will hand over: Kg and Sec Nos per item and batch, with any fractional Sec Nos highlighted in amber. Nothing is created or changed — use it before transferring to see which rows still need a whole-piece decision." },
			{ name: "CNC to Supplier/WIP", note: "Forwards material on from the CNC Warehouse once machining is done." },
			{ name: "PDF", note: "A shareable batch plan — DUNO/Mark No, Customer Drawing No, Planned Kg, batch details and Sec Qty — for the production or supplier team, with its own Download button in the popup's corner." },
			{ name: "Return Excess Entry", note: "Review Qty/dimensions and enter a mandatory Reason for every row, confirm that the material will be received into the Finished Goods Warehouse, then the return Stock Entry is created." },
			{ name: "Make Final Stock Entry", note: "Appears once Job work order 1's operations are ALL complete. Creates a draft Manufacture Stock Entry that consumes the supplier-warehouse raw material and produces the finished good into the Finished Goods Warehouse — review and submit it from there." },
		],
		calcs: [
			{
				title: "Fractional Sec Nos at transfer — keep 4.5, or round to 5?",
				item: "ISMB450", group: "Structurals",
				length: 900, sec_qty: "4.5 planned", unit_weight: 72.4,
				formula:
					"One purchased batch is shared by 5 drawings — 8 Nos in total across the whole Material Planning. " +
					"But this Material Issue Plan covers only 3 of those drawings, so it pulls 4.5 Nos " +
					"(Kg-per-piece = (900÷1000) × 72.4 = 65.16, so 4.5 × 65.16 = 293.22 Kg). " +
					"Leave it at 4.5 to issue the exact planned weight, or type 5 to hand over whole bars: " +
					"5 × 65.16 = 325.80 Kg",
				result: "293.22 Kg (4.5 Nos)  →  or 325.80 Kg (5 Nos), excess 32.58 Kg",
				note:
					"A fractional 4.5 is expected, not an error — it is simply this plan's share of a bar that " +
					"several drawings sub-divide. If you type 5, the system re-checks free stock for the higher " +
					"figure, refuses it outright if the batch can't cover it, and books the extra 32.58 Kg " +
					"straight into Excess Material Return so it comes back to the batch later.",
			},
			{
				title: "Where that 32.58 Kg of surplus shows up",
				item: "ISMB450", group: "Structurals",
				length: 900, sec_qty: "3 rows sharing the batch", unit_weight: 72.4,
				formula:
					"The same transfer, seen from the item table. Those 4.5 Nos were not one row — they were " +
					"3 drawings sharing the batch, at 2 Nos, 1.5 Nos and 1 Nos. The 32.58 Kg surplus belongs " +
					"to all three, so it is split in proportion to their Sec Nos: " +
					"2÷4.5 × 32.58, 1.5÷4.5 × 32.58, 1÷4.5 × 32.58",
				result: "14.48 Kg + 10.86 Kg + 7.24 Kg = 32.58 Kg",
				note:
					"Each figure lands in that row's Transfer Excess Kg column, so the surplus is visible against " +
					"the drawings that caused it instead of only as one lump in Excess Material Items. The parts " +
					"always add back to the total. Transfer again later and round up again, and the column " +
					"accumulates rather than resetting. Do not confuse it with Excess Qty next to it: Excess Qty " +
					"compares the mapped batch against the drawing's planned weight and is set when the row is " +
					"fetched; Transfer Excess Kg is created purely by your whole-piece decision at transfer time.",
			},
		],
		notes: [
			"Cut plates arrive here already sized to the PIECE. The cut is planned once on the Cut Sheet against the batch (see that section), so a row reaching this plan already carries W1's dimensions and its share of the pieces — there is nothing to re-enter here, and the transfer moves that piece rather than the whole plate. The plate's own Length/Width/Sec Nos are rewritten to the remnant when the first transfer from that sheet is submitted, and restored if it is cancelled.",
			"Nothing is ever offered for transfer unless it's BOTH purchased (a Purchase Receipt allocated it) AND reserved (a manual step back on Material Planning 1) — after a Purchase Receipt submits, its popup tells you exactly which Material Planning to open and reserve if anything's still pending.",
			"Why fractions turn up here and not in Material Planning: a Material Planning covering 10 drawings feeds a SEPARATE Material Issue Plan per drawing, and each plan only ever pulls its own drawings' reserved rows. A batch planned across 5 rows can therefore present as 4.5 Nos when only 3 of those drawings are being issued. That is the whole reason Sec Nos is editable here — this is the first point at which anyone knows how many physical bars are actually going out of the door.",
			"Nothing rounds automatically, anywhere. Material Planning reserves the exact Kg each drawing needs; this popup is the ONLY place a fraction becomes whole pieces, and only because you typed it. Whatever you add on top is recorded as excess to return, never quietly absorbed.",
		],
	},
	{
		id: "supplier-operation-entry",
		title: "Supplier Operation Entry (Operations)",
		kicker: "One per operation, tracking Nos completed",
		purpose:
			"One Supplier Operation Entry exists per Process Planning row. Supplier Operation " +
			"Entry 1 (the first operation) tracks Kg consumed from what was transferred; every " +
			"operation after that tracks Nos (pieces) handed forward from the one before it.",
		fields: [
			{ name: "Consumption Log", note: "Log how many Nos (pieces) of each drawing were completed, with a Date. Weight (Kg) is auto-calculated from the drawing's own per-piece weight." },
			{ name: "Drawing Details", note: "Per-drawing Qty to Manufacture, Available to Consume (Nos), Completed Qty (Nos), Customer Weight (Kg) and Planned Weight (Kg) — the last two now show on every operation, not just the first." },
			{ name: "Available to Consume (Nos)", note: "Supplier Operation Entry 1 gets this from what's actually been transferred; every later one gets it from the PREVIOUS operation's own Completed Qty, once that operation is saved (while still draft) or submitted." },
		],
		steps: [
			"Logging Nos against a drawing in Consumption Log auto-advances Status from Open to In Progress, and — when Inspection Mandatory is off — immediately updates that drawing's Completed Qty.",
			"Status must be set to Completed before a Supplier Operation Entry can be submitted, and every earlier operation in the sequence must already be submitted too.",
		],
		buttons: [
			{ name: "Add All Drawing (Testing group)", note: "Fills Consumption Log with one row per drawing at its full available quantity in one click, instead of adding rows one by one. For quick testing/data entry, not a normal production step." },
		],
		notes: [
			"If Inspection Mandatory is ticked for this operation, Consumption Log no longer completes anything directly — see Inspection below for what happens instead.",
		],
	},
	{
		id: "inspection",
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
			{ name: "Job work order", note: "Display name only — the same Subcontracting Order doctype underneath, created from a Production Plan, driving every operation whether performed in-house or by a supplier." },
			{ name: "Consumption Log", note: "Where completed Nos (pieces) are logged, per drawing, on a Supplier Operation Entry — the source of truth for what's been done at that operation." },
			{ name: "Inspection Mandatory", note: "A per-operation flag (set on Production Plan's Process Planning table) that requires an Inspection Entry to accept quantity before it counts as Completed — see the Inspection section." },
			{ name: "Finished Goods Warehouse", note: "The Material Issue Plan field that receives both the finished good (Make Final Stock Entry) and any off-cut/unconsumed material (Return Excess Entry)." },
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
				<p>${__("A step-by-step walkthrough of every table, field, and button — with worked examples — written so a first-time user can follow it start to finish, from Material Planning all the way through Production Plan, Job work order, Material Issue Plan, and Inspection.")}</p>
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
