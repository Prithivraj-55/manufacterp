import frappe


def run():
    mips = frappe.get_all("Material Issue Plan", fields=["name", "excess_return_warehouse"], limit=200)
    for m in mips:
        count = frappe.db.count("SCO Excess Material Item", {"parent": m.name})
        if count:
            print(m.name, "excess_return_warehouse=", m.excess_return_warehouse, "rows=", count)
