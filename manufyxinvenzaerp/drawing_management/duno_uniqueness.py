"""DUNO/Mark No must be unique inside anything that plans several drawings together.

A DUNO is a mark off the customer's drawing -- "1B1", "TYPE 2". It is unique within
one job because the customer made it so, and `unique` is 0 on both Drawing and Sales
Order DUNO Item, so nothing stops two Sales Orders using the same mark. That was
harmless while one Material Planning covered exactly one Sales Order.

It stops being harmless the moment one plan spans several Sales Orders, because
roughly ten places key per-drawing figures on the DUNO alone within a plan:

    subcontracting._get_mp_drawing_weights_by_duno    planned weight
    subcontracting._get_mp_mapped_weight_by_duno      mapped (reserved) weight
    subcontracting._get_mp_excess_by_duno             excess to return
    subcontracting._get_mp_reserved_batches           which batches belong to a job
    subcontracting._consumption_for_completed         finished_fraction per drawing
    material_issue_plan.refresh_weight_summary        the Job Work Order's own rows
    material_issue_plan_transfer._linked_mp_names_and_duno_scope
                                                      which batches may be transferred
    material_issue_plan_transfer.drawing_by_duno      which drawing a row belongs to
    purchase_receipt (mm_by_duno)                     which row a receipt allocates to

Two rows sharing a DUNO inside one plan collapse into one key: weights double-count,
and the transfer offers another Sales Order's reserved batches for shipment to this
job's supplier. That is steel moving to the wrong place, not a bad label -- which is
why the plan-level checks here THROW.

Every one of those sites aggregates within a single Material Planning or a single
Production Plan. So making a plan incapable of holding a duplicate makes all of them
correct by construction, with no change to the ledger code itself.

Two strengths, deliberately:

  - Material Planning and Production Plan HARD BLOCK. This is where the damage
    happens, and refusing costs nothing -- the rows are being assembled by hand.
  - Sales Order and Drawing only WARN. A mark is the customer's, not ours. Two
    unrelated customers both sending "TYPE 1" is normal and must not block an
    import; it only matters if somebody later tries to plan those two jobs
    together, and the plan-level block catches that with a clear message.
"""

from collections import defaultdict

import frappe
from frappe import _


# Callers hand in NORMALISED rows -- plain dicts with these keys -- rather than raw
# child rows, because the same three fields are spelled differently on either side
# of the fence: Material Planning BOM Item has duno_mark_no / customer_drawing_number,
# Production Plan Item has custom_duno_mark_no / custom_customer_drawing_number.
# Teaching this module both spellings would mean it silently reads nothing the day a
# third table joins with a fourth spelling.
def normalise(row, duno_field="duno_mark_no", cdn_field="customer_drawing_number",
              drawing_field="drawing"):
    return {
        "idx": row.get("idx"),
        "duno_mark_no": row.get(duno_field),
        "sales_order": row.get("sales_order"),
        "customer_drawing_number": row.get(cdn_field),
        "drawing": row.get(drawing_field),
    }


def find_duplicates(rows):
    """Group normalised rows by DUNO and return only the marks used more than once.

    Rows with no DUNO are ignored -- a blank mark is a separate complaint, raised
    where the field is actually required.

    Comparison is on the stripped mark. Trailing whitespace off a pasted spreadsheet
    cell is not a different drawing, and treating "1B1 " as distinct from "1B1" would
    let exactly the collision this guards against walk straight through.

    Returns {duno_mark_no: [row, row, ...]} for the clashing marks only.
    """
    by_duno = defaultdict(list)
    for row in rows:
        duno = (row.get("duno_mark_no") or "").strip()
        if not duno:
            continue
        by_duno[duno].append(row)
    return {duno: rs for duno, rs in by_duno.items() if len(rs) > 1}


def _describe(row):
    """One clashing row, named the way the person fixing it would name it."""
    parts = []
    if row.get("idx"):
        parts.append(_("Row {0}").format(row.get("idx")))
    if row.get("sales_order"):
        parts.append(str(row.get("sales_order")))
    if row.get("customer_drawing_number"):
        parts.append(str(row.get("customer_drawing_number")))
    elif row.get("drawing"):
        parts.append(str(row.get("drawing")))
    return " / ".join(parts) or _("(unidentified row)")


