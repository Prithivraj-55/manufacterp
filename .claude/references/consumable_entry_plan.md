# Consumable Entry on Stock Entry — plan

## What was asked

1. A **Consumable Entry** tick on Stock Entry, next to Inspection Required.
2. Ticked, it reveals **Sales Order**.
3. Picking a Sales Order reveals **Production Plan**, listing only the plans made
   against that order.
4. Picking a Production Plan fetches its **Job Work Order** and fills it in.
5. Two fields hold the same value — *Job work order* and *Subcontracting Order (PP
   Flow)*. One of them goes.
6. Ticking Consumable Entry ticks **Consumable** on every item row: the ones already
   there, and any added afterwards.

## The chain it hangs on, verified against the site

```
Sales Order  →  Production Plan     via  Production Plan Item.sales_order
Production Plan  →  Job Work Order  via  Subcontracting Order.custom_production_plan

PP-INT-2026-00002   SAL-ORD-2026-00019   SC-ORD-2026-00002
PP-INT-2026-00001   SAL-ORD-2026-00016   SC-ORD-2026-00001
```

Both hops are one link away, so no new fields are needed to make them.

## Which duplicate goes, and why that one

The two are not equals:

- **`subcontracting_order`** is ERPNext's own field. It cannot be deleted, and it is
  what 102 places in the Python and 8 in the JS already read — most of them ERPNext's.
  It is also the one showing as **"Job work order"**, because the rename was done as a
  Translation on the doctype (T9), so it already carries the friendly label.
- **`custom_sco_ref`** is this app's, labelled "Subcontracting Order (PP Flow)". It
  exists for a reason that has since gone away: ERPNext's `validate_subcontract_order`
  used to throw when `supplied_items` was empty, so the flow avoided the core field.
  `CustomStockEntry.validate_subcontract_order` now returns early for a PP-flow order,
  which solves that properly.

So **`custom_sco_ref` is hidden** and the core field stays on screen under its
translated name. Nothing is deleted and no read site changes: every Stock Entry this
app creates already dual-writes both, and the new fetch will keep doing so. Deleting
the column outright would mean rewriting 33 call sites and migrating submitted
documents — worth doing one day, not in the middle of a feature.

## What gets built

**Fields on Stock Entry** (custom fields, exported to `custom/stock_entry.json`):

| Field | Type | Shown when |
|---|---|---|
| `custom_consumable_entry` | Check | always, right after Inspection Required |
| `custom_consumable_sales_order` | Link → Sales Order | Consumable Entry is ticked |
| `custom_consumable_production_plan` | Link → Production Plan | a Sales Order is chosen |

**Property Setter**: `custom_sco_ref` hidden.

**Client script** (Stock Entry, installed from `setup.py` like the others):

- Production Plan's list is filtered to plans for the chosen Sales Order, through a
  whitelisted query rather than a link filter — the join runs through Production Plan
  Item, which a plain filter cannot express.
- Choosing a Production Plan fills the Job Work Order, writing **both** fields so the
  33 existing readers keep working.
- Changing the Sales Order clears the Production Plan and the Job Work Order beneath
  it, so a stale pair cannot survive a change of mind.
- Ticking Consumable Entry ticks Consumable on every existing row; unticking leaves
  them alone, since a row may have been ticked deliberately.
- Rows added afterwards arrive ticked, while the box is on.

**Server side**: one whitelisted method, `get_production_plans_for_sales_order`, and a
`validate` guard so the three fields cannot hold a combination that does not exist —
a Production Plan that is not against the chosen Sales Order is refused rather than
silently accepted.

## What is deliberately not touched

Nothing existing changes behaviour: no field is deleted, no read site is rewritten, the
`custom_is_consumable` tick on the item row keeps its own meaning and can still be set
by hand, and Stock Entries created by the app's own flows are unaffected — none of them
sets Consumable Entry, so none of them sees any of this.
