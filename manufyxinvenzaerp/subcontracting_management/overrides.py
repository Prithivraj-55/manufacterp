import frappe
from frappe.utils import flt

from erpnext.subcontracting.doctype.subcontracting_order.subcontracting_order import (
    SubcontractingOrder,
)


class CustomSubcontractingOrder(SubcontractingOrder):
    """Override of ERPNext's SubcontractingOrder that relaxes PO-dependent
    validations for SCOs created directly from a Production Plan.
    Standard SCOs (with purchase_order set) behave exactly as before.
    """

    def _is_pp_flow(self):
        return bool(self.get("custom_production_plan"))

    # ── Top-level validate override ───────────────────────────────────────────

    def validate(self):
        if not self._is_pp_flow():
            super().validate()
            return

        # PP flow: skip all PO-dependent validation; run only what's safe.
        self._pp_validate_items()
        self.validate_supplied_items()
        self.calculate_additional_costs()
        self._pp_calculate_amounts()

    # ── on_submit / on_cancel overrides ──────────────────────────────────────

    def on_submit(self):
        if not self._is_pp_flow():
            super().on_submit()
            return
        self.update_status()
        # Skip update_subcontracted_quantity_in_po — no PO exists.

    def on_cancel(self):
        if not self._is_pp_flow():
            super().on_cancel()
            return
        self.update_status()
        self._cancel_and_delete_soes()

    def _cancel_and_delete_soes(self):
        """Cancel submitted SOEs then delete all SOEs linked to this SCO."""
        soes = frappe.get_all(
            "Supplier Operation Entry",
            filters={"subcontracting_order": self.name},
            fields=["name", "docstatus"],
            order_by="sequence_id desc",
        )
        for soe in soes:
            doc = frappe.get_doc("Supplier Operation Entry", soe.name)
            if doc.docstatus == 1:
                doc.cancel()
            frappe.delete_doc("Supplier Operation Entry", soe.name, ignore_permissions=True, force=True)

    # ── Item validation ───────────────────────────────────────────────────────

    def _pp_validate_items(self):
        for item in self.items:
            if not item.bom:
                frappe.throw(
                    frappe._("Row {0}: Please set a BOM for Item {1}.").format(item.idx, item.item_code)
                )
            is_active = frappe.db.get_value("BOM", item.bom, "is_active")
            if not is_active:
                frappe.throw(
                    frappe._("Row {0}: BOM {1} is not active.").format(item.idx, item.bom)
                )

    # ── Amount calculation ────────────────────────────────────────────────────

    def _pp_calculate_amounts(self):
        total_qty = total = 0
        for item in self.items:
            item.amount = flt(item.qty) * flt(item.rate)
            total_qty += flt(item.qty)
            total += flt(item.amount)
        self.total_qty = total_qty
        self.total = total

    # Keep individual overrides so they're safe if called from elsewhere.

    def validate_purchase_order_for_subcontracting(self):
        if self._is_pp_flow():
            return
        super().validate_purchase_order_for_subcontracting()

    def validate_service_items(self):
        if self._is_pp_flow():
            return
        super().validate_service_items()

    def validate_items(self):
        if self._is_pp_flow():
            self._pp_validate_items()
            return
        super().validate_items()

    def calculate_service_costs(self):
        if self._is_pp_flow():
            return
        super().calculate_service_costs()

    def calculate_supplied_items_qty_and_amount(self):
        if self._is_pp_flow():
            return
        super().calculate_supplied_items_qty_and_amount()

    def calculate_items_qty_and_amount(self):
        if self._is_pp_flow():
            self._pp_calculate_amounts()
            return
        super().calculate_items_qty_and_amount()