def assert_unique(rows, table_label):
    """Refuse a plan that would hold two rows with the same DUNO.

    The message names both sides and both Sales Orders, because the fix is always
    "these two jobs use the same mark" and the first question is which two.
    """
    duplicates = find_duplicates(rows)
    if not duplicates:
        return

    blocks = []
    for duno in sorted(duplicates):
        clashing = duplicates[duno]
        sales_orders = sorted({str(r.get("sales_order") or "") for r in clashing if r.get("sales_order")})
        lines = "".join("<li>{0}</li>".format(frappe.utils.escape_html(_describe(r))) for r in clashing)
        blocks.append(
            "<p><b>{duno}</b> {used}:</p><ul>{lines}</ul>".format(
                duno=frappe.utils.escape_html(duno),
                used=_("is used by {0} rows").format(len(clashing))
                + (_(" across Sales Orders {0}").format(", ".join(sales_orders)) if len(sales_orders) > 1 else ""),
                lines=lines,
            )
        )

    frappe.throw(
        _("Two or more rows in {0} share the same DUNO/Mark No.").format(table_label)
        + "".join(blocks)
        + "<p>"
        + _(
            "Per-drawing weights, batch reservations and transfers are all tracked by "
            "DUNO/Mark No within a plan, so a repeated mark would double-count weight and "
            "could send one Sales Order's reserved material to another's supplier."
        )
        + "</p><p>"
        + _(
            "Either plan these Sales Orders separately, or give the clashing drawings "
            "distinct marks."
        )
        + "</p>",
        title=_("Duplicate DUNO/Mark No"),
    )


def warnings_enabled():
    """Whether the Sales Order / Drawing warning is switched on.

    Manufyxinvenza Settings -> "Show Warning for Duplicate DUNO". Gates ONLY the two
    warnings; the Material Planning and Production Plan blocks ignore it entirely,
    because those protect the weight ledger rather than inform somebody.

    Defaults to ON when the setting has never been saved. A Single with no row in
    tabSingles reads back None, and treating that as OFF would silently drop the
    warning on every site until somebody opened Settings and pressed Save.
    """
    value = frappe.db.get_single_value("Manufyxinvenza Settings", "warn_on_duplicate_duno")
    return True if value is None else bool(frappe.utils.cint(value))


def find_clashes_on_other_sales_orders(sales_order, dunos):
    """Which of these marks are already used by a DIFFERENT Sales Order.

    Looks at Drawings rather than Sales Order DUNO Items: a Drawing is the thing a
    plan actually references, and cancelled ones are excluded so a revision (which
    cancels the old drawing before inserting the new) never reports against itself.

    Returns {duno_mark_no: [sales_order, ...]}.
    """
    dunos = [d for d in {(d or "").strip() for d in dunos} if d]
    if not dunos:
        return {}

    rows = frappe.get_all(
        "Drawing",
        filters={
            "duno_mark_no": ["in", dunos],
            "docstatus": ["!=", 2],
            "sales_order": ["not in", [sales_order or ""]],
        },
        fields=["duno_mark_no", "sales_order"],
    )

    clashes = defaultdict(set)
    for r in rows:
        if r.sales_order:
            clashes[r.duno_mark_no].add(r.sales_order)
    return {duno: sorted(sos) for duno, sos in clashes.items()}


def warn_text_for_clashes(clashes):
    """The warning line shown on a Sales Order / Drawing, one per clashing mark.

    Worded as information, not an error: reusing a mark is legitimate and only
    becomes a problem if these jobs are later planned together. Saying so is what
    stops it reading as something that must be fixed now.
    """
    lines = []
    for duno in sorted(clashes):
        lines.append(
            _("DUNO/Mark No <b>{0}</b> is also used on {1}. That is allowed, but these "
              "Sales Orders cannot then be combined in one Material Planning or "
              "Production Plan unless one of the marks is changed.")
            .format(frappe.utils.escape_html(duno),
                    ", ".join(frappe.utils.escape_html(s) for s in clashes[duno]))
        )
    return lines
