# SEP 14 — Finished goods in Nos and Kg

> **Status: proposal, waiting for client confirmation. No code written.**
> Client document: `~/Downloads/Nos_vs_Kg_Order_Walkthrough.pdf` (13 pages).

## The problem

The client sells fabricated structures by **Nos, Kg or Tonne**. Production counts **Nos**
per drawing (Drawing, Operation Entry). A Nos ↔ Kg conversion depends on the drawing,
because one FG item covers drawings of very different weight (e.g. 1B14 = 41.98 Kg/piece,
1B5 = 547.28 Kg/piece), so no conversion factor on the item can work.

Verified on the live site, 14 Sep 2026:
- All Sales Orders sell "Fabricated Structurs" in **Kg**, but SO-16's drawings produce
  FINGOODS001 in **Nos**, so a Delivery Note can never find stock of the item sold.
- **Live bug:** `create_finished_goods_entry` books the finished piece count in the FG
  item's stock UOM. For a Kg FG item ("Fabricated Structurs", SO-17 to SO-22, 25 Nos per
  drawing) that books 25 pieces as **25 Kg**. Nothing has been booked on those yet.
- Sales Order quantities do not reconcile with drawing weights (SO-16: 10 Kg vs
  9,974.59 Kg of drawings).
- Stock Settings "Allow UOM with conversion rate defined in item" is **off**, so any UOM
  can be picked on any line, and ERPNext falls back to a conversion factor of **1.0**
  when none is found (2 Nos silently becomes 2 Kg). The only global conversion on the
  site is Kg ↔ Tonne.

## Proposed design

- **FG item:** stock UOM **Kg**, Secondary UOM **Nos**, UOM table limited to Kg, Tonne
  (1,000) and Nos (factor set per line). Batch per drawing: `FG-<order>-<DUNO>`. Same
  style of rule as the existing Structurals/Plates rule in `item_management/item.py`.
- **Stock is always Kg with Sec Nos**, whatever the order unit. Only the selling UOM on a
  Sales Order / Delivery Note / Sales Invoice line follows the order (Nos, Kg or Tonne).
- **Order in Nos:** one Sales Order line per drawing, conversion factor = the drawing's
  Kg per piece, checked on save.
- **Order in Kg / Tonne:** one line; drawings stay in the Drawing List; order Kg must
  equal the total customer weight.
- **Production Plan / Work Order / Job Work Order:** FG quantity in Kg with Sec Nos.
  This fixes the 25 → 25 Kg bug.
- **Final Stock Entry:** Kg = finished pieces × Kg per piece, Sec Nos = pieces, batch =
  drawing.
- **Delivery Note:** rows per drawing batch, whole pieces only, and the last piece of a
  drawing takes the batch's remaining Kg.
- **FG lines:** UOM validated on FG lines only, not through the site-wide Stock Setting.

24 new custom fields (full list in the PDF): Drawing (Weight per Piece), Sales Order Item
(5), Production Plan Item (2), Subcontracting Order Item (2), Work Order (2), Batch (4),
Delivery Note Item (4), Sales Invoice Item (4). Stock Entry Detail and Batch already carry
Sec Qty / Sec UOM; Stock Entry Detail already carries Drawing / DUNO.

## Open decisions (client)

1. FG weight = customer provided weight, or calculated from raw materials?
2. Tolerance between order quantity and drawing weights?
3. One Sales Order line per drawing for Nos orders: acceptable?
4. Whole pieces only on delivery?
5. Batch naming format.
6. Any unit besides Nos, Kg and Tonne?
7. Existing data: FINGOODS001 holds 6 Nos from MAT-STE-00005 / 00010, and SO-16 to SO-22
   are on the old setup. Convert them, or apply the new setup to new orders only?

## Phases, once approved

1. Master rules (FG item UOMs and batch, Sales Order UOM, customer weight mandatory,
   order vs drawings check)
2. Production side (Kg FG quantity; Final Stock Entry in Kg + Nos + batch)
3. Delivery Note
4. Report and data migration
